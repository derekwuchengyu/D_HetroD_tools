#!/usr/bin/env python3
"""
測試 windows_slide_tagging.py 的 Python 代碼
輸入：軌跡數據 (trajectory)
輸出：標籤 (tags)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Union, Tuple
import sys
import os

# 添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# 導入我們要測試的模塊
from windows_slide_tagging import (
    analyze_trajectory_frame_by_frame,
    calculate_action_tags,
    calculate_speed_tags,
    trajectory_tag_match,
    get_zone,
    ZONE_POLYGON,
    ZonePolygon, 
    CacheManager
)

def main():
    """主函數"""
    print("Windows Slide Tagging 測試程序")
    print("=" * 60)
    
    csv_path = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv"

    # 讀 CSV
    track_id = 8
    df = pd.read_csv(csv_path)
    df = df[df['trackId'] == track_id]  # 只測試 trackId 為 35 的數據
    tag = "路口直行"  # 可改成 "左轉" 或 "右轉"
    

    try:
        group_sorted = df.sort_values("frame")

        print(f"Processing track {track_id} with {len(group_sorted)} frames...")
        
        for tag in ["路口直行", "左轉", "右轉"]:
            if tag not in ["左轉"]:
                continue
            print(f"  目標標籤: {tag}")
            # 進行幀級別分析，整合trajectory_tag_match結果
            frame_results = analyze_trajectory_frame_by_frame(group_sorted, track_id, target_tag=tag)

            # print(frame_results)
            if frame_results:
                # print(f"  目標標籤 '{target_tag}' - 生成了 {len(frame_results)} 個標籤")
                    
                # 統計標籤類型
                action_tag_counts = {}
                speed_tag_counts = {}
                    
                for result in frame_results:
                    for tag in result['action_tags']:
                        action_tag_counts[tag] = action_tag_counts.get(tag, 0) + 1
                    for tag in result['speed_tags']:
                        speed_tag_counts[tag] = speed_tag_counts.get(tag, 0) + 1
                    
            print(f"    動作標籤統計: {action_tag_counts}")
            print(f"    速度標籤統計: {speed_tag_counts}")
        else:
            pass
            # print(f"  目標標籤 '{target_tag}' - 沒有生成標籤")

        # print(f"\n示例輸出:")
        # print(f"生成了 {len(tags)} 個標籤")
        
        # if tags:
        #     # 保存結果到文件
        #     save_results_to_file(tags)
            
        #     # 顯示部分結果
        #     print("\n部分結果展示:")
        #     for i, tag in enumerate(tags[:3]):
        #         print(f"  {tag}")
        
    except Exception as e:
        print(f"測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
