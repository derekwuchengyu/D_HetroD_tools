#!/usr/bin/env python3
"""
Quick test of the updated visualization with a static frame
"""

import sys
sys.path.append('/home/hcis-s19/Documents/ChengYu/HetroD_sample')

from visualize_moving_tags import TrajectoryVisualizer
import matplotlib.pyplot as plt

def test_static_frame():
    """Test a single frame of the visualization."""
    
    # Create visualizer
    visualizer = TrajectoryVisualizer(
        tags_file='tags.csv',
        trajectory_file='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv',
        background_image='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png'
    )
    
    # Load data
    print("Loading data...")
    visualizer.load_data()
    
    # Setup plot
    print("Setting up visualization...")
    visualizer.setup_plot()
    
    # Animate a single frame (frame 100)
    print("Rendering frame 100...")
    test_frame = 100
    visualizer.animate_frame(test_frame)
    
    # Save the result
    plt.savefig('test_frame_100.png', dpi=150, bbox_inches='tight')
    print("Saved test frame as 'test_frame_100.png'")
    
    print("Testing completed! Check if vehicles appear on roads in the saved image.")

if __name__ == "__main__":
    test_static_frame()
