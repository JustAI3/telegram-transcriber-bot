from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Callback data format: lang_<code>_<file_id> (we'll truncate file_id if it's too long, or use an internal store, 
    # but telegram callback data limit is 64 bytes. file_ids can be long. 
    # Let's save file_id in FSM or pass only a short prefix/ID)
    
    # Actually, it's better to use FSM to store the uploaded file info.
    # So the keyboard just sends the language code.
    
    builder.button(text="Автоопределение", callback_data="lang_auto")
    builder.button(text="Русский", callback_data="lang_ru")
    builder.button(text="English", callback_data="lang_en")
    builder.button(text="Español", callback_data="lang_es")
    builder.button(text="Français", callback_data="lang_fr")
    builder.button(text="Deutsch", callback_data="lang_de")
    
def get_diarization_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, разделить по спикерам", callback_data="diar_yes")
    builder.button(text="Нет, просто текст", callback_data="diar_no")
    builder.adjust(1)
    return builder.as_markup()

def get_billing_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="1 час (180 руб)", callback_data="buy_60")
    builder.button(text="5 часов (800 руб)", callback_data="buy_300")
    builder.button(text="10 часов (1500 руб)", callback_data="buy_600")
    builder.adjust(1)
    return builder.as_markup()
