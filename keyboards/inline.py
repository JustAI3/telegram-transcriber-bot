from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_diarization_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, разделить по спикерам", callback_data="diar_yes")],
            [InlineKeyboardButton(text="Нет, просто текст", callback_data="diar_no")]
        ]
    )
