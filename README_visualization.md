# Trajectory Visualization with Tags

This Python script visualizes moving vehicle trajectories with behavioral tags overlay. It displays animated bounding boxes showing vehicle positions over time with their corresponding action and speed tags.

## Features

- **Animated visualization**: Shows vehicles moving over time
- **Bounding boxes**: Oriented rectangles representing vehicle dimensions and heading
- **Color-coded actions**: Different colors for different behavioral states
- **Tag display**: Shows action tags (moving, waiting, etc.) and speed tags above each vehicle
- **Efficient data handling**: Processes large trajectory files in chunks
- **Animation export**: Can save animations as MP4 files

## Requirements

```bash
pip install pandas numpy matplotlib
```

For saving animations as MP4:
```bash
pip install ffmpeg-python
```

## Usage

### Basic Usage

```bash
python visualize_moving_tags.py --tags tags.csv --trajectory your_trajectory.csv
```

### Command Line Options

- `--tags`: Path to tags CSV file (default: tags.csv)
- `--trajectory`: Path to trajectory CSV file (default: trajectory.csv)
- `--save`: Save animation as MP4 file
- `--output`: Output filename for saved animation (default: trajectory_animation.mp4)
- `--create-sample`: Create sample trajectory data for testing

### Examples

1. **Basic visualization with existing data:**
   ```bash
   python visualize_moving_tags.py --tags tags.csv --trajectory my_trajectory.csv
   ```

2. **Create sample data and visualize:**
   ```bash
   python visualize_moving_tags.py --create-sample --trajectory sample_trajectory.csv
   python visualize_moving_tags.py --tags tags.csv --trajectory sample_trajectory.csv
   ```

3. **Save animation to MP4:**
   ```bash
   python visualize_moving_tags.py --save --output my_animation.mp4
   ```

4. **Run the example script:**
   ```bash
   python run_visualization_example.py
   ```

## Data Format

### Tags CSV Format
The tags.csv file should contain:
- `trackId`: Unique identifier for each track
- `frame`: Frame number
- `action_tags`: List of action tags (e.g., ['moving'], ['waiting'])
- `speed_tags`: List of speed tags (e.g., ['fast', 'constant_speed'])

### Trajectory CSV Format
The trajectory CSV file should contain:
- `recordingId`: Recording session identifier
- `trackId`: Unique identifier for each track (must match tags)
- `frame`: Frame number
- `trackLifetime`: Lifetime of the track
- `xCenter`, `yCenter`: Center coordinates of the vehicle
- `heading`: Vehicle heading in degrees
- `width`, `length`: Vehicle dimensions
- `xVelocity`, `yVelocity`: Velocity components
- `xAcceleration`, `yAcceleration`: Acceleration components
- `lonVelocity`, `latVelocity`: Longitudinal and lateral velocities
- `lonAcceleration`, `latAcceleration`: Longitudinal and lateral accelerations

## Color Coding

- **Blue**: Moving vehicles
- **Red**: Waiting vehicles
- **Green**: Turning vehicles
- **Orange**: Accelerating vehicles
- **Purple**: Decelerating vehicles
- **Gray**: Stopped vehicles
- **Black**: Unknown action (default)

## Performance Tips

- The script automatically filters trajectory data to only include tracks that have tags
- Large trajectory files are processed in chunks to manage memory usage
- Animation frame rate and quality can be adjusted in the code

## Troubleshooting

1. **"No matching trajectory data found"**: Ensure trackId values in both files match
2. **Memory issues with large files**: Reduce chunk_size in the load_data() method
3. **Animation too fast/slow**: Adjust the interval parameter in FuncAnimation
4. **Missing ffmpeg**: Install ffmpeg for MP4 export functionality

## Customization

You can customize the visualization by modifying:
- `action_colors` dictionary for different color schemes
- Animation speed by changing the `interval` parameter
- Text positioning and formatting
- Bounding box transparency (`alpha` parameter)
- Plot dimensions and styling

## Example Output

The visualization shows:
- Moving bounding boxes representing vehicles
- Text labels with track ID and tags
- Color-coded vehicles based on their primary action
- Time-synchronized animation of vehicle behavior

Each vehicle displays:
```
ID: 0
moving
fast, constant_speed
```

This provides immediate visual feedback about vehicle behavior patterns in your traffic scenarios.
