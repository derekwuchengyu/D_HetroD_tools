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
        self.max_cache_size = 5
        
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
        
        # Scenario ID選擇/輸入
        id_frame = ttk.Frame(scenario_frame)
        id_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(id_frame, text="Scenario ID:").pack(side=tk.LEFT)
        self.scenario_id_var = tk.StringVar()
        self.scenario_id_combo = ttk.Combobox(id_frame, textvariable=self.scenario_id_var, width=15, font=self.combobox_font)
        self.scenario_id_combo.pack(side=tk.LEFT, padx=(5, 5))
        self.scenario_id_combo.bind('<<ComboboxSelected>>', self.on_scenario_id_change)
        self.scenario_id_combo.bind('<KeyRelease>', self.on_scenario_id_change)
        
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
        
        # 分類選擇
        ttk.Label(desc_frame, text="Category:").pack(anchor=tk.W)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(desc_frame, textvariable=self.category_var, 
                                          values=self.categories, state="readonly", font=self.combobox_font)
        self.category_combo.pack(fill=tk.X, pady=(2, 0))
        self.category_combo.bind('<<ComboboxSelected>>', self.on_category_change)
        
        # Referred Object區域
        referred_frame = ttk.LabelFrame(parent, text="Referred Object (Single Select)", padding=10)
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
        related_frame = ttk.LabelFrame(parent, text="Related Objects (Multiple Select)", padding=10)
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
        tracks_file = "/home/hcis-s19/Documents/ChengYu/HetroD_sample/00_tracks_0-367.csv"
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
        """載入軌跡數據"""
        try:
            self.tracks_df = pd.read_csv(file_path)
            
            # 獲取frame範圍
            frames = sorted(self.tracks_df['frame'].unique())
            self.frame_range = (frames[0], frames[-1])
            self.current_frame = frames[0]
            
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
            scenario_ids = sorted(self.annotations_df['scenarioId'].unique())
            self.scenario_id_combo['values'] = scenario_ids
            
    def create_empty_annotations(self):
        """創建空的標注數據"""
        self.annotations_df = pd.DataFrame(columns=[
            'scenarioId', 'description', 'category', 'frame', 'trackId', 'role'
        ])
        
    def toggle_mode(self):
        """切換標注模式和Replay模式"""
        self.is_annotation_mode = not self.is_annotation_mode
        
        if self.is_annotation_mode:
            self.mode_button.config(text="Replay Mode")
        else:
            self.mode_button.config(text="Annotation Mode")
            # 當切換到Replay模式時，更新scenario範圍
            self.update_scenario_range()
        
        # 標記需要UI更新以確保狀態正確應用
        self.ui_needs_update = True
        
        # 更新右側面板的狀態
        self.update_annotation_panel_state()
        
        # 重新渲染場景
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
                    # Scenario ID combo box 在兩種模式下都保持啟用
                    if child == self.scenario_id_combo:
                        child.config(state='normal')
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
        """更新track選項 - 優化版本，避免不必要的UI重建"""
        if self.tracks_df is None:
            return
        
        # 確保相關變數存在，避免渲染時出錯
        if not hasattr(self, 'related_vars'):
            self.related_vars = {}
            
        # 只有在明確需要更新UI時才進行更新（例如切換scenario）
        if not self.ui_needs_update:
            return
            
        # 獲取當前frame的所有trackID
        current_tracks = self.get_current_tracks()
        track_ids = sorted(current_tracks['trackId'].unique()) if not current_tracks.empty else []
        
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
        
        # 添加referred object選項 (五列排列)
        self.create_five_column_layout(self.referred_content_frame, track_ids, 'referred')

        # 添加related objects選項 (五列排列)
        self.create_five_column_layout(self.related_content_frame, track_ids, 'related')

        # 在標注模式下恢復之前的選擇狀態（如果track還存在的話）
        if self.is_annotation_mode:
            if current_referred and current_referred in [str(tid) for tid in track_ids]:
                self.referred_var.set(current_referred)
                
            for track_id in track_ids:
                if track_id in current_related and track_id in self.related_vars:
                    self.related_vars[track_id].set(current_related[track_id])
        
        # 更新狀態追蹤
        self.last_track_ids = track_ids.copy()
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
                    text=f"T_{track_id}",
                    variable=self.referred_var,
                    value=str(track_id),
                    command=self.on_referred_change,
                    state=widget_state
                )
                radio.pack(anchor=tk.W, pady=1)
                self.referred_radios[track_id] = radio
            else:  # related
                var = tk.BooleanVar()
                checkbox = ttk.Checkbutton(
                    columns[col_idx],
                    text=f"T_{track_id}",
                    variable=var,
                    command=self.on_related_change,
                    state=widget_state
                )
                checkbox.pack(anchor=tk.W, pady=1)
                self.related_vars[track_id] = var
                self.related_checkboxes[track_id] = checkbox
            
    def get_current_tracks(self):
        """獲取當前frame的軌跡數據"""
        if self.tracks_df is None:
            return pd.DataFrame()
        return self.tracks_df[self.tracks_df['frame'] == self.current_frame]
        
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
            
        # 更新左側圖像以反映變化
        self.update_display_left_only()
        
    def check_scenario_boundary(self):
        """檢查是否超出當前scenario的frame範圍"""
        current_scenario_id = self.scenario_id_var.get()
        if not current_scenario_id:
            return
            
        # 獲取當前scenario的frame範圍
        scenario_range = self.get_scenario_frame_range(current_scenario_id)
        if scenario_range is None:
            return
            
        scenario_min, scenario_max = scenario_range
        
        # 如果當前frame超出了scenario的最大frame，重置選擇
        if self.current_frame > scenario_max:
            self.reset_selections_to_initial_state()
        
    def update_display(self):
        """更新顯示 - 分離左右側更新"""
        self.update_frame_label()
        # 只有在需要更新UI時才更新右側（例如切換scenario）
        if self.ui_needs_update:
            self.update_track_options()  # 只在必要時更新右側UI
            self.load_current_annotations()
        self.render_scene()  # 總是更新左側場景
    
    def update_display_left_only(self):
        """只更新左側圖像顯示，不更新右側UI"""
        self.update_frame_label()
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
                self.referred_var.set(str(referred_tracks[0]))
            else:
                self.referred_var.set('')
                
            # 設置related objects（多選）
            for track_id, var in self.related_vars.items():
                var.set(track_id in related_tracks)
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
        """渲染場景 - 優化版本，使用背景緩存"""
        self.canvas.delete("all")
        
        if self.background_image is None:
            return
            
        # 獲取canvas實際大小
        canvas_width = self.canvas.winfo_width() or 800
        canvas_height = self.canvas.winfo_height() or 600
        current_canvas_size = (canvas_width, canvas_height)
        
        # 檢查背景緩存
        if (self.last_canvas_size != current_canvas_size or 
            current_canvas_size not in self.background_cache):
            
            # 保持背景圖片的原始比例，縮放到適合canvas
            bg_width, bg_height = self.background_image.size
            scale_x = canvas_width / bg_width
            scale_y = canvas_height / bg_height
            scale = min(scale_x, scale_y)  # 保持比例
            
            new_width = int(bg_width * scale)
            new_height = int(bg_height * scale)
            
            bg_resized = self.background_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # 計算居中位置
            offset_x = (canvas_width - new_width) // 2
            offset_y = (canvas_height - new_height) // 2
            
            # 創建完整大小的圖像，背景為白色
            background_base = Image.new('RGB', (canvas_width, canvas_height), 'white')
            background_base.paste(bg_resized, (offset_x, offset_y))
            
            # 緩存背景圖像和相關參數
            self.background_cache[current_canvas_size] = {
                'image': background_base.copy(),
                'scale': scale,
                'offset_x': offset_x,
                'offset_y': offset_y
            }
            
            # 限制緩存大小
            if len(self.background_cache) > self.max_cache_size:
                # 移除最舊的緩存項目
                oldest_key = next(iter(self.background_cache))
                del self.background_cache[oldest_key]
            
            self.last_canvas_size = current_canvas_size
        
        # 從緩存獲取背景
        cache_data = self.background_cache[current_canvas_size]
        full_image = cache_data['image'].copy()
        scale = cache_data['scale']
        offset_x = cache_data['offset_x']
        offset_y = cache_data['offset_y']
        
        # 在背景上繪製bounding boxes
        draw = ImageDraw.Draw(full_image)
        current_tracks = self.get_current_tracks()
        if not current_tracks.empty:
            for _, track in current_tracks.iterrows():
                self.draw_bbox(draw, track, canvas_width, canvas_height, scale, offset_x, offset_y)
                
        # 顯示圖片
        self.photo = ImageTk.PhotoImage(full_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        

        
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

                    # Draw text background
                    draw.rectangle([center_px - 2, center_py - 2 + shift_y, 
                                  center_px + text_width + 2, center_py + text_height + 2 + shift_y], 
                                 fill='white', outline='black')
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
            if str(int(track_id)) == self.referred_var.get():
                return 'red'  # referred object用紅色
            elif track_id in self.related_vars and self.related_vars[track_id].get():
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
            current_values.sort()  # 保持排序
            self.scenario_id_combo['values'] = current_values
        
        # 設置為當前選擇
        self.scenario_id_var.set(new_id)
        self.current_scenario_id = new_id
        
        # 清空當前標注（但保留checked items）
        self.description_text.delete(1.0, tk.END)
        self.category_var.set('')
        
        # 標記需要UI更新（創建新scenario時需要清空選擇）
        self.ui_needs_update = True
        
        # 更新顯示
        self.update_display()
        
    def on_referred_change(self):
        """referred object改變時的處理"""
        self.current_referred = self.referred_var.get()
        # 只在標注模式下保存
        if self.is_annotation_mode:
            self.save_current_annotations()
        self.update_display_left_only()  # 只更新左側圖像
        
    def on_related_change(self):
        """related objects改變時的處理"""
        self.current_related = {
            track_id for track_id, var in self.related_vars.items() 
            if var.get()
        }
        # 只在標注模式下保存
        if self.is_annotation_mode:
            self.save_current_annotations()
        self.update_display_left_only()  # 只更新左側圖像
        
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
                    'trackId': int(referred),
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
                'trackId': int(referred),
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
        """保存標注到文件"""
        try:
            # Ensure category column consistency by converting any array/list values to strings
            if not self.annotations_df.empty and 'category' in self.annotations_df.columns:
                def convert_category_to_string(cat):
                    if isinstance(cat, (list, tuple)):
                        return ', '.join(map(str, cat))
                    elif hasattr(cat, '__iter__') and not isinstance(cat, str):
                        # Handle numpy arrays and other iterable types
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
        """跳到第一幀"""
        # 在標注模式下保存當前frame的標注
        if self.is_annotation_mode:
            self.save_current_annotations()
        self.current_frame = self.frame_range[0]
        # 檢查scenario邊界
        self.check_scenario_boundary()
        self.update_display()
        
    def last_frame(self):
        """跳到最後一幀"""
        # 在標注模式下保存當前frame的標注
        if self.is_annotation_mode:
            self.save_current_annotations()
        self.current_frame = self.frame_range[1]
        # 檢查scenario邊界
        self.check_scenario_boundary()
        self.update_display()
        
    def prev_frame(self):
        """前一幀"""
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
            self.update_display()
            
    def next_frame(self):
        """下一幀"""
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
            self.update_display()
            
    def toggle_play(self):
        """切換播放/暫停"""
        if self.is_playing:
            self.stop_play()
        else:
            self.start_play()
            
    def start_play(self):
        """開始播放"""
        self.is_playing = True
        self.play_button.config(text="||")  # 暫停符號用更簡單的符號
        self.play_thread = threading.Thread(target=self.play_loop, daemon=True)
        self.play_thread.start()
        
    def stop_play(self):
        """停止播放"""
        self.is_playing = False
        if hasattr(self, 'play_button'):
            self.play_button.config(text="▶")  # 播放符號用更簡單的符號
        
    def play_loop(self):
        """播放循環"""
        while self.is_playing and self.current_frame < self.frame_range[1]:
            time.sleep(self.play_speed / 1000.0)
            if self.is_playing:  # 再次檢查
                self.root.after(0, self.next_frame)
                
        # 播放結束
        self.root.after(0, self.stop_play)
        
    def reset_annotations(self):
        """重置右邊面板的選擇項目"""
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
            # messagebox.showinfo("Reset Complete", "Current selections have been reset.")

def main():
    root = tk.Tk()
    app = ScenarioAnnotationTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()
