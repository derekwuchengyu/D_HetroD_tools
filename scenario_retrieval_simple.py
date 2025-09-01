#!/usr/bin/env python3
"""
簡化版 Scenario Retrieval Tool for "ego直行遇到路口對向車道一輛車左轉" scenarios

專注於軌跡交集判斷，提供可調參數
"""

import pandas as pd
import numpy as np
import ast
from datetime import datetime
from typing import List
import os

class SimpleScenarioRetrieval:
    def __init__(self, tracks_file, tracks_meta_file, tags_file, annotations_file, 
                 distance_threshold=25.0, intersection_threshold=0.1):
        """
        Initialize the simple scenario retrieval tool
        
        Args:
            tracks_file: Path to tracks CSV file
            tags_file: Path to tags CSV file
            annotations_file: Path to annotations CSV file
            distance_threshold: Maximum distance for trajectory interaction (meters)
            intersection_threshold: Tolerance for position-based intersection detection (meters)
                                  Lower values = more precise intersection detection
        """
        self.tracks_file = tracks_file
        self.tracks_meta_file = tracks_meta_file
        self.tags_file = tags_file
        self.annotations_file = annotations_file
        self.distance_threshold = distance_threshold
        self.intersection_threshold = intersection_threshold
        
        # Load data
        print("Loading data...")
        self.tracks_df = pd.read_csv(tracks_file)
        self.tags_df = pd.read_parquet(tags_file)
        self.tags_df = pd.read_parquet(tags_file)
        self.tracks_meta_df = pd.read_csv(self.tracks_meta_file)
        
        # Load existing annotations or create new
        if os.path.exists(annotations_file):
            self.annotations_df = pd.read_parquet(annotations_file)
        else:
            self.annotations_df = pd.DataFrame(columns=[
                'scenarioId', 'description', 'category', 'frame', 'trackId', 'role'
            ])
        
        print(f"Loaded {len(self.tracks_df)} track records")
        print(f"Loaded {len(self.tags_df)} tag records")
        print(f"Existing annotations: {len(self.annotations_df)}")
        print(f"Distance threshold: {distance_threshold}m")
        print(f"Intersection threshold: {intersection_threshold}m (position tolerance)")
        
        # Get next scenario ID
        self.next_scenario_id = self._get_next_scenario_id()
        
    def _get_next_scenario_id(self):
        """Get the next available scenario ID"""
        if self.annotations_df.empty:
            return 1
        
        existing_ids = []
        for sid in self.annotations_df['scenarioId'].unique():
            try:
                if isinstance(sid, str) and sid.startswith('scenario_'):
                    existing_ids.append(int(sid.split('_')[1]))
                elif str(sid).isdigit():
                    existing_ids.append(int(sid))
            except:
                continue
        
        return max(existing_ids) + 1 if existing_ids else 1
    
    def parse_action_tags(self, tags_str):
        """Parse action tags string to list"""
        try:
            return ast.literal_eval(tags_str)
        except:
            return []
    
    def find_tagged_vehicles(self, tag):
        """Find vehicles with specific tag"""
        print(f"\nFinding vehicles with '{tag}' tag...")        
        
        tagged_vehicles_df =  self.tags_df[self.tags_df['action_tags'].apply(lambda tags: tag in tags)]

        
        # 用 groupby 直接計算每個 trackId 的 frame range
        tagged_track_ranges = {}
        grouped = tagged_vehicles_df.groupby('trackId')['frame']
        for track_id, frames in grouped:
            frames_sorted = sorted(frames.tolist())
            tagged_track_ranges[track_id] = {
                'start_frame': int(min(frames_sorted)),
                'end_frame': int(max(frames_sorted)),
                'frames': frames_sorted
            }

        print(f"Found {len(tagged_track_ranges)} vehicles with '{tag}' tag")
        return tagged_track_ranges
    
    def find_intersecting_agents(self, ego_traj, agent_tracks, start_frame, end_frame):
        """
        Find agents whose trajectories intersect with the ego's trajectory during the given frame range.
        Based on the reference implementation with position-based intersection detection.
        """
        intersecting_agents = []
        
        # 多一秒 for 判斷traj 交集
        start_frame -= 30
        end_frame += 30
        
        # Filter ego trajectory to the specified frame range
        ego_traj_filtered = ego_traj[
            (ego_traj['frame'] >= start_frame) & 
            (ego_traj['frame'] <= end_frame)
        ].sort_values('frame')
        
        if ego_traj_filtered.empty:
            return intersecting_agents
        
        # Filter time ranged ego trajectory
        tracks_df = self.tracks_df[
            (self.tracks_df['frame'] >= start_frame) & 
            (self.tracks_df['frame'] <= end_frame)
        ]

        # Get ego positions as numpy array for efficient comparison
        ego_positions = ego_traj_filtered[["xCenter", "yCenter"]].values
        
        for agent_id in agent_tracks:
            try:
                # Get agent trajectory data for the frame range
                agent_data = tracks_df[
                    (tracks_df['trackId'] == agent_id)
                ].sort_values('frame')
                
                if agent_data.empty:
                    continue
                    
                # Get agent positions as numpy array
                agent_positions = agent_data[["xCenter", "yCenter"]].values
                
                # Check for intersection using position proximity
                # Using the same logic as reference: np.isclose with tolerance
                if np.any(np.isclose(agent_positions[:, None], ego_positions, atol=self.intersection_threshold).all(axis=2)):
                    intersecting_agents.append(agent_id)
                    
            except Exception as e:
                # Skip agents with data issues
                print(f"Warning: Error processing agent {agent_id}: {e}")
                continue

        return intersecting_agents
    
    def calculate_vehicle_angle(self, track_id, frame):
        """
        Calculate vehicle's heading angle at a specific frame
        Returns angle in degrees (0-360)
        """
        # Get vehicle data around the target frame for angle calculation
        vehicle_data = self.tracks_df[
            (self.tracks_df['trackId'] == track_id) & 
            (self.tracks_df['frame'] == frame)
        ]
        
        # Use the heading angle if available in the data
        if 'heading' in vehicle_data.columns:
            return vehicle_data.iloc[0]['heading']

        return None
    
    def is_opposite_direction(self, ego_id, agent_id, frame, tolerance_deg=45):
        """
        Check if two vehicles are moving in opposite directions
        Returns True if the angle between their headings > 120 degrees
        """
        ego_angle = self.calculate_vehicle_angle(ego_id, frame)
        agent_angle = self.calculate_vehicle_angle(agent_id, frame)
        
        if ego_angle is None or agent_angle is None:
            print(f"    Warning: Could not calculate angles for vehicles {ego_id}, {agent_id} at frame {frame}")
            return False
        
        angle_diff = abs(ego_angle - agent_angle)
        cos_diff = np.cos(np.deg2rad(angle_diff))
        cos_tolerance = np.cos(np.deg2rad(180 - tolerance_deg))
        
        is_opposite = cos_diff <= cos_tolerance
        
        print(f"    Angle check: ego {ego_id} ({ego_angle:.1f}°) vs agent {agent_id} ({agent_angle:.1f}°) -> diff: {angle_diff:.1f}° {'✓ Opposite' if is_opposite else '✗ Not opposite'}")
        
        return is_opposite
    
    def find_scenarios(self, max_scenarios=10):
        """
        Find scenarios matching the criteria using improved intersection detection
        Similar to the reference main() function structure
        """
        description = "ego直行遇到路口對向車道一輛汽車左轉"
        print(f"\n3. Finding '{description}' scenarios...")
        
        straight_tracks = self.find_tagged_vehicles('路口直行')
        turning_tracks = self.find_tagged_vehicles('turning_left')

        scenarios = []
        
        # Convert turning tracks to list of agent IDs for batch processing
        agent_ids = list(turning_tracks.keys())
        
        # For each straight vehicle (potential ego)
        for ego_id, ego_info in straight_tracks.items():
            if len(scenarios) >= max_scenarios:
                break
             
            ego_class = self.tracks_meta_df[self.tracks_meta_df['trackId'] == ego_id]['class'].values
            if len(ego_class) == 0 or ego_class[0] != 'car':
                print(f"Skipping ego vehicle {ego_id}: class is not 'car'")
                continue
            
            # if ego_id != 114:
            #     continue
                
            print(f"\nChecking ego vehicle {ego_id}...")
            
            ego_start, ego_end = ego_info['start_frame'], ego_info['end_frame']
            
            # Get ego trajectory for the entire range
            ego_traj = self.tracks_df[
                self.tracks_df['trackId'] == ego_id
            ].sort_values('frame')
            
            if ego_traj.empty:
                continue
            
            # Find intersecting agents using the improved method
            intersecting_agents = self.find_intersecting_agents(
                ego_traj, agent_ids, ego_start, ego_end
            )
            
            print(f"  Found {len(intersecting_agents)} intersecting agents: {intersecting_agents}")
            
            # Process each intersecting agent
            for agent_id in intersecting_agents:
                
                agent_class = self.tracks_meta_df[self.tracks_meta_df['trackId'] == agent_id]['class'].values
                if len(agent_class) == 0 or (agent_class[0] != 'car' and agent_class[0] != 'truck'):
                    print(f"Skipping agent vehicle {agent_id}: class is not vehicle(car or truck)")
                    continue
                    
                agent_info = turning_tracks[agent_id]
                agent_start, agent_end = agent_info['start_frame'], agent_info['end_frame']
                
                # Find overlapping time period
                overlap_start = max(ego_start, agent_start)
                overlap_end = min(ego_end, agent_end)
                
                if overlap_start > overlap_end:
                    continue  # No time overlap
                
                # Check if vehicles are moving in opposite directions at ego start frame
                if not self.is_opposite_direction(ego_id, agent_id, overlap_start):
                    print(f"    ✗ Skipping agent {agent_id}: not moving in opposite direction to ego {ego_id}")
                    continue
                
                # # Calculate minimum distance for reporting
                # _, min_dist = self.check_trajectory_intersection(
                #     ego_id, agent_id, (overlap_start, overlap_end)
                # )
                
                print(f"    ✓ Found scenario: ego {ego_id} vs agent {agent_id} (overlap: {overlap_start}-{overlap_end})") #, min distance: {min_dist:.1f}m)")
                
                scenarios.append({
                    'ego_id': ego_id,
                    'agent_id': agent_id,
                    'start_frame': overlap_start,
                    'end_frame': overlap_end,
                    'ego_straight_range': (ego_start, ego_end),
                    'agent_turning_range': (agent_start, agent_end),
                    'description': description,
                    # 'min_distance': min_dist
                })
        
        print(f"\nFound {len(scenarios)} scenarios matching criteria")
        return scenarios
    
    def save_scenarios_to_annotations(self, scenarios):
        """Save identified scenarios to annotations.csv"""
        print(f"\n4. Saving scenarios to annotations...")
        
        new_annotations = []
        
        for i, scenario in enumerate(scenarios):
            scenario_id = f"{self.next_scenario_id + i}"
            description = scenarios[i]['description']
            category = "intersection_turning_left_ego_straight"
            
            ego_id = scenario['ego_id']
            agent_id = scenario['agent_id']
            ego_range = scenario['ego_straight_range']
            # min_dist = scenario['min_distance']
            
            print(f"Saving {scenario_id}: ego {ego_id} vs agent {agent_id}")# (min dist: {min_dist:.1f}m)")
            
            # Add annotations for ego vehicle (referred) for entire straight trajectory
            for frame in range(ego_range[0], ego_range[1] + 1):
                new_annotations.append({
                    'scenarioId': scenario_id,
                    'description': description,
                    'category': category,
                    'frame': frame,
                    'trackId': ego_id,
                    'role': 'refer'
                })
            
            # Add annotations for agent vehicle (related) for entire straight trajectory
            for frame in range(ego_range[0], ego_range[1] + 1):
                # Check if agent exists in this frame
                agent_exists = not self.tracks_df[
                    (self.tracks_df['trackId'] == agent_id) & 
                    (self.tracks_df['frame'] == frame)
                ].empty
                
                if agent_exists:
                    new_annotations.append({
                        'scenarioId': scenario_id,
                        'description': description,
                        'category': category,
                        'frame': frame,
                        'trackId': agent_id,
                        'role': 'related'
                    })
        
        # Convert to DataFrame and append to existing annotations
        if new_annotations:
            new_df = pd.DataFrame(new_annotations)
            
            # Ensure category column consistency by converting any list values to strings
            if not self.annotations_df.empty and 'category' in self.annotations_df.columns:
                # Convert existing list-type categories to strings
                def convert_category_to_string(cat):
                    if isinstance(cat, (list, tuple)):
                        return ', '.join(map(str, cat))
                    elif hasattr(cat, '__iter__') and not isinstance(cat, str):
                        # Handle numpy arrays and other iterable types
                        try:
                            return ', '.join(map(str, cat))
                        except:
                            return str(cat)
                    return str(cat) if cat is not None else ''
                
                self.annotations_df['category'] = self.annotations_df['category'].apply(convert_category_to_string)
            
            self.annotations_df = pd.concat([self.annotations_df, new_df], ignore_index=True)
            
            # Save to file
            try:
                self.annotations_df.to_parquet(self.annotations_file, index=False)
                print(f"Saved {len(new_annotations)} new annotation records")
                print(f"Total scenarios saved: {len(scenarios)}")
            except Exception as e:
                print(f"Error saving annotations to parquet: {e}")
                # Try to save as CSV as fallback
                csv_file = self.annotations_file.replace('.parquet', '.csv')
                try:
                    self.annotations_df.to_csv(csv_file, index=False)
                    print(f"Saved annotations to CSV instead: {csv_file}")
                except Exception as csv_e:
                    print(f"Failed to save as CSV too: {csv_e}")
                    print("Annotations were prepared but not saved due to file format issues")
        else:
            print("No new annotations to save")
    
    def run(self, max_scenarios=10):
        """Run the complete scenario retrieval process"""
        # description = "ego直行遇到路口對向車道一輛車左轉"
        # print("Starting Simple Scenario Retrieval for '" + description + "' scenarios")
        print("=" * 70)
        
        # Find scenarios
        scenarios = self.find_scenarios(max_scenarios)
        # return 
        if scenarios:
            # Save to annotations
            self.save_scenarios_to_annotations(scenarios)
            
            print("\n" + "=" * 70)
            print("Scenario Retrieval Complete!")
            print(f"Found and saved {len(scenarios)} scenarios")
            
            # Print summary
            for i, scenario in enumerate(scenarios):
                scenario_id = f"{self.next_scenario_id + i}"
                ego_id = scenario['ego_id']
                agent_id = scenario['agent_id']
                ego_range = scenario['ego_straight_range']
                # min_dist = scenario['min_distance']
                print(f"{scenario_id}: ego {ego_id} (frames {ego_range[0]}-{ego_range[1]}) vs agent {agent_id}") # (min dist: {min_dist:.1f}m)")
        else:
            print("\nNo scenarios found matching the criteria")
            print("Try adjusting the thresholds:")
            print(f"  Current intersection_threshold: {self.intersection_threshold}m (position tolerance)")
            print(f"  Current distance_threshold: {self.distance_threshold}m")
            print("  Tip: Increase intersection_threshold for more lenient intersection detection")

def main():
    """Main function"""
    # File paths
    tracks_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/00_tracks_0-367.csv"
    tracks_meta_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/data/00_tracksMeta.csv"
    tags_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/tags.parquet"
    annotations_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/annotations_oppsite_TL_vehicle.parquet"

    # Check if files exist
    for file_path in [tracks_file, tags_file]:
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return
    
    # Run scenario retrieval with adjustable parameters
    # You can adjust these thresholds based on your needs:
    # - intersection_threshold: tolerance for position-based intersection detection (meters)
    # - distance_threshold: general interaction distance (not currently used)
    retrieval = SimpleScenarioRetrieval(
        tracks_file, tracks_meta_file, tags_file, annotations_file,
        distance_threshold=30.0,      # General interaction distance
        intersection_threshold=1.0    # Position tolerance for intersection detection (similar to reference atol=1e-1)
    )
    
    # Find up to 5 scenarios
    retrieval.run(max_scenarios=30)

if __name__ == "__main__":
    main()
