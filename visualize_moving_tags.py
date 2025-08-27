#!/usr/bin/env python3
"""
Visualization script for moving trajectories with tags.
Displays moving bounding boxes with action and speed tags overlaid.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle
import matplotlib
matplotlib.use("TkAgg")
import ast
import argparse
from typing import Dict, List, Tuple, Optional
import warnings
import os
from PIL import Image
import cv2
warnings.filterwarnings('ignore')    
plt.rcParams["font.family"] = 'WenQuanYi Zen Hei' #Droid Sans Fallback
plt.rcParams["axes.unicode_minus"] = False

class TrajectoryVisualizer:
    def __init__(self, tags_file: str, trajectory_file: str, background_image: str = None):
        """
        Initialize the visualizer with tags and trajectory data.
        
        Args:
            tags_file: Path to tags.csv file
            trajectory_file: Path to trajectory CSV file
            background_image: Path to background image file (optional)
        """
        self.tags_file = tags_file
        self.trajectory_file = trajectory_file
        self.background_image = background_image
        self.tags_df = None
        self.trajectory_df = None
        self.fig = None
        self.ax = None
        self.track_patches = {}
        self.track_texts = {}
        self.frame_text = None  # Text object for frame number display
        self.background_extent = None  # Will store the extent of the background image
        
        # Dataset specific parameters - no scaling needed for full display
        self.ortho_px_to_meter = 0.0499967249445942  # From recording meta
        
        # Color mapping for different action tags
        self.action_colors = {
            'waiting': 'red',
            'lane_change': 'yellow',
            'lane_change_left': 'orange',
            'lane_change_right': 'cyan',
            'turning_left': 'green',
            'turning_right': [0.866, 0.674, 0.188],
            '左轉': [0.466, 0.974, 0.2],
            '右轉': '#3b2d15',
            '直行': 'lightblue', 
            'accelerating': 'orange',
            'decelerating': 'purple',
            'moving': 'blue',
            'stopped': 'gray'
        }
        
        # Default color if tag not found
        self.default_color = 'black'
        
    def load_data(self):
        """Load tags and trajectory data."""
        print("Loading tags data...")
        self.tags_df = pd.read_csv(self.tags_file)
        
        # Parse the string representations of lists
        self.tags_df['action_tags'] = self.tags_df['action_tags'].apply(ast.literal_eval)
        self.tags_df['speed_tags'] = self.tags_df['speed_tags'].apply(ast.literal_eval)
        
        print("Loading trajectory data...")
        # Load trajectory data in chunks to handle large files efficiently
        chunk_size = 10000
        chunks = []
        
        # Get unique track IDs from tags to filter trajectory data
        unique_track_ids = self.tags_df['trackId'].unique()
        
        for chunk in pd.read_csv(self.trajectory_file, chunksize=chunk_size):
            # Filter chunk to only include tracks that have tags
            filtered_chunk = chunk[chunk['trackId'].isin(unique_track_ids)]
            if not filtered_chunk.empty:
                chunks.append(filtered_chunk)
        
        if chunks:
            self.trajectory_df = pd.concat(chunks, ignore_index=True)
        else:
            raise ValueError("No matching trajectory data found for tracks with tags")
        
        print(f"Loaded {len(self.trajectory_df)} trajectory points for {len(unique_track_ids)} tracks")
        
    def parse_tags(self, action_tags: List[str], speed_tags: List[str]) -> Tuple[str, str]:
        """
        Parse action and speed tags to get display strings.
        
        Args:
            action_tags: List of action tags
            speed_tags: List of speed tags
            
        Returns:
            Tuple of (action_string, speed_string)
        """
        action_str = ', '.join(action_tags) if action_tags else 'unknown'
        speed_str = ', '.join(speed_tags) if speed_tags else 'unknown'
        return action_str, speed_str
    
    def get_color_for_action(self, action_tags: List[str]) -> str:
        """
        Get color based on primary action tag.
        
        Args:
            action_tags: List of action tags
            
        Returns:
            Color string
        """
        if not action_tags:
            return self.default_color

        priority_actions = self.action_colors.keys()
        action = [tag for tag in priority_actions if tag in action_tags]

        # Use the first action tag for color
        primary_action = action[0]
        return self.action_colors.get(primary_action, self.default_color)
    
    def create_bounding_box(self, x: float, y: float, heading: float, 
                           width: float, length: float) -> Rectangle:
        """
        Create a rotated bounding box rectangle.
        
        Args:
            x, y: Center coordinates
            heading: Heading angle in degrees
            width, length: Box dimensions
            
        Returns:
            matplotlib Rectangle patch
        """
        # Convert heading to radians
        # heading_rad = np.radians(heading)
        heading = heading * -1
        heading = heading if heading >= 0 else heading + 360
        
        # Calculate corner offset from center
        dx = length / 2
        dy = width / 2
        
        # Calculate bottom-left corner before rotation
        x_bl = x - dx
        y_bl = y - dy
        
        # Create rectangle
        rect = Rectangle((x_bl, y_bl), length, width, 
                        angle=heading, rotation_point='center')
        return rect
    
    def setup_plot(self):
        """Setup the matplotlib figure and axis."""
        self.fig, self.ax = plt.subplots(figsize=(15, 8))
        
        # Load and display background image if provided
        if self.background_image and os.path.exists(self.background_image):
            try:
                import cv2
                # Load background image at full resolution - no scaling
                background_image = cv2.cvtColor(cv2.imread(self.background_image), cv2.COLOR_BGR2RGB)
                
                # Display the background image at full size
                self.ax.imshow(background_image, alpha=0.8, zorder=0)
                print(f"Background image loaded: {self.background_image}")
                print(f"Background image size: {background_image.shape[1]} x {background_image.shape[0]} (width x height)")
                
            except Exception as e:
                print(f"Warning: Could not load background image {self.background_image}: {e}")
        
        # Set axis properties for full trajectory display
        # Let matplotlib auto-scale to show all trajectories
        self.ax.set_autoscale_on(True)
        self.ax.set_aspect('equal')
        self.ax.grid(True, alpha=0.3, zorder=1)
        self.ax.set_xlabel('X Position (pixels)')
        self.ax.set_ylabel('Y Position (pixels)')
        self.ax.set_title('Moving Trajectories with Tags - Full Display')
        
        # Initialize frame number label
        self.frame_text = self.ax.text(0.02, 0.98, '', transform=self.ax.transAxes,
                                      fontsize=14, fontweight='bold',
                                      bbox=dict(boxstyle='round,pad=0.5', 
                                               facecolor='yellow', 
                                               alpha=0.8,
                                               edgecolor='black'),
                                      verticalalignment='top',
                                      zorder=10)  # High z-order to appear on top
        
        # Create legend for action types
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, label=action) 
                          for action, color in self.action_colors.items()]
        self.ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
        
        plt.tight_layout()
        
    def animate_frame(self, frame_num: int):
        """
        Animate a single frame.
        
        Args:
            frame_num: Current frame number
        """
        # Clear previous patches and texts
        for track_id in list(self.track_patches.keys()):
            if self.track_patches[track_id] in self.ax.patches:
                self.track_patches[track_id].remove()
            if track_id in self.track_texts and self.track_texts[track_id] in self.ax.texts:
                self.track_texts[track_id].remove()
        
        self.track_patches.clear()
        self.track_texts.clear()
        
        # Get trajectory data for current frame
        frame_trajectory = self.trajectory_df[self.trajectory_df['frame'] == frame_num]
        
        # Get tags data for current frame
        frame_tags = self.tags_df[self.tags_df['frame'] == frame_num]
        
        # Merge trajectory and tags data
        frame_data = pd.merge(frame_trajectory, frame_tags, on=['trackId', 'frame'], how='inner')
        
        # Draw bounding boxes and labels for each track
        for _, row in frame_data.iterrows():
            track_id = row['trackId']
            # Convert from meters to pixel coordinates (no scaling)
            x = row['xCenter'] / self.ortho_px_to_meter
            y = -row['yCenter'] / self.ortho_px_to_meter  # Y is negated for image coordinates
            heading = row['heading']  # Keep heading as-is (in degrees)
            width = row['width'] / self.ortho_px_to_meter
            length = row['length'] / self.ortho_px_to_meter
            action_tags = row['action_tags']
            speed_tags = row['speed_tags']
            
            # Get color based on action
            color = self.get_color_for_action(action_tags)
            
            # Create bounding box
            bbox = self.create_bounding_box(x, y, heading, width, length)
            bbox.set_facecolor(color)
            bbox.set_alpha(0.6)
            bbox.set_edgecolor('black')
            bbox.set_linewidth(1)
            bbox.set_zorder(2)  # Ensure bounding boxes appear above background
            
            # Add to plot
            self.ax.add_patch(bbox)
            self.track_patches[track_id] = bbox
            
            # Create label text
            action_str, speed_str = self.parse_tags(action_tags, speed_tags)
            action_str = action_str.replace('waiting', '')
            if action_str == '':
                label = ''
            else:
                label = f"ID:{track_id}\n{action_str}" # \n{speed_str}"
            
            # Position text above the bounding box
            text_y = y + length/2 + 80
            text = self.ax.text(x, text_y, label, 
                              ha='center', va='bottom',
                              fontsize=8, 
                              bbox=dict(boxstyle='round,pad=0.3', 
                                       facecolor='white', 
                                       alpha=0.8,
                                       edgecolor='gray'),
                              zorder=3)  # Ensure text appears above everything
            self.track_texts[track_id] = text
        
        # Update frame number label
        self.frame_text.set_text(f'Frame: {frame_num}')
        
        return list(self.track_patches.values()) + list(self.track_texts.values()) + [self.frame_text]
    
    def visualize(self, save_animation: bool = False, output_file: str = 'trajectory_animation.mp4'):
        """
        Create and display the visualization.
        
        Args:
            save_animation: Whether to save animation to file
            output_file: Output file path for saved animation
        """
        # Load data
        self.load_data()
        
        # Setup plot
        self.setup_plot()
        
        # Get frame range with 3x speed (skip every 3rd frame)
        min_frame = max(self.trajectory_df['frame'].min(), self.tags_df['frame'].min())
        max_frame = min(self.trajectory_df['frame'].max(), self.tags_df['frame'].max())
        frames = range(0, max_frame + 1, 3)  # Skip every 3rd frame for 3x speed
        
        print(f"Creating animation for frames {min_frame} to {max_frame} (every 3rd frame)")
        
        # Create animation with 3x faster frame rate
        anim = animation.FuncAnimation(
            self.fig, self.animate_frame, frames=frames,
            interval=66, blit=True, repeat=True  # ~30 FPS (33ms interval) for 3x speed
        )
        
        if save_animation:
            print(f"Saving animation to {output_file}...")
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=10, metadata=dict(artist='TrajectoryVisualizer'), bitrate=1800)
            anim.save(output_file, writer=writer)
            print("Animation saved!")
        
        plt.show()
        
        return anim

def main():
    parser = argparse.ArgumentParser(description='Visualize moving trajectories with tags')
    parser.add_argument('--tags', default='tags.csv', 
                       help='Path to tags CSV file (default: tags.csv)')
    parser.add_argument('--trajectory', default='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv',
                       help='Path to trajectory CSV file (default: trajectory.csv)')
    parser.add_argument('--background', default='/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_background.png',
                       help='Path to background image file (default: 00_background.png)')
    parser.add_argument('--save', action='store_true',
                       help='Save animation as MP4 file')
    parser.add_argument('--output', default='trajectory_animation.mp4',
                       help='Output file for saved animation')

    
    args = parser.parse_args()
    
    
    try:
        # Create visualizer
        visualizer = TrajectoryVisualizer(args.tags, args.trajectory, args.background)
        
        # Run visualization
        anim = visualizer.visualize(save_animation=args.save, output_file=args.output)
        
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        print("Use --create-sample to generate sample trajectory data for testing")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
