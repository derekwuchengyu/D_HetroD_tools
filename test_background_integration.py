#!/usr/bin/env python3
"""
Test script to validate background image integration.
"""

import os
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np

def test_background_image():
    """Test loading and displaying the background image."""
    background_path = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png"
    
    print("Testing background image integration...")
    print(f"Background image path: {background_path}")
    
    if not os.path.exists(background_path):
        print(f"❌ Background image not found: {background_path}")
        return False
    
    try:
        # Load the image
        img = Image.open(background_path)
        img_array = np.array(img)
        
        print(f"✅ Image loaded successfully")
        print(f"   Image size: {img.size}")
        print(f"   Image mode: {img.mode}")
        print(f"   Array shape: {img_array.shape}")
        
        # Create a test plot
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Display the image with some test extent
        test_extent = [-100, 100, -100, 100]  # left, right, bottom, top
        ax.imshow(img_array, extent=test_extent, aspect='auto', alpha=0.7)
        
        # Add some test elements
        ax.scatter([0, 20, -30], [0, 40, -20], c=['red', 'blue', 'green'], s=100, zorder=2)
        ax.text(0, 50, "Test Background Image", ha='center', fontsize=16, 
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8), zorder=3)
        
        ax.set_xlim(-100, 100)
        ax.set_ylim(-100, 100)
        ax.set_xlabel('X Position')
        ax.set_ylabel('Y Position')
        ax.set_title('Background Image Test')
        ax.grid(True, alpha=0.3, zorder=1)
        
        # Save test image
        output_path = "background_test.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Test plot saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error loading background image: {e}")
        return False

def test_visualization_with_background():
    """Test the actual visualization with background."""
    print("\nTesting visualization with background...")
    
    try:
        from visualize_moving_tags import TrajectoryVisualizer
        
        # Test with sample data
        tags_file = "tags.csv"
        trajectory_file = "sample_trajectory.csv"
        background_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png"
        
        if not os.path.exists(tags_file):
            print(f"❌ Tags file not found: {tags_file}")
            return False
            
        if not os.path.exists(trajectory_file):
            print(f"❌ Trajectory file not found: {trajectory_file}")
            return False
        
        # Create visualizer with background
        print("Creating visualizer with background...")
        visualizer = TrajectoryVisualizer(tags_file, trajectory_file, background_file)
        
        # Load data
        visualizer.load_data()
        print(f"✅ Data loaded: {len(visualizer.trajectory_df)} trajectory points")
        
        # Test setup_plot method
        visualizer.setup_plot()
        print("✅ Plot setup with background completed")
        
        # Save a test frame
        frame_num = 0
        visualizer.animate_frame(frame_num)
        
        # Save the plot
        test_output = "visualization_with_background_test.png"
        visualizer.fig.savefig(test_output, dpi=150, bbox_inches='tight')
        plt.close(visualizer.fig)
        
        print(f"✅ Test visualization saved to: {test_output}")
        return True
        
    except Exception as e:
        print(f"❌ Error in visualization test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Background Image Integration Test")
    print("=" * 40)
    
    # Test 1: Basic image loading
    test1_success = test_background_image()
    
    # Test 2: Integration with visualization
    test2_success = test_visualization_with_background()
    
    print("\n" + "=" * 40)
    print("Test Results:")
    print(f"Basic image loading: {'✅ PASS' if test1_success else '❌ FAIL'}")
    print(f"Visualization integration: {'✅ PASS' if test2_success else '❌ FAIL'}")
    
    if test1_success and test2_success:
        print("\n🎉 All tests passed! Background image integration is working correctly.")
        print("\nGenerated files:")
        if os.path.exists("background_test.png"):
            print("- background_test.png: Basic background image test")
        if os.path.exists("visualization_with_background_test.png"):
            print("- visualization_with_background_test.png: Full visualization test")
    else:
        print("\n⚠️  Some tests failed. Please check the error messages above.")

if __name__ == "__main__":
    main()
