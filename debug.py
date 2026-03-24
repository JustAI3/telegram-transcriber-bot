"""
Система логирования для отладки бота.
Используется для выявления глюков и проблем в работе.
"""
import logging
import json
from datetime import datetime
from typing import Any, Optional

# Настройка логгера
debug_logger = logging.getLogger("debug")
debug_logger.setLevel(logging.DEBUG)

# Формат для логов
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

# Хендлер для консоли
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
debug_logger.addHandler(console_handler)


def log_event(user_id: int, event_type: str, data: Optional[dict] = None):
    """
    Логирует событие для отладки.
    
    Args:
        user_id: ID пользователя
        event_type: Тип события (например, "HANDLER_START", "STATE_CHANGE")
        data: Дополнительные данные о событии
    """
    log_data = {
        "user_id": user_id,
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data or {}
    }
    debug_logger.info(f"EVENT: {json.dumps(log_data)}")


def log_error(user_id: int, error_type: str, error_message: str, additional_data: Optional[dict] = None):
    """
    Логирует ошибку для отладки.
    
    Args:
        user_id: ID пользователя
        error_type: Тип ошибки
        error_message: Сообщение об ошибке
        additional_data: Дополнительные данные
    """
    log_data = {
        "user_id": user_id,
        "error_type": error_type,
        "error_message": error_message,
        "timestamp": datetime.now().isoformat(),
        "additional_data": additional_data or {}
    }
    debug_logger.error(f"ERROR: {json.dumps(log_data)}")


def log_state_change(user_id: int, old_state: Optional[str], new_state: Optional[str]):
    """
    Логирует переход состояния FSM.
    """
    log_data = {
        "user_id": user_id,
        "old_state": old_state,
        "new_state": new_state,
        "timestamp": datetime.now().isoformat()
    }
    debug_logger.info(f"STATE_CHANGE: {json.dumps(log_data)}")


def log_callback_received(user_id: int, callback_data: str):
    """
    Логирует получение callback от пользователя.
    """
    log_data = {
        "user_id": user_id,
        "callback_data": callback_data,
        "timestamp": datetime.now().isoformat()
    }
    debug_logger.info(f"CALLBACK_RECEIVED: {json.dumps(log_data)}")
