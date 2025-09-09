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
                 distance_threshold=25.0, intersection_threshold=2.0):
        """
        Initialize the simp            print("No scenarios found matching the criteria")
            print("Try adjusting the thresholds:")
            print(f"  Current conflict zone threshold: {self.intersection_threshold}m")
            print(f"  Current distance_threshold: {self.distance_threshold}m")
            print("  Tip: Increase conflict zone threshold for more lenient PET calculation")
            print("  Current PET threshold: ≤ 5 seconds")enario retrieval tool
        
        Args:
            tracks_file: Path to tracks CSV file
            tags_file: Path to tags CSV file
            annotations_file: Path to annotations CSV file
            distance_threshold: Maximum distance for trajectory interaction (meters)
            intersection_threshold: Distance threshold to define conflict zone for PET calculation (meters)
                                  Smaller values = more precise conflict zone detection
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
        print(f"Conflict zone threshold for PET: {intersection_threshold}s")
        print("Using Post-Encroachment Time (PET) ≤ 5 seconds for intersection detection")
        
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
        if len(tagged_track_ranges) > 0:
            print(f"Found {len(tagged_track_ranges)} vehicles with '{tag}' tag")
        return tagged_track_ranges
    
    def calculate_post_encroachment_time(self, ego_traj, agent_traj, conflict_threshold=2.0):
        """
        Calculate Post-Encroachment Time (PET) between two vehicles.
        PET is the time between when the first vehicle leaves a conflict zone
        and when the second vehicle enters the same conflict zone.
        
        Args:
            ego_traj: Ego vehicle trajectory DataFrame
            agent_traj: Agent vehicle trajectory DataFrame  
            conflict_threshold: Distance threshold to define conflict zone (meters)
            
        Returns:
            PET in seconds (positive value), or None if no conflict found
        """
        try:
            # Find potential conflict points where vehicles are close
            ego_positions = ego_traj[["xCenter", "yCenter", "frame"]].values
            agent_positions = agent_traj[["xCenter", "yCenter", "frame"]].values
            
            min_pet = float('inf')
            conflict_found = False
            
            # For each ego position, find the closest agent position
            for ego_pos in ego_positions:
                ego_x, ego_y, ego_frame = ego_pos
                
                # Calculate distances to all agent positions
                distances = np.sqrt((agent_positions[:, 0] - ego_x)**2 + 
                                  (agent_positions[:, 1] - ego_y)**2)
                
                # Find agent positions within conflict threshold
                conflict_indices = np.where(distances <= conflict_threshold)[0]
                
                if len(conflict_indices) > 0:
                    conflict_found = True
                    # Get the closest agent frame to this ego position
                    closest_agent_frame = agent_positions[conflict_indices[0], 2]
                    
                    # Calculate time difference (assuming 30 FPS)
                    time_diff = (ego_frame - closest_agent_frame) / 30.0
                    
                    if abs(time_diff) < min_pet:
                        min_pet = time_diff
            
            return min_pet if conflict_found and min_pet != float('inf') else None
            
        except Exception as e:
            print(f"Error calculating PET: {e}")
            return None

    def find_intersecting_agents(self, ego_traj, agent_tracks, start_frame, end_frame, pet_range=(-3.0, 3.0)):
        """
        Find agents whose trajectories have Post-Encroachment Time (PET) <= 5 seconds with ego vehicle.
        Updated to use PET instead of simple position-based intersection detection.
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
        
        # Filter time ranged trajectory data
        tracks_df = self.tracks_df[
            (self.tracks_df['frame'] >= start_frame) & 
            (self.tracks_df['frame'] <= end_frame)
        ]

        for agent_id in agent_tracks:
            try:
                # Get agent trajectory data for the frame range
                agent_data = tracks_df[
                    (tracks_df['trackId'] == agent_id)
                ].sort_values('frame')
                
                if agent_data.empty:
                    continue
                
                # Calculate Post-Encroachment Time
                pet = self.calculate_post_encroachment_time(
                    ego_traj_filtered, agent_data, 
                    conflict_threshold=self.intersection_threshold
                )
                
                # Check if PET <= 5 seconds
                if pet is not None and pet_range[0] < pet_range < pet_range[1]:
                    print(f"    Found intersecting agent {agent_id} with PET: {pet:.2f}s")
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
    
    def get_relative_position(self, ego_id, agent_id, frame):
        """
        Calculate the relative position of agent vehicle with respect to ego vehicle.
        Returns one of: '左前', '前方', '右前', '右側', '左側', '左後', '後面', '右後'
        
        Args:
            ego_id: ID of ego vehicle
            agent_id: ID of agent vehicle
            frame: Frame to check the relative position
            
        Returns:
            String indicating relative position, or None if calculation fails
        """
        try:
            # Get positions of both vehicles at the given frame
            ego_data = self.tracks_df[
                (self.tracks_df['trackId'] == ego_id) & 
                (self.tracks_df['frame'] == frame)
            ]
            agent_data = self.tracks_df[
                (self.tracks_df['trackId'] == agent_id) & 
                (self.tracks_df['frame'] == frame)
            ]
            
            if ego_data.empty or agent_data.empty:
                return None
            
            ego_x, ego_y = ego_data.iloc[0]['xCenter'], ego_data.iloc[0]['yCenter']
            agent_x, agent_y = agent_data.iloc[0]['xCenter'], agent_data.iloc[0]['yCenter']
            
            # Get ego vehicle's heading angle
            ego_angle = self.calculate_vehicle_angle(ego_id, frame)
            if ego_angle is None:
                return None
            
            # Calculate vector from ego to agent
            dx = agent_x - ego_x
            dy = agent_y - ego_y
            
            # Calculate the angle of the vector from ego to agent
            vector_angle = np.degrees(np.arctan2(dy, dx))
            if vector_angle < 0:
                vector_angle += 360
            
            # Calculate relative angle (agent relative to ego's heading direction)
            relative_angle = vector_angle - ego_angle
            if relative_angle < 0:
                relative_angle += 360
            
            # Determine relative position based on relative angle
            # 0° = 前方, 90° = 右側, 180° = 後面, 270° = 左側
            if 337.5 <= relative_angle or relative_angle < 22.5:
                position = '前方'
            elif 22.5 <= relative_angle < 67.5:
                position = '右前'
            elif 67.5 <= relative_angle < 112.5:
                position = '右側'
            elif 112.5 <= relative_angle < 157.5:
                position = '右後'
            elif 157.5 <= relative_angle < 202.5:
                position = '後面'
            elif 202.5 <= relative_angle < 247.5:
                position = '左後'
            elif 247.5 <= relative_angle < 292.5:
                position = '左側'
            elif 292.5 <= relative_angle < 337.5:
                position = '左前'
            else:
                position = '未知'
            
            print(f"    Position check: agent {agent_id} is at {position} of ego {ego_id} (relative angle: {relative_angle:.1f}°)")
            return position
            
        except Exception as e:
            print(f"    Warning: Error in relative position calculation: {e}")
            return None
    
    def is_motorcycle_from_right_side(self, ego_id, agent_id, frame):
        """
        Check if the motorcycle agent is coming from the right side of ego's turning path.
        For a right turn scenario, the motorcycle should be approaching from the ego's right side.
        Uses heading_in_relative_direction_to() to determine spatial relationship.
        
        Args:
            ego_id: ID of ego vehicle (turning right)
            agent_id: ID of agent vehicle (motorcycle going straight)
            frame: Frame to check the spatial relationship
            
        Returns:
            True if motorcycle is coming from right side, False otherwise
        """
        try:
            # Get positions of both vehicles at the given frame
            ego_data = self.tracks_df[
                (self.tracks_df['trackId'] == ego_id) & 
                (self.tracks_df['frame'] == frame)
            ]
            agent_data = self.tracks_df[
                (self.tracks_df['trackId'] == agent_id) & 
                (self.tracks_df['frame'] == frame)
            ]
            
            if ego_data.empty or agent_data.empty:
                return False
            
            ego_x, ego_y = ego_data.iloc[0]['xCenter'], ego_data.iloc[0]['yCenter']
            agent_x, agent_y = agent_data.iloc[0]['xCenter'], agent_data.iloc[0]['yCenter']
            
            # Get ego vehicle's heading angle
            ego_angle = self.calculate_vehicle_angle(ego_id, frame)
            if ego_angle is None:
                return False
            
            # Calculate vector from ego to agent
            dx = agent_x - ego_x
            dy = agent_y - ego_y
            
            # Calculate the angle of the vector from ego to agent
            vector_angle = np.degrees(np.arctan2(dy, dx))
            if vector_angle < 0:
                vector_angle += 360
            
            # Use heading_in_relative_direction_to() to check if vehicles are in perpendicular relationship
            # For right turn scenario, ego and motorcycle should be roughly perpendicular (90 degrees)
            is_perpendicular = self.heading_in_relative_direction_to(ego_id, agent_id, frame, direction='perpendicular')
            
            # Calculate relative angle (agent relative to ego's heading)
            relative_angle = vector_angle - ego_angle
            if relative_angle < 0:
                relative_angle += 360
            if relative_angle > 360:
                relative_angle -= 360
            
            # For right side detection:
            # - Right side is roughly 270-90 degrees relative to ego's heading
            # - We use a range around 270 degrees (± 60 degrees) to be more flexible
            is_right_side = (210 <= relative_angle <= 330)
            
            # Combine perpendicular heading check with spatial position check
            is_valid_scenario = is_perpendicular and is_right_side
            
            print(f"    Spatial check: ego {ego_id} heading {ego_angle:.1f}°, agent {agent_id} at relative angle {relative_angle:.1f}°")
            print(f"    Perpendicular check: {'✓' if is_perpendicular else '✗'}, Right side: {'✓' if is_right_side else '✗'}")
            print(f"    Overall: {'✓ Valid right-side scenario' if is_valid_scenario else '✗ Not valid right-side scenario'}")
            
            return is_valid_scenario
            
        except Exception as e:
            print(f"    Warning: Error in spatial relationship check: {e}")
            return False

    def is_agent_passing_by_ego(self, ego_id, agent_id, start_frame, end_frame, min_distance_threshold=5.0):
        """
        Check if agent vehicle passes by (overtakes or is overtaken by) ego vehicle during the given time period.
        This function analyzes the relative position changes and distance variations between two vehicles.
        
        Args:
            ego_id: ID of ego vehicle
            agent_id: ID of agent vehicle
            start_frame: Start frame of the analysis period
            end_frame: End frame of the analysis period
            min_distance_threshold: Minimum distance threshold to consider as "close passing" (meters)
            
        Returns:
            dict: {
                'is_passing_by': bool,
                'passing_type': str ('overtaking_agent', 'overtaken_by_agent', 'parallel_passing', 'none'),
                'min_distance': float,
                'min_distance_frame': int,
                'initial_relative_position': str,
                'final_relative_position': str,
                'distance_variation': float
            }
        """
        try:
            # Get trajectories for both vehicles in the specified time range
            ego_traj = self.tracks_df[
                (self.tracks_df['trackId'] == ego_id) & 
                (self.tracks_df['frame'] >= start_frame) & 
                (self.tracks_df['frame'] <= end_frame)
            ].sort_values('frame')
            
            agent_traj = self.tracks_df[
                (self.tracks_df['trackId'] == agent_id) & 
                (self.tracks_df['frame'] >= start_frame) & 
                (self.tracks_df['frame'] <= end_frame)
            ].sort_values('frame')
            
            if ego_traj.empty or agent_traj.empty:
                return {
                    'is_passing_by': False,
                    'passing_type': 'none',
                    'min_distance': float('inf'),
                    'min_distance_frame': -1,
                    'initial_relative_position': 'unknown',
                    'final_relative_position': 'unknown',
                    'distance_variation': 0.0
                }
            
            # Calculate distances between vehicles for each overlapping frame
            distances = []
            frames = []
            relative_positions = []
            
            for _, ego_row in ego_traj.iterrows():
                frame = ego_row['frame']
                agent_row = agent_traj[agent_traj['frame'] == frame]
                
                if not agent_row.empty:
                    agent_row = agent_row.iloc[0]
                    
                    # Calculate Euclidean distance
                    distance = np.sqrt(
                        (ego_row['xCenter'] - agent_row['xCenter'])**2 + 
                        (ego_row['yCenter'] - agent_row['yCenter'])**2
                    )
                    
                    distances.append(distance)
                    frames.append(frame)
                    
                    # Get relative position
                    rel_pos = self.get_relative_position(ego_id, agent_id, frame)
                    relative_positions.append(rel_pos)
            
            if not distances:
                return {
                    'is_passing_by': False,
                    'passing_type': 'none',
                    'min_distance': float('inf'),
                    'min_distance_frame': -1,
                    'initial_relative_position': 'unknown',
                    'final_relative_position': 'unknown',
                    'distance_variation': 0.0
                }
            
            # Find minimum distance and its frame
            min_distance = min(distances)
            min_distance_frame = frames[distances.index(min_distance)]
            
            # Get initial and final relative positions
            initial_relative_position = relative_positions[0] if relative_positions else 'unknown'
            final_relative_position = relative_positions[-1] if relative_positions else 'unknown'
            
            # Calculate distance variation (range of distances)
            distance_variation = max(distances) - min(distances)
            
            # Determine if it's a passing scenario
            is_passing_by = False
            passing_type = 'none'
            
            # Check if minimum distance is within threshold (vehicles get close)
            if min_distance <= min_distance_threshold:
                is_passing_by = True
                
                # Analyze relative position changes to determine passing type
                if initial_relative_position and final_relative_position:
                    # Agent overtaking ego (agent moves from behind to front)
                    if (initial_relative_position in ['左後', '後面', '右後'] and 
                        final_relative_position in ['左前', '前方', '右前']):
                        passing_type = 'overtaking_agent'
                    
                    # Ego overtaking agent (agent moves from front to behind)
                    elif (initial_relative_position in ['左前', '前方', '右前'] and 
                          final_relative_position in ['左後', '後面', '右後']):
                        passing_type = 'overtaken_by_agent'
                    
                    # Parallel passing (side-by-side movement)
                    elif (initial_relative_position in ['左側', '右側'] or 
                          final_relative_position in ['左側', '右側']):
                        passing_type = 'parallel_passing'
                    
                    # If relative positions changed but don't fit clear patterns
                    elif initial_relative_position != final_relative_position:
                        passing_type = 'complex_passing'
                    else:
                        passing_type = 'close_following'
            
            # Additional check: significant distance variation might indicate passing even if not very close
            elif distance_variation > min_distance_threshold * 2:
                is_passing_by = True
                passing_type = 'distant_passing'
            
            result = {
                'is_passing_by': is_passing_by,
                'passing_type': passing_type,
                'min_distance': min_distance,
                'min_distance_frame': min_distance_frame,
                'initial_relative_position': initial_relative_position,
                'final_relative_position': final_relative_position,
                'distance_variation': distance_variation
            }
            
            # Print detailed analysis
            print(f"    Pass-by analysis for ego {ego_id} vs agent {agent_id}:")
            print(f"      Min distance: {min_distance:.2f}m at frame {min_distance_frame}")
            print(f"      Position change: {initial_relative_position} → {final_relative_position}")
            print(f"      Distance variation: {distance_variation:.2f}m")
            print(f"      Passing type: {passing_type}")
            print(f"      Is passing by: {'✓' if is_passing_by else '✗'}")
            
            return result
            
        except Exception as e:
            print(f"    Warning: Error in pass-by analysis: {e}")
            return {
                'is_passing_by': False,
                'passing_type': 'error',
                'min_distance': float('inf'),
                'min_distance_frame': -1,
                'initial_relative_position': 'unknown',
                'final_relative_position': 'unknown',
                'distance_variation': 0.0
            }

    def heading_in_relative_direction_to(self, ego_id, agent_id, frame, direction='opposite'):
        """
        Check if two vehicles are moving in specific relative directions
        Returns True if the angle between their headings matches the specified direction
        
        Args:
            ego_id: ID of ego vehicle
            agent_id: ID of agent vehicle  
            frame: Frame to check
            direction: 'opposite', 'same', or 'perpendicular'
        """
        ego_angle = self.calculate_vehicle_angle(ego_id, frame)
        agent_angle = self.calculate_vehicle_angle(agent_id, frame)
        
        if ego_angle is None or agent_angle is None:
            print(f"    Warning: Could not calculate angles for vehicles {ego_id}, {agent_id} at frame {frame}")
            return False
        
        if direction == 'opposite':
            direction_degree = 180
            tolerance_deg = 45
        elif direction == 'same':
            direction_degree = 0
            tolerance_deg = 20
        elif direction == 'perpendicular':
            direction_degree = 90
            tolerance_deg = 30  # Allow ±30 degrees for perpendicular
        else:
            print(f"    Warning: Unknown direction '{direction}', using 'opposite'")
            direction_degree = 180
            tolerance_deg = 45
        
        angle_diff = abs(ego_angle - agent_angle)
        # Handle angle wrapping (e.g., 350° and 10° should have diff of 20°)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        
        # For perpendicular check, we want the difference to be around 90° or 270°
        if direction == 'perpendicular':
            # Check if angle difference is close to 90° or 270° (which is the same as 90°)
            is_perpendicular = (direction_degree - tolerance_deg <= angle_diff <= direction_degree + tolerance_deg)
            print(f"    Angle check: ego {ego_id} ({ego_angle:.1f}°) vs agent {agent_id} ({agent_angle:.1f}°) -> diff: {angle_diff:.1f}° {'✓ ' + direction if is_perpendicular else '✗ Not ' + direction}")
            return is_perpendicular
        else:
            # For opposite and same direction checks
            cos_diff = np.cos(np.deg2rad(angle_diff))
            cos_tolerance = np.cos(np.deg2rad(direction_degree - tolerance_deg))
            is_relative_direction = cos_diff <= cos_tolerance
            print(f"    Angle check: ego {ego_id} ({ego_angle:.1f}°) vs agent {agent_id} ({agent_angle:.1f}°) -> diff: {angle_diff:.1f}° {'✓ ' + direction if is_relative_direction else '✗ Not ' + direction}")
            return is_relative_direction
    
    def find_scenarios_TR_KEEP(self, max_scenarios=10):
        """
        Find scenarios where ego vehicle turns right and encounters a motorcycle going straight from the right side
        Scenario: "ego右轉遇到右側機車直行"
        """
        description = "ego右轉遇到右側機車直行"
        print(f"\n3. Finding '{description}' scenarios...")

        # Ego vehicles are turning right
        ego_turning_tracks = self.find_tagged_vehicles('右轉')
        # ego_turning_right_tracks = self.find_tagged_vehicles('右轉')
        # Agent vehicles are going straight 
        agent_straight_tracks = self.find_tagged_vehicles('路口直行')

        scenarios = []
            
        # Convert straight tracks to list of agent IDs for batch processing
        agent_ids = list(agent_straight_tracks.keys())
            
        # For each turning right vehicle (potential ego)
        for ego_id, ego_info in ego_turning_tracks.items():
            # if ego_id not in ego_turning_right_tracks:
            #     continue
            
            if len(scenarios) >= max_scenarios:
                break
                
            ego_class = self.tracks_meta_df[self.tracks_meta_df['trackId'] == ego_id]['class'].values
            if len(ego_class) == 0 or ego_class[0] != 'car':
                # print(f"Skipping ego vehicle {ego_id}: class is not 'car'")
                continue
                
            # if ego_id != 114:
            #     continue
                    
            print(f"\nChecking ego vehicle {ego_id} (turning right)...")
                
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
            if len(intersecting_agents) > 0:
                print(f"  Found {len(intersecting_agents)} intersecting agents: {intersecting_agents}")
                    
            # Process each intersecting agent
            for agent_id in intersecting_agents:
                    
                agent_class = self.tracks_meta_df[self.tracks_meta_df['trackId'] == agent_id]['class'].values
                # Filter for motorcycles only
                if len(agent_class) == 0 or agent_class[0] != 'motorcycle':
                    continue
                        
                agent_info = agent_straight_tracks[agent_id]
                agent_start, agent_end = agent_info['start_frame'], agent_info['end_frame']
                    
                # Find overlapping time period
                overlap_start = max(ego_start, agent_start)
                overlap_end = min(ego_end, agent_end)
                    
                if overlap_start > overlap_end:
                    continue  # No time overlap
                
                # Check initial relative position of motorcycle at frame start
                initial_position = self.get_relative_position(ego_id, agent_id, overlap_start)
                if initial_position not in ['左後', '後面', '右後']:
                    print(f"    ✗ Skipping agent {agent_id}: initial position '{initial_position}' not in required positions (左後, 後面, 右後)")
                    continue
                
                # Check if motorcycle passes by ego during the scenario
                pass_by_result = self.is_agent_passing_by_ego(
                    ego_id, agent_id, overlap_start, overlap_end, 
                    min_distance_threshold=8.0  # Adjust threshold as needed
                )
                
                if not pass_by_result['is_passing_by']:
                    print(f"    ✗ Skipping agent {agent_id}: motorcycle does not pass by ego (passing type: {pass_by_result['passing_type']})")
                    continue
                
                # Log the passing behavior for analysis
                print(f"    ✓ Motorcycle {agent_id} passes by ego {ego_id}: {pass_by_result['passing_type']}")
                print(f"      Min distance: {pass_by_result['min_distance']:.2f}m, Position change: {pass_by_result['initial_relative_position']} → {pass_by_result['final_relative_position']}")
                    
                # # Check if motorcycle is coming from the right side of ego's turning path
                # if not self.is_motorcycle_from_right_side(ego_id, agent_id, overlap_start):
                #     print(f"    ✗ Skipping agent {agent_id}: motorcycle not coming from right side")
                #     continue
                    
                print(f"    ✓ Found scenario: ego {ego_id} (turning right) vs motorcycle {agent_id} (initial position: {initial_position})")
                    
                scenarios.append({
                    'ego_id': ego_id,
                    'agent_id': agent_id,
                    'start_frame': overlap_start,
                    'end_frame': overlap_end,
                    'ego_turning_range': (ego_start, ego_end),
                    'agent_straight_range': (agent_start, agent_end),
                    'description': description,
                    'initial_position': initial_position,
                    'passing_behavior': pass_by_result,  # Add passing behavior analysis
                })
            
        print(f"\nFound {len(scenarios)} scenarios matching criteria")
        return scenarios
    
    
    def find_scenarios_TL_KEEP(self, max_scenarios=10):
        """
        Find scenarios matching the criteria using improved intersection detection
        Similar to the reference main() function structure
        """
        description = "ego直行路口遇到對向車道汽車左轉於前"
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
                # print(f"Skipping ego vehicle {ego_id}: class is not 'car'")
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
            if len(intersecting_agents) > 0:
                print(f"  Found {len(intersecting_agents)} intersecting agents: {intersecting_agents}")
                
            # Process each intersecting agent
            for agent_id in intersecting_agents:
                
                agent_class = self.tracks_meta_df[self.tracks_meta_df['trackId'] == agent_id]['class'].values
                if len(agent_class) == 0 or (agent_class[0] != 'car' and agent_class[0] != 'truck'):
                # if len(agent_class) == 0 or (agent_class[0] != 'motorcycle'):
                    # print(f"Skipping agent vehicle {agent_id}: class is not vehicle(car or truck)")
                    continue
                    
                agent_info = turning_tracks[agent_id]
                agent_start, agent_end = agent_info['start_frame'], agent_info['end_frame']
                
                # Find overlapping time period
                overlap_start = max(ego_start, agent_start)
                overlap_end = min(ego_end, agent_end)
                
                if overlap_start > overlap_end:
                    continue  # No time overlap
                
                # Check if vehicles are moving in opposite directions at ego start frame
                if not self.heading_in_relative_direction_to(ego_id, agent_id, overlap_start, direction='opposite'):
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
            category = "intersection_turning_right_ego_motorcycle_straight"
            
            ego_id = scenario['ego_id']
            agent_id = scenario['agent_id']
            
            # Get the appropriate range based on scenario type
            if 'ego_turning_range' in scenario:
                ego_range = scenario['ego_turning_range']
            else:
                ego_range = scenario.get('ego_straight_range', (scenario['start_frame'], scenario['end_frame']))
            
            initial_position = scenario.get('initial_position', 'unknown')
            print(f"Saving {scenario_id}: ego {ego_id} (turning right) vs motorcycle {agent_id} (initial: {initial_position})")
            
            # Add annotations for ego vehicle (referred) for entire turning trajectory
            for frame in range(ego_range[0], ego_range[1] + 1):
                new_annotations.append({
                    'scenarioId': scenario_id,
                    'description': description,
                    'category': category,
                    'frame': frame,
                    'trackId': ego_id,
                    'role': 'refer'
                })
            
            # Add annotations for agent vehicle (related) for entire turning trajectory timeframe
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
        # scenarios = self.find_scenarios_TR_KEEP(max_scenarios)
        scenarios = self.find_scenarios_TL_KEEP(max_scenarios)
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
                initial_position = scenario.get('initial_position', 'unknown')
                
                # Get the appropriate range based on scenario type
                if 'ego_turning_range' in scenario:
                    ego_range = scenario['ego_turning_range']
                    range_type = "turning"
                else:
                    ego_range = scenario.get('ego_straight_range', (scenario['start_frame'], scenario['end_frame']))
                    range_type = "straight"
                
                print(f"{scenario_id}: ego {ego_id} ({range_type}, frames {ego_range[0]}-{ego_range[1]}) vs motorcycle {agent_id} (initial: {initial_position})")
        else:
            print("\nNo scenarios found matching the criteria")
            print("Try adjusting the thresholds:")
            print(f"  Current intersection_threshold: {self.intersection_threshold}m (position tolerance)")
            print(f"  Current distance_threshold: {self.distance_threshold}m")
            print("  Tip: Increase intersection_threshold for more lenient intersection detection")

def main():
    """Main function"""
    # File paths
    tracks_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/data/00_tracks.csv"
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
    # - intersection_threshold: conflict zone distance threshold for PET calculation (meters)
    # - distance_threshold: general interaction distance (not currently used)
    # - PET threshold is fixed at 5 seconds
    retrieval = SimpleScenarioRetrieval(
        tracks_file, tracks_meta_file, tags_file, annotations_file,
        distance_threshold=30.0,      # General interaction distance
        intersection_threshold=2.0    # Conflict zone threshold for PET calculation
    )
    
    # Find up to 5 scenarios
    retrieval.run(max_scenarios=3000)

if __name__ == "__main__":
    main()
