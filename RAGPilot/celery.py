import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
from RAGPilot.settings import BASE_DIR

load_dotenv(os.path.join(BASE_DIR, '.env'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RAGPilot.settings')
app = Celery(
    'RAGPilot',
    backend=f"redis://{os.getenv('REDIS_HOST', 'redis')}:6379/0",
    broker=f"redis://{os.getenv('REDIS_HOST', 'redis')}:6379/1"
)
app.conf.imports = (
    "celery_app.extractors.extract_pdf",
    "celery_app.extractors.extract_structured_file",
    "celery_app.tasks.conversations",
)
app.conf.timezone = 'Asia/Taipei'
app.conf.enable_utc = True
app.conf.beat_schedule = {}

app.conf.task_routes = {
    'celery_app.tasks.conversations.*': {'queue': 'conversation_queue'},
    'celery_app.extractors.*': {'queue': 'extractor_queue'},
}

app.conf.task_default_queue = 'default'


