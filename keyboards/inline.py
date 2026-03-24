from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Callback data format: lang_<code> (e.g., lang_ru)
    # Используем .add(InlineKeyboardButton(...)) для большей надежности в некоторых версиях aiogram 3
    
    builder.add(
        InlineKeyboardButton(text="Автоопределение", callback_data="lang_auto"),
        InlineKeyboardButton(text="Русский", callback_data="lang_ru"),
        InlineKeyboardButton(text="English", callback_data="lang_en"),
        InlineKeyboardButton(text="Español", callback_data="lang_es"),
        InlineKeyboardButton(text="Français", callback_data="lang_fr"),
        InlineKeyboardButton(text="Deutsch", callback_data="lang_de")
    )
    
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()
    
def get_diarization_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Да, разделить по спикерам", callback_data="diar_yes"),
        InlineKeyboardButton(text="Нет, просто текст", callback_data="diar_no")
    )
    builder.adjust(1)
    return builder.as_markup()

def get_billing_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="1 час (180 руб)", callback_data="buy_60"),
        InlineKeyboardButton(text="5 часов (800 руб)", callback_data="buy_300"),
        InlineKeyboardButton(text="10 часов (1500 руб)", callback_data="buy_600")
    )
    builder.adjust(1)
    return builder.as_markup()
