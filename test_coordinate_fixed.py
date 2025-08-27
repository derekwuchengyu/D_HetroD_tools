#!/usr/bin/env python3
"""
Test script to verify the fixed coordinate system
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import cv2
import os

def test_fixed_coordinates():
    """Test the coordinate system with correct transformation."""
    
    # Load trajectory data sample
    trajectory_file = '/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv'
    df = pd.read_csv(trajectory_file, nrows=1000)
    
    # Load recording meta
    meta_df = pd.read_csv('/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_recordingMeta.csv')
    ortho_px_to_meter = meta_df['orthoPxToMeter'].iloc[0]
    scale_down_factor = 4
    
    print("=== Original Trajectory Coordinates ===")
    print(f"X range: {df['xCenter'].min():.2f} to {df['xCenter'].max():.2f}")
    print(f"Y range: {df['yCenter'].min():.2f} to {df['yCenter'].max():.2f}")
    
    # Apply correct coordinate transformation (following reference implementation)
    x_pixel = df['xCenter'] / ortho_px_to_meter / scale_down_factor
    y_pixel = -df['yCenter'] / ortho_px_to_meter / scale_down_factor  # Y is negated!
    
    print(f"\n=== Converted to Image Coordinates ===")
    print(f"orthoPxToMeter: {ortho_px_to_meter}")
    print(f"scale_down_factor: {scale_down_factor}")
    print(f"X range: {x_pixel.min():.0f} to {x_pixel.max():.0f}")
    print(f"Y range: {y_pixel.min():.0f} to {y_pixel.max():.0f}")
    
    # Dataset limits from visualizer_params.json
    x_limits = [314, 3424]
    y_limits = [2020, 134]
    
    print(f"\n=== Dataset Limits (from config) ===")
    print(f"X limits: {x_limits}")
    print(f"Y limits: {y_limits}")
    
    # Check if coordinates fit within limits
    x_in_range = (x_pixel >= x_limits[0]) & (x_pixel <= x_limits[1])
    y_in_range = (y_pixel >= y_limits[1]) & (y_pixel <= y_limits[0])  # Y limits are inverted
    
    print(f"\n=== Coordinate Validation ===")
    print(f"X coordinates in range: {x_in_range.sum()}/{len(x_pixel)} ({x_in_range.mean()*100:.1f}%)")
    print(f"Y coordinates in range: {y_in_range.sum()}/{len(y_pixel)} ({y_in_range.mean()*100:.1f}%)")
    
    # Create a test plot
    plt.figure(figsize=(15, 8))
    
    # Load and display background
    background_file = '/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png'
    if os.path.exists(background_file):
        background_image = cv2.cvtColor(cv2.imread(background_file), cv2.COLOR_BGR2RGB)
        if scale_down_factor > 1:
            (image_height, image_width) = background_image.shape[:2]
            background_image = cv2.resize(background_image,
                                       dsize=(int(image_width / scale_down_factor),
                                             int(image_height / scale_down_factor)),
                                       interpolation=cv2.INTER_NEAREST)
        plt.imshow(background_image, alpha=0.8, zorder=0)
        print(f"\n=== Background Image ===")
        print(f"Scaled image size: {background_image.shape[1]} x {background_image.shape[0]} (width x height)")
    
    # Plot trajectory points (correctly transformed)
    plt.scatter(x_pixel, y_pixel, c='red', s=10, alpha=0.8, zorder=2, label='Trajectory Points')
    
    # Set limits
    plt.xlim(x_limits)
    plt.ylim(y_limits)
    plt.gca().set_aspect('equal')
    
    # Remove ticks
    plt.gca().set_xticklabels([])
    plt.gca().set_yticklabels([])
    
    plt.title('Fixed Coordinate System - Trajectories on Background Map')
    plt.legend()
    
    # Save test result
    plt.savefig('coordinate_fixed_result.png', dpi=150, bbox_inches='tight')
    print(f"\n=== Test completed! ===")
    print("Saved result as 'coordinate_fixed_result.png'")
    print("Trajectory points should now align with roads on the background map.")
    
    plt.show()

if __name__ == "__main__":
    test_fixed_coordinates()
