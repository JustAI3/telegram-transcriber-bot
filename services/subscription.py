import logging
from aiogram import Bot
from config import CHANNEL_ID

logger = logging.getLogger(__name__)


async def check_subscription(bot: Bot, user_id: int) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.
    Возвращает True если подписан, False если нет.
    """
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        # Статусы, которые считаются как "подписан"
        subscribed_statuses = ["member", "administrator", "creator"]
        return member.status in subscribed_statuses
    except Exception as e:
        # Fail-open: при ошибке API разрешаем доступ
        logger.error(f"Error checking subscription: {e}")
        return True
