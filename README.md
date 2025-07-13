# OpenCores 爬蟲程式 (Selenium 版本)

## 功能介紹

這是一個基於 Selenium 的專業級 OpenCores 網站爬蟲程式，可以：
- 🔐 使用真實瀏覽器自動登入 OpenCores 網站
- 🌐 處理 JavaScript 渲染的動態內容和分類展開
- 📊 智能分析項目分類和文件狀態
- 📁 自動下載有文件的項目（file_state = 'yes'）
- 📦 自動解壓縮 .tar.gz 文件
- 🔄 支援續傳功能（跳過已下載的項目）
- 🎛️ 支援有頭/無頭模式運行
- ⚙️ 豐富的命令行參數配置

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

**重要：** 此版本需要安裝 Chrome 瀏覽器。程式會自動下載並管理 ChromeDriver。

### 2. 設置環境變數

在 Windows 系統中：
```powershell
$env:OPENCORES_USERNAME="your_username"
$env:OPENCORES_PASSWORD="your_password"
```

在 Linux/Mac 系統中：
```bash
export OPENCORES_USERNAME="your_username"
export OPENCORES_PASSWORD="your_password"
```

### 3. 運行程式

基本用法：
```bash
python crawler.py
```

帶參數運行：
```bash
# 無頭模式運行
python crawler.py --headless

# 自訂下載路徑
python crawler.py --download-path ./my_downloads

# 清空下載路徑重新開始
python crawler.py --clean-download-path

# 保留壓縮檔案
python crawler.py --keep-compressed

# 組合使用
python crawler.py --headless --download-path ./downloads --clean-download-path
```

## 核心功能特性

### 🌟 Selenium 優勢
- **真實瀏覽器環境**：完全模擬真實用戶操作
- **JavaScript 支援**：處理動態加載的內容和分類展開
- **反爬蟲對策**：更難被網站檢測為爬蟲
- **穩定登入**：基於元素檢測的可靠登入機制

### 📊 智能項目分析
- **分類展開**：自動展開所有項目分類
- **狀態檢測**：識別項目文件狀態（yes/no/external）
- **選擇性下載**：只下載有文件的項目
- **統計報告**：顯示各分類項目數量統計

### 📦 自動文件處理
- **自動解壓縮**：支援 .tar.gz 文件自動解壓
- **智能組織**：按項目名稱組織文件結構
- **可選保留**：可選擇保留或刪除原始壓縮檔

### 🔄 續傳功能
- **斷點續傳**：自動跳過已下載的項目
- **狀態記錄**：記錄處理進度
- **增量更新**：只下載新項目

### 🎛️ 靈活配置
- **命令行參數**：豐富的運行選項
- **路徑自訂**：可指定下載目錄
- **模式選擇**：有頭/無頭模式切換

## 配置選項

### 環境變數
| 變數名 | 必需 | 說明 | 預設值 |
|--------|------|------|--------|
| `OPENCORES_USERNAME` | ✅ | OpenCores 用戶名 | - |
| `OPENCORES_PASSWORD` | ✅ | OpenCores 密碼 | - |

### 命令行參數
| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| `--headless` | bool | 是否使用無頭模式 | False |
| `--tags` | flag | 是否包含標籤資訊 | False |
| `--project-info` | flag | 是否僅收集項目資訊（不下載） | False |
| `--keep-compressed` | flag | 是否保留原始壓縮檔案 | False |
| `--download-path` | str | 指定下載目錄路徑 | 'downloads' |
| `--clean-download-path` | flag | 清空下載目錄重新開始 | False |

### 使用範例
```bash
# 基本下載
python crawler.py

# 無頭模式 + 自訂路徑
python crawler.py --headless --download-path ./my_downloads

# 重新開始下載所有項目
python crawler.py --clean-download-path

# 僅收集項目資訊，不下載文件
python crawler.py --project-info

# 包含標籤信息的分析
python crawler.py --tags --project-info
```

## 輸出結構

程式會在指定目錄建立以下結構：

```
downloads/
├── project_name_1/
|   └── project_name_1/       # 解壓縮資料夾結構
│       ├── src/              # 自動解壓縮的源代碼
│       ├── doc/              # 自動解壓縮的文檔
│       ├── rtl/              # 自動解壓縮的RTL文件
│       └── README.md         # 項目說明
├── project_name_2/
|   └── project_name_2/
│       ├── verilog/
│       ├── testbench/
│       └── synthesis/
└── ...
```

### 文件處理說明
- ✅ **自動解壓縮**：.tar.gz 文件會自動解壓到項目目錄
- 🗑️ **清理壓縮檔**：預設刪除原始壓縮檔（可用 `--keep-compressed` 保留）
- 📁 **智能組織**：按項目名稱分類組織
- 🔄 **續傳支援**：已存在的項目目錄會被跳過

## 日誌和錯誤處理

程式會產生以下檔案：
- `opencores_crawler.log` - 詳細的操作日誌
- `failed_downloads.json` - 失敗的下載記錄

## 技術細節

### 登入機制
- 使用 Selenium 自動化填寫登入表單
- 支援自動勾選「記住我」選項  
- 同步 cookies 到 requests session 用於檔案下載
- 基於 "My account" 連結檢測登入狀態

### 項目分析流程
1. **分類展開**：自動點擊所有分類標題展開內容
2. **狀態檢測**：分析項目文件狀態（yes/no/external）
3. **選擇性處理**：只下載有文件的項目
4. **統計報告**：提供詳細的分類統計信息

