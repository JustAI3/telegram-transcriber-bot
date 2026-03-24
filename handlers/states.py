from aiogram.fsm.state import State, StatesGroup

class TranscribeProcess(StatesGroup):
    waiting_for_language = State()
    waiting_for_diarization = State()
    processing = State()
