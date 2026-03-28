"""
Менеджер дискового пространства для временных файлов.
Обеспечивает автоматическую очистку старых файлов и контроль использования диска.
"""

import os
import shutil
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from config import MAX_STORAGE_GB

# Папка для временных файлов
TEMP_DIR = Path("temp_files")
MAX_FILES_PER_USER = 100
logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Исключение для проблем с хранилищем"""
    pass


def _safe_file_size(path: Path) -> int:
    """Безопасно получает размер файла, возвращая 0 при ошибке"""
    try:
        return path.stat().st_size
    except (OSError, FileNotFoundError):
        return 0


def get_storage_usage() -> tuple[int, int]:
    """
    Возвращает (использовано_МБ, всего_МБ) для папки временных файлов.
    """
    if not TEMP_DIR.exists():
        return 0, MAX_STORAGE_GB * 1024
    
    total_size = sum(
        _safe_file_size(path)
        for path in TEMP_DIR.rglob("*")
        if path.is_file()
    )
    
    used_mb = total_size / (1024 * 1024)
    return int(used_mb), MAX_STORAGE_GB * 1024


async def cleanup_old_files(max_age_hours: int = 1) -> int:
    """
    Удаляет файлы старше max_age_hours часов.
    Возвращает количество освобождённых МБ.
    """
    if not TEMP_DIR.exists():
        return 0
    
    now = datetime.now()
    cutoff = now - timedelta(hours=max_age_hours)
    freed_bytes = 0
    
    # Собираем файлы для удаления
    files_to_delete = []
    for path in TEMP_DIR.rglob("*"):
        if path.is_file():
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                if mtime < cutoff:
                    files_to_delete.append(path)
            except (OSError, FileNotFoundError) as e:
                logger.error(f"Error accessing {path}: {e}")
    
    # Удаляем файлы
    for path in files_to_delete:
        try:
            if path.exists():  # Проверка существования перед удалением
                size = path.stat().st_size
                path.unlink()
                freed_bytes += size
                logger.info(f"Deleted old file: {path}")
        except Exception as e:
            logger.error(f"Error deleting {path}: {e}")
    
    # Удаляем пустые директории
    for path in sorted(TEMP_DIR.rglob("*"), reverse=True):  # От листьев к корню
        if path.is_dir():
            try:
                if not any(path.iterdir()):
                    path.rmdir()
                    logger.info(f"Removed empty directory: {path}")
            except Exception:
                pass
    
    return int(freed_bytes / (1024 * 1024))


async def ensure_storage_available(required_mb: int) -> bool:
    """
    Проверяет и при необходимости освобождает место.
    Возвращает True если место доступно.
    """
    used_mb, max_mb = get_storage_usage()
    available_mb = max_mb - used_mb
    
    if available_mb >= required_mb:
        return True
    
    # Пытаемся освободить место
    logger.info(f"Storage low: {available_mb}MB available, need {required_mb}MB. Cleaning up...")
    
    # Очищаем файлы старше 1 часа
    freed = await cleanup_old_files(max_age_hours=1)
    available_mb += freed
    
    if available_mb >= required_mb:
        return True
    
    # Если всё ещё не хватает, очищаем файлы старше 30 минут
    freed = await cleanup_old_files(max_age_hours=0.5)
    available_mb += freed
    
    return available_mb >= required_mb


def get_user_temp_dir(user_id: int) -> Path:
    """
    Возвращает папку для временных файлов пользователя.
    Выбрасывает StorageError если превышен лимит файлов.
    """
    user_dir = TEMP_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Проверка количества файлов
    files_count = sum(1 for _ in user_dir.rglob("*") if _.is_file())
    if files_count >= MAX_FILES_PER_USER:
        raise StorageError(f"Too many files for user {user_id}")
    
    return user_dir


async def cleanup_user_files(user_id: int) -> None:
    """Удаляет все временные файлы пользователя"""
    user_dir = TEMP_DIR / str(user_id)
    if user_dir.exists():
        try:
            shutil.rmtree(user_dir, ignore_errors=True)
            logger.info(f"Cleaned up files for user {user_id}")
        except Exception as e:
            logger.error(f"Error cleaning up user {user_id} files: {e}")


def get_file_age_hours(file_path: Path) -> float:
    """Возвращает возраст файла в часах"""
    if not file_path.exists():
        return 0
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    age = datetime.now() - mtime
    return age.total_seconds() / 3600


async def get_storage_stats() -> dict:
    """Возвращает статистику использования хранилища"""
    used_mb, max_mb = get_storage_usage()
    
    # Подсчитываем количество пользователей и файлов
    users_count = 0
    files_count = 0
    
    if TEMP_DIR.exists():
        for user_dir in TEMP_DIR.iterdir():
            if user_dir.is_dir():
                users_count += 1
                files_count += sum(1 for _ in user_dir.rglob("*") if _.is_file())
    
    return {
        "used_mb": used_mb,
        "max_mb": max_mb,
        "available_mb": max_mb - used_mb,
        "usage_percent": round(used_mb / max_mb * 100, 1) if max_mb > 0 else 0,
        "users_count": users_count,
        "files_count": files_count
    }
