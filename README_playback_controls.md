# 軌跡可視化播放控制功能

## 新增功能

### 鍵盤控制
- **空白鍵 (Space)**: 播放/暫停切換
- **左箭頭 (←)**: 倒轉播放
- **右箭頭 (→)**: 正向播放
- **上箭頭 (↑)**: 加速播放 (最大 5x)
- **下箭頭 (↓)**: 減速播放 (最小 0.2x)
- **R 鍵**: 重置為正常速度和正向播放
- **Escape 鍵**: 退出程式

### 畫面顯示
- **黃色框**: 顯示當前幀數
- **綠色框**: 顯示控制指示和當前狀態
  - 播放狀態 (Playing/Paused)
  - 播放方向 (Forward/Reverse)
  - 播放速度 (0.2x - 5.0x)

### 使用方法
```bash
# 基本使用
python visualize_moving_tags.py --tags tags.csv

# 指定所有參數
python visualize_moving_tags.py \
  --tags tags.csv \
  --trajectory /path/to/trajectory.csv \
  --background /path/to/background.png

# 保存動畫
python visualize_moving_tags.py --tags tags.csv --save --output my_animation.mp4
```

### 技術實現
- 保持原有架構不變
- 新增播放控制變數 (`is_playing`, `is_reverse`, `speed_multiplier`)
- 新增鍵盤事件處理函數 (`on_key_press`)
- 修改動畫幀更新邏輯支援播放控制
- 新增控制狀態顯示

### 注意事項
- 確保 matplotlib 視窗有焦點以接收鍵盤事件
- 播放控制在動畫運行時實時生效
- 倒轉播放會回到之前的幀
- 速度控制會影響幀跳躍的步長
