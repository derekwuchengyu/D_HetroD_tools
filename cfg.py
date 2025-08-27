# 反向映射表
LANE_TYPE_MAPPING_REV = {v: k for k, v in {
    "VEHICLE": "road",
    "BIKE": "bicycle_lane"
}.items()}

ROADLINE_TYPE_MAPPING_REV = {
    ("line_thin", "solid", "white"): "SOLID_WHITE",
    ("line_thin", "solid", "yellow"): "SOLID_YELLOW",
    ("line_thin", "solid", "blue"): "SOLID_BLUE",
    ("line_thin", "dashed", "white"): "DASHED_WHITE",
    ("line_thin", "dashed", "yellow"): "DASHED_YELLOW",
    ("line_thin", "solid_dash", "white"): "SOLID_DASH_WHITE",
    ("line_thin", "solid_dash", "yellow"): "SOLID_DASH_YELLOW",
    ("line_thin", "dash_solid", "white"): "DASH_SOLID_WHITE",
    ("line_thin", "dash_solid", "yellow"): "DASH_SOLID_YELLOW",
    ("line_thick", "solid", "white"): "DOUBLE_SOLID_WHITE",
    ("line_thick", "solid", "yellow"): "DOUBLE_SOLID_YELLOW",
    ("line_thick", "dashed", "white"): "DOUBLE_DASH_WHITE",
    ("line_thick", "dashed", "yellow"): "DOUBLE_DASH_YELLOW",
    ("virtual", None, None): "NONE"
}

ZONE_MAPPING = {
    # R1
    '1106':'RI_1',
    '1105':'RI_1',
    '1104':'RI_1',
    '1103':'RI_2',
    '1107':'RI_2',
    '1108':'RI_2',
    '1109':'RI_-1',
    '1111':'RI_-1',
    '1113':'RI_-1',
    '1110':'RI_-2',
    '1112':'RI_-2',
    '1114':'RI_-2',
    # R2
    '1080':'RII_1',
    '1077':'RII_2', #emergency_lane
    '1081':'RII_-1',
    '1084':'RII_-2', #emergency_lane
    # R3
    '1137':'RIII_1',
    '1063':'RIII_1',
    '1138':'RIII_2',
    '1062':'RIII_2',
    '1057':'RIII_2',
    '1068':'RIII_-1',
    '1070':'RIII_-1',
    '1069':'RIII_-2',
    '1071':'RIII_-2',
    # R4
    '1027':'RIV_1',
    '1033':'RIV_1',
    '1034':'RIV_1',
    '1028':'RIV_2',
    '1029':'RIV_2',
    '1031':'RIV_2',
    '1032':'RIV_2',
    '1025':'RIV_2',
    '1026':'RIV_2',
    '1041':'RIV_-1',
    '1040':'RIV_-1',
    '1038':'RIV_-1',
    '1037':'RIV_-1',
    '1036':'RIV_-1',
    # R5
    '1098':'RV_1',
    
    # Intersections
    '1102':'INT_1',
    '1003':'INT_2',
    
}
    
