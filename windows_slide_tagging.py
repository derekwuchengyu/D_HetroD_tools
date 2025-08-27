import json
import os
from turtle import st
import pandas as pd
import numpy as np
from pathlib import Path
from collections import OrderedDict
from functools import wraps
from cfg import ZONE_MAPPING

from shapely.geometry import Polygon as ShapelyPolygon,  MultiPoint, Polygon
from shapely.ops import unary_union
from shapely.geometry.polygon import orient
from shapely.validation import make_valid

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib import font_manager

class CacheManager:
    def __init__(self):
        self.caches = {}
        self.stats = {}
        self.num_processes = max(int(0.9 * os.cpu_count()), 1)
        self.semantic_lane_cache = None
        self.road_side_cache = None

    def set_num_processes(self, num):
        self.num_processes = max(min(os.cpu_count() - 1, num), 1)

    def make_hashable(self, obj):
        """將物件轉成可 hash，用於快取 key"""
        if isinstance(obj, (list, tuple, set)):
            return tuple(self.make_hashable(x) for x in obj)
        elif isinstance(obj, dict):
            return tuple(sorted((k, self.make_hashable(v)) for k, v in obj.items()))
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, np.ndarray):
            return tuple(obj.flatten())
        elif hasattr(obj, "__class__") and not isinstance(obj, (str, int, float)):
            # 對 class 物件，無參數初始化的 class 可以用類名做 key
            return obj.__class__.__name__
        else:
            return obj

    def create_class_cache(self, name, maxsize=512):
        """適合無參數 class 的單例快取"""
        if name not in self.caches:
            self.caches[name] = OrderedDict()
            self.stats[name] = {'hits':0, 'misses':0}

        def decorator(cls):
            def wrapper():
                key = cls.__name__
                cache = self.caches[name]
                stats = self.stats[name]

                if key in cache:
                    stats['hits'] += 1
                    # print(f"[Cache hit] {name}")
                    return cache[key]

                instance = cls()
                cache[key] = instance
                stats['misses'] += 1
                print(f"[Cache miss] {name}")

                if len(cache) > maxsize:
                    cache.popitem(last=False)
                return instance

            return wrapper

        return decorator

    def clear_all(self):
        for cache in self.caches.values():
            cache.clear()
    
    def info(self):
        return {name: len(cache) for name, cache in self.caches.items()}
    
    def get_stats(self, name=None):
        if name:
            stats = self.stats[name]
            total = stats['hits'] + stats['misses']
            hit_rate = stats['hits'] / total if total > 0 else 0
            return {
                'name': name,
                'hits': stats['hits'],
                'misses': stats['misses'],
                'hit_rate': f"{hit_rate:.2%}",
                'cache_size': len(self.caches[name])
            }
        return {name: self.get_stats(name) for name in self.stats}

cache_manager = CacheManager()

