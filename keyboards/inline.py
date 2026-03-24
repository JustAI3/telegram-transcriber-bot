from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_language_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора языка аудио"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
            [InlineKeyboardButton(text="🇺🇦 Українська", callback_data="lang_uk")],
            [InlineKeyboardButton(text="🤖 Автоопределение", callback_data="lang_auto")]
        ]
    )

def get_diarization_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора режима разделения по спикерам"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, разделить по спикерам", callback_data="diar_yes")],
            [InlineKeyboardButton(text="Нет, просто текст", callback_data="diar_no")]
        ]
    )
