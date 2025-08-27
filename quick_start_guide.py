#!/usr/bin/env python3
"""
Quick start guide for trajectory visualization with background map.
"""

import os

def main():
    print("🗺️  Trajectory Visualization with Background Map")
    print("=" * 50)
    
    # Check if required files exist
    files_to_check = [
        ("tags.csv", "Behavioral tags data"),
        ("/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv", "Vehicle trajectories"),
        ("/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png", "Background map")
    ]
    
    all_files_exist = True
    for file_path, description in files_to_check:
        if os.path.exists(file_path):
            print(f"✓ {description}: {os.path.basename(file_path)}")
        else:
            print(f"✗ {description}: MISSING - {file_path}")
            all_files_exist = False
    
    if not all_files_exist:
        print("\n❌ Some required files are missing. Please check the file paths.")
        return
    
    print(f"\n🎯 Available Visualization Options:")
    print("-" * 40)
    
    print("\n1. 🎬 ANIMATED visualization (interactive window):")
    print("   python3 visualize_moving_tags.py")
    print("   • Shows moving vehicles with tags over time")
    print("   • Background map is automatically loaded")
    print("   • Color-coded vehicles by behavior")
    
    print("\n2. 📸 STATIC snapshots (saves PNG files):")
    print("   python3 static_visualization.py")
    print("   • Creates multi-frame snapshots")
    print("   • Shows trajectory paths with start/end points")
    print("   • Good for reports and presentations")
    
    print("\n3. 🚀 QUICK start with example script:")
    print("   python3 run_visualization_example.py")
    print("   • Guided visualization with helpful messages")
    
    print("\n4. 💾 SAVE animation as MP4:")
    print("   python3 visualize_moving_tags.py --save --output my_animation.mp4")
    
    print("\n🎨 Vehicle Color Coding:")
    print("-" * 25)
    print("• 🔵 Blue: Moving vehicles")
    print("• 🔴 Red: Waiting vehicles") 
    print("• 🟢 Green: Turning vehicles")
    print("• 🟠 Orange: Accelerating vehicles")
    print("• 🟣 Purple: Decelerating vehicles")
    print("• ⚪ Gray: Stopped vehicles")
    
    print("\n📊 Data Summary:")
    print("-" * 15)
    
    # Quick data check
    try:
        import pandas as pd
        tags_df = pd.read_csv("tags.csv")
        unique_tracks = len(tags_df['trackId'].unique())
        frame_range = (tags_df['frame'].min(), tags_df['frame'].max())
        print(f"• {unique_tracks} vehicles with behavioral tags")
        print(f"• Frame range: {frame_range[0]:.0f} to {frame_range[1]:.0f}")
        print(f"• {len(tags_df)} total data points")
    except Exception as e:
        print(f"• Could not read tags data: {e}")
    
    print(f"\n🗺️  Background Map Features:")
    print("-" * 28)
    print("• Automatically scaled to match trajectory bounds")
    print("• Semi-transparent overlay (alpha=0.7)")
    print("• Vehicles and text appear above the map")
    print("• Map coordinates are aligned with trajectory data")
    
    print(f"\n✨ Ready to visualize! Choose an option above to get started.")

if __name__ == "__main__":
    main()
