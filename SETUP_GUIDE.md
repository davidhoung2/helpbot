# 本地安装指南

## 系統要求
- **Python 版本**: 3.11 或 3.12（不支持 3.13，因為 audioop 已移除）
- **作業系統**: Windows、macOS 或 Linux

## 安裝步驟

### 1. 解壓文件
```bash
tar -xzf ChatGPT-Discord-Bot.tar.gz
cd ChatGPT-Discord-Bot
```

### 2. 檢查 Python 版本
```bash
python --version
# 應該顯示 3.11.x 或 3.12.x
```

如果顯示 3.13 或更高版本，請降級到 Python 3.12：
- **Windows**: 從 python.org 下載 3.12 版本
- **macOS**: `brew install python@3.12`
- **Linux**: 使用系統包管理器安装

### 3. 創建虛擬環境（建議）
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 4. 安裝依賴
```bash
pip install -r requirements.txt
```

### 5. 設置環境變量
```bash
cp .env.example .env
# 編輯 .env 文件，添加你的 Discord Bot Token
```

### 6. 運行機器人
```bash
python main.py
```

## 常見問題

### ModuleNotFoundError: No module named 'audioop'
- **原因**: 你使用的是 Python 3.13+（不支持）
- **解決方案**: 降級到 Python 3.11 或 3.12

### ModuleNotFoundError: No module named 'discord'
- **原因**: 依賴未安裝
- **解決方案**: 運行 `pip install -r requirements.txt`

### Bot 無法連接到 Discord
- **原因**: Discord Bot Token 無效或未設置
- **解決方案**: 檢查 `.env` 文件中的 `DISCORD_BOT_TOKEN`

## 需要幫助？
檢查 `replit.md` 了解更多功能和命令說明。
