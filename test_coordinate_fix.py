#!/usr/bin/env python3
"""
Test script to verify coordinate system fixes
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import cv2
import os

def test_coordinate_system():
    """Test the coordinate system alignment with background image."""
    
    # Load trajectory data sample
    trajectory_file = '/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv'
    df = pd.read_csv(trajectory_file, nrows=1000)
    
    print("=== Original Trajectory Coordinates ===")
    print(f"X range: {df['xCenter'].min():.2f} to {df['xCenter'].max():.2f}")
    print(f"Y range: {df['yCenter'].min():.2f} to {df['yCenter'].max():.2f}")
    
    # Apply scale factor (like the reference implementation)
    scale_down_factor = 4
    x_scaled = df['xCenter'] / scale_down_factor
    y_scaled = df['yCenter'] / scale_down_factor
    
    print(f"\n=== Scaled Coordinates (÷{scale_down_factor}) ===")
    print(f"X range: {x_scaled.min():.2f} to {x_scaled.max():.2f}")
    print(f"Y range: {y_scaled.min():.2f} to {y_scaled.max():.2f}")
    
    # Dataset limits from visualizer_params.json
    x_limits = [314, 3424]
    y_limits = [2020, 134]
    
    print(f"\n=== Dataset Limits (from config) ===")
    print(f"X limits: {x_limits}")
    print(f"Y limits: {y_limits}")
    
    # Check if coordinates fit within limits
    x_in_range = (x_scaled >= x_limits[0]) & (x_scaled <= x_limits[1])
    y_in_range = (y_scaled >= y_limits[1]) & (y_scaled <= y_limits[0])  # Y is inverted
    
    print(f"\n=== Coordinate Validation ===")
    print(f"X coordinates in range: {x_in_range.sum()}/{len(x_scaled)} ({x_in_range.mean()*100:.1f}%)")
    print(f"Y coordinates in range: {y_in_range.sum()}/{len(y_scaled)} ({y_in_range.mean()*100:.1f}%)")
    
    # Load and check background image
    background_file = '/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png'
    if os.path.exists(background_file):
        try:
            img = cv2.cvtColor(cv2.imread(background_file), cv2.COLOR_BGR2RGB)
            print(f"\n=== Background Image Info ===")
            print(f"Original size: {img.shape[1]} x {img.shape[0]} (width x height)")
            
            # Apply scale down
            if scale_down_factor > 1:
                img_scaled = cv2.resize(img, 
                                      (int(img.shape[1] / scale_down_factor),
                                       int(img.shape[0] / scale_down_factor)),
                                      interpolation=cv2.INTER_NEAREST)
                print(f"Scaled size: {img_scaled.shape[1]} x {img_scaled.shape[0]} (width x height)")
                
        except Exception as e:
            print(f"Error loading background image: {e}")
    
    # Create a test plot
    plt.figure(figsize=(15, 8))
    
    # Load and display background
    if os.path.exists(background_file):
        background_image = cv2.cvtColor(cv2.imread(background_file), cv2.COLOR_BGR2RGB)
        if scale_down_factor > 1:
            (image_height, image_width) = background_image.shape[:2]
            background_image = cv2.resize(background_image,
                                       dsize=(int(image_width / scale_down_factor),
                                             int(image_height / scale_down_factor)),
                                       interpolation=cv2.INTER_NEAREST)
        plt.imshow(background_image, alpha=0.8, zorder=0)
    
    # Plot trajectory points (scaled)
    plt.scatter(x_scaled, y_scaled, c='red', s=5, alpha=0.7, zorder=2, label='Trajectory Points')
    
    # Set limits
    plt.xlim(x_limits)
    plt.ylim(y_limits)
    plt.gca().set_aspect('equal')
    
    # Remove ticks
    plt.gca().set_xticklabels([])
    plt.gca().set_yticklabels([])
    
    plt.title('Coordinate System Test - Trajectories on Background Map')
    plt.legend()
    
    # Save test result
    plt.savefig('coordinate_test_result.png', dpi=150, bbox_inches='tight')
    print(f"\n=== Test completed! ===")
    print("Saved result as 'coordinate_test_result.png'")
    print("Check if trajectory points align with roads on the background map.")
    
    plt.show()

if __name__ == "__main__":
    test_coordinate_system()
