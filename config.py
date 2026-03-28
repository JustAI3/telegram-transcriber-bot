import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")

# Local Telegram Bot API settings
USE_LOCAL_API = os.getenv("USE_LOCAL_API", "False").lower() == "true"
LOCAL_API_URL = os.getenv("LOCAL_API_URL", "http://telegram-api:8081")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Volume path for local API files
LOCAL_API_VOLUME_PATH = os.getenv("LOCAL_API_VOLUME_PATH", "/var/lib/telegram-bot-api")

# Канал для проверки подписки
CHANNEL_ID = os.getenv("CHANNEL_ID", "@e_mysienko")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/e_mysienko")

# Лимиты файлов
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
MAX_STORAGE_GB = int(os.getenv("MAX_STORAGE_GB", "10"))

if not BOT_TOKEN or not ASSEMBLYAI_API_KEY:
    raise ValueError("Missing API tokens in .env file")

if USE_LOCAL_API and (not API_ID or not API_HASH):
    raise ValueError("API_ID and API_HASH required when USE_LOCAL_API=True")
