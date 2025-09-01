#!/usr/bin/env python3
"""
Example usage of the trajectory visualizer.
This script demonstrates how to use the visualizer with the HetroD sample data.
"""

import os
import sys
from visualize_moving_tags import TrajectoryVisualizer

def main():
    # Paths to data files
    tags_file = "tags.csv"
    trajectory_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv"
    background_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png"
    
    print("HetroD Trajectory Visualization Example")
    print("=" * 40)
    
    # Check if required files exist
    for file_path, name in [(tags_file, "Tags file"), 
                           (trajectory_file, "Trajectory file"), 
                           (background_file, "Background image")]:
        if not os.path.exists(file_path):
            print(f"Error: {name} not found: {file_path}")
            return
        else:
            print(f"✓ {name} found")
    
    try:
        # Create visualizer with background image
        print("\nInitializing visualizer with background map...")
        visualizer = TrajectoryVisualizer(tags_file, trajectory_file, background_file)
        
        # Run visualization
        print("Starting visualization...")
        print("- Blue boxes: moving vehicles")
        print("- Red boxes: waiting vehicles")
        print("- Text shows: Track ID, action tags, speed tags")
        print("- Background shows the road map")
        print()
        print("Close the plot window to exit.")
        
        anim = visualizer.visualize(save_animation=False)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
