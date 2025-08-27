import xml.etree.ElementTree as ET
import json
import utm

from cfg import LANE_TYPE_MAPPING_REV, ROADLINE_TYPE_MAPPING_REV


def osm_to_argoverse(osm_file, output_file):
    tree = ET.parse(osm_file)
    root = tree.getroot()

    # 節點
    nodes = {}
    for node in root.findall("node"):
        nid = int(node.attrib["id"])
        lat = float(node.attrib["lat"])
        lon = float(node.attrib["lon"])
        # 經緯度轉 UTM
        easting, northing, zone_num, zone_letter = utm.from_latlon(lat, lon)
        nodes[nid] = (easting, northing, 0.0)

    # way
    ways = {}
    for way in root.findall("way"):
        wid = int(way.attrib["id"])
        nds = [int(nd.attrib["ref"]) for nd in way.findall("nd")]
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        ways[wid] = {"nodes": nds, "tags": tags}

    # relation
    relations = {}
    for rel in root.findall("relation"):
        rid = int(rel.attrib["id"])
        members = []
        for mem in rel.findall("member"):
            members.append({
                "ref": int(mem.attrib["ref"]),
                "role": mem.attrib.get("role", ""),
                "type": mem.attrib["type"]
            })
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in rel.findall("tag")}
        relations[rid] = {"members": members, "tags": tags}

    output = {
        "pedestrian_crossings": {},
        "lane_segments": {},
        "drivable_areas": {}
    }

    # Pedestrian crossings
    for wid, wdata in ways.items():
        if wdata["tags"].get("type") == "zebra_marking":
            # print(wdata["nodes"])
            coords = [{"x": nodes[nid][0], "y": nodes[nid][1], "z": nodes[nid][2]}
                      for nid in wdata["nodes"]]
            if len(coords) >= 4:
                # print(f"Processing pedestrian crossing {wid} with coordinates: {coords}")
                output["pedestrian_crossings"][wid] = {
                    "id": wid,
                    "edge1": coords[:2],
                    "edge2": coords[2:4]
                }

    # Lane segments
    for rid, rdata in relations.items():
        if rdata["tags"].get("type") == "lanelet":
            # lane type
            lane_type = LANE_TYPE_MAPPING_REV.get(rdata["tags"].get("subtype"), "VEHICLE")

            # 左右邊界 way
            left_way_id = None
            right_way_id = None
            for mem in rdata["members"]:
                if mem["role"] == "left":
                    left_way_id = mem["ref"]
                elif mem["role"] == "right":
                    right_way_id = mem["ref"]

            # 邊界座標
            left_boundary = [{"x": nodes[nid][0], "y": nodes[nid][1], "z": nodes[nid][2]}
                             for nid in ways.get(left_way_id, {}).get("nodes", [])]
            right_boundary = [{"x": nodes[nid][0], "y": nodes[nid][1], "z": nodes[nid][2]}
                              for nid in ways.get(right_way_id, {}).get("nodes", [])]

            # 邊界標線型態
            left_tags = ways.get(left_way_id, {}).get("tags", {})
            right_tags = ways.get(right_way_id, {}).get("tags", {})

            left_type = ROADLINE_TYPE_MAPPING_REV.get(
                (left_tags.get("type"), left_tags.get("subtype"), left_tags.get("color")),
                "NONE"
            )
            right_type = ROADLINE_TYPE_MAPPING_REV.get(
                (right_tags.get("type"), right_tags.get("subtype"), right_tags.get("color")),
                "NONE"
            )

            output["lane_segments"][rid] = {
                "id": rid,
                "is_intersection": rdata["tags"].get("is_intersection") == "true",
                "lane_type": lane_type,
                "left_lane_boundary": left_boundary,
                "left_lane_mark_type": left_type,
                "right_lane_boundary": right_boundary,
                "right_lane_mark_type": right_type,
                "successors": [],
                "predecessors": [],
                "right_neighbor_id": None,
                "left_neighbor_id": None
            }

    # Drivable areas
    for rid, rdata in relations.items():
        if rdata["tags"].get("subtype") == "intersection" or rdata["tags"].get("subtype") == "freespace":# or rdata["tags"].get("subtype") == "road":
            area_nodes = []
            for mem in rdata["members"]:
                if mem["type"] == "way":
                    area_nodes.extend(ways[mem["ref"]]["nodes"])
            coords = [{"x": nodes[nid][0], "y": nodes[nid][1], "z": nodes[nid][2]} for nid in area_nodes]
            output["drivable_areas"][rid] = {
                "id": rid,
                "area_boundary": coords
            }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"Argoverse map JSON saved to {output_file}")

osm_to_argoverse("/home/hcis-s19/Documents/ChengYu/HetroD_sample/maps/lanelets/18_location/location18.osm", 
                 "/home/hcis-s19/Documents/ChengYu/HetroD_sample/maps/lanelets/18_location/log_map_archive_location18.json")