### 下載和解壓縮
- **智能下載**：使用固定URL格式 `{base_url}/download/{project_name}`
- **自動解壓縮**：檢測 .tar.gz 文件並自動解壓
- **安全檢查**：防止路徑遍歷攻擊
- **文件管理**：可選保留或刪除原始壓縮檔

### 爬取策略
- 使用 Selenium 處理 JavaScript 動態內容
- 智能等待頁面和分類加載完成
- 使用 requests 下載大文件（效率更高）
- 續傳功能：檢查已存在的項目目錄

### 效能優化
- 隱式等待：10 秒
- 顯式等待：15 秒（用於特定元素）
- 自動資源清理

## 工作流程

### 執行步驟
1. **🔐 登入驗證**
   - 自動填寫登入表單
   - 檢測 "My account" 連結確認登入狀態
   - 同步 cookies 到下載會話

2. **📊 項目分析**
   - 訪問 `/projects` 頁面
   - 自動展開所有分類
   - 分析項目文件狀態
   - 生成統計報告

3. **📁 智能下載**
   - 過濾有文件的項目（file_state = 'yes'）
   - 跳過已下載的項目（續傳）
   - 使用固定URL格式下載

4. **📦 自動處理**
   - 檢測 .tar.gz 文件格式
   - 自動解壓縮到項目目錄
   - 可選刪除原始壓縮檔

### 日誌輸出範例
```
正在訪問項目頁面: https://opencores.org/projects
=== 展開所有分類 ===
找到 12 個分類
展開第 1 個分類
...
=== 收集項目資訊 ===
正在處理分類: Arithmetic core
找到 119 個項目
...
總共找到 1234 個項目
過濾後可下載項目: 856/1234
處理項目 1/856: project_name (分類: Arithmetic core)
下載成功: downloads/project_name/project_name.tar.gz
成功解壓縮 125 個文件到 downloads/project_name
爬取完成！成功處理 856/856 個項目
```

## 系統需求

### 必需軟體
- Python 3.7+
- Google Chrome 瀏覽器
- 網路連接

### 推薦配置
- RAM: 4GB+
- 儲存空間: 根據要下載的項目數量而定
- 網路: 穩定的寬頻連接

## 故障排除

### 常見問題

#### 1. ChromeDriver 相關錯誤
```
WebDriverException: Message: 'chromedriver' executable needs to be in PATH
```
**解決方法：**
- 確保已安裝 `webdriver-manager`
- 檢查網路連接（需要下載 ChromeDriver）
- 在中國大陸可能需要設置代理

#### 2. 登入失敗
```
登入失敗，請檢查用戶名和密碼
```
**解決方法：**
- 確認環境變數設置正確
- 檢查 OpenCores 帳號是否有效
- 確認網站是否正常運作

#### 3. 元素找不到
```
NoSuchElementException: Unable to locate element
```
**解決方法：**
- 網站結構可能已更改
- 增加等待時間
- 檢查網路連接

### 除錯模式

使用有頭模式進行除錯：
```bash
# 顯示瀏覽器窗口
python crawler.py

# 或明確指定
python crawler.py --headless false
```

查看詳細日誌：
```bash
tail -f opencores_crawler.log
```

## 最佳實踐

### 1. 使用專用帳號
- 建議使用專門的 OpenCores 帳號
- 避免使用主要帳號

### 2. 下載策略
- **批量下載**：直接運行進行完整下載
- **續傳下載**：程式會自動跳過已下載的項目

### 3. 存儲管理
- **自訂路徑**：使用 `--download-path` 指定下載目錄
- **清理重啟**：使用 `--clean-download-path` 重新開始
- **壓縮檔案**：根據需要決定是否保留原始檔案

### 4. 監控和除錯
- 使用有頭模式觀察瀏覽器操作
- 監控日誌檔案瞭解處理進度
- 注意記憶體和磁碟空間使用

## 更新日誌

### v3.0.0 (智能版本)
- ✨ 新增命令行參數支援
- ✨ 智能項目分類分析和展開
- ✨ 項目文件狀態檢測（yes/no/external）
- ✨ 自動解壓縮 .tar.gz 功能
- ✨ 續傳功能：跳過已下載項目
- ✨ 選擇性下載：只下載有文件的項目
- ✨ 自訂下載路徑支援
- ✨ 統計報告：分類項目數量分析
- 🔧 優化登入檢測機制
- 🔧 改善文件組織結構
- 🔧 更好的錯誤處理和日誌

### v2.0.0 (Selenium 版本)
- ✨ 完全重寫為 Selenium 實現
- ✨ 支援 JavaScript 渲染的動態內容
- ✨ 新增無頭模式支援
- ✨ 自動 WebDriver 管理
- ✨ 更穩定的登入機制
- ✨ 智能等待機制
- 🔧 改善錯誤處理
- 🔧 優化資源管理

### v1.0.0 (requests 版本)
- 基本的 requests + BeautifulSoup 實現
- 基礎登入和下載功能

## 許可證

本程式僅供學習和研究使用。下載的內容請遵守相應的開源許可證。

## 貢獻

如果您發現問題或有改善建議，歡迎提出 issue 或 pull request。

## 技術支援

如遇到問題，請：
1. 查看日誌檔案 `opencores_crawler.log`
2. 檢查系統需求是否滿足
3. 確認環境變數設置正確
4. 嘗試使用有頭模式進行除錯 