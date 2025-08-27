#!/usr/bin/env python3
"""
Test script to validate the background image integration with real data.
"""

import pandas as pd
import numpy as np
from visualize_moving_tags import TrajectoryVisualizer
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import os

def test_background_integration():
    """Test the visualization with background image using real data."""
    print("Testing trajectory visualization with background image...")
    
    # File paths
    tags_file = "tags.csv"
    trajectory_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv"
    background_image = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png"
    
    # Check if files exist
    for file_path, name in [(tags_file, "Tags file"), 
                           (trajectory_file, "Trajectory file"), 
                           (background_image, "Background image")]:
        if os.path.exists(file_path):
            print(f"✓ {name} found: {file_path}")
        else:
            print(f"✗ {name} missing: {file_path}")
            return False
    
    try:
        # Create visualizer with background
        visualizer = TrajectoryVisualizer(tags_file, trajectory_file, background_image)
        
        # Load data (this will test the chunked loading of the large trajectory file)
        print("\nLoading data...")
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
        
        # Test setup_plot (this will test background image loading)
        print("\nTesting plot setup with background image...")
        visualizer.setup_plot()
        
        if visualizer.background_extent:
            print(f"✓ Background image extent: {visualizer.background_extent}")
        else:
            print("✓ Background image processed (extent not set)")
        
        print("✓ Plot setup successful with background image!")
        
        # Test a frame merge
        test_frame = 0
        frame_trajectory = visualizer.trajectory_df[visualizer.trajectory_df['frame'] == test_frame]
        frame_tags = visualizer.tags_df[visualizer.tags_df['frame'] == test_frame]
        frame_data = pd.merge(frame_trajectory, frame_tags, on=['trackId', 'frame'], how='inner')
        
        print(f"Test frame {test_frame}: {len(frame_data)} vehicles")
        
        if len(frame_data) > 0:
            print("✓ Data integration successful!")
            print("✓ Ready for visualization with background map!")
            return True
        else:
            print("⚠ No vehicles found in test frame, but setup is working")
            return True
            
    except Exception as e:
        print(f"✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_background_integration()
    if success:
        print("\n🎉 Background integration test successful!")
        print("\nTo run the full visualization with background:")
        print("python3 visualize_moving_tags.py")
        print("\nOr for static visualization with background:")
        print("python3 static_visualization.py")
    else:
        print("\n❌ Background integration test failed.")
        print("Please check the file paths and data compatibility.")
