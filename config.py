import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "")

if not BOT_TOKEN or not ASSEMBLYAI_API_KEY:
    raise ValueError("Missing API tokens in .env file")
