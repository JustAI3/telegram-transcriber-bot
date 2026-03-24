import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.bot.api import parse_mode_as_enum
from aiogram.types import BotCommand
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from handlers import user_handlers
from database import init_db

async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Справка и инструкция"),
    ]
    await bot.set_my_commands(commands)
    await bot.set_my_description(description="Привет! Я мощный бот для транскрибации аудио в текст.\n\n"
                                 "Просто отправь мне аудиофайл или перешли голосовое сообщение, "
                                 "и я переведу его в текст, автоматически определив спикеров.\n"
                                 "Работаю на базе нейросетей AssemblyAI.")
    await bot.set_my_short_description(short_description="Перевожу ваши голосовые и аудио в текст!")

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    
    init_db()
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация роутеров ПЕРЕД командами и стартом
    dp.include_router(user_handlers.router)
    
    # Run bot
    await set_bot_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
