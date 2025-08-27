#!/usr/bin/env python3
"""
Test script to validate the visualization setup without opening GUI.
"""

import pandas as pd
import numpy as np
from visualize_moving_tags import TrajectoryVisualizer
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

def test_data_loading():
    """Test data loading and basic functionality."""
    print("Testing trajectory visualization setup...")
    
    try:
        # Create visualizer
        visualizer = TrajectoryVisualizer("tags.csv", "sample_trajectory.csv")
        
        # Load data
        visualizer.load_data()
        
        # Print basic statistics
        print(f"Tags data shape: {visualizer.tags_df.shape}")
        print(f"Trajectory data shape: {visualizer.trajectory_df.shape}")
        
        # Check unique tracks
        tags_tracks = set(visualizer.tags_df['trackId'].unique())
        traj_tracks = set(visualizer.trajectory_df['trackId'].unique())
        common_tracks = tags_tracks.intersection(traj_tracks)
        
        print(f"Tracks with tags: {len(tags_tracks)}")
        print(f"Tracks with trajectory: {len(traj_tracks)}")
        print(f"Common tracks: {len(common_tracks)}")
        
        # Check frame ranges
        tags_frames = (visualizer.tags_df['frame'].min(), visualizer.tags_df['frame'].max())
        traj_frames = (visualizer.trajectory_df['frame'].min(), visualizer.trajectory_df['frame'].max())
        
        print(f"Tags frame range: {tags_frames}")
        print(f"Trajectory frame range: {traj_frames}")
        
        # Test parsing functions
        sample_tags = visualizer.tags_df.iloc[0]
        action_str, speed_str = visualizer.parse_tags(sample_tags['action_tags'], sample_tags['speed_tags'])
        color = visualizer.get_color_for_action(sample_tags['action_tags'])
        
        print(f"Sample action tags: {action_str}")
        print(f"Sample speed tags: {speed_str}")
        print(f"Sample color: {color}")
        
        # Check if we can create a frame merge
        test_frame = visualizer.trajectory_df['frame'].iloc[0]
        frame_trajectory = visualizer.trajectory_df[visualizer.trajectory_df['frame'] == test_frame]
        frame_tags = visualizer.tags_df[visualizer.tags_df['frame'] == test_frame]
        frame_data = pd.merge(frame_trajectory, frame_tags, on=['trackId', 'frame'], how='inner')
        
        print(f"Test frame {test_frame}: {len(frame_data)} vehicles")
        
        if len(frame_data) > 0:
            print("✓ Data loading and merging successful!")
            print("✓ Ready for visualization")
            return True
        else:
            print("✗ No data found for test frame")
            return False
            
    except Exception as e:
        print(f"✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_data_loading()
    if success:
        print("\nTo run the full visualization:")
        print("python3 visualize_moving_tags.py --tags tags.csv --trajectory sample_trajectory.csv")
        print("\nOr use the example script:")
        print("python3 run_visualization_example.py")
    else:
        print("\nPlease check the data files and try again.")
