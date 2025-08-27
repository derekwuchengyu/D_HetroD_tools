import pandas as pd
import uuid
import math

# ===== CONFIG =====
FRAME_INTERVAL_NS = int(1e9 / 30)  # e.g., 10 Hz recording
DEFAULT_HEIGHT_M = 1.5
DEFAULT_CATEGORY = "VEHICLE"  # change if needed
DEFAULT_NUM_INTERIOR_PTS = 0

# Heading (degrees) to quaternion (z-rotation only)
def heading_to_quaternion(heading_deg):
    yaw = math.radians(heading_deg)
    qw = math.cos(yaw / 2.0)
    qx = 0.0
    qy = 0.0
    qz = math.sin(yaw / 2.0)
    return qw, qx, qy, qz

def convert_track_to_feather(input_csv, output_feather):
    df = pd.read_csv(input_csv)
    df = df.head(10000)

    # Generate a persistent UUID per trackId
    track_id_to_uuid = {tid: str(uuid.uuid4()) for tid in df['trackId'].unique()}

    output_rows = []
    for _, row in df.iterrows():
        qw, qx, qy, qz = heading_to_quaternion(row['heading'])
        output_rows.append({
            "track_uuid": track_id_to_uuid[row['trackId']],
            "timestamp_ns": int(row['frame']) * FRAME_INTERVAL_NS,
            "category": DEFAULT_CATEGORY,
            "length_m": float(row['length']),
            "width_m": float(row['width']),
            "height_m": DEFAULT_HEIGHT_M,
            "qw": qw,
            "qx": qx,
            "qy": qy,
            "qz": qz,
            "tx_m": float(row['xCenter']),
            "ty_m": float(row['yCenter']),
            "tz_m": 0.0,
            "num_interior_pts": DEFAULT_NUM_INTERIOR_PTS
        })

    out_df = pd.DataFrame(output_rows)
    out_df.to_feather(output_feather)
    print(f"Saved to {output_feather}")

if __name__ == "__main__":
    convert_track_to_feather("/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv", "/home/hcis-s19/Documents/ChengYu/RefAV/output/sm_dataset/val/0a18-hetrod/sm_annotations.feather")
