# Scenario Annotation Tool 使用說明

## 功能概述

這是一個用於標注自動駕駛scenario的Python工具，具備以下主要功能：

1. **左側顯示背景 + bbox** - 視覺化顯示軌跡數據和bounding boxes
2. **Frame標籤顯示** - 只更新frame數字，不重畫整個圖像
3. **右側三區塊標注面板**：
   - Scenario description + Category
   - Referred object (單選)
   - Related objects (多選)
4. **自動載入trackID** - 根據當前frame動態更新可選的軌跡ID
5. **自動保存annotations.csv** - 每次標注變更自動保存
6. **播放控制** - 支援播放/暫停、前後移動、Reset功能

## 文件結構

```
scenario_annotation_tool.py    # 主程序
test_annotation_tool.py       # 測試腳本
annotations.csv               # 標注結果文件
00_tracks_358-367.csv        # 軌跡數據
00_background.png            # 背景圖片
```

## 使用方法

### 1. 啟動工具

```bash
cd /home/hcis-s19/Documents/ChengYu/HetroD_sample
python scenario_annotation_tool.py
```

### 2. 界面說明

#### 左側面板（可視化區域）
- **主顯示區域**: 顯示背景圖片和bounding boxes
- **Frame控制**: 顯示當前frame號碼
- **播放控制按鈕**:
  - ⏮ : 跳到第一幀
  - ⏪ : 前一幀
  - ▶/⏸ : 播放/暫停
  - ⏩ : 下一幀
  - ⏭ : 跳到最後一幀
  - Reset : 重置所有標注
- **速度控制**: 調整播放速度 (50-1000ms)

#### 右側面板（標注區域）

1. **Scenario Description & Category**
   - Description: 文本描述框，可輸入scenario的詳細描述
   - Category: 下拉選單，包含預定義的scenario類別：
     - Lane Change (變道)
     - Overtaking (超車)
     - Intersection (路口)
     - Merge (匯入)
     - Cut-in (切入)
     - Following (跟車)
     - Turning (轉彎)
     - Emergency (緊急)
     - Other (其他)

2. **Referred Object (Single Select)**
   - 單選按鈕列表
   - 選擇主要關注的軌跡對象
   - 選中的軌跡會以紅色顯示

3. **Related Objects (Multiple Select)**
   - 複選框列表
   - 可選擇多個相關的軌跡對象
   - 選中的軌跡會以藍色顯示

4. **文件操作按鈕**
   - Load Tracks: 載入軌跡CSV文件
   - Load Background: 載入背景圖片
   - Save Annotations: 手動保存標注文件

### 3. 標注流程

1. **載入數據**: 工具會自動載入默認的軌跡數據和背景圖片
2. **選擇frame**: 使用播放控制按鈕移動到要標注的frame
3. **輸入描述**: 在Description框中描述當前scenario
4. **選擇分類**: 從Category下拉選單選擇適當的分類
5. **選擇對象**: 
   - 在Referred Object中選擇主要關注的軌跡
   - 在Related Objects中選擇相關的軌跡
6. **自動保存**: 標注會自動保存到annotations.csv
7. **繼續標注**: 移動到下一frame，工具會延續前一幀的分類選項

### 4. 顏色編碼

- **綠色**: 普通軌跡
- **紅色**: Referred object (主要關注對象)
- **藍色**: Related objects (相關對象)

### 5. 數據格式

#### 軌跡數據 (CSV格式)
必須包含以下列：
- `trackId`: 軌跡ID
- `frame`: 幀號
- `xCenter`, `yCenter`: 中心坐標
- `width`, `length`: 寬度和長度
- `heading`: 航向角

#### 標注數據 (annotations.csv)
包含以下列：
- `frame`: 幀號
- `scenario description`: scenario描述
- `category`: 分類
- `referred`: 主要關注對象ID
- `related`: 相關對象ID列表 (逗號分隔)

## 特色功能

### 1. 智能frame切換
- 只更新frame標籤，不重新渲染整個圖像
- 自動載入當前frame的軌跡列表
- 延續前一幀的分類選項

### 2. 實時標注保存
- 每次修改描述、分類或對象選擇時自動保存
- 不需要手動保存操作
- 防止數據丟失

### 3. 改進的bounding box繪製
- 使用正確的坐標轉換
- 支援旋轉的bounding boxes
- 根據選擇狀態動態改變顏色

### 4. 用戶友好的界面
- 滾動式軌跡選擇列表
- 直觀的播放控制
- 可調整的播放速度

## 故障排除

### 常見問題

1. **工具無法啟動**
   ```bash
   # 檢查必要的Python包
   python -c "import tkinter, pandas, numpy, PIL; print('All packages available')"
   ```

2. **背景圖片不顯示**
   - 確認00_background.png文件存在
   - 使用"Load Background"按鈕手動載入

3. **軌跡數據載入失敗**
   - 確認CSV文件格式正確
   - 檢查必要的列是否存在

4. **bounding box位置不正確**
   - 檢查ortho_px_to_meter參數設置
   - 確認座標系統的一致性

### 測試工具

運行測試腳本來驗證功能：
```bash
python test_annotation_tool.py
```

## 技術細節

### 座標轉換
- 使用`ortho_px_to_meter = 0.0499967249445942`進行像素到米的轉換
- 支援任意角度的bounding box旋轉

### 多線程播放
- 播放功能使用獨立線程，不會阻塞UI
- 支援暫停和速度調整

### 數據持久化
- 使用pandas DataFrame進行數據管理
- CSV格式便於後續處理和分析

## 擴展建議

1. **添加更多分類**: 可在`categories`列表中添加新的scenario類型
2. **自定義顏色**: 修改`get_track_color`方法自定義顯示顏色
3. **批量操作**: 添加批量標注功能
4. **導出功能**: 支援導出為其他格式(JSON, XML等)
5. **快捷鍵**: 添加鍵盤快捷鍵支援

## 聯繫資訊

如有問題或建議，請聯繫開發團隊。
