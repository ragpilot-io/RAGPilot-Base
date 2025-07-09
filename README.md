![sidebar_logo](https://github.com/nickchen1998/RAGPilot/blob/main/static/w_sidebar_logo.png?raw=true)

---

# 🎯 數據領航員（RAGPilot）

> **_本專所呈現之資料皆為網路爬取之公開資料，站台僅提資料的呈現、查詢、請求，若要使用本站台中的內容進行任何的分析、商業、醫療...等其他功能，請務必核實資料正確性。_**

---

## ⚒️ Built With

- [Python](https://www.python.org/) - Python Programming Language
- [Django](https://www.djangoproject.com/) - Python Web Framework
- [django-allauth](https://django-allauth.readthedocs.io/) - Authentication & Social Login
- [Postgres](https://www.postgresql.org/) - Database with pgvector
- [Redis](https://redis.io/) - Caching & Celery Backend
- [OpenAI](https://openai.com/) - AI Model
- [Cohere](https://cohere.ai/) - AI Model
- [LangChain](https://www.langchain.com/) - LLM Framework
- [Celery](https://docs.celeryproject.org/en/stable/) - Asynchronous Task Queue
- [Tailwind CSS](https://tailwindcss.com/) - CSS Framework (CDN)
- [daisyUI](https://daisyui.com/) - Tailwind CSS Components (CDN)

---

## 🗂️ 專案結構

```
RAGPilot/
├── RAGPilot/              # Django 專案設定
│   ├── settings.py          # 主要設定檔
│   ├── wsgi.py             # WSGI 配置
│   └── urls.py             # URL 路由
├── home/                   # 首頁應用
├── profiles/               # 用戶資料應用
├── conversations/          # 對話記錄應用
├── crawlers/               # 爬蟲數據統一管理
│   ├── models/             # 資料模型
│   ├── views/              # 網頁視圖
│   ├── tools/              # LangChain 工具
│   └── admin.py            # 管理介面
├── celery_app/             # Celery 任務
│   ├── tasks/              # 任務定義
│   └── crawlers/           # 爬蟲任務實作
├── templates/              # HTML 模板
├── utils/                  # 工具函數
└── docker-compose.yml      # Docker 配置
```

---

## 🚀 快速開始

### 1️⃣ 安裝依賴套件

**請先下載 Python3.11 以上版本以及 Poetry 套件管理器**

建議使用 Poetry 管理依賴：

```bash
# 安裝 Python 依賴
poetry install

# 如果是從 WebSocket 版本升級，請先更新依賴
poetry update
```

> **注意**: 如果您是從之前的 WebSocket 版本升級，請執行 `poetry update` 來移除舊的 WebSocket 依賴並安裝新的 HTTP API 依賴。

### 2️⃣ 環境變數設定

於專案根目錄下建立 `.env` 檔案：

```dotenv
# Django 基本設定
DJANGO_SECRET_KEY=your-super-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# API 金鑰
OPENAI_API_KEY=your-openai-api-key
COHERE_API_KEY=your-cohere-api-key

# Google OAuth 設定（取得方式詳見第六步）
GOOGLE_OAUTH2_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-google-client-secret
```

### 3️⃣ 啟動資料庫服務

```bash
# 啟動基本服務（PostgreSQL + Redis + Selenium Hub + Chrome + Conversation Queue）
docker-compose up -d --build
```

### 4️⃣ 資料庫初始化

```bash
# 若日後資料表有更動（選用）
python manage.py makemigrations

# 執行資料庫遷移
python manage.py migrate

# 創建超級用戶
python manage.py createsuperuser
```

### 5️⃣ 啟動應用程式

```bash
# 啟動 Django 開發服務器
python manage.py runserver
```

### 6️⃣ Google OAuth 設定

本專案支援 Google OAuth 登入功能，讓用戶可以使用 Google 帳戶快速註冊和登入。

#### 🔧 Google Cloud Console 設定

1. **創建 OAuth 應用程式**：
   - 前往 [Google Cloud Console](https://console.cloud.google.com/)
   - 創建新專案或選擇現有專案
   - 啟用 Google+ API（在「API 和服務」→「程式庫」中搜尋並啟用）

2. **設定 OAuth 2.0 憑證**：
   - 在「API 和服務」→「憑證」中點擊「建立憑證」→「OAuth 用戶端 ID」
   - 選擇應用程式類型：「網路應用程式」
   - 設定授權重新導向 URI：
     - 開發環境：`http://localhost:8000/accounts/google/login/callback/`
     - 生產環境：`https://yourdomain.com/accounts/google/login/callback/`

3. **設定環境變數**：
   - 將 Client ID 和 Client Secret 添加到 `.env` 檔案：
   ```
   GOOGLE_OAUTH_CLIENT_ID=your_google_client_id_here
   GOOGLE_OAUTH_CLIENT_SECRET=your_google_client_secret_here
   ```

4. **將設定寫入 Postgres**：
   ```bash
   python manage.py setup_google_oauth
   ```

### 7️⃣ 訪問應用

- **Web 應用**: http://localhost:8000
- **管理後台**: http://localhost:8000/admin/

---

## 🐳 Docker 完整部署

### 啟動所有服務

```bash
# 啟動基本服務（PostgreSQL + Redis + Selenium Hub + Chrome + Conversation Queue）
docker-compose up -d --build

# 啟動完整服務（包含爬蟲、站台），在本地開發時不需要使用
docker-compose --profile production up -d
```

### 服務說明

- **postgres** - PostgreSQL 資料庫 (含 pgvector)
- **redis** - Redis 服務 (Celery Backend & Caching)
- **celery-beat** - Celery 排程服務
- **celery-*-worker** - Celery 工作進程
- **django** - Django 應用服務器（生產環境使用 Gunicorn）

### 生產環境部署

生產環境建議使用 Docker Compose，內建使用 Gunicorn 作為 WSGI 服務器：

```bash
# 生產環境部署（包含所有服務）
docker-compose --profile production up -d

# 或者手動啟動 Django 服務器
gunicorn RAGPilot.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

---

## 🎨 前端開發

### 樣式框架

本專案使用 **CDN 版本** 的 Tailwind CSS 和 daisyUI：

- **Tailwind CSS**: https://cdn.tailwindcss.com
- **daisyUI**: https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css

### 開發流程

1. **修改 HTML 模板**: 直接在 `templates/` 中編輯 HTML
2. **使用 Tailwind 類**: 無需建構步驟，直接使用 Tailwind CSS 類
3. **daisyUI 組件**: 直接使用 daisyUI 提供的組件類
4. **即時預覽**: 修改後儲存即可立即看到效果

---

## 📝 注意事項

1. **資料庫**: 需要 PostgreSQL 並啟用 pgvector 擴展
2. **API 金鑰**: 確保設定正確的 OpenAI 和 Cohere API 金鑰
3. **環境變數**: 生產環境請使用安全的 SECRET_KEY 和密碼
4. **Google OAuth**: 如啟用，請確保重定向 URI 設定正確
5. **智能輪詢**: 系統使用 API 輪詢機制，只在有待處理訊息時才輪詢，減少資源消耗

---

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request 來改善這個專案！
