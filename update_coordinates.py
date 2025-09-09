#!/usr/bin/env python3
import json
import xml.etree.ElementTree as ET
import utm

def update_self_defined_area_coordinates():
    osm_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/maps/lanelets/18_location/location18.osm"
    json_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/maps/lanelets/18_location/log_map_archive_location18.json"
    
    # 讀取 OSM 檔案
    tree = ET.parse(osm_file)
    root = tree.getroot()
    
    # 節點
    nodes = {}
    for node in root.findall("node"):
        nid = int(node.attrib["id"])
        lat = float(node.attrib["lat"])
        lon = float(node.attrib["lon"])
        if nid != -25970:
            continue
        # 經緯度轉 UTM
        easting, northing, zone_num, zone_letter = utm.from_latlon(lat, lon)
        nodes[nid] = {
            'x': easting,
            'y': northing,
            'lat': lat,
            'lon': lon,
            'zone': f"{zone_num}{zone_letter}"
        }
    
    print(f"讀取了 {len(nodes)} 個節點")
    print(nodes)
    # exit()

    # 讀取 JSON 檔案
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 更新 self_defined_area 的座標
    if 'self_defined_area' in data:
        for area_id, area_data in data['self_defined_area'].items():
            print(f"\n處理區域 {area_id}:")
            if 'area_boundary' in area_data:
                for i, point in enumerate(area_data['area_boundary']):
                    if 'node' in point:
                        node_id = point['node']
                        if node_id in nodes:
                            old_x = point.get('x', 'N/A')
                            old_y = point.get('y', 'N/A')
                            new_x = nodes[node_id]['x']
                            new_y = nodes[node_id]['y']
                            
                            point['x'] = new_x
                            point['y'] = new_y
                            
                            print(f"  節點 {node_id}: ({old_x}, {old_y}) -> ({new_x:.6f}, {new_y:.6f})")
                            print(f"    原始座標: lat={nodes[node_id]['lat']}, lon={nodes[node_id]['lon']}")
                            print(f"    UTM Zone: {nodes[node_id]['zone']}")
                        else:
                            print(f"  警告: 找不到節點 {node_id}")
    
    # # 寫回 JSON 檔案
    # with open(json_file, 'w', encoding='utf-8') as f:
    #     json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f"\n已更新座標並寫回 {json_file}")

if __name__ == "__main__":
    update_self_defined_area_coordinates()
