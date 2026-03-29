"""
Админ панель для мониторинга статистики использования бота.
Команда /adm доступна только для ADMIN_ID.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

import database as db
from debug import log_event

router = Router()

ADMIN_ID = 32631659


@router.message(Command("adm"))
async def admin_panel(message: Message):
    """Показывает админ панель со статистикой использования"""
    if message.from_user.id != ADMIN_ID:
        return
    
    log_event(message.from_user.id, "ADMIN_PANEL_ACCESS", {})
    
    # Получаем статистику
    stats = db.get_stats_summary()
    
    # Формируем текст топ языков
    lang_stats = "\n".join([f"  {lang}: {count}" for lang, count in stats['top_languages']])
    if not lang_stats:
        lang_stats = "  Нет данных"
    
    stats_text = f"""
📊 **Админ панель**

👥 **Пользователи:** {stats['total_users']}
📝 **Всего запросов:** {stats['total_requests']}
✅ **Успешность:** {stats['success_rate']:.1f}%
📁 **Общий объём:** {stats['total_size_mb']:.1f} MB
📈 **Активность (24ч):** {stats['active_today']}

🌍 **Топ языки:**
{lang_stats}

⚠️ **Ошибок:** {stats['errors_count']}
📦 **Средний файл:** {stats['avg_size']:.2f} MB

💡 **Рекомендации:**
"""
    
    # Добавляем рекомендации
    total_requests = stats['total_requests']
    avg_size = stats['avg_size']
    errors_count = stats['errors_count']
    active_today = stats['active_today']
    total_users = stats['total_users']
    
    if avg_size > 15:
        stats_text += "• Многие файлы >15MB — нужен локальный API\n"
    if total_requests > 0 and errors_count > total_requests * 0.1:
        stats_text += "• Много ошибок — проверь логи\n"
    if total_users > 0 and active_today > total_users * 2:
        stats_text += "• Высокая активность — подумай о масштабировании\n"
    
    if stats_text.endswith("💡 **Рекомендации:**\n"):
        stats_text += "• Всё в порядке, рекомендаций нет\n"
    
    await message.answer(stats_text, parse_mode="Markdown")
