![sidebar\_logo](/static/w_sidebar_logo.png?raw=true)

---

# 🎯 數據領航員企業版（RAGPilot Enterprise）

> ***本系統所有資料均來自用戶自行上傳與管理之內容，平台僅提供資料的查詢、比對與分析功能。若欲進一步用於商業或醫療用途，請務必再次確認資料來源之正確性與時效性。
***

---

## ⚒️ Built With

* [Python](https://www.python.org/) - Python Programming Language
* [Django](https://www.djangoproject.com/) - Python Web Framework
* [Postgres](https://www.postgresql.org/) - Database with pgvector
* [Redis](https://redis.io/) - Caching & Celery Backend
* [OpenAI](https://openai.com/) - AI Model
* [Cohere](https://cohere.ai/) - AI Model
* [LangChain](https://www.langchain.com/) - LLM Framework
* [Celery](https://docs.celeryproject.org/en/stable/) - Asynchronous Task Queue
* [Tailwind CSS](https://tailwindcss.com/) - CSS Framework (CDN)
* [daisyUI](https://daisyui.com/) - Tailwind CSS Components (CDN)

---

## 🗂️ 專案結構

```
RAGPilot/
├── RAGPilot/              # Django 專案設定
│   ├── settings.py
│   ├── wsgi.py
│   └── urls.py
├── home/                  # 首頁與系統儀表板
├── profiles/              # 用戶資料與配額設定
├── conversations/         # 問答與紀錄管理
├── celery_app/            # 非同步任務模組
│   ├── tasks/
├── templates/             # HTML 模板
├── utils/                 # 工具函數
└── docker-compose.yml     # Docker 配置
```

---

## 🚀 快速開始

### 1️⃣ 安裝依賴套件

請先安裝 Python 3.11+ 與 Poetry：

```bash
# 安裝依賴
poetry install
```

### 2️⃣ 設定環境變數

於專案根目錄建立 `.env` 檔案：

```dotenv
# API 金鑰
OPENAI_API_KEY=your-openai-api-key
COHERE_API_KEY=your-cohere-api-key
```

---

## 🐳 Docker 部署（企業版）

### 一行指令啟動全部服務

```bash
docker-compose up -d --build
```

此指令會啟動以下服務：

* PostgresSQL（含 pgvector 擴充）
* Redis（做為 Celery 的任務隊列後端與快取）
* Django（主站）
* Celery（背景任務處理）

### 常用指令

在使用下方指令前，請先使用 `docker exec -it ragpilot-base-django /bin/bash` 進入 django 容器當中，或直接使用 Docker UI
介面進入 Django 容器當中的 Exec 介面。

- 建立 superuser：

```bash
python manage.py createsuperuser
```

- 資料庫遷移：

```bash
python manage.py makemigrations # 此指令應該於開發時先於 IDE 當中執行
python manage.py migrate
```

---

## 🔁 修改後重啟方式

若修改內容涉及以下模組，請使用對應的指令重啟服務：

| 修改內容         | 重啟指令                                          |
|--------------|-----------------------------------------------|
| Django 後端程式碼 | `docker-compose restart ragpilot-base-django` |
| Celery 任務模組  | `docker-compose restart ragpilot-base-celery` |

> 為保系統效能與穩定性，請確保修改後同步重啟對應服務。

---

## 📝 注意事項

1. **企業版僅支援自建資料源**：所有資料皆由使用者自行上傳與管理，不包含爬蟲或外部資料來源。
2. **請正確設定 API 金鑰**：如需使用 OpenAI、Cohere 模型，需填入對應金鑰。
3. **建議使用 Docker Compose 部署**：內建服務配置已針對企業需求最佳化。
4. **資料安全與隱私**：請務必妥善管理 `.env` 檔案，避免外洩敏感資訊。
