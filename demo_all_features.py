#!/usr/bin/env python3
"""
Comprehensive demonstration of the trajectory visualization tools.
This script shows all available visualization options.
"""

import os
import sys
import subprocess
from visualize_moving_tags import create_sample_trajectory_data

def run_command(cmd, description):
    """Run a command and print results."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            print("Output:")
            print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        if result.returncode == 0:
            print("✓ Success!")
        else:
            print(f"✗ Failed with return code {result.returncode}")
        return result.returncode == 0
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False

def main():
    print("Trajectory Visualization Demonstration")
    print("=====================================")
    
    # Check if we're in the right directory
    if not os.path.exists("tags.csv"):
        print("Error: tags.csv not found. Please run this script from the HetroD_sample directory.")
        sys.exit(1)
    
    
    # 2. Test data loading
    run_command("python3 test_visualization.py", "Testing data loading and validation")
    
    # 3. Create static visualizations
    run_command("python3 static_visualization.py", "Creating static visualization images")
    
    # 4. Show available files
    print(f"\n{'='*60}")
    print("Available visualization files:")
    print('='*60)
    
    files_to_check = [
        "visualize_moving_tags.py",
        "static_visualization.py", 
        "run_visualization_example.py",
        "test_visualization.py",
        "tags.csv",
        "trajectory_snapshots.png",
        "trajectory_paths.png",
        "README_visualization.md"
    ]
    
    for filename in files_to_check:
        status = "✓" if os.path.exists(filename) else "✗"
        size = f"({os.path.getsize(filename)} bytes)" if os.path.exists(filename) else ""
        print(f"{status} {filename} {size}")
    
    # 5. Provide usage instructions
    print(f"\n{'='*60}")
    print("Usage Instructions:")
    print('='*60)
    print("""
1. For ANIMATED visualization (opens interactive window):
   python3 visualize_moving_tags.py --tags tags.csv --trajectory sample_trajectory.csv
   
   OR use the example script:
   python3 run_visualization_example.py

2. For STATIC visualizations (creates PNG files):
   python3 static_visualization.py
   
3. To use with YOUR OWN trajectory data:
   python3 visualize_moving_tags.py --tags tags.csv --trajectory YOUR_FILE.csv
   
4. To save animated visualization as MP4:
   python3 visualize_moving_tags.py --save --output my_animation.mp4
   
5. To create custom static snapshots:
   python3 static_visualization.py --frames 0 50 100 150 200
   
Key Features:
- Blue boxes = moving vehicles
- Red boxes = waiting vehicles  
- Text shows track ID and behavioral tags
- Bounding boxes show vehicle orientation and size
- Animation shows time progression
- Static plots good for reports/presentations

Files created:
- trajectory_snapshots.png: Multi-frame snapshot grid
- trajectory_paths.png: Complete trajectory paths with start/end points
""")
    
    print("\nRead README_visualization.md for detailed documentation!")

if __name__ == "__main__":
    main()