@cache_manager.create_class_cache('ZonePolygon')
class ZonePolygon:
    def __init__(self):
        """
        ZONE_POLYGON : {'zone_name': [[Polygon1 points list],[Polygon2 points list], ...], ...}
        """
        self.zone_name = None
        self.coordinates = []
        self.ZONE_MAPPING = ZONE_MAPPING
        self.ZONE_MAPPING_REV = self.reverse_mapping()
        self.ZONE_POLYGON = self.get_zone_polygon()
        
        
    def reverse_mapping(self):
        """
        反轉 ZONE_MAPPING，將 lane_id 映射到 zone_name
        """
        reversed_mapping = {}
        for lane_id, zone_name in self.ZONE_MAPPING.items():
            if zone_name not in reversed_mapping:
                reversed_mapping[zone_name] = []
            reversed_mapping[zone_name].append(lane_id)
        return reversed_mapping
    
    def get_zone_polygon(self):
        """
        輸入 zone_name，輸出該 zone 的 polygon (list of (x, y) tuples)
        會把該 zone 內所有 lane_segments 的右邊界 & 左邊界合併成一個封閉區域
        """
        recording_meta_file = '/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_recordingMeta.csv'
        map_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/maps/lanelets/18_location/log_map_archive_location18.json"
        with open(map_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        lane_segments = data.get("lane_segments", {})
        drivable_areas = data.get("drivable_areas", {})
        
        df = pd.read_csv(recording_meta_file)
        xUtmOrigin = df['xUtmOrigin'].values[0]
        yUtmOrigin = df['yUtmOrigin'].values[0]
        # orthoPxToMeter = df['orthoPxToMeter'].values[0]

        self.ZONE_POLYGON = {}

        for zone, lane_ids in self.ZONE_MAPPING_REV.items():
            self.ZONE_POLYGON[zone] = []

            lane_polygons = []

            for lane_id in lane_ids:
                if zone.startswith("INT_"):
                    intersection_id = lane_id
                    intersection = drivable_areas.get(str(intersection_id)) or drivable_areas.get(int(intersection_id))
                    if not intersection:
                        continue
                    
                    coords = [(pt["x"]-xUtmOrigin, pt["y"]-yUtmOrigin) for pt in intersection["area_boundary"]]
                     
                else:
                    lane = lane_segments.get(str(lane_id)) or lane_segments.get(int(lane_id))
                    if not lane:
                        continue
                    
                    # 建立右/左邊界座標
                    right_boundary = [(pt["x"]-xUtmOrigin, pt["y"]-yUtmOrigin) for pt in lane["right_lane_boundary"]]
                    left_boundary = [(pt["x"]-xUtmOrigin, pt["y"]-yUtmOrigin) for pt in lane["left_lane_boundary"]]

                    # 合併成初步 polygon（右邊界 + 左邊界反序）
                    coords = right_boundary + left_boundary[::-1]

                try:
                    poly = ShapelyPolygon(coords)

                    # 修正自交
                    if not poly.is_valid:
                        hull = MultiPoint(coords).convex_hull  # compute convex hull
                        coords = list(hull.exterior.coords)[:-1]  # exclude repeated first point
                        poly = ShapelyPolygon(coords)
                        

                    lane_polygons.append(poly)
                    # self.ZONE_POLYGON[lane_id].append(coords)
                except Exception as e:
                    print(f"Failed to create polygon for lane {lane_id}: {e}")
                    continue

            if lane_polygons:
                # 將同一 zone 的多個 lane polygon 合併成單個 polygon（多部分 Polygon 可保持 list）
                merged = unary_union(lane_polygons)
                if merged.geom_type == "Polygon":
                    self.ZONE_POLYGON[zone].append(list(merged.exterior.coords))
                elif merged.geom_type == "MultiPolygon":
                    for sub_poly in merged.geoms:
                        self.ZONE_POLYGON[zone].append(list(sub_poly.exterior.coords))

        return self.ZONE_POLYGON



def is_point_in_polygon(point, polygon):
    """
    Determine if a point is inside a polygon using the ray-casting algorithm.

    :param point: (x, y) coordinates of the point.
    :param polygon: List of (x, y) coordinates defining the polygon vertices.
    :return: True if the point is inside the polygon, False otherwise.
    """
    x, y = point
    n = len(polygon)
    inside = False

    px1, py1 = polygon[0]
    for i in range(1, n + 1):
        px2, py2 = polygon[i % n]
        if y > min(py1, py2):
            if y <= max(py1, py2):
                if x <= max(px1, px2):
                    if py1 != py2:
                        xinters = (y - py1) * (px2 - px1) / (py2 - py1) + px1
                    if px1 == px2 or x <= xinters:
                        inside = not inside
        px1, py1 = px2, py2

    return inside

ZONE_POLYGON = ZonePolygon().ZONE_POLYGON
# print(ZONE_POLYGON)
def get_zone(point):
    """
    獲取點所在的區域
    :param point: (x, y) 座標點
    """
    for zone_name, polygons in ZONE_POLYGON.items():
        for polygon in polygons:
            if is_point_in_polygon(point, polygon):
                return zone_name
    return None

def get_distance_to_intersection(point, max_distance=50.0):
    """
    計算點到最近路口的距離
    :param point: (x, y) 座標點
    :param max_distance: 最大檢查距離(米)
    :return: 到最近路口的距離，如果沒有路口在範圍內則返回None
    """
    min_distance = float('inf')
    found_intersection = False
    
    # 檢查所有路口區域
    for zone_name, polygons in ZONE_POLYGON.items():
        if zone_name.startswith("INT_"):
            for polygon in polygons:
                # 計算點到多邊形的最短距離
                px, py = point
                min_poly_distance = float('inf')
                
                # 計算到多邊形每條邊的距離
                for i in range(len(polygon)):
                    x1, y1 = polygon[i]
                    x2, y2 = polygon[(i + 1) % len(polygon)]
                    
                    # 計算點到線段的距離
                    A = px - x1
                    B = py - y1
                    C = x2 - x1
                    D = y2 - y1
                    
                    dot = A * C + B * D
                    len_sq = C * C + D * D
                    
                    if len_sq == 0:
                        distance = np.sqrt(A * A + B * B)
                    else:
                        param = dot / len_sq
                        if param < 0:
                            xx, yy = x1, y1
                        elif param > 1:
                            xx, yy = x2, y2
                        else:
                            xx = x1 + param * C
                            yy = y1 + param * D
                        
                        distance = np.sqrt((px - xx) ** 2 + (py - yy) ** 2)
                    
                    min_poly_distance = min(min_poly_distance, distance)
                
                # 如果點在多邊形內，距離為0
                if is_point_in_polygon(point, polygon):
                    min_poly_distance = 0
                
                min_distance = min(min_distance, min_poly_distance)
                found_intersection = True
    
    if found_intersection and min_distance <= max_distance:
        return min_distance
    return None 

def check_turn(start_zone, end_zone, tag):
    """根據起點與終點的 zone 判斷是否符合轉向"""
    start_road = start_zone.split('_')[0]
    start_lane = start_zone.split('_')[1]
    end_road = end_zone.split('_')[0]
    end_lane = end_zone.split('_')[1]
    
    right_turn = {("RI", "RII"), ("RII", "RIII"), ("RIII", "RIV"), ("RIV", "RI"), ("RV", "RI")}
    left_turn = {("RI", "RIV"), ("RIV", "RIII"), ("RIII", "RII"), ("RII", "RI")}
    straight = {("RI", "RIII"), ("RIII", "RI"), ("RII", "RIV"), ("RIV", "RII")}

    if tag == "右轉":
        return (start_road, end_road) in right_turn
    elif tag == "左轉":
        return (start_road, end_road) in left_turn
    elif tag == "直行":
        return (start_road, end_road) in straight
    return False

def find_first_last_zone(trajectory, min_frames=5):
    """
    找出 trajectory 的第一個穩定 zone 與最後一個穩定 zone
    min_frames: 進入同一 zone 連續幾幀才算穩定
    """
    first_zone = None
    last_zone = None

    prev_zone = None
    count = 0
    stable_zone = None

    zone = get_zone(trajectory[0][-2:])
    # print(trajectory[0][-2:], zone)
    for pt in trajectory:
        point_xy = pt[-2:]  # (x, y)
        zone = get_zone(point_xy)
        # print(point_xy, zone)

        if zone == prev_zone and zone is not None:
            count += 1
        else:
            count = 1
            prev_zone = zone

        # 如果連續 min_frames 幀都在同一 zone
        if count >= min_frames:
            stable_zone = zone
            if first_zone is None:
                first_zone = stable_zone
            last_zone = stable_zone

    return first_zone, last_zone

def visualize_window(window_traj=None, start_zone=None, end_zone=None, tag="", match=True):
    plt.rcParams["font.family"] = 'WenQuanYi Zen Hei' #Droid Sans Fallback
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots()
    ax.set_aspect("equal")

    # 收集所有座標，用來設定合理的 xlim/ylim
    all_x = []
    all_y = []
    for polygons in ZONE_POLYGON.values():
        for poly in polygons:
            if len(poly) >= 3:  # polygon 至少 3 點
                all_x.extend([p[0] for p in poly])
                all_y.extend([p[1] for p in poly])

    if all_x and all_y:
        ax.set_xlim(min(all_x)-5, max(all_x)+5)
        ax.set_ylim(min(all_y)-5, max(all_y)+5)

    labeled_zones = set()

    # 畫出每個 zone
    for zone_name, polygons in ZONE_POLYGON.items():
        for polygon_coords in polygons:
            if len(polygon_coords) < 3:
                continue  # 空或少於3點的 polygon 跳過

            poly_patch = Polygon(
                polygon_coords,
                closed=True,
                fill=True,
                edgecolor="blue",
                linewidth=0.2,
                # label=zone_name if zone_name not in labeled_zones else ""
            )
            ax.add_patch(poly_patch)

            # 標 zone 名稱於 polygon 中心
            poly_x = [p[0] for p in polygon_coords]
            poly_y = [p[1] for p in polygon_coords]
            ax.text(
                sum(poly_x)/len(poly_x),
                sum(poly_y)/len(poly_y),
                zone_name,
                ha="center",
                va="center",
                fontsize=10,
                color="black"
            )
        # labeled_zones.add(zone_name)

    # 畫軌跡
    if window_traj:
        xs = [pt[-2] for pt in window_traj]
        ys = [pt[-1] for pt in window_traj]
        ax.plot(xs, ys, "b-", label="trajectory")

        # 起點
        ax.plot(xs[0], ys[0], "go", markersize=8, label=f"Start: {start_zone}")
        ax.text(xs[0], ys[0], start_zone or "None", color="green", fontsize=8)

        # 終點
        ax.plot(xs[-1], ys[-1], "ro", markersize=8, label=f"End: {end_zone}")
        ax.text(xs[-1], ys[-1], end_zone or "None", color="red", fontsize=8)

    # 標題
    ax.set_title(f"Tag={tag}, Match={match}", fontsize=12, color="black" if match else "gray")

    ax.legend()
    plt.show()

def calculate_speed_tags(velocity, acceleration, lon_velocity, lat_velocity, lon_acceleration, lat_acceleration):
    """計算速度相關標籤"""
    speed_tags = []
    
    # 計算總速度
    total_speed = np.sqrt(velocity[0]**2 + velocity[1]**2)
    total_accel = np.sqrt(acceleration[0]**2 + acceleration[1]**2)
    
    # 速度狀態
    if total_speed < 0.5:  # m/s
        speed_tags.append("stopped")
    elif total_speed < 2.0:
        speed_tags.append("slow")
    elif total_speed < 8.0:
        speed_tags.append("normal")
    else:
        speed_tags.append("fast")
    
    # 加速度狀態
    if lon_acceleration > 1.0:  # m/s²
        speed_tags.append("accelerating")
    elif lon_acceleration < -1.0:
        speed_tags.append("decelerating")
    else:
        speed_tags.append("constant_speed")
    
    return speed_tags

def calculate_action_tags(current_point, previous_points, current_zone, previous_zones, velocity, heading):
    """計算動作相關標籤"""
    action_tags = []
    
    # 基本移動狀態
    total_speed = np.sqrt(velocity[0]**2 + velocity[1]**2)
    if total_speed < 0.5:
        action_tags.append("waiting")
    else:
        action_tags.append("moving")
    
    # 車道變換檢測 - 檢測整個跨越車道過程
    if len(previous_zones) >= 10:  # 需要更多歷史數據來檢測完整過程
        # 檢查更長的歷史軌跡以找到穩定的起始和結束車道
        window_size = min(60, len(previous_zones))  # 檢查最近30幀或所有可用幀
        zone_window = previous_zones[-window_size:] + [current_zone]
        
        # 過濾掉None值並保持順序
        valid_zones_with_idx = [(i, zone) for i, zone in enumerate(zone_window) if zone is not None]
        
        if len(valid_zones_with_idx) >= 10:  # 至少需要10個有效zone
            # 找到穩定的起始車道（連續出現至少3次）
            start_stable_zone = None
            end_stable_zone = None
            
            # 從前往後找穩定的起始車道
            for i in range(len(valid_zones_with_idx) - 2):
                zone = valid_zones_with_idx[i][1]
                # 檢查接下來的幾個zone是否相同
                consecutive_count = 1
                for j in range(i + 1, min(i + 5, len(valid_zones_with_idx))):
                    if valid_zones_with_idx[j][1] == zone:
                        consecutive_count += 1
                    else:
                        break
                
                if consecutive_count >= 3:  # 至少連續3次才算穩定
                    start_stable_zone = zone
                    break
            
            # 從後往前找穩定的結束車道
            for i in range(len(valid_zones_with_idx) - 1, 1, -1):
                zone = valid_zones_with_idx[i][1]
                # 檢查前面的幾個zone是否相同
                consecutive_count = 1
                for j in range(i - 1, max(i - 5, -1), -1):
                    if valid_zones_with_idx[j][1] == zone:
                        consecutive_count += 1
                    else:
                        break
                
                if consecutive_count >= 3:  # 至少連續3次才算穩定
                    end_stable_zone = zone
                    break
            
            # 檢查是否發生了車道變換
            if (start_stable_zone and end_stable_zone and 
                start_stable_zone != end_stable_zone and
                '_' in start_stable_zone and '_' in end_stable_zone):
                
                start_road = start_stable_zone.rsplit('_', 1)[0]
                end_road = end_stable_zone.rsplit('_', 1)[0]
                
                # 同一條路但不同車道才算車道變換
                if start_road == end_road:
                    try:
                        start_lane = int(start_stable_zone.rsplit('_', 1)[1])
                        end_lane = int(end_stable_zone.rsplit('_', 1)[1])
                        
                        if start_lane != end_lane:
                            # 判斷車道變換方向
                            if end_lane > start_lane:
                                action_tags.append("lane_change_right")
                            else:
                                action_tags.append("lane_change_left")
                            
                            # 也添加通用的lane_change標籤
                            action_tags.append("lane_change")
                            
                    except ValueError:
                        # 如果車道編號不是數字，跳過
                        pass
    
    # 轉向檢測（基於heading變化）
    if len(previous_points) >= 100:
        # 計算最近幾幀的heading變化
        prev_headings = [pt[2] if len(pt) > 2 else heading for pt in previous_points[-100:]]
        
        # 處理角度環形特性的heading變化計算
        heading_changes = []
        for i in range(1, len(prev_headings)):
            diff = prev_headings[i] - prev_headings[i-1]
            # 處理角度跨越0/360度的情況
            if diff > 180:
                diff -= 360
            elif diff < -180:
                diff += 360
            heading_changes.append(diff)
        
        sum_heading_change = np.sum(heading_changes)
        
        # 檢查是否在路口區域或靠近路口（基於距離）
        is_at_intersection = current_zone is not None and current_zone.startswith("INT_")
        
        # 計算到路口的距離，如果在30米內則認為靠近路口
        distance_to_intersection = get_distance_to_intersection(current_point[:2], max_distance=3.0)
        is_near_intersection = distance_to_intersection is not None
        
        # 綜合判斷：當前在路口或靠近路口
        near_intersection = is_at_intersection or is_near_intersection
        # print(is_at_intersection, distance_to_intersection)
        
        # print(f"Current zone: {current_zone}, Distance to intersection: {distance_to_intersection}, Near intersection: {near_intersection}")
        
        if near_intersection:
            if sum_heading_change > 7:  # 度數
                action_tags.append("turning_left")
            elif sum_heading_change < -7:
                action_tags.append("turning_right")
    
    return action_tags

def tag_post_process(action_tags):
    """
    標籤後處理函數，用於過濾不一致的轉向標籤
    
    規則：
    - 如果同時出現 turning_left/turning_right 和 直行，則移除轉向標籤
    - 如果同時出現 turning_left 和 turning_right，則移除所有轉向標籤
    - 如果同時出現 左轉/右轉 和 直行，則移除中文轉向標籤
    
    :param action_tags: 原始標籤列表
    :return: 處理後的標籤列表
    """
    if not action_tags:
        return action_tags
    
    # 創建標籤集合用於快速查找
    tag_set = set(action_tags)
    
    # 定義轉向相關標籤
    turning_tags = {'turning_left', 'turning_right'}
    chinese_turn_tags = {'左轉', '右轉'}
    straight_tags = {'直行'}
    
    # 檢查是否有衝突的標籤組合
    has_turning = bool(turning_tags & tag_set)
    has_chinese_turn = bool(chinese_turn_tags & tag_set)
    has_straight = bool(straight_tags & tag_set)
    has_both_turns = 'turning_left' in tag_set and 'turning_right' in tag_set
    has_both_chinese_turns = '左轉' in tag_set and '右轉' in tag_set
    
    # 處理邏輯
    filtered_tags = []
    
    for tag in action_tags:
        should_keep = True
        
        # 規則1: 如果同時有英文轉向和直行，移除英文轉向標籤
        if tag in turning_tags and has_straight:
            should_keep = False
            
        # 規則2: 如果同時有中文轉向和直行，移除中文轉向標籤  
        elif tag in chinese_turn_tags and has_straight:
            should_keep = False
            
        # 規則3: 如果同時有左轉和右轉（英文），移除所有轉向標籤
        elif tag in turning_tags and has_both_turns:
            should_keep = False
            
        # 規則4: 如果同時有左轉和右轉（中文），移除所有中文轉向標籤
        elif tag in chinese_turn_tags and has_both_chinese_turns:
            should_keep = False
        
        if should_keep:
            filtered_tags.append(tag)
    
    return filtered_tags

def analyze_trajectory_frame_by_frame(track_data, track_id, target_tag="右轉"):
    """分析軌跡的每一幀，產生action_tags和speed_tags，並整合trajectory_tag_match結果"""
    results = []
    previous_points = []
    previous_zones = []
    
    # 取出完整軌跡用於trajectory_tag_match分析
    trajectory = list(zip(track_data["xCenter"], track_data["yCenter"]))

    for window_size in [330, 450]:  # 嘗試不同窗口大小
        

        # 執行trajectory_tag_match分析獲取窗口結果
        window_size = min(len(trajectory), window_size)
        window_results = trajectory_tag_match(trajectory, target_tag, track_id, 
                                            window_size=window_size, slide_step=30, 
                                            min_frames=6, visualize=False)

        # 建立frame到window標籤的映射
        frame_to_window_tags = {}
        for window in window_results:
            start_frame = window['start_frame']
            end_frame = window['end_frame']
            turn_tag = window['turn_tag']
            for frame_idx in range(start_frame, end_frame + 1):
                if frame_idx not in frame_to_window_tags:
                    frame_to_window_tags[frame_idx] = []
                if turn_tag:
                    frame_to_window_tags[frame_idx].append(turn_tag)

        if window_results is not None or len(trajectory) < window_size:
            break
                    
                    
    
    for frame_idx, (idx, row) in enumerate(track_data.iterrows()):
        frame = row['frame']
        x, y = row['xCenter'], row['yCenter']
        heading = row['heading']
        velocity = (row['xVelocity'], row['yVelocity'])
        acceleration = (row['xAcceleration'], row['yAcceleration'])
        lon_velocity = row['lonVelocity']
        lat_velocity = row['latVelocity']
        lon_acceleration = row['lonAcceleration']
        lat_acceleration = row['latAcceleration']
        
        current_point = (x, y, heading)
        current_zone = get_zone((x, y))
        
        # 計算基本動作標籤（不再需要未來zone信息）
        action_tags = calculate_action_tags(current_point, previous_points, current_zone, previous_zones, velocity, heading)
        
        # 添加trajectory_tag_match的結果到action_tags中
        if frame_idx in frame_to_window_tags:
            window_tags = frame_to_window_tags[frame_idx]
            action_tags.extend(window_tags)
        
        # 去重action_tags，保持原有順序
        action_tags = list(dict.fromkeys(action_tags))
        
        # 應用標籤後處理，過濾不一致的轉向標籤
        action_tags = tag_post_process(action_tags)
        
        speed_tags = calculate_speed_tags(velocity, acceleration, lon_velocity, lat_velocity, lon_acceleration, lat_acceleration)
        
        results.append({
            'trackId': track_id,
            'frame': frame,
            'action_tags': action_tags,
            'speed_tags': speed_tags
        })
        
        # 更新歷史記錄
        previous_points.append(current_point)
        previous_zones.append(current_zone)
        
        # 保持歷史記錄在合理範圍內
        if len(previous_points) > 500:
            previous_points.pop(0)
        if len(previous_zones) > 500:
            previous_zones.pop(0)
            
    # print(results);exit()
    # print(previous_zones)
    
    
    return results

def trajectory_tag_match(trajectory, tag, track_id, window_size=200, slide_step=30, min_frames=5, visualize=False):
    """
    分析軌跡的滑動窗口，產生每個窗口的標籤
    返回所有窗口的結果列表
    """
    n = len(trajectory)
    window_results = []
    
    for start_idx in range(0, n - window_size + 1, slide_step):
        end_idx = start_idx + window_size
        window_traj = trajectory[start_idx:end_idx]

        start_zone, end_zone = find_first_last_zone(window_traj, min_frames=min_frames)
        # print(f"Track {track_id} Window {start_idx}-{end_idx}: Start Zone: {start_zone}, End Zone: {end_zone}")

        match = False
        turn_tag = None
        if start_zone and end_zone:
            # 檢查各種轉向可能
            if check_turn(start_zone, end_zone, "右轉"):
                turn_tag = "右轉"
                match = (tag == "右轉")
            elif check_turn(start_zone, end_zone, "左轉"):
                turn_tag = "左轉"
                match = (tag == "左轉")
            elif check_turn(start_zone, end_zone, "直行"):
                turn_tag = "直行"
                match = (tag == "直行")
            else:
                continue
                turn_tag = "其他"
                match = False

        # 記錄窗口結果
        window_result = {
            'trackId': track_id,
            'start_frame': start_idx,
            'end_frame': end_idx - 1,
            'start_zone': start_zone,
            'end_zone': end_zone,
            'turn_tag': turn_tag,
            'match_target': match,
            'target_tag': tag
        }
        window_results.append(window_result)

        if visualize:
            visualize_window(window_traj, start_zone, end_zone, turn_tag or "None", match)

    return window_results





# ===== 測試範例 =====
if __name__ == "__main__":

    import pandas as pd

    # 假設你已經有 trajectory_tag_match 函式
    # from your_module import trajectory_tag_match

    csv_path = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/dataset_tools_612db6a0/data/00_tracks.csv"

    # 讀 CSV
    df = pd.read_csv(csv_path)
    # df = df.head(1000000)  # 測試時只取前10000行

    # 存儲所有幀級別的結果
    all_frame_results = []
    
    # 依 trackId 分組
    tag = "右轉"  # 可改成 "左轉" 或 "直行"

    for track_id, group in df.groupby("trackId"):
        # print(track_id)
        # 限制處理數量以便測試
        # if track_id != 25:  # 只處理前6個tracks作為示例
        #     continue
        
        # 按 frame 排序
        group_sorted = group.sort_values("frame")
        
        print(f"Processing track {track_id} with {len(group_sorted)} frames...")
        
        # 進行幀級別分析，整合trajectory_tag_match結果
        frame_results = analyze_trajectory_frame_by_frame(group_sorted, track_id, target_tag=tag)
        all_frame_results.extend(frame_results)

    # 將幀級別結果轉換為DataFrame並保存
    tags_df = pd.DataFrame(all_frame_results)
    
    # 將標籤列表轉換為字符串格式
    tags_df['action_tags'] = tags_df['action_tags'].apply(lambda x: str(x))
    tags_df['speed_tags'] = tags_df['speed_tags'].apply(lambda x: str(x))
    
    # 保存為統一的CSV文件
    output_path = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/tags.csv"
    tags_df.to_csv(output_path, index=False)
    
    print(f"Results saved to {output_path}")
    
    # 顯示一些統計信息
    print(f"Total frames processed: {len(tags_df)}")
    print(f"Tracks processed: {tags_df['trackId'].nunique()}")
    
    # # 顯示前幾行結果
    # print("\nFirst 10 rows of results:")
    # print(tags_df.head(10))
        
        
        

