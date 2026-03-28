"""
Сервис транскрибации аудио файлов через AssemblyAI.
Включает проверку размера файлов и управление временными файлами.
"""

import assemblyai as aai
import os
import logging
import shutil
import aiohttp
from pathlib import Path
from aiogram import Bot
from config import ASSEMBLYAI_API_KEY, BOT_TOKEN, USE_LOCAL_API, LOCAL_API_VOLUME_PATH, MAX_FILE_SIZE_MB
from services.cleanup import ensure_storage_available, get_user_temp_dir, cleanup_user_files
import asyncio
from concurrent.futures import ThreadPoolExecutor

aai.settings.api_key = ASSEMBLYAI_API_KEY

executor = ThreadPoolExecutor(max_workers=5)
logger = logging.getLogger(__name__)


class FileTooBigError(Exception):
    """Исключение для файлов превышающих лимит размера"""
    pass


class StorageError(Exception):
    """Исключение для проблем с местом на диске"""
    pass


def sync_transcribe(file_path: str, language_code: str = "auto", diarization: bool = False) -> aai.Transcript:
    """Синхронная транскрибация файла"""
    transcriber = aai.Transcriber()
    
    if language_code == "auto":
        config = aai.TranscriptionConfig(
            speaker_labels=diarization,
            language_detection=True
        )
    else:
        config = aai.TranscriptionConfig(
            speaker_labels=diarization,
            language_code=language_code
        )
    
    transcript = transcriber.transcribe(file_path, config)
    return transcript


async def async_transcribe(file_path: str, language_code: str = "auto", diarization: bool = False) -> aai.Transcript:
    """Асинхронная транскрибация файла"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, sync_transcribe, file_path, language_code, diarization)


def format_transcript(transcript: aai.Transcript) -> str:
    """Форматирование результата транскрибации"""
    if transcript.error:
        return f"Ошибка транскрибации: {transcript.error}"
    
    if not transcript.utterances:
        return transcript.text

    # Форматирование с учетом спикеров
    formatted_text = ""
    for utterance in transcript.utterances:
        speaker = f"Спикер {utterance.speaker}"
        formatted_text += f"**{speaker}**: {utterance.text}\n\n"
        
    return formatted_text.strip()


async def download_telegram_file(bot: Bot, file_id: str, user_id: int, file_name: str) -> tuple[Path, int]:
    """
    Скачивает файл из Telegram с проверкой размера и доступного места.
    
    Возвращает (путь_к_файлу, размер_файла_в_байтах).
    
    Выбрасывает:
    - FileTooBigError: если файл превышает MAX_FILE_SIZE_MB
    - StorageError: если недостаточно места на диске
    """
    # Получаем информацию о файле
    file = await bot.get_file(file_id)
    file_size_bytes = file.file_size or 0
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    logger.info(f"File info: {file_id}, size: {file_size_mb:.2f} MB")
    
    # Проверяем размер файла
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise FileTooBigError(
            f"Файл слишком большой: {file_size_mb:.1f} МБ. Максимум: {MAX_FILE_SIZE_MB} МБ"
        )
    
    # Проверяем и освобождаем место (с запасом 50%)
    required_mb = int(file_size_mb * 1.5) + 10  # +10 МБ на результат
    if not await ensure_storage_available(required_mb):
        raise StorageError(
            "Недостаточно места на сервере. Попробуйте позже."
        )
    
    # Создаём папку пользователя
    temp_dir = get_user_temp_dir(user_id)
    file_path = temp_dir / f"{file_id}_{file_name}"
    
    # Если используем локальный API, файл уже на диске
    if USE_LOCAL_API and file.file_path:
        # Путь в контейнере бота (примонтированный volume)
        local_path = os.path.join(LOCAL_API_VOLUME_PATH, file.file_path)
        if os.path.exists(local_path):
            shutil.copy(local_path, str(file_path))
            logger.info(f"File copied from local storage: {local_path} -> {file_path}")
            return file_path, file_size_bytes
        else:
            logger.warning(f"Local file not found at {local_path}, falling back to download")
    
    # Скачиваем файл
    try:
        # Пробуем через прямой HTTP запрос (для больших файлов)
        telegram_file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(telegram_file_url) as response:
                if response.status == 200:
                    with open(file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    logger.info(f"File downloaded via HTTP: {file_path}")
                else:
                    raise Exception(f"Telegram HTTP {response.status}")
    except Exception as e:
        # Если HTTP запрос не удался, используем стандартный метод
        logger.warning(f"HTTP download failed: {e}, falling back to bot API")
        await bot.download(file.file_id, destination=str(file_path))
        logger.info(f"File downloaded via bot API: {file_path}")
    
    return file_path, file_size_bytes


async def transcribe_user_file(
    bot: Bot, 
    file_id: str, 
    user_id: int, 
    file_name: str,
    language_code: str = "auto",
    diarization: bool = False
) -> tuple[str, Path]:
    """
    Полный цикл транскрибации файла пользователя.
    
    1. Скачивает файл с проверками
    2. Транскрибирует
    3. Сохраняет результат
    4. Удаляет исходный файл
    
    Возвращает (текст_транскрипции, путь_к_файлу_результата).
    """
    file_path = None
    result_path = None
    
    try:
        # Скачиваем файл
        file_path, file_size = await download_telegram_file(bot, file_id, user_id, file_name)
        
        # Транскрибируем
        transcript = await async_transcribe(str(file_path), language_code, diarization)
        
        # Форматируем результат
        formatted_text = format_transcript(transcript)
        
        # Сохраняем в файл
        result_filename = f"transcript_{file_id}.txt"
        result_path = file_path.parent / result_filename
        
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(formatted_text)
        
        return formatted_text, result_path
        
    finally:
        # Удаляем исходный файл после обработки
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"Cleaned up source file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up source file: {e}")


async def cleanup_after_sending(result_path: Path, user_id: int) -> None:
    """
    Очистка после отправки результата пользователю.
    Удаляет файл результата.
    """
    if result_path and result_path.exists():
        try:
            result_path.unlink()
            logger.info(f"Cleaned up result file: {result_path}")
        except Exception as e:
            logger.error(f"Error cleaning up result file: {e}")
