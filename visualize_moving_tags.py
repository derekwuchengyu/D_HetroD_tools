#!/usr/bin/env python3
"""
Visualization script for moving trajectories with tags.
Displays moving bounding boxes with action and speed tags overlaid.
"""

import json
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
import polars as pl

warnings.filterwarnings('ignore')    
plt.rcParams["font.family"] = ['WenQuanYi Zen Hei', 'DejaVu Sans'] #Droid Sans Fallback
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
        
        # Playback control variables
        self.is_playing = True
        self.is_reverse = False
        self.speed_multiplier = 1.0
        self.current_frame_index = 0
        self.frames_list = []
        self.animation_obj = None
        self.control_text = None  # Text object for control instructions
        self.base_interval = 50  # Base interval in ms for normal speed (~15 FPS)

        
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
            '路口直行': 'lightblue', 
            'accelerating': 'orange',
            'decelerating': 'purple',
            'straight': 'blue',
            'moving': 'darkseagreen',
            'stopped': 'gray'
        }
                
        # Tag filtering variables
        self.visible_tags = set(self.action_colors.keys())  # Initially show all tags
        self.tag_selection_mode = False  # Toggle for tag selection interface
        self.tag_text = None  # Text object for tag selection display
        self.tag_list = list(self.action_colors.keys())  # Fixed order list of all tags
        self.current_tag_page = 0  # Current page for tag selection (10 tags per page)
        self.tags_per_page = 10
        
        # Default color if tag not found
        self.default_color = 'black'
        
    def load_data(self):
        """Load tags and trajectory data."""
        print("Loading tags data...")
        self.tags_df = pd.read_parquet("/home/hcis-s19/Documents/ChengYu/HetroD_sample/tags.parquet")
        
        # # Parse the string representations of lists
        # self.tags_df['action_tags'] = self.tags_df['action_tags'].apply(ast.literal_eval)
        # self.tags_df['speed_tags'] = self.tags_df['speed_tags'].apply(ast.literal_eval)
        
        
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
        
    def parse_tags(self, action_tags: List[str], speed_tags: List[str]) -> Tuple[str, str, bool]:
        """
        Parse action and speed tags to get display strings and visibility.
        
        Args:
            action_tags: List of action tags
            speed_tags: List of speed tags
            
        Returns:
            Tuple of (action_string, speed_string, should_show_text)
        """
        # Remove 'moving' and 'waiting' from action tags for cleaner display
        action_tags = [tag for tag in action_tags if tag != 'moving' and tag != 'waiting']
        
        # Check if any action tag is visible
        visible_action_tags = [tag for tag in action_tags if tag in self.visible_tags]
        should_show_text = len(visible_action_tags) > 0
        
        action_str = ', '.join(visible_action_tags) if visible_action_tags else ''
        speed_str = ', '.join(speed_tags) if speed_tags else ''
        return action_str, speed_str, should_show_text
    
    def get_color_for_action(self, action_tags: List[str]) -> Tuple[str, bool]:
        """
        Get color based on primary action tag, considering visibility filter.
        
        Args:
            action_tags: List of action tags
            
        Returns:
            Tuple of (color_string, should_display_track)
        """
        if not action_tags:
            return self.default_color, True

        priority_actions = self.action_colors.keys()
        visible_actions = [tag for tag in priority_actions if tag in action_tags and tag in self.visible_tags]
        
        if not visible_actions:
            return None, False  # This track should not be displayed

        # Use the first visible action tag for color
        primary_action = visible_actions[0]
        return self.action_colors.get(primary_action, self.default_color), True
    
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
    
    def on_key_press(self, event):
        """
        Handle keyboard events for playback control and tag selection.
        
        Args:
            event: Keyboard event
        """
        if event.key == ' ':  # Spacebar - toggle play/pause
            self.is_playing = not self.is_playing
            status = "Playing" if self.is_playing else "Paused"
            print(f"Animation {status}")
        
        elif event.key == 'left':  # Left arrow - reverse
            self.is_reverse = True
            if not self.is_playing:
                self.is_playing = True
            print("Reverse playback")
        
        elif event.key == 'right':  # Right arrow - forward
            self.is_reverse = False
            if not self.is_playing:
                self.is_playing = True
            print("Forward playback")
        
        elif event.key == 'up':  # Up arrow - speed up
            self.speed_multiplier = min(self.speed_multiplier * 1.5, 5.0)
            print(f"Speed: {self.speed_multiplier:.1f}x")
            self.restart_animation()
        
        elif event.key == 'down':  # Down arrow - slow down
            self.speed_multiplier = max(self.speed_multiplier / 1.5, 0.2)
            print(f"Speed: {self.speed_multiplier:.1f}x")
            self.restart_animation()
        
        elif event.key == 'r':  # R key - reset to normal speed and forward
            self.speed_multiplier = 1.0
            self.is_reverse = False
            self.is_playing = True
            print("Reset to normal speed and forward playback")
            self.restart_animation()
        
        elif event.key == 't':  # T key - toggle tag selection mode
            self.tag_selection_mode = not self.tag_selection_mode
            if self.tag_selection_mode:
                print("Tag selection mode ON - Use 1-9,0 to toggle tags, Left/Right to change page")
                self.show_current_tag_page()
            else:
                print("Tag selection mode OFF")
        
        elif event.key in '1234567890' and self.tag_selection_mode:  # Number keys - toggle individual tags
            if event.key == '0':
                index = 9
            else:
                index = int(event.key) - 1
            
            start_index = self.current_tag_page * self.tags_per_page
            actual_index = start_index + index
            
            if 0 <= actual_index < len(self.tag_list):
                tag = self.tag_list[actual_index]
                if tag in self.visible_tags:
                    self.visible_tags.remove(tag)
                    print(f"Tag '{tag}' hidden")
                else:
                    self.visible_tags.add(tag)
                    print(f"Tag '{tag}' shown")
                self.show_current_tag_page()
        
        elif event.key == 'ctrl+left' and self.tag_selection_mode:  # Ctrl+Left - previous page
            max_pages = (len(self.tag_list) - 1) // self.tags_per_page
            self.current_tag_page = max(0, self.current_tag_page - 1)
            print(f"Tag page {self.current_tag_page + 1}/{max_pages + 1}")
            self.show_current_tag_page()
        
        elif event.key == 'ctrl+right' and self.tag_selection_mode:  # Ctrl+Right - next page
            max_pages = (len(self.tag_list) - 1) // self.tags_per_page
            self.current_tag_page = min(max_pages, self.current_tag_page + 1)
            print(f"Tag page {self.current_tag_page + 1}/{max_pages + 1}")
            self.show_current_tag_page()
        
        elif event.key == 'a':  # A key - show all tags
            self.visible_tags = set(self.action_colors.keys())
            print("All tags shown")
        
        elif event.key == 'n':  # N key - hide all tags
            self.visible_tags = set()
            print("All tags hidden")
        
        elif event.key == 'escape':  # Escape - quit
            plt.close(self.fig)
        
        # Update control instructions and tag display
        self.update_control_text()
        self.update_tag_text()
    
    def show_current_tag_page(self):
        """Show the current page of tags in tag selection mode."""
        start_index = self.current_tag_page * self.tags_per_page
        end_index = min(start_index + self.tags_per_page, len(self.tag_list))
        max_pages = (len(self.tag_list) - 1) // self.tags_per_page + 1
        
        print(f"\nTag Selection Page {self.current_tag_page + 1}/{max_pages}:")
        for i in range(start_index, end_index):
            key = '0' if (i - start_index) == 9 else str((i - start_index) + 1)
            tag = self.tag_list[i]
            status = "✓" if tag in self.visible_tags else "✗"
            print(f"  {key}: {status} {tag}")
        
        if max_pages > 1:
            print("Use Ctrl+Left/Right to change pages")
    
    def update_control_text(self):
        """Update the control instructions text display."""
        direction = "Reverse" if self.is_reverse else "Forward"
        status = "Playing" if self.is_playing else "Paused"
        tag_mode = "ON" if self.tag_selection_mode else "OFF"
        controls = (f"Controls: Space=Play/Pause | ←→=Direction | ↑↓=Speed | R=Reset | T=Tag Selection | A=All Tags | N=No Tags | ESC=Quit\n"
                   f"Status: {status} | Direction: {direction} | Speed: {self.speed_multiplier:.1f}x | Tag Mode: {tag_mode}")
        
        if self.control_text:
            self.control_text.set_text(controls)
    
    def update_tag_text(self):
        """Update the tag selection display."""
        if self.tag_selection_mode:
            start_index = self.current_tag_page * self.tags_per_page
            end_index = min(start_index + self.tags_per_page, len(self.tag_list))
            max_pages = (len(self.tag_list) - 1) // self.tags_per_page + 1
            
            tag_info = f"Tag Selection Page {self.current_tag_page + 1}/{max_pages} (1-9,0 to toggle):\n"
            for i in range(start_index, end_index):
                key = '0' if (i - start_index) == 9 else str((i - start_index) + 1)
                tag = self.tag_list[i]
                status = "✓" if tag in self.visible_tags else "✗"
                tag_info += f"{key}:{status}{tag} "
                if ((i - start_index) + 1) % 3 == 0:  # New line every 3 tags for better formatting
                    tag_info += "\n"
            
            if max_pages > 1:
                tag_info += "\nCtrl+←/→: Change page"
        else:
            visible_count = len(self.visible_tags)
            total_count = len(self.action_colors)
            tag_info = f"Visible Tags: {visible_count}/{total_count}"
        
        if self.tag_text:
            self.tag_text.set_text(tag_info)
    
    def get_next_frame_index(self):
        """
        Get the next frame index based on playback direction and speed.
        
        Returns:
            Next frame index
        """
        if not self.is_playing:
            return self.current_frame_index
        
        step = int(self.speed_multiplier)
        if step < 1:
            # When speed is very slow, we keep step=1 but adjust interval timing instead
            step = 1
        
        if self.is_reverse:
            self.current_frame_index = max(0, self.current_frame_index - step)
        else:
            self.current_frame_index = min(len(self.frames_list) - 1, self.current_frame_index + step)
        
        return self.current_frame_index
    
    def get_current_interval(self):
        """
        Calculate the current interval for animation based on speed multiplier.
        When speed_multiplier < 1, we increase the interval to slow down playback.
        
        Returns:
            Current interval in milliseconds
        """
        if self.speed_multiplier < 1:
            # For slow speeds, increase interval proportionally
            return int(self.base_interval / self.speed_multiplier)
        else:
            # For normal and fast speeds, use base interval
            return self.base_interval
    
    def restart_animation(self):
        """
        Restart the animation with updated interval based on current speed.
        This is needed when speed_multiplier changes to apply new timing.
        """
        if self.animation_obj and hasattr(self, 'frames_list'):
            # Stop current animation
            self.animation_obj.event_source.stop()
            
            # Create new animation with updated interval
            frame_indices = range(len(self.frames_list))
            current_interval = self.get_current_interval()
            
            self.animation_obj = animation.FuncAnimation(
                self.fig, self.animate_frame, frames=frame_indices,
                interval=current_interval, blit=True, repeat=True
            )
            
            # Start the new animation
            self.animation_obj.event_source.start()
    
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
        
        # Initialize control instructions label
        self.control_text = self.ax.text(0.02, 0.02, '', transform=self.ax.transAxes,
                                        fontsize=10,
                                        bbox=dict(boxstyle='round,pad=0.5', 
                                                 facecolor='lightgreen', 
                                                 alpha=0.8,
                                                 edgecolor='black'),
                                        verticalalignment='bottom',
                                        zorder=10)
        
        # Initialize tag selection label
        self.tag_text = self.ax.text(0.98, 0.02, '', transform=self.ax.transAxes,
                                    fontsize=9,
                                    bbox=dict(boxstyle='round,pad=0.5', 
                                             facecolor='lightcyan', 
                                             alpha=0.8,
                                             edgecolor='black'),
                                    verticalalignment='bottom',
                                    horizontalalignment='right',
                                    zorder=10)
        
        # Set up keyboard event handling
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
        # Update initial control text and tag text
        self.update_control_text()
        self.update_tag_text()
        
        # Create legend for action types
        legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color, label=action) 
                          for action, color in self.action_colors.items()]
        self.ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
        
        plt.tight_layout()
        
    def animate_frame(self, frame_index: int):
        """
        Animate a single frame with playback control support.
        
        Args:
            frame_index: Current frame index in the frames list
        """
        # Get the actual frame number based on current playback state
        if hasattr(self, 'frames_list') and self.frames_list:
            # Get next frame index based on playback controls
            next_index = self.get_next_frame_index()
            if next_index < len(self.frames_list):
                frame_num = self.frames_list[next_index]
            else:
                frame_num = self.frames_list[-1]
        else:
            frame_num = frame_index
        
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
            action_tags = list(row['action_tags'])
            speed_tags = list(row['speed_tags'])
            
            # Get color based on action and visibility filter
            color, should_display = self.get_color_for_action(action_tags)
            
            # Skip this track if it should not be displayed
            if not should_display:
                continue
            
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
            
            # Create label text only if there are visible tags
            action_str, speed_str, should_show_text = self.parse_tags(action_tags, speed_tags)
            
            if should_show_text and action_str:  # Only show text if there are visible action tags
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
        
        return (list(self.track_patches.values()) + 
                list(self.track_texts.values()) + 
                [self.frame_text, self.control_text, self.tag_text])
    
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
        self.frames_list = list(range(0, max_frame + 1, 3))  # Skip every 3rd frame for 3x speed
        
        print(f"Creating animation for frames {min_frame} to {max_frame} (every 3rd frame)")
        print("Keyboard Controls:")
        print("  Space: Play/Pause")
        print("  Left Arrow: Reverse playback")
        print("  Right Arrow: Forward playback") 
        print("  Up Arrow: Speed up")
        print("  Down Arrow: Slow down")
        print("  R: Reset to normal speed and forward")
        print("  T: Toggle tag selection mode")
        print("  1-9,0: Toggle individual tags (in tag selection mode)")
        print("  Ctrl+Left/Right: Change tag pages (in tag selection mode)")
        print("  A: Show all tags")
        print("  N: Hide all tags")
        print("  Escape: Quit")
        
        # Create animation with playback control
        frame_indices = range(len(self.frames_list))
        current_interval = self.get_current_interval()
        self.animation_obj = animation.FuncAnimation(
            self.fig, self.animate_frame, frames=frame_indices,
            interval=current_interval, blit=True, repeat=True
        )
        
        if save_animation:
            print(f"Saving animation to {output_file}...")
            Writer = animation.writers['ffmpeg']
            writer = Writer(fps=10, metadata=dict(artist='TrajectoryVisualizer'), bitrate=1800)
            self.animation_obj.save(output_file, writer=writer)
            print("Animation saved!")
        
        # Make sure the plot window has focus for keyboard events
        self.fig.canvas.manager.show()
        plt.show()
        
        return self.animation_obj

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
