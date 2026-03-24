import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
LAVATOP_API_KEY = os.getenv("LAVATOP_API_KEY", "WbiVrIRPY7e1vSYG1gWzEIRkGCcBQwCuA9UjQwCUaXnB7923MSfdxfV7tKK4r7YQ")

# Идентификаторы продуктов (офферов) из Lava.top
# Вам нужно создать 3 продукта/оффера в личном кабинете Lava.top и вписать их ID сюда или в .env
OFFER_ID_60 = os.getenv("OFFER_ID_60", "offer-uuid-for-60-min")
OFFER_ID_300 = os.getenv("OFFER_ID_300", "offer-uuid-for-300-min")
OFFER_ID_600 = os.getenv("OFFER_ID_600", "offer-uuid-for-600-min")

if not BOT_TOKEN or not ASSEMBLYAI_API_KEY:
    raise ValueError("Missing API tokens in .env file")
