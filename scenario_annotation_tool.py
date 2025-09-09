#!/usr/bin/env python3
"""
Scenario Annotation Tool
功能：
1. 左側顯示背景 + bbox
2. frame 用 Label 顯示，不重畫整個圖
3. 右側三區塊：Scenario Management + Scenario description + Category、Referred object、Related objects
4. Scenario ID管理，支援新增和選擇現有scenario
5. Category選項, Referred object單選, Related objects多選, 自動載入當前的trackID
6. 每轉換幀自動存 annotations.parquet（columns: scenarioId,description,category,frame,trackId,role）
7. role=['refer', 'related'], 分trackID存入不同的role
8. 支援播放/暫停、前後移動、Reset
9. 當超出scenario最後一個frame時，自動重置refer和related選擇到初始狀態
10. 支援Parquet格式存儲，自動轉換舊CSV文件
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import numpy as np
from PIL import Image, ImageTk, ImageDraw
import os
import csv
import threading
import time
from typing import Dict, List, Set, Optional, Tuple
import pyarrow as pa
import pyarrow.parquet as pq

# from backup.scenario_runner.srunner.scenarios import other_leading_vehicle

class ScenarioAnnotationTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Scenario Annotation Tool")
        self.root.geometry("2150x1600")
        
        # 設置較大的字體
        self.default_font = ('Arial', 10)
        self.label_font = ('Arial', 9, 'bold')
        self.button_font = ('DejaVu Sans', 9)  # 使用支援Unicode符號的字體
        self.symbol_font = ('Symbola', 12)  # 專門用於符號的字體
        self.combobox_font = ('Arial', 12)  # 專門用於下拉選單的較大字體
        
        # 配置style
        self.setup_styles()
        
        # 數據相關變量
        self.tracks_df = None
        self.background_image = None
        self.annotations_df = None
        # self.annotations_file = "annotations.parquet"
        # self.annotations_file = "annotations_ego_right_turn_motorcycle_straight.parquet"
        self.annotations_file = "annotations_oppsite_TL_vehicle.parquet"
        self.ortho_px_to_meter = 0.0499967249445942

        # 當前狀態
        self.current_frame = 0
        self.frame_range = (0, 42341)
        self.is_playing = False
        self.play_thread = None
        self.play_speed = 33  # ms
        
        # 模式控制
        self.is_annotation_mode = False  # True: 標注模式, False: Replay模式 (預設為Replay模式)
        self.current_scenario_range = None  # 當前scenario的frame範圍
        
        # 標注狀態
        self.current_scenario_id = ""
        self.current_category = ""
        self.current_description = ""
        self.current_referred = ""
        self.current_related = set()
        
        # 優化渲染的狀態追蹤
        self.last_track_ids = []
        self.last_referred_related_state = {}
        self.ui_needs_update = True
        
        # 圖像緩存用於優化渲染
        self.background_cache = {}
        self.last_canvas_size = None
        
        # 限制緩存大小以防止記憶體過度使用
        self.max_cache_size = 10  # 增加緩存大小
        
        # 性能優化相關變量
        self.last_frame_render_time = 0
        self.render_frame_cache = {}  # 完整frame的渲染緩存
        self.track_bbox_cache = {}  # bbox計算緩存
        self.last_tracks_hash = None  # 追蹤tracks數據變化
        self.render_dirty = True  # 標記是否需要重新渲染
        
        # 超高速渲染優化
        self.track_data_cache = {}  # 預計算track數據緩存
        self.color_cache = {}  # 顏色計算緩存
        self.background_precomputed = {}  # 預計算背景
        self.skip_complex_rendering = False  # 跳過複雜渲染
        self.last_selection_state = None  # 上次選擇狀態
        self.minimal_render_mode = False  # 最小化渲染模式
        
        # 鍵盤控制相關變量
        self.key_pressed = {}
        self.key_repeat_timer = None
        self.key_repeat_delay = 500  # 初始延遲時間 (ms)
        self.key_repeat_interval = 15  # 重複間隔時間 (ms)
        
        # 點擊檢測相關變量
        self.last_rendered_tracks = []  # 儲存當前幀渲染的track數據，用於點擊檢測
        self.current_scale = 1.0
        self.current_offset_x = 0
        self.current_offset_y = 0
        
        # 可用的分類選項
        self.categories = [
            "Lane Change",
            "Overtaking", 
            "Intersection",
            "Merge",
            "Cut-in",
            "Following",
            "Turning",
            "Emergency",
            "Other"
        ]
        
        self.setup_ui()
        self.load_data()
        
        # 初始化UI狀態
        self.update_annotation_panel_state()
        
        # 設置鍵盤事件綁定
        self.setup_keyboard_bindings()
        
    def setup_styles(self):
        """設置字體樣式"""
        style = ttk.Style()
        
        # 配置各種元件的字體
        style.configure('TLabel', font=self.default_font)
        style.configure('TButton', font=self.button_font)
        style.configure('TLabelframe.Label', font=self.label_font)
        style.configure('TCombobox', font=self.combobox_font)  # 使用較大的字體
        style.configure('TCheckbutton', font=self.default_font)
        style.configure('TRadiobutton', font=self.default_font)
        
        # 設定下拉選單的選項字體大小
        self.root.option_add('*TCombobox*Listbox.font', self.combobox_font)
        
        # 為符號按鈕配置特殊字體
        try:
            # 嘗試使用支援Unicode符號的字體
            style.configure('Symbol.TButton', font=('Segoe UI Symbol', 12))
        except:
            try:
                # 備選字體
                style.configure('Symbol.TButton', font=('Arial Unicode MS', 12))
            except:
                # 最後備選
                style.configure('Symbol.TButton', font=('DejaVu Sans', 12))
    
    def setup_keyboard_bindings(self):
        """設置鍵盤事件綁定"""
        # 初始化按鍵狀態字典
        self.key_pressed = {'Left': False, 'Right': False}
        
        # 確保窗口可以接收鍵盤事件
        self.root.focus_set()
        
        # 綁定按鍵事件
        self.root.bind('<KeyPress-Left>', self.on_key_press)
        self.root.bind('<KeyPress-Right>', self.on_key_press)
        self.root.bind('<KeyRelease-Left>', self.on_key_release)
        self.root.bind('<KeyRelease-Right>', self.on_key_release)
        
        # 確保窗口保持焦點
        self.root.bind('<FocusIn>', lambda e: self.root.focus_set())
        
        # 在窗口關閉時清理定時器
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def on_key_press(self, event):
        """按鍵按下事件處理"""
        key = event.keysym
        
        # 如果鍵已經被按住，則忽略重複的按鍵事件
        if key in self.key_pressed and self.key_pressed[key]:
            return
            
        self.key_pressed[key] = True
        
        # 立即執行一次移動
        if key == 'Left':
            self.prev_frame()
        elif key == 'Right':
            self.next_frame()
            
        # 設置重複按鍵定時器
        self.key_repeat_timer = self.root.after(self.key_repeat_delay, 
                                               lambda: self.start_key_repeat(key))
        
    def on_key_release(self, event):
        """按鍵釋放事件處理"""
        key = event.keysym
        self.key_pressed[key] = False
        
        # 取消重複按鍵定時器
        if self.key_repeat_timer:
            self.root.after_cancel(self.key_repeat_timer)
            self.key_repeat_timer = None
            
    def start_key_repeat(self, key):
        """開始重複按鍵"""
        if key in self.key_pressed and self.key_pressed[key]:
            # 執行對應的動作
            if key == 'Left':
                self.prev_frame()
            elif key == 'Right':
                self.next_frame()
                
            # 設置下一次重複
            self.key_repeat_timer = self.root.after(self.key_repeat_interval, 
                                                   lambda: self.start_key_repeat(key))
    
    def on_closing(self):
        """窗口關閉時的清理工作"""
        # 停止播放
        self.stop_play()
        
        # 清理按鍵重複定時器
        if self.key_repeat_timer:
            self.root.after_cancel(self.key_repeat_timer)
            self.key_repeat_timer = None
            
        # 在標注模式下保存當前標注
        if self.is_annotation_mode:
            self.save_current_annotations()
            
        # 關閉窗口
        self.root.destroy()
        
    def setup_ui(self):
        """設置用戶界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左側：可視化區域
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 圖像顯示區域
        self.image_frame = ttk.Frame(left_frame)
        self.image_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.image_frame, bg='white', width=1400, height=1000)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 綁定點擊事件
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        self.canvas.bind('<Control-Button-1>', self.on_canvas_ctrl_click)
        
        # 控制區域
        control_frame = ttk.Frame(left_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Frame控制
        frame_control = ttk.Frame(control_frame)
        frame_control.pack(fill=tk.X)
        
        ttk.Label(frame_control, text="Frame:").pack(side=tk.LEFT)
        self.frame_label = ttk.Label(frame_control, text=str(self.current_frame), font=self.label_font)
        self.frame_label.pack(side=tk.LEFT, padx=(5, 20))
        
        # 播放控制按鈕 - 使用ASCII符號
        ttk.Button(frame_control, text="|<", command=self.first_frame, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame_control, text="<", command=self.prev_frame, width=3).pack(side=tk.LEFT, padx=2)
        self.play_button = ttk.Button(frame_control, text="▶", command=self.toggle_play, width=3)
        self.play_button.pack(side=tk.LEFT, padx=2)
        ttk.Button(frame_control, text=">", command=self.next_frame, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(frame_control, text=">|", command=self.last_frame, width=3).pack(side=tk.LEFT, padx=2)
        
        # 模式切換按鈕
        self.mode_button = ttk.Button(frame_control, text="Annotation Mode", command=self.toggle_mode, width=15)
        self.mode_button.pack(side=tk.LEFT, padx=(20, 5))
        
        ttk.Button(frame_control, text="Reset", command=self.reset_annotations, width=6).pack(side=tk.LEFT, padx=(5, 2))
        
        # 速度控制
        speed_frame = ttk.Frame(control_frame)
        speed_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(speed_frame, text="Speed:").pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value="33")
        speed_scale = ttk.Scale(speed_frame, from_=15, to=1000, orient=tk.HORIZONTAL, 
                               variable=self.speed_var, command=self.update_speed)
        speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        speed_label = ttk.Label(speed_frame, textvariable=self.speed_var, width=5)
        speed_label.pack(side=tk.LEFT)
        ttk.Label(speed_frame, text="ms").pack(side=tk.LEFT)
        
        # 性能監控顯示
        perf_frame = ttk.Frame(control_frame)
        perf_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(perf_frame, text="Render Time:").pack(side=tk.LEFT)
        self.perf_label = ttk.Label(perf_frame, text="0ms", foreground="green")
        self.perf_label.pack(side=tk.LEFT, padx=(5, 10))
        
        ttk.Label(perf_frame, text="Frame Cache:").pack(side=tk.LEFT)
        self.cache_label = ttk.Label(perf_frame, text="0")
        self.cache_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # 右側：標注區域
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        # 設置右側面板寬度
        right_frame.configure(width=500)
        right_frame.pack_propagate(False)
        
        self.setup_annotation_panel(right_frame)
        
    def setup_annotation_panel(self, parent):
        """設置標注面板"""
        # Scenario ID區域
        scenario_frame = ttk.LabelFrame(parent, text="Scenario Management", padding=10)
        scenario_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Scenario ID選擇（僅下拉選單）
        id_frame = ttk.Frame(scenario_frame)
        id_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(id_frame, text="Scenario ID:").pack(side=tk.LEFT)
        self.scenario_id_var = tk.StringVar()
        self.scenario_id_combo = ttk.Combobox(id_frame, textvariable=self.scenario_id_var, width=15, font=self.combobox_font, state="readonly")
        self.scenario_id_combo.pack(side=tk.LEFT, padx=(5, 5))
        self.scenario_id_combo.bind('<<ComboboxSelected>>', self.on_scenario_id_change)
        
        # New Scenario按鈕
        ttk.Button(id_frame, text="New Scenario", command=self.new_scenario, width=12).pack(side=tk.LEFT, padx=(5, 0))
        
        # Scenario Description區域
        desc_frame = ttk.LabelFrame(parent, text="Scenario Description & Category", padding=10)
        desc_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 描述文本框
        ttk.Label(desc_frame, text="Description:").pack(anchor=tk.W)
        self.description_text = tk.Text(desc_frame, height=4, wrap=tk.WORD, font=self.default_font)
        self.description_text.pack(fill=tk.X, pady=(2, 10))
        self.description_text.bind('<KeyRelease>', self.on_description_change)
        
        # 為文本框添加特殊的鍵盤事件處理，但不影響正常的文本編輯
        self.description_text.bind('<Control-Left>', lambda e: self.prev_frame())
        self.description_text.bind('<Control-Right>', lambda e: self.next_frame())
        
        # 分類選擇
        ttk.Label(desc_frame, text="Category:").pack(anchor=tk.W)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(desc_frame, textvariable=self.category_var, 
                                          values=self.categories, state="readonly", font=self.combobox_font)
        self.category_combo.pack(fill=tk.X, pady=(2, 0))
        self.category_combo.bind('<<ComboboxSelected>>', self.on_category_change)
        
        # Referred Object區域
        referred_frame = ttk.LabelFrame(parent, text="Referred Object (Click to Select)", padding=10)
        referred_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 滾動區域用於referred objects
        self.referred_scroll_frame = ttk.Frame(referred_frame)
        self.referred_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        referred_canvas = tk.Canvas(self.referred_scroll_frame, height=510)
        referred_scrollbar = ttk.Scrollbar(self.referred_scroll_frame, orient="vertical", command=referred_canvas.yview)
        self.referred_content_frame = ttk.Frame(referred_canvas)
        
        self.referred_content_frame.bind(
            "<Configure>",
            lambda e: referred_canvas.configure(scrollregion=referred_canvas.bbox("all"))
        )
        
        referred_canvas.create_window((0, 0), window=self.referred_content_frame, anchor="nw")
        referred_canvas.configure(yscrollcommand=referred_scrollbar.set)
        
        referred_canvas.pack(side="left", fill="both", expand=True)
        referred_scrollbar.pack(side="right", fill="y")
        
        self.referred_var = tk.StringVar()
        self.referred_radios = {}
        
        # Related Objects區域
        related_frame = ttk.LabelFrame(parent, text="Related Objects (Ctrl+Click to Toggle)", padding=10)
        related_frame.pack(fill=tk.BOTH, expand=True)
        
        # 滾動區域用於related objects
        self.related_scroll_frame = ttk.Frame(related_frame)
        self.related_scroll_frame.pack(fill=tk.BOTH, expand=True)
        
        related_canvas = tk.Canvas(self.related_scroll_frame, height=510)
        related_scrollbar = ttk.Scrollbar(self.related_scroll_frame, orient="vertical", command=related_canvas.yview)
        self.related_content_frame = ttk.Frame(related_canvas)
        
        self.related_content_frame.bind(
            "<Configure>",
            lambda e: related_canvas.configure(scrollregion=related_canvas.bbox("all"))
        )
        
        related_canvas.create_window((0, 0), window=self.related_content_frame, anchor="nw")
        related_canvas.configure(yscrollcommand=related_scrollbar.set)
        
        related_canvas.pack(side="left", fill="both", expand=True)
        related_scrollbar.pack(side="right", fill="y")
        
        self.related_vars = {}
        self.related_checkboxes = {}
        
        # 文件操作按鈕
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(file_frame, text="Load Tracks", command=self.load_tracks_file).pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="Load Background", command=self.load_background_file).pack(fill=tk.X, pady=2)
        ttk.Button(file_frame, text="Save Annotations", command=self.save_annotations).pack(fill=tk.X, pady=2)
        
    def load_data(self):
        """載入默認數據"""
        # 嘗試載入軌跡數據
        # tracks_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/00_tracks_358-367.csv"
        # tracks_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/00_tracks_0-367.csv"
        tracks_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/data/00_tracks.csv"
        if os.path.exists(tracks_file):
            self.load_tracks(tracks_file)
        
        # 嘗試載入背景圖片
        bg_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/00_background.png"
        if os.path.exists(bg_file):
            self.load_background(bg_file)
        
        # 載入或創建標注文件
        self.load_annotations()
        
        # 更新顯示
        self.update_display()
        
    def load_tracks_file(self):
        """從文件選擇器載入軌跡數據"""
        file_path = filedialog.askopenfilename(
            title="Select Tracks CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.load_tracks(file_path)
            
    def load_tracks(self, file_path):
        """載入軌跡數據 - 超高速版本"""
        try:
            # 使用更快的CSV讀取選項
            self.tracks_df = pd.read_csv(file_path, 
                                       dtype={'trackId': 'int32', 'frame': 'int32'},  # 指定數據類型
                                       engine='c')  # 使用C引擎
            
            # 建立frame索引以加速查詢
            self._frame_index = self.tracks_df.groupby('frame').groups
            
            # 獲取frame範圍
            frames = sorted(self.tracks_df['frame'].unique())
            self.frame_range = (frames[0], frames[-1])
            self.current_frame = frames[0]
            
            # 清空所有緩存
            self.render_frame_cache.clear()
            self.track_bbox_cache.clear()
            self.color_cache.clear()
            self.render_dirty = True
            
            # 標記需要UI更新（只在載入新軌跡數據時）
            self.ui_needs_update = True
            
            # 更新track選項
            self.update_track_options()
            self.update_display()
            
            messagebox.showinfo("Success", f"Loaded tracks from {file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tracks: {str(e)}")
            
    def load_background_file(self):
        """從文件選擇器載入背景圖片"""
        file_path = filedialog.askopenfilename(
            title="Select Background Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
        )
        if file_path:
            self.load_background(file_path)
            
    def load_background(self, file_path):
        """載入背景圖片"""
        try:
            self.background_image = Image.open(file_path)
            # 清空背景緩存
            self.background_cache.clear()
            self.last_canvas_size = None
            self.update_display()
            # messagebox.showinfo("Success", f"Loaded background from {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load background: {str(e)}")
            
    def load_annotations(self):
        """載入標注數據"""
        if os.path.exists(self.annotations_file):
            try:
                self.annotations_df = pd.read_parquet(self.annotations_file)
                # 如果是舊格式，需要轉換
                if 'scenario description' in self.annotations_df.columns:
                    self.convert_old_format()
                # 更新scenario_id選項和下一個ID
                self.update_scenario_id_options()
            except Exception as e:
                print(f"Error loading parquet file: {e}")
                self.create_empty_annotations()
        else:
            self.create_empty_annotations()
            
    def convert_old_format(self):
        """轉換舊格式的標注數據"""
        new_rows = []
        scenario_counter = 1
        
        for _, row in self.annotations_df.iterrows():
            frame = row['frame']
            description = row.get('description', '')
            category = row.get('category', '')
            referred = row.get('referred', '')
            related = row.get('related', '')
            
            scenario_id = f"{scenario_counter}"
            scenario_counter += 1
            
            # 添加referred object
            if (referred is not None and str(referred) != '' and 
                str(referred) != 'nan' and str(referred).lower() != 'nan'):
                new_rows.append({
                    'scenarioId': scenario_id,
                    'description': description,
                    'category': category,
                    'frame': frame,
                    'trackId': int(referred),
                    'role': 'refer'
                })
            
            # 添加related objects
            if (related is not None and str(related) != '' and 
                str(related) != 'nan' and str(related).lower() != 'nan'):
                related_ids = str(related).split(',') if ',' in str(related) else [str(related)]
                for track_id in related_ids:
                    if track_id.strip():
                        new_rows.append({
                            'scenarioId': scenario_id,
                            'description': description,
                            'category': category,
                            'frame': frame,
                            'trackId': int(track_id.strip()),
                            'role': 'related'
                        })
        
        # 創建新的DataFrame
        if new_rows:
            self.annotations_df = pd.DataFrame(new_rows)
        else:
            self.create_empty_annotations()
            
    def update_scenario_id_options(self):
        """更新scenario_id選項"""
        if self.annotations_df is not None and not self.annotations_df.empty:
            scenario_ids = sorted(self.annotations_df['scenarioId'].unique(), key=lambda x: int(x) if str(x).isdigit() else float('inf'))
            self.scenario_id_combo['values'] = scenario_ids
            
    def create_empty_annotations(self):
        """創建空的標注數據"""
        self.annotations_df = pd.DataFrame(columns=[
            'scenarioId', 'description', 'category', 'frame', 'trackId', 'role'
        ])
        
    def toggle_mode(self):
        """切換標注模式和Replay模式 - 超高速版本"""
        self.is_annotation_mode = not self.is_annotation_mode
        
        if self.is_annotation_mode:
            self.mode_button.config(text="Replay Mode")
        else:
            self.mode_button.config(text="Annotation Mode")
            # 當切換到Replay模式時，更新scenario範圍
            self.update_scenario_range()
        
        # 清空所有緩存因為模式改變會影響顏色和渲染
        self.color_cache.clear()
        self.render_frame_cache.clear()
        
        # 標記需要UI更新以確保狀態正確應用
        self.ui_needs_update = True
        
        # 更新右側面板的狀態
        self.update_annotation_panel_state()
        
        # 標記需要重新渲染
        self.render_dirty = True
        
        # 在切換到Replay模式時，重置選擇狀態
        if not self.is_annotation_mode:
            self.reset_selections_to_initial_state()
        
        self.render_scene()
        
        # 如果有當前 scenario，確保 UI 狀態正確
        if self.scenario_id_var.get():
            self.update_display()
        
    def update_annotation_panel_state(self):
        """更新標注面板的啟用/禁用狀態"""
        annotation_state = 'normal' if self.is_annotation_mode else 'disabled'
        
        # Scenario ID 選擇在兩種模式下都啟用，但其他功能不同
        # 只禁用New Scenario按鈕和其他非scenario_id的控件
        for child in self.scenario_id_combo.master.winfo_children():
            if hasattr(child, 'config'):
                try:
                    # Scenario ID combo box 在兩種模式下都保持唯讀狀態
                    if child == self.scenario_id_combo:
                        child.config(state='readonly')
                    else:
                        # 其他控件（如New Scenario按鈕）在Replay模式下禁用
                        child.config(state=annotation_state)
                except:
                    pass
        
        # 禁用/啟用描述和分類區域
        self.description_text.config(state=annotation_state)
        self.category_combo.config(state=annotation_state)
        
        # 禁用/啟用referred和related選項
        for radio in self.referred_radios.values():
            radio.config(state=annotation_state)
        for checkbox in self.related_checkboxes.values():
            checkbox.config(state=annotation_state)
            
    def update_scenario_range(self):
        """更新當前scenario的frame範圍"""
        current_scenario_id = self.scenario_id_var.get()
        if current_scenario_id:
            self.current_scenario_range = self.get_scenario_frame_range(current_scenario_id)
        else:
            self.current_scenario_range = None
            
    def update_track_options(self):
        """更新track選項 - 只顯示已標注的track"""
        if self.tracks_df is None:
            return
        
        # 確保相關變數存在，避免渲染時出錯
        if not hasattr(self, 'related_vars'):
            self.related_vars = {}
            
        # 只有在明確需要更新UI時才進行更新（例如切換scenario）
        if not self.ui_needs_update:
            return
            
        # 獲取已標注的track IDs
        annotated_track_ids = self.get_annotated_track_ids()
        
        # 保存當前的選擇狀態
        current_referred = self.referred_var.get() if hasattr(self, 'referred_var') else ''
        current_related = {track_id: var.get() for track_id, var in self.related_vars.items()}
        
        # 清空現有選項
        for widget in self.referred_content_frame.winfo_children():
            widget.destroy()
        for widget in self.related_content_frame.winfo_children():
            widget.destroy()
            
        self.referred_radios.clear()
        self.related_vars.clear()
        self.related_checkboxes.clear()
        
        # 只為已標注的track添加選項
        if annotated_track_ids:
            # 添加referred object選項 (五列排列)
            self.create_five_column_layout(self.referred_content_frame, annotated_track_ids, 'referred')

            # 添加related objects選項 (五列排列)  
            self.create_five_column_layout(self.related_content_frame, annotated_track_ids, 'related')

            # 在標注模式下恢復之前的選擇狀態（如果track還存在的話）
            if self.is_annotation_mode:
                if current_referred and int(float(current_referred)) in annotated_track_ids:
                    self.referred_var.set(current_referred)
                    
                for track_id in annotated_track_ids:
                    if track_id in current_related and track_id in self.related_vars:
                        self.related_vars[track_id].set(current_related[track_id])
        
        # 更新狀態追蹤
        self.last_track_ids = annotated_track_ids.copy() if annotated_track_ids else []
        self.last_referred_related_state = {track_id: var.get() for track_id, var in self.related_vars.items() if track_id in self.related_vars}
        self.ui_needs_update = False  # 重置標記，直到下次切換scenario

    def create_five_column_layout(self, parent_frame, track_ids, widget_type):
        """創建五列布局的track選項"""
        if not track_ids:
            return
            
        # 計算每列的數量
        num_tracks = len(track_ids)
        tracks_per_column = 15 #(num_tracks + 4) // 5  # 向上取整

        # 創建五個列的框架
        columns = []
        for i in range(5):
            col_frame = ttk.Frame(parent_frame)
            col_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=2)
            columns.append(col_frame)
        
        # 根據當前模式決定初始狀態
        widget_state = 'normal' if self.is_annotation_mode else 'disabled'
        
        # 將track分配到各列
        for idx, track_id in enumerate(track_ids):
            col_idx = idx // tracks_per_column
            if col_idx >= 5:  # 防止超出範圍
                col_idx = 4

            if widget_type == 'referred':
                radio = ttk.Radiobutton(
                    columns[col_idx],
                    text=f"T_{int(track_id)}",
                    variable=self.referred_var,
                    value=str(int(track_id)),
                    command=self.on_referred_change,
                    state=widget_state
                )
                radio.pack(anchor=tk.W, pady=1)
                self.referred_radios[track_id] = radio
            else:  # related
                var = tk.BooleanVar()
                checkbox = ttk.Checkbutton(
                    columns[col_idx],
                    text=f"T_{int(track_id)}",
                    variable=var,
                    command=self.on_related_change,
                    state=widget_state
                )
                checkbox.pack(anchor=tk.W, pady=1)
                self.related_vars[track_id] = var
                self.related_checkboxes[track_id] = checkbox
            
    def get_current_tracks(self):
        """獲取當前frame的軌跡數據 - 超高速版本"""
        if self.tracks_df is None:
            return pd.DataFrame()
        
        # 使用預建索引進行超快查詢
        if not hasattr(self, '_frame_index'):
            self._frame_index = self.tracks_df.groupby('frame').groups
        
        if self.current_frame in self._frame_index:
            indices = self._frame_index[self.current_frame]
            # 只返回必要的列以減少數據處理
            essential_cols = ['trackId', 'xCenter', 'yCenter', 'width', 'length', 'heading']
            return self.tracks_df.iloc[indices][essential_cols]
        else:
            return pd.DataFrame(columns=['trackId', 'xCenter', 'yCenter', 'width', 'length', 'heading'])
        
    def get_scenario_frame_range(self, scenario_id):
        """獲取指定scenario的frame範圍"""
        if self.annotations_df is None or self.annotations_df.empty:
            return None
            
        if not scenario_id:
            return None
            
        # scenario_id保持為字符串，不轉換為整數
        # 獲取該scenario的所有frames
        scenario_frames = self.annotations_df[
            self.annotations_df['scenarioId'] == scenario_id
        ]['frame'].unique()
        
        if len(scenario_frames) == 0:
            return None
            
        return (int(scenario_frames.min()), int(scenario_frames.max()))
        
    def reset_selections_to_initial_state(self):
        """重置選擇項目到初始狀態"""
        # 清空referred object選擇
        self.referred_var.set('')
        
        # 清空related objects選擇
        for var in self.related_vars.values():
            var.set(False)
            
        # 清除顏色緩存以確保顏色正確更新
        self.color_cache.clear()
        self.render_dirty = True
            
        # 更新左側圖像以反映變化
        self.update_display_left_only()
        
    def check_scenario_boundary(self):
        """檢查是否超出當前scenario的frame範圍"""
        current_scenario_id = self.scenario_id_var.get()
        if not current_scenario_id:
            # 如果沒有選擇scenario，清除顏色緩存確保所有框框都是綠色
            if not self.is_annotation_mode:
                self.color_cache.clear()
                self.render_dirty = True
            return
            
        # 獲取當前scenario的frame範圍
        scenario_range = self.get_scenario_frame_range(current_scenario_id)
        if scenario_range is None:
            # 如果scenario範圍無效，清除顏色緩存
            if not self.is_annotation_mode:
                self.color_cache.clear()
                self.render_dirty = True
            return
            
        scenario_min, scenario_max = scenario_range
        
        # 檢查是否超出scenario範圍
        if self.current_frame < scenario_min or self.current_frame > scenario_max:
            if not self.is_annotation_mode:
                # 在Replay模式下，如果超出scenario範圍，重置選擇並清除緩存
                self.reset_selections_to_initial_state()
                # 額外確保顏色緩存被清除
                self.color_cache.clear()
                self.render_dirty = True
        
    def update_display(self):
        """更新顯示 - 分離左右側更新，優化性能"""
        self.update_frame_label()
        # 只有在需要更新UI時才更新右側（例如切換scenario）
        if self.ui_needs_update:
            self.update_track_options()  # 只在必要時更新右側UI
            self.load_current_annotations()
        
        # 標記需要重新渲染
        self.render_dirty = True
        self.render_scene()  # 總是更新左側場景
    
    def update_display_left_only(self):
        """只更新左側圖像顯示，不更新右側UI - 優化性能"""
        self.update_frame_label()
        self.render_dirty = True
        self.render_scene()
        
    def update_frame_label(self):
        """更新frame標籤"""
        self.frame_label.config(text=str(self.current_frame))
        
    def load_current_annotations(self):
        """載入當前frame的標注"""
        if self.annotations_df is None:
            return
            
        current_scenario_id = self.scenario_id_var.get()
        if not current_scenario_id:
            return
        
        # scenario_id保持為字符串，不轉換為整數
        # 獲取當前scenario在當前frame的標注
        current_ann = self.annotations_df[
            (self.annotations_df['scenarioId'] == current_scenario_id) & 
            (self.annotations_df['frame'] == self.current_frame)
        ]
        
        if not current_ann.empty:
            # 載入描述和分類（從第一行獲取）
            first_row = current_ann.iloc[0]
            
            # 載入描述
            desc = first_row.get('description', '')
            if desc is not None and str(desc) != 'nan' and str(desc).strip():
                self.description_text.delete(1.0, tk.END)
                self.description_text.insert(1.0, str(desc))
                
            # 載入分類  
            category = first_row.get('category', '')
            if category is not None and str(category) != 'nan':
                # 處理category可能是數組的情況
                if hasattr(category, '__len__') and not isinstance(category, str):
                    # 如果是數組，取第一個元素或連接為字符串
                    if len(category) > 0:
                        category_str = str(category[0]) if len(category) == 1 else ', '.join(map(str, category))
                    else:
                        category_str = ''
                else:
                    category_str = str(category)
                
                if category_str.strip():
                    self.category_var.set(category_str)
            
            # 載入referred和related objects
            referred_tracks = current_ann[current_ann['role'] == 'refer']['trackId'].tolist()
            related_tracks = current_ann[current_ann['role'] == 'related']['trackId'].tolist()
            
            # 設置referred object（單選）
            if referred_tracks:
                self.referred_var.set(str(int(referred_tracks[0])))
            else:
                self.referred_var.set('')
                
            # 設置related objects（多選）
            for track_id, var in self.related_vars.items():
                var.set(track_id in related_tracks)
                
            # 清除顏色緩存以確保載入的選擇立即反映在視覺上
            self.color_cache.clear()
            self.render_dirty = True
        else:
            # 如果當前frame沒有標注，但scenario_id已選擇，延續該scenario的描述和分類
            self.inherit_scenario_info(current_scenario_id)
            
    def inherit_scenario_info(self, scenario_id):
        """延續scenario的基本信息"""
        if self.annotations_df is None:
            return
            
        scenario_ann = self.annotations_df[self.annotations_df['scenarioId'] == scenario_id]
        if not scenario_ann.empty:
            first_row = scenario_ann.iloc[0]
            
            # 載入描述
            desc = first_row.get('description', '')
            if desc is not None and str(desc) != 'nan' and str(desc).strip():
                self.description_text.delete(1.0, tk.END)
                self.description_text.insert(1.0, str(desc))
                
            # 載入分類
            category = first_row.get('category', '')
            if category is not None and str(category) != 'nan':
                # 處理category可能是數組的情況
                if hasattr(category, '__len__') and not isinstance(category, str):
                    # 如果是數組，取第一個元素或連接為字符串
                    if len(category) > 0:
                        category_str = str(category[0]) if len(category) == 1 else ', '.join(map(str, category))
                    else:
                        category_str = ''
                else:
                    category_str = str(category)
                
                if category_str.strip():
                    self.category_var.set(category_str)
                
    def render_scene(self):
        """渲染場景 - 超高速優化版本，目標15ms以下"""
        start_time = time.time()
        
        if self.background_image is None:
            return
        
        # 獲取當前tracks和狀態
        current_tracks = self.get_current_tracks()
        if current_tracks.empty:
            # 如果沒有tracks，只顯示背景
            self.render_background_only()
            render_time = (time.time() - start_time) * 1000
            self.update_performance_display(render_time)
            return
        
        # 計算當前狀態的哈希
        tracks_hash = self.compute_fast_hash(current_tracks)
        selection_state = self.get_selection_state_hash()
        
        # 檢查是否可以使用緩存
        cache_key = (self.current_frame, tracks_hash, self.is_annotation_mode, selection_state)
        
        if (not self.render_dirty and 
            cache_key in self.render_frame_cache and 
            self.last_tracks_hash == tracks_hash and
            self.last_selection_state == selection_state):
            # 使用完整緩存
            self.display_cached_image(cache_key)
            return
        
        # 快速渲染路徑
        self.fast_render_path(current_tracks, cache_key, tracks_hash, selection_state)
        
        # 記錄性能
        render_time = (time.time() - start_time) * 1000
        self.last_frame_render_time = render_time
        self.update_performance_display(render_time)
        
    def compute_fast_hash(self, tracks_df):
        """快速計算tracks哈希"""
        if tracks_df.empty:
            return 0
        # 只使用trackId進行哈希，避免浮點數計算
        return hash(tuple(sorted(tracks_df['trackId'].astype(int).tolist())))
    
    def get_selection_state_hash(self):
        """獲取選擇狀態哈希"""
        referred = self.referred_var.get() if hasattr(self, 'referred_var') else ''
        related = tuple(sorted([str(tid) for tid, var in self.related_vars.items() if var.get()])) if hasattr(self, 'related_vars') else ()
        return hash((referred, related))
    
    def render_background_only(self):
        """只渲染背景"""
        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        current_canvas_size = (canvas_width, canvas_height)
        
        if current_canvas_size in self.background_cache:
            bg_data = self.background_cache[current_canvas_size]
            self.photo = ImageTk.PhotoImage(bg_data['image'])
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
    
    def display_cached_image(self, cache_key):
        """顯示緩存的圖像"""
        cached_image = self.render_frame_cache[cache_key]
        self.photo = ImageTk.PhotoImage(cached_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
    
    def fast_render_path(self, current_tracks, cache_key, tracks_hash, selection_state):
        """快速渲染路徑"""
        # 獲取canvas大小和背景
        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        current_canvas_size = (canvas_width, canvas_height)
        
        # 確保背景緩存存在
        self.ensure_background_cache(current_canvas_size, canvas_width, canvas_height)
        
        # 獲取背景數據
        cache_data = self.background_cache[current_canvas_size]
        full_image = cache_data['image'].copy()
        scale = cache_data['scale']
        offset_x = cache_data['offset_x']
        offset_y = cache_data['offset_y']
        
        # 保存縮放參數
        self.current_scale = scale
        self.current_offset_x = offset_x
        self.current_offset_y = offset_y
        
        # 批量處理所有tracks
        self.batch_render_tracks(current_tracks, full_image, scale, offset_x, offset_y, canvas_width, canvas_height)
        
        # 顯示結果
        self.photo = ImageTk.PhotoImage(full_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        # 緩存結果
        self.cache_render_result(cache_key, full_image, tracks_hash, selection_state)
    
    def ensure_background_cache(self, current_canvas_size, canvas_width, canvas_height):
        """確保背景緩存存在"""
        if (self.last_canvas_size != current_canvas_size or 
            current_canvas_size not in self.background_cache):
            
            # 快速背景處理
            bg_width, bg_height = self.background_image.size
            scale = min(canvas_width / bg_width, canvas_height / bg_height)
            
            new_width = int(bg_width * scale)
            new_height = int(bg_height * scale)
            
            # 使用更快的重採樣算法
            bg_resized = self.background_image.resize((new_width, new_height), Image.Resampling.NEAREST)
            
            offset_x = (canvas_width - new_width) // 2
            offset_y = (canvas_height - new_height) // 2
            
            background_base = Image.new('RGB', (canvas_width, canvas_height), 'white')
            background_base.paste(bg_resized, (offset_x, offset_y))
            
            self.background_cache[current_canvas_size] = {
                'image': background_base.copy(),
                'scale': scale,
                'offset_x': offset_x,
                'offset_y': offset_y
            }
            
            self.last_canvas_size = current_canvas_size
    
    def batch_render_tracks(self, tracks_df, image, scale, offset_x, offset_y, canvas_width, canvas_height):
        """批量渲染所有tracks - 超高速版本"""
        self.last_rendered_tracks = []
        
        if tracks_df.empty:
            return
        
        draw = ImageDraw.Draw(image)
        
        # 預計算所有需要的數據
        track_render_data = []
        
        # 使用向量化操作
        track_ids = tracks_df['trackId'].values
        x_centers = tracks_df['xCenter'].values / self.ortho_px_to_meter
        y_centers = -tracks_df['yCenter'].values / self.ortho_px_to_meter
        widths = tracks_df['width'].values
        lengths = tracks_df['length'].values
        headings = tracks_df['heading'].values
        
        # 批量計算所有tracks的渲染數據
        for i, (track_id, x, y, width, length, heading) in enumerate(zip(
            track_ids, x_centers, y_centers, widths, lengths, headings)):
            
            # 快速顏色計算
            color = self.get_track_color_fast(track_id)
            
            # 快速bbox計算
            pixel_corners, center_px, center_py = self.calculate_bbox_fast(
                x, y, width, length, heading, scale, offset_x, offset_y, canvas_width, canvas_height)
            
            if pixel_corners:
                track_render_data.append((track_id, color, pixel_corners, center_px, center_py))
                
                # 保存點擊檢測數據（簡化版）
                self.last_rendered_tracks.append({
                    'track_id': track_id,
                    'pixels': pixel_corners
                })
        
        # 批量繪製 - 分離線條和文字渲染
        self.batch_draw_polygons(draw, track_render_data)
        self.batch_draw_text(draw, track_render_data)
    
    def get_track_color_fast(self, track_id):
        """快速獲取track顏色 - 使用緩存"""
        # 簡化的顏色邏輯，優先使用緩存
        if track_id in self.color_cache:
            cache_entry = self.color_cache[track_id]
            if cache_entry['mode'] == self.is_annotation_mode:
                return cache_entry['color']
        
        # 計算顏色
        if not self.is_annotation_mode:
            # Replay模式 - 檢查scenario範圍和refer/related
            if self.current_scenario_range is not None:
                scenario_start, scenario_end = self.current_scenario_range
                if scenario_start <= self.current_frame <= scenario_end:
                    # 在scenario範圍內，檢查refer/related
                    if self.annotations_df is not None:
                        current_scenario_id = self.scenario_id_var.get()
                        scenario_tracks = self.annotations_df[
                            (self.annotations_df['scenarioId'] == current_scenario_id) &
                            (self.annotations_df['frame'] == self.current_frame)
                        ]
                        
                        # 檢查是否為referred或related track
                        referred_tracks = scenario_tracks[scenario_tracks['role'] == 'refer']['trackId'].tolist()
                        related_tracks = scenario_tracks[scenario_tracks['role'] == 'related']['trackId'].tolist()
                        
                        if track_id in referred_tracks:
                            color = 'red'  # referred object用紅色
                        elif track_id in related_tracks:
                            color = 'blue'  # related objects用藍色
                        else:
                            color = 'yellow'  # scenario範圍內的其他track用黃色
                    else:
                        color = 'yellow'  # 沒有annotations時用黃色
                else:
                    color = 'green'  # 超出scenario範圍的track用綠色
            else:
                color = 'green'  # 沒有scenario時全部用綠色
        else:
            # 標注模式
            color = 'green'
            referred = self.referred_var.get()
            if referred and str(int(float(track_id))) == str(int(float(referred))):
                color = 'red'
            elif track_id in self.related_vars and self.related_vars[track_id].get():
                color = 'blue'
        
        # 緩存結果
        self.color_cache[track_id] = {'color': color, 'mode': self.is_annotation_mode}
        return color
    
    def calculate_bbox_fast(self, x, y, width, length, heading, scale, offset_x, offset_y, canvas_width, canvas_height):
        """快速計算bbox - 使用預計算和近似"""
        # 簡化的bbox計算
        heading_rad = np.radians(-heading if heading >= 0 else -heading + 360)
        
        # 快速角點計算
        dx = length / (2 * self.ortho_px_to_meter)
        dy = width / (2 * self.ortho_px_to_meter)
        
        cos_h = np.cos(heading_rad)
        sin_h = np.sin(heading_rad)
        
        # 計算四個角點
        corners = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
        pixel_corners = []
        
        for corner_x, corner_y in corners:
            # 旋轉
            rotated_x = corner_x * cos_h - corner_y * sin_h + x
            rotated_y = corner_x * sin_h + corner_y * cos_h + y
            
            # 縮放和偏移
            scaled_x = int(rotated_x * scale + offset_x)
            scaled_y = int(rotated_y * scale + offset_y)
            
            # 邊界檢查
            scaled_x = max(0, min(canvas_width - 1, scaled_x))
            scaled_y = max(0, min(canvas_height - 1, scaled_y))
            
            pixel_corners.append((scaled_x, scaled_y))
        
        # 中心點
        center_px = max(10, min(canvas_width - 30, int(x * scale + offset_x)))
        center_py = max(10, min(canvas_height - 20, int(y * scale + offset_y)))
        
        return pixel_corners, center_px, center_py
    
    def batch_draw_polygons(self, draw, track_render_data):
        """批量繪製多邊形"""
        for track_id, color, pixel_corners, center_px, center_py in track_render_data:
            if len(pixel_corners) >= 4:
                draw.polygon(pixel_corners, outline=color, width=2)  # 減少線寬提升性能
    
    def batch_draw_text(self, draw, track_render_data):
        """批量繪製文字"""
        for track_id, color, pixel_corners, center_px, center_py in track_render_data:
            if len(pixel_corners) >= 4:
                text_str = str(int(track_id))
                fill_color = 'white' if color != 'yellow' else 'DimGray'
                
                # 簡化的文字背景
                try:
                    # 估算文字大小而不是精確計算
                    text_width = len(text_str) * 7  # 估算
                    text_height = 12  # 固定高度
                    
                    # 計算y偏移
                    shift_y = center_py - min(pixel_corners, key=lambda p: p[1])[1]
                    
                    # 繪製背景
                    draw.rectangle([center_px - 2, center_py - 2 + shift_y, 
                                  center_px + text_width + 2, center_py + text_height + 2 + shift_y], 
                                 fill=fill_color, outline='black', width=1)
                    
                    # 繪製文字
                    draw.text((center_px, center_py + shift_y), text_str, fill=color)
                except:
                    # 失敗時只繪製文字
                    draw.text((center_px, center_py), text_str, fill=color)
    
    def cache_render_result(self, cache_key, image, tracks_hash, selection_state):
        """緩存渲染結果"""
        self.render_frame_cache[cache_key] = image.copy()
        self.last_tracks_hash = tracks_hash
        self.last_selection_state = selection_state
        self.render_dirty = False
        
        # 限制緩存大小
        if len(self.render_frame_cache) > 30:  # 減少緩存大小
            # 移除最舊的緩存
            oldest_key = next(iter(self.render_frame_cache))
            del self.render_frame_cache[oldest_key]
        
        # 清理顏色緩存
        if len(self.color_cache) > 200:
            self.color_cache.clear()
        
    def update_performance_display(self, render_time):
        """更新性能監控顯示"""
        if hasattr(self, 'perf_label'):
            color = "green"
            if render_time > 30:
                color = "red"
            elif render_time > 20:
                color = "orange"
            
            self.perf_label.config(text=f"{render_time:.1f}ms", foreground=color)
        
        if hasattr(self, 'cache_label'):
            cache_count = len(self.render_frame_cache)
            self.cache_label.config(text=str(cache_count))
        
    def calculate_bbox_data(self, track, canvas_width, canvas_height, scale, offset_x, offset_y):
        """計算bbox的所有必要數據"""
        try:
            x_center = track['xCenter']
            y_center = track['yCenter']
            width = track['width']
            length = track['length']
            heading = track['heading']
            
            # Convert from meters to pixel coordinates
            x = x_center / self.ortho_px_to_meter
            y = -y_center / self.ortho_px_to_meter
            
            # Convert heading
            heading = heading * -1
            heading = heading if heading >= 0 else heading + 360
            heading_rad = np.radians(heading)
            
            # Calculate corner offset from center
            dx = length / (2 * self.ortho_px_to_meter)
            dy = width / (2 * self.ortho_px_to_meter)
            
            # Calculate corners
            corners = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
            
            # Rotate and translate corners
            cos_h = np.cos(heading_rad)
            sin_h = np.sin(heading_rad)
            
            pixel_corners = []
            for corner_x, corner_y in corners:
                rotated_x = corner_x * cos_h - corner_y * sin_h + x
                rotated_y = corner_x * sin_h + corner_y * cos_h + y
                
                scaled_x = int(rotated_x * scale + offset_x)
                scaled_y = int(rotated_y * scale + offset_y)
                
                scaled_x = max(0, min(canvas_width - 1, scaled_x))
                scaled_y = max(0, min(canvas_height - 1, scaled_y))
                
                pixel_corners.append((scaled_x, scaled_y))
            
            # Calculate center position
            center_px = int(x * scale + offset_x)
            center_py = int(y * scale + offset_y)
            
            center_px = max(10, min(canvas_width - 30, center_px))
            center_py = max(10, min(canvas_height - 20, center_py))
            
            # Calculate y shift
            shift_y = center_py - min(pixel_corners, key=lambda p: p[1])[1]
            
            return pixel_corners, center_px, center_py, shift_y
            
        except Exception as e:
            print(f"Error calculating bbox data for track {track.get('trackId', 'unknown')}: {e}")
            return None, 0, 0, 0
    
    def get_corner_coordinates(self, track):
        """獲取track的角點坐標用於點擊檢測"""
        try:
            x_center = track['xCenter']
            y_center = track['yCenter']
            width = track['width']
            length = track['length']
            heading = track['heading']
            
            x = x_center / self.ortho_px_to_meter
            y = -y_center / self.ortho_px_to_meter
            
            heading = heading * -1
            heading = heading if heading >= 0 else heading + 360
            heading_rad = np.radians(heading)
            
            dx = length / (2 * self.ortho_px_to_meter)
            dy = width / (2 * self.ortho_px_to_meter)
            
            corners = [(-dx, -dy), (dx, -dy), (dx, dy), (-dx, dy)]
            
            cos_h = np.cos(heading_rad)
            sin_h = np.sin(heading_rad)
            
            rotated_corners = []
            for corner_x, corner_y in corners:
                rotated_x = corner_x * cos_h - corner_y * sin_h + x
                rotated_y = corner_x * sin_h + corner_y * cos_h + y
                rotated_corners.append((rotated_x, rotated_y))
            
            return rotated_corners
            
        except Exception as e:
            print(f"Error calculating corner coordinates for track {track.get('trackId', 'unknown')}: {e}")
            return []
        
    def calculate_track_pixels(self, track, scale, offset_x, offset_y):
        """計算track的像素坐標多邊形，用於點擊檢測"""
        try:
            # 參考draw_bbox的邏輯
            x_center = track['xCenter']
            y_center = track['yCenter']
            width = track['width']
            length = track['length']
            heading = track['heading']
            
            # Convert from meters to pixel coordinates
            x = x_center / self.ortho_px_to_meter
            y = -y_center / self.ortho_px_to_meter  # Y is negated for image coordinates
            
            # Convert heading to match the reference implementation
            heading = heading * -1
            heading = heading if heading >= 0 else heading + 360
            
            # Convert heading to radians for calculations
            heading_rad = np.radians(heading)
            
            # Calculate corner offset from center
            dx = length / (2 * self.ortho_px_to_meter)
            dy = width / (2 * self.ortho_px_to_meter)
            
            # Calculate the four corners relative to center
            corners = [
                (-dx, -dy),  # bottom-left
                (dx, -dy),   # bottom-right
                (dx, dy),    # top-right
                (-dx, dy)    # top-left
            ]
            
            # Rotate and translate corners
            rotated_corners = []
            cos_h = np.cos(heading_rad)
            sin_h = np.sin(heading_rad)
            
            for corner_x, corner_y in corners:
                # Rotate around center
                rotated_x = corner_x * cos_h - corner_y * sin_h + x
                rotated_y = corner_x * sin_h + corner_y * cos_h + y
                rotated_corners.append((rotated_x, rotated_y))
            
            # Apply scaling and offset to match the displayed background image
            pixel_corners = []
            for px, py in rotated_corners:
                # Apply scale and offset to match background image position
                scaled_x = px * scale + offset_x
                scaled_y = py * scale + offset_y
                pixel_corners.append((scaled_x, scaled_y))
            
            return pixel_corners
            
        except Exception as e:
            print(f"Error calculating pixels for track {track.get('trackId', 'unknown')}: {e}")
            return None

        
    def draw_bbox(self, draw, track, canvas_width, canvas_height, scale, offset_x, offset_y):
        """繪製bounding box"""
        try:
            # 參考visualize_moving_tags.py的實現
            x_center = track['xCenter']
            y_center = track['yCenter']
            width = track['width']
            length = track['length']
            heading = track['heading']
            track_id = track['trackId']
            
            # Convert from meters to pixel coordinates (參考visualize_moving_tags.py)
            x = x_center / self.ortho_px_to_meter
            y = -y_center / self.ortho_px_to_meter  # Y is negated for image coordinates
            
            # Convert heading to match the reference implementation
            heading = heading * -1
            heading = heading if heading >= 0 else heading + 360
            
            # Convert heading to radians for calculations
            heading_rad = np.radians(heading)
            
            # Calculate corner offset from center
            dx = length / (2 * self.ortho_px_to_meter)
            dy = width / (2 * self.ortho_px_to_meter)
            
            # Calculate the four corners relative to center
            corners = [
                (-dx, -dy),  # bottom-left
                (dx, -dy),   # bottom-right
                (dx, dy),    # top-right
                (-dx, dy)    # top-left
            ]
            
            # Rotate and translate corners
            rotated_corners = []
            cos_h = np.cos(heading_rad)
            sin_h = np.sin(heading_rad)
            
            for corner_x, corner_y in corners:
                # Rotate around center
                rotated_x = corner_x * cos_h - corner_y * sin_h + x
                rotated_y = corner_x * sin_h + corner_y * cos_h + y
                rotated_corners.append((rotated_x, rotated_y))
            
            # Apply scaling and offset to match the displayed background image
            pixel_corners = []
            for px, py in rotated_corners:
                # Apply scale and offset to match background image position
                scaled_x = int(px * scale + offset_x)
                scaled_y = int(py * scale + offset_y)
                
                # Ensure coordinates are within canvas bounds
                scaled_x = max(0, min(canvas_width - 1, scaled_x))
                scaled_y = max(0, min(canvas_height - 1, scaled_y))
                
                pixel_corners.append((scaled_x, scaled_y))
            
            # Draw bounding box
            if len(pixel_corners) >= 4:
                # Get color based on selection state
                color = self.get_track_color(track_id)
                # print(color, track_id, self.referred_var.get(), self.current_referred, self.related_vars.items())
                
                # Draw polygon with thicker line for better visibility
                draw.polygon(pixel_corners, outline=color, width=3)
                
                # Draw track ID at center
                center_px = int(x * scale + offset_x)
                center_py = int(y * scale + offset_y)
                
                # Ensure text position is within canvas
                center_px = max(10, min(canvas_width - 30, center_px))
                center_py = max(10, min(canvas_height - 20, center_py))
                
                # Add background to text for better visibility
                text_str = str(int(track_id))
                try:
                    # Get text size for background rectangle
                    bbox = draw.textbbox((center_px, center_py), text_str)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    #heading y shift
                    shift_y = center_py - min(pixel_corners, key=lambda p: p[1])[1]


                    fill_color = 'white' if color != 'yellow' else 'DimGray'


                    # Draw text background
                    draw.rectangle([center_px - 2, center_py - 2 + shift_y, 
                                  center_px + text_width + 2, center_py + text_height + 2 + shift_y], 
                                 fill=fill_color, outline='black')
                except:
                    # Fallback for older PIL versions
                    pass
                
                draw.text((center_px, center_py+shift_y), text_str, fill=color)
                
        except Exception as e:
            print(f"Error drawing bbox for track {track.get('trackId', 'unknown')}: {e}")
            
    def get_track_color(self, track_id):
        """獲取軌跡顏色"""
        # 在Replay模式下，根據scenario範圍決定顏色
        if not self.is_annotation_mode:
            if self.current_scenario_range is not None:
                scenario_start, scenario_end = self.current_scenario_range
                if scenario_start <= self.current_frame <= scenario_end:
                    # 在scenario範圍內，顯示scenario相關的顏色
                    if self.annotations_df is not None:
                        current_scenario_id = self.scenario_id_var.get()
                        scenario_tracks = self.annotations_df[
                            (self.annotations_df['scenarioId'] == current_scenario_id) &
                            (self.annotations_df['frame'] == self.current_frame)
                        ]
                        
                        # 檢查是否為referred或related track
                        referred_tracks = scenario_tracks[scenario_tracks['role'] == 'refer']['trackId'].tolist()
                        related_tracks = scenario_tracks[scenario_tracks['role'] == 'related']['trackId'].tolist()
                        
                        if track_id in referred_tracks:
                            return 'red'  # referred object用紅色
                        elif track_id in related_tracks:
                            return 'blue'  # related objects用藍色
                        else:
                            return 'yellow'  # scenario範圍內的其他track用黃色
                else:
                    return 'green'  # 超出scenario範圍的track用綠色
            else:
                return 'green'  # 沒有scenario時全部用綠色
        else:
            # 標注模式下的原有邏輯
            current_referred = self.referred_var.get()
            # 確保類型一致性的比較
            if current_referred:
                try:
                    track_id_str = str(int(float(track_id)))
                    current_referred_str = str(int(float(current_referred)))
                    if track_id_str == current_referred_str:
                        return 'red'  # referred object用紅色
                except (ValueError, TypeError):
                    pass
            
            # 檢查related objects
            if track_id in self.related_vars and self.related_vars[track_id].get():
                return 'blue'  # related objects用藍色
            else:
                return 'green'  # 其他用綠色
            
    def on_description_change(self, event=None):
        """描述改變時的處理"""
        self.current_description = self.description_text.get(1.0, tk.END).strip()
        # self.save_current_annotations()
        
    def on_category_change(self, event=None):
        """分類改變時的處理"""
        self.current_category = self.category_var.get()
        # self.save_current_annotations()
        
    def on_scenario_id_change(self, event=None):
        """scenario_id改變時的處理"""
        new_scenario_id = self.scenario_id_var.get()
        if new_scenario_id != self.current_scenario_id:
            self.current_scenario_id = new_scenario_id
            
            # 清除所有緩存以確保顏色正確更新
            self.color_cache.clear()
            self.render_frame_cache.clear()
            self.render_dirty = True
            
            # 更新scenario範圍（對兩種模式都重要）
            self.update_scenario_range()
            
            # 如果選擇了有效的scenario，跳到該scenario的起始frame
            if new_scenario_id:
                scenario_range = self.get_scenario_frame_range(new_scenario_id)
                if scenario_range is not None:
                    scenario_start, _ = scenario_range
                    self.current_frame = scenario_start
            
            # 標記需要UI更新（只有切換scenario時才更新）
            self.ui_needs_update = True
            
            # 根據模式決定是否載入標注，但都要更新右側UI
            if self.is_annotation_mode:
                # 標注模式：載入該scenario的標注資訊
                self.load_current_annotations()
            else:
                # Replay模式：不載入標注資訊，只刷新refer/related選擇
                self.reset_selections_to_initial_state()
            
            # 單次更新完整顯示（包括frame label和右側UI）
            self.update_display()
        
    def new_scenario(self):
        """創建新的scenario"""
        # 從現有annotations中找到最大的scenario_id數字
        max_num = 0
        if self.annotations_df is not None and not self.annotations_df.empty:
            scenario_ids = self.annotations_df['scenarioId'].unique()
            for sid in scenario_ids:
                if sid is not None and str(sid) != 'nan':
                    try:
                        # 直接轉換為整數，不分割
                        num = int(str(sid))
                        max_num = max(max_num, num)
                    except:
                        pass
        
        new_id = f"{max_num + 1}"
        
        # 更新combo box的選項
        current_values = list(self.scenario_id_combo['values']) if self.scenario_id_combo['values'] else []
        if new_id not in current_values:
            current_values.append(new_id)
            current_values.sort(key=lambda x: int(x) if str(x).isdigit() else float('inf'))  # 數字升序排序
            self.scenario_id_combo['values'] = current_values
        
        # 設置為當前選擇
        self.scenario_id_var.set(new_id)
        self.current_scenario_id = new_id
        
        # 清空當前標注（但保留checked items）
        self.description_text.delete(1.0, tk.END)
        self.category_var.set('')
        
        # 清空選擇狀態
        self.referred_var.set('')
        for var in self.related_vars.values():
            var.set(False)
        
        # 標記需要UI更新（創建新scenario時需要清空選擇和右側面板）
        self.ui_needs_update = True
        
        # 更新顯示 - 新scenario沒有標注，所以右側面板會是空的
        self.update_display()
        
    def on_referred_change(self):
        """referred object改變時的處理 - 超高速版本"""
        self.current_referred = self.referred_var.get()
        # 清空顏色緩存以確保顏色更新
        self.color_cache.clear()
        # 只在標注模式下保存
        if self.is_annotation_mode:
            self.save_current_annotations()
        # 標記需要重新渲染
        self.render_dirty = True
        self.render_scene()
        
    def on_related_change(self):
        """related objects改變時的處理 - 超高速版本"""
        self.current_related = {
            track_id for track_id, var in self.related_vars.items() 
            if var.get()
        }
        # 清空顏色緩存以確保顏色更新
        self.color_cache.clear()
        # 只在標注模式下保存
        if self.is_annotation_mode:
            self.save_current_annotations()
        # 標記需要重新渲染
        self.render_dirty = True
        self.render_scene()
        
    def propagate_annotations_to_current_frame(self):
        """將當前選擇的annotations延續到當前frame"""
        scenario_id = self.scenario_id_var.get()
        if not scenario_id:
            return
            
        # 獲取當前的選擇狀態
        description = self.description_text.get(1.0, tk.END).strip()
        category = self.category_var.get()
        referred = self.referred_var.get()
        related_tracks = {
            track_id for track_id, var in self.related_vars.items() 
            if var.get()
        }
        
        # 如果有任何選擇，延續到當前frame
        if referred or related_tracks or description or category:
            # 刪除當前scenario_id和frame的現有標注
            mask = (self.annotations_df['scenarioId'] == scenario_id) & (self.annotations_df['frame'] == self.current_frame)
            self.annotations_df = self.annotations_df[~mask]
            
            new_rows = []
            
            # 添加referred object
            if referred:
                new_rows.append({
                    'scenarioId': scenario_id,
                    'description': description,
                    'category': category,
                    'frame': self.current_frame,
                    'trackId': int(float(referred)),
                    'role': 'refer'
                })
                
            # 添加related objects
            for track_id in related_tracks:
                new_rows.append({
                    'scenarioId': scenario_id,
                    'description': description,
                    'category': category,
                    'frame': self.current_frame,
                    'trackId': track_id,
                    'role': 'related'
                })
                
            # 添加新行到DataFrame
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                self.annotations_df = pd.concat([self.annotations_df, new_df], ignore_index=True)
                
            # 自動保存到文件
            self.save_annotations_to_file()
        
    def save_current_annotations(self):
        """保存當前frame的標注"""
        # 只在標注模式下保存
        if not self.is_annotation_mode:
            return
            
        if self.annotations_df is None:
            self.create_empty_annotations()
            
        scenario_id = self.scenario_id_var.get()
        if not scenario_id:
            return  # 如果沒有選擇scenario_id，不保存
            
        # 準備數據
        description = self.description_text.get(1.0, tk.END).strip()
        category = self.category_var.get()
        referred = self.referred_var.get()
        related_tracks = {
            track_id for track_id, var in self.related_vars.items() 
            if var.get()
        }
        
        # 檢查是否有任何選擇的項目，如果沒有則跳過儲存
        if not referred and not related_tracks:
            return
        
        # 刪除當前scenario_id和frame的現有標注
        mask = (self.annotations_df['scenarioId'] == scenario_id) & (self.annotations_df['frame'] == self.current_frame)
        self.annotations_df = self.annotations_df[~mask]
        
        new_rows = []
        
        # 添加referred object
        if referred:
            new_rows.append({
                'scenarioId': scenario_id,
                'description': description,
                'category': category,
                'frame': self.current_frame,
                'trackId': int(float(referred)),
                'role': 'refer'
            })
            
        # 添加related objects
        for track_id in related_tracks:
            new_rows.append({
                'scenarioId': scenario_id,
                'description': description,
                'category': category,
                'frame': self.current_frame,
                'trackId': track_id,
                'role': 'related'
            })
            
        # 添加新行到DataFrame
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            self.annotations_df = pd.concat([self.annotations_df, new_df], ignore_index=True)
            
        # 自動保存到文件
        self.save_annotations_to_file()
        
    def save_annotations_to_file(self):
        """保存標注到文件 - 優化版本，使用非同步保存"""
        def save_async():
            try:
                # Ensure category column consistency by converting any array/list values to strings
                if not self.annotations_df.empty and 'category' in self.annotations_df.columns:
                    def convert_category_to_string(cat):
                        if isinstance(cat, (list, tuple)):
                            return ', '.join(map(str, cat))
                        elif hasattr(cat, '__iter__') and not isinstance(cat, str):
                            try:
                                return ', '.join(map(str, cat))
                            except:
                                return str(cat)
                        return str(cat) if cat is not None else ''
                    
                    self.annotations_df['category'] = self.annotations_df['category'].apply(convert_category_to_string)
                
                self.annotations_df.to_parquet(self.annotations_file, index=False)
            except Exception as e:
                print(f"Error saving annotations: {e}")
                # Try to save as CSV as fallback
                csv_file = self.annotations_file.replace('.parquet', '.csv')
                try:
                    self.annotations_df.to_csv(csv_file, index=False)
                    print(f"Saved annotations to CSV instead: {csv_file}")
                except Exception as csv_e:
                    print(f"Failed to save as CSV too: {csv_e}")
        
        # 非同步保存以避免阻塞UI
        threading.Thread(target=save_async, daemon=True).start()
            
    def save_annotations(self):
        """手動保存標注"""
        file_path = filedialog.asksaveasfilename(
            title="Save Annotations",
            defaultextension=".parquet",
            filetypes=[("Parquet files", "*.parquet"), ("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            try:
                if file_path.endswith('.csv'):
                    self.annotations_df.to_csv(file_path, index=False)
                else:
                    self.annotations_df.to_parquet(file_path, index=False)
                messagebox.showinfo("Success", f"Annotations saved to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save annotations: {str(e)}")
                
    def update_speed(self, value):
        """更新播放速度"""
        self.play_speed = int(float(value))
        
    def first_frame(self):
        """跳到第一幀 - 優化版本"""
        # 在標注模式下保存當前frame的標注
        if self.is_annotation_mode:
            self.save_current_annotations()
        self.current_frame = self.frame_range[0]
        # 檢查scenario邊界
        self.check_scenario_boundary()
        # 標記需要重新渲染
        self.render_dirty = True
        self.update_display()
        
    def last_frame(self):
        """跳到最後一幀 - 優化版本"""
        # 在標注模式下保存當前frame的標注
        if self.is_annotation_mode:
            self.save_current_annotations()
        self.current_frame = self.frame_range[1]
        # 檢查scenario邊界
        self.check_scenario_boundary()
        # 標記需要重新渲染
        self.render_dirty = True
        self.update_display()
        
    def prev_frame(self):
        """前一幀 - 優化版本"""
        if self.current_frame > self.frame_range[0]:
            # 在標注模式下保存當前frame的標注
            if self.is_annotation_mode:
                self.save_current_annotations()
            self.current_frame -= 1
            # 在標注模式下延續annotations到新frame
            if self.is_annotation_mode:
                self.propagate_annotations_to_current_frame()
            # 檢查scenario邊界
            self.check_scenario_boundary()
            # 標記需要重新渲染
            self.render_dirty = True
            self.update_display()
            
    def next_frame(self):
        """下一幀 - 優化版本"""
        if self.current_frame < self.frame_range[1]:
            # 在標注模式下保存當前frame的標注
            if self.is_annotation_mode:
                self.save_current_annotations()
            self.current_frame += 1
            # 在標注模式下延續annotations到新frame
            if self.is_annotation_mode:
                self.propagate_annotations_to_current_frame()
            # 檢查scenario邊界
            self.check_scenario_boundary()
            # 標記需要重新渲染
            self.render_dirty = True
            self.update_display()
            
    def toggle_play(self):
        """切換播放/暫停 - 優化版本"""
        if self.is_playing:
            self.stop_play()
        else:
            self.start_play()
            
    def start_play(self):
        """開始播放 - 優化版本"""
        self.is_playing = True
        self.play_button.config(text="||")  # 暫停符號用更簡單的符號
        self.play_thread = threading.Thread(target=self.play_loop, daemon=True)
        self.play_thread.start()
        
    def stop_play(self):
        """停止播放 - 優化版本"""
        self.is_playing = False
        if hasattr(self, 'play_button'):
            self.play_button.config(text="▶")  # 播放符號用更簡單的符號
        
    def play_loop(self):
        """播放循環 - 優化版本，動態調整播放速度"""
        while self.is_playing and self.current_frame < self.frame_range[1]:
            start_time = time.time()
            
            # 在UI線程中執行frame更新
            self.root.after(0, self.next_frame)
            
            # 動態調整延遲時間基於渲染性能
            if hasattr(self, 'last_frame_render_time'):
                # 如果渲染時間超過目標，減少延遲
                target_frame_time = self.play_speed
                if self.last_frame_render_time > 20:  # 如果渲染超過20ms
                    target_frame_time = max(10, target_frame_time - self.last_frame_render_time)
                
                time.sleep(max(0.001, target_frame_time / 1000.0))
            else:
                time.sleep(self.play_speed / 1000.0)
                
        # 播放結束
        self.root.after(0, self.stop_play)
        
    def reset_annotations(self):
        """重置右邊面板的選擇項目 - 優化版本"""
        # 只在標注模式下允許重置
        if not self.is_annotation_mode:
            messagebox.showinfo("Info", "Reset is only available in Annotation Mode.")
            return
            
        result = messagebox.askyesno("Confirm Reset", "Are you sure you want to reset current selections?")
        if result:
            # 僅清空右邊面板的選擇，不涉及CSV檔案
            self.description_text.delete(1.0, tk.END)
            self.category_var.set('')
            self.scenario_id_var.set('')
            self.referred_var.set('')
            for var in self.related_vars.values():
                var.set(False)
            # 更新scenario範圍
            self.update_scenario_range()
            # 清除緩存以確保視覺更新
            self.color_cache.clear()
            self.render_frame_cache.clear()
            # 標記需要重新渲染
            self.render_dirty = True
            self.update_display()
            self.render_scene()

    def on_canvas_click(self, event):
        """處理普通點擊事件 - 選擇referred object - 優化版本"""
        self.root.focus_set()  # 確保窗口保持焦點
        
        # 只在標注模式下處理點擊
        if not self.is_annotation_mode:
            return
            
        # 檢查是否有scenario ID，沒有則創建新的
        if not self.scenario_id_var.get():
            self.new_scenario()
            
        # 檢查點擊位置是否在某個track上
        clicked_track_id = self.find_track_at_position(event.x, event.y)
        
        if clicked_track_id is not None:
            # 確保該track在右側面板中可見（作為refer角色）
            self.ensure_track_in_panel(clicked_track_id, 'refer')
            
            # 設置為referred object，確保類型一致性
            self.referred_var.set(str(int(clicked_track_id)))
            self.on_referred_change()
            
    def on_canvas_ctrl_click(self, event):
        """處理Ctrl+點擊事件 - 切換related objects - 優化版本"""
        self.root.focus_set()  # 確保窗口保持焦點
        
        # 只在標注模式下處理點擊
        if not self.is_annotation_mode:
            return
            
        # 檢查是否有scenario ID，沒有則創建新的
        if not self.scenario_id_var.get():
            self.new_scenario()
            
        # 檢查點擊位置是否在某個track上
        clicked_track_id = self.find_track_at_position(event.x, event.y)
        
        if clicked_track_id is not None:
            # 確保該track在右側面板中可見（作為related角色）
            self.ensure_track_in_panel(clicked_track_id, 'related')
            
            if clicked_track_id in self.related_vars:
                # 切換related object的選擇狀態
                current_state = self.related_vars[clicked_track_id].get()
                self.related_vars[clicked_track_id].set(not current_state)
                self.on_related_change()
                
    def ensure_track_in_panel(self, track_id, role='related'):
        """確保指定的track在右側面板中可見"""
        # 檢查track是否已經在面板中（無論是referred還是related）
        track_exists = (track_id in self.related_vars or 
                       track_id in self.referred_radios)
        
        # 如果track不在當前面板中，添加一個佔位標注
        if not track_exists:
            scenario_id = self.scenario_id_var.get()
            if scenario_id:
                # 創建一個基本標注記錄，讓track出現在面板中
                new_row = pd.DataFrame([{
                    'scenarioId': scenario_id,
                    'description': '',
                    'category': '',
                    'frame': self.current_frame,
                    'trackId': track_id,
                    'role': role  # 使用傳入的角色
                }])
                
                if self.annotations_df is None or self.annotations_df.empty:
                    self.annotations_df = new_row
                else:
                    self.annotations_df = pd.concat([self.annotations_df, new_row], ignore_index=True)
                
                # 標記需要更新UI並立即更新
                self.ui_needs_update = True
                self.update_track_options()
                self.ui_needs_update = False
            
    def find_track_at_position(self, x, y):
        """找到指定位置的track ID"""
        for track_data in self.last_rendered_tracks:
            if self.point_in_polygon(x, y, track_data['pixels']):
                return track_data['track_id']
        return None
        
    def point_in_polygon(self, x, y, polygon):
        """使用ray casting算法檢查點是否在多邊形內"""
        if len(polygon) < 3:
            return False
            
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
            
        return inside
    
    def get_annotated_track_ids(self):
        """獲取當前scenario已標注的所有track IDs"""
        if self.annotations_df is None or self.annotations_df.empty:
            return []
            
        current_scenario_id = self.scenario_id_var.get()
        if not current_scenario_id:
            return []
            
        # 獲取當前scenario的所有已標注track IDs
        scenario_annotations = self.annotations_df[
            self.annotations_df['scenarioId'] == current_scenario_id
        ]
        
        if scenario_annotations.empty:
            return []
            
        # 獲取所有已標注的track IDs並排序
        annotated_tracks = sorted(scenario_annotations['trackId'].unique())
        return annotated_tracks

def main():
    root = tk.Tk()
    app = ScenarioAnnotationTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
