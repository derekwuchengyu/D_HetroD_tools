#!/usr/bin/env python3
"""
Static visualization script for trajectory snapshots.
Shows multiple frames in a grid layout.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import ast
import argparse
from typing import List, Tuple
import matplotlib
import os
from PIL import Image
matplotlib.use('Agg')  # Use non-interactive backend for server environments


class StaticTrajectoryVisualizer:
    def __init__(self, tags_file: str, trajectory_file: str, background_image: str = None):
        """Initialize the static visualizer."""
        self.tags_file = tags_file
        self.trajectory_file = trajectory_file
        self.background_image = background_image
        self.tags_df = None
        self.trajectory_df = None
        
        # Color mapping for different action tags
        self.action_colors = {
            'moving': 'blue',
            'waiting': 'red',
            'turning': 'green',
            'accelerating': 'orange',
            'decelerating': 'purple',
            'stopped': 'gray'
        }
        self.default_color = 'black'
        
    def load_data(self):
        """Load and process data."""
        print("Loading data...")
        self.tags_df = pd.read_csv(self.tags_file)
        self.tags_df['action_tags'] = self.tags_df['action_tags'].apply(ast.literal_eval)
        self.tags_df['speed_tags'] = self.tags_df['speed_tags'].apply(ast.literal_eval)
        
        # Load trajectory data efficiently
        chunk_size = 10000
        chunks = []
        unique_track_ids = self.tags_df['trackId'].unique()
        
        for chunk in pd.read_csv(self.trajectory_file, chunksize=chunk_size):
            filtered_chunk = chunk[chunk['trackId'].isin(unique_track_ids)]
            if not filtered_chunk.empty:
                chunks.append(filtered_chunk)
        
        if chunks:
            self.trajectory_df = pd.concat(chunks, ignore_index=True)
        else:
            raise ValueError("No matching trajectory data found")
            
    def get_color_for_action(self, action_tags: List[str]) -> str:
        """Get color based on action tags."""
        if not action_tags:
            return self.default_color
        return self.action_colors.get(action_tags[0], self.default_color)
    
    def create_bounding_box(self, ax, x: float, y: float, heading: float, 
                           width: float, length: float, color: str, track_id: int,
                           action_tags: List[str], speed_tags: List[str]):
        """Create and add a bounding box to the plot."""
        # Create rectangle
        heading_rad = np.radians(heading)
        x_bl = x - length / 2
        y_bl = y - width / 2
        
        rect = Rectangle((x_bl, y_bl), length, width, 
                        angle=heading, rotation_point='center',
                        facecolor=color, alpha=0.6, edgecolor='black', linewidth=1,
                        zorder=2)  # Ensure bounding boxes appear above background
        ax.add_patch(rect)
        
        # Add text label
        action_str = ', '.join(action_tags) if action_tags else 'unknown'
        speed_str = ', '.join(speed_tags) if speed_tags else 'unknown'
        label = f"ID:{track_id}\n{action_str}\n{speed_str}"
        
        text_y = y + length/2 + 2
        ax.text(x, text_y, label, ha='center', va='bottom', fontsize=6,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                         alpha=0.8, edgecolor='gray'), zorder=3)
    
    def create_snapshot(self, frame_num: int, ax, title: str = None):
        """Create a snapshot for a specific frame."""
        # Get data for this frame
        frame_trajectory = self.trajectory_df[self.trajectory_df['frame'] == frame_num]
        frame_tags = self.tags_df[self.tags_df['frame'] == frame_num]
        frame_data = pd.merge(frame_trajectory, frame_tags, on=['trackId', 'frame'], how='inner')
        
        # Calculate bounds
        if not frame_data.empty:
            x_min, x_max = frame_data['xCenter'].min(), frame_data['xCenter'].max()
            y_min, y_max = frame_data['yCenter'].min(), frame_data['yCenter'].max()
            
            # Add padding
            x_padding = max((x_max - x_min) * 0.1, 5)
            y_padding = max((y_max - y_min) * 0.1, 5)
            
            plot_x_min = x_min - x_padding
            plot_x_max = x_max + x_padding
            plot_y_min = y_min - y_padding
            plot_y_max = y_max + y_padding
            
            # Load and display background image if provided
            if self.background_image and os.path.exists(self.background_image):
                try:
                    img = Image.open(self.background_image)
                    img_array = np.array(img)
                    
                    # Set background image extent
                    extent_padding = 0.2
                    img_x_range = (x_max - x_min) * (1 + extent_padding)
                    img_y_range = (y_max - y_min) * (1 + extent_padding)
                    
                    img_center_x = (x_min + x_max) / 2
                    img_center_y = (y_min + y_max) / 2
                    
                    background_extent = [
                        img_center_x - img_x_range/2,  # left
                        img_center_x + img_x_range/2,  # right
                        img_center_y - img_y_range/2,  # bottom
                        img_center_y + img_y_range/2   # top
                    ]
                    
                    # Display the background image
                    ax.imshow(img_array, extent=background_extent, aspect='auto', alpha=0.7, zorder=0)
                    
                except Exception as e:
                    print(f"Warning: Could not load background image for frame {frame_num}: {e}")
        else:
            plot_x_min, plot_x_max = -50, 50
            plot_y_min, plot_y_max = -50, 50
        
        # Set up plot
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3, zorder=1)
        ax.set_xlabel('X Position (m)', fontsize=8)
        ax.set_ylabel('Y Position (m)', fontsize=8)
        
        if title:
            ax.set_title(title, fontsize=10)
        else:
            ax.set_title(f'Frame {frame_num}', fontsize=10)
        
        # Set plot limits
        ax.set_xlim(plot_x_min, plot_x_max)
        ax.set_ylim(plot_y_min, plot_y_max)
        
        # Draw vehicles
        if not frame_data.empty:
            for _, row in frame_data.iterrows():
                color = self.get_color_for_action(row['action_tags'])
                self.create_bounding_box(
                    ax, row['xCenter'], row['yCenter'], row['heading'],
                    row['width'], row['length'], color, row['trackId'],
                    row['action_tags'], row['speed_tags']
                )
        else:
            ax.text(0.5, 0.5, 'No data for this frame', 
                   ha='center', va='center', transform=ax.transAxes)
    
    def create_multi_frame_plot(self, frames: List[int], output_file: str = 'trajectory_snapshots.png'):
        """Create a multi-frame plot."""
        n_frames = len(frames)
        
        # Determine grid layout
        if n_frames <= 4:
            rows, cols = 2, 2
        elif n_frames <= 6:
            rows, cols = 2, 3
        elif n_frames <= 9:
            rows, cols = 3, 3
        else:
            rows, cols = 4, 4
        
        fig, axes = plt.subplots(rows, cols, figsize=(15, 12))
        if rows == 1:
            axes = [axes]
        if cols == 1:
            axes = [[ax] for ax in axes]
        
        # Create snapshots
        for i, frame in enumerate(frames):
            if i >= rows * cols:
                break
            row, col = i // cols, i % cols
            self.create_snapshot(frame, axes[row][col])
        
        # Hide unused subplots
        for i in range(len(frames), rows * cols):
            row, col = i // cols, i % cols
            axes[row][col].set_visible(False)
        
        # Add overall title and legend
        fig.suptitle('Trajectory Snapshots with Behavioral Tags', fontsize=16)
        
        # Create legend
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, label=action) 
                          for action, color in self.action_colors.items()]
        fig.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(0.98, 0.98))
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Multi-frame plot saved to {output_file}")
    
    def create_trajectory_plot(self, output_file: str = 'trajectory_paths.png'):
        """Create a plot showing trajectory paths with start/end points."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Plot trajectory paths for each track
        for track_id in self.trajectory_df['trackId'].unique():
            track_data = self.trajectory_df[self.trajectory_df['trackId'] == track_id].sort_values('frame')
            
            if len(track_data) > 1:
                # Get action color from tags
                track_tags = self.tags_df[self.tags_df['trackId'] == track_id]
                if not track_tags.empty:
                    sample_action = track_tags.iloc[0]['action_tags']
                    color = self.get_color_for_action(sample_action)
                else:
                    color = self.default_color
                
                # Plot trajectory path
                ax.plot(track_data['xCenter'], track_data['yCenter'], 
                       color=color, alpha=0.7, linewidth=2, label=f'Track {track_id}')
                
                # Mark start and end points
                start_point = track_data.iloc[0]
                end_point = track_data.iloc[-1]
                
                ax.scatter(start_point['xCenter'], start_point['yCenter'], 
                          color=color, s=100, marker='o', edgecolor='black', linewidth=2)
                ax.scatter(end_point['xCenter'], end_point['yCenter'], 
                          color=color, s=100, marker='s', edgecolor='black', linewidth=2)
                
                # Add track ID label
                ax.text(start_point['xCenter'], start_point['yCenter'] + 2, 
                       f'Track {track_id}', ha='center', va='bottom', fontsize=8,
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
        
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('X Position (m)')
        ax.set_ylabel('Y Position (m)')
        ax.set_title('Complete Trajectory Paths\n(○ = start, ■ = end)')
        
        # Add action color legend
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, label=action) 
                          for action, color in self.action_colors.items()]
        ax.legend(handles=legend_elements, loc='best')
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Trajectory paths plot saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Create static trajectory visualizations')
    parser.add_argument('--tags', default='tags.csv', help='Path to tags CSV file')
    parser.add_argument('--trajectory', default='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv', help='Path to trajectory CSV file')
    parser.add_argument('--background', default='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png',
                       help='Path to background image file')
    parser.add_argument('--frames', type=int, nargs='+', default=[0, 10, 20, 30, 40, 50],
                       help='Frame numbers to visualize (default: 0 10 20 30 40 50)')
    parser.add_argument('--output-snapshots', default='trajectory_snapshots.png',
                       help='Output file for multi-frame snapshots')
    parser.add_argument('--output-paths', default='trajectory_paths.png',
                       help='Output file for trajectory paths')
    
    args = parser.parse_args()
    
    try:
        # Create visualizer
        visualizer = StaticTrajectoryVisualizer(args.tags, args.trajectory, args.background)
        visualizer.load_data()
        
        # Create visualizations
        print("Creating multi-frame snapshots...")
        visualizer.create_multi_frame_plot(args.frames, args.output_snapshots)
        
        print("Creating trajectory paths plot...")
        visualizer.create_trajectory_plot(args.output_paths)
        
        print("Static visualizations complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
