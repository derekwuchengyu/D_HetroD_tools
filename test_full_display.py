#!/usr/bin/env python3
"""
Test the full-size visualization without scaling
"""

import sys
sys.path.append('/home/hcis-s19/Documents/ChengYu/HetroD_sample')

from visualize_moving_tags import TrajectoryVisualizer
import matplotlib.pyplot as plt
import pandas as pd

def test_full_display():
    """Test the visualization at full size."""
    
    # Create visualizer
    visualizer = TrajectoryVisualizer(
        tags_file='tags.csv',
        trajectory_file='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv',
        background_image='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png'
    )
    
    # Load data first to check coordinate ranges
    print("Loading data...")
    visualizer.load_data()
    
    # Check coordinate ranges
    df = visualizer.trajectory_df
    ortho_px_to_meter = visualizer.ortho_px_to_meter
    
    print(f"\n=== Coordinate Analysis ===")
    print(f"Original coordinates (meters):")
    print(f"  X range: {df['xCenter'].min():.2f} to {df['xCenter'].max():.2f}")
    print(f"  Y range: {df['yCenter'].min():.2f} to {df['yCenter'].max():.2f}")
    
    # Convert to pixels
    x_pixels = df['xCenter'] / ortho_px_to_meter
    y_pixels = -df['yCenter'] / ortho_px_to_meter
    
    print(f"\nConverted to pixels (full size):")
    print(f"  X range: {x_pixels.min():.0f} to {x_pixels.max():.0f}")
    print(f"  Y range: {y_pixels.min():.0f} to {y_pixels.max():.0f}")
    
    # Setup plot
    print("\nSetting up visualization...")
    visualizer.setup_plot()
    
    # Show coordinate range for visualization
    x_lims = visualizer.ax.get_xlim()
    y_lims = visualizer.ax.get_ylim()
    print(f"Plot limits: X[{x_lims[0]:.0f}, {x_lims[1]:.0f}], Y[{y_lims[0]:.0f}, {y_lims[1]:.0f}]")
    
    # Animate a single frame (frame 100)
    print("\nRendering frame 100...")
    test_frame = 100
    visualizer.animate_frame(test_frame)
    
    # Save the result
    plt.savefig('test_full_display.png', dpi=150, bbox_inches='tight')
    print("Saved test frame as 'test_full_display.png'")
    
    print("\nTesting completed! Check if vehicles appear correctly sized on the full map.")

if __name__ == "__main__":
    test_full_display()
