import os
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.inline import get_language_keyboard, get_diarization_keyboard
from handlers.states import TranscribeProcess
from services.transcriber import async_transcribe, format_transcript
import database as db

router = Router()
logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    db.get_user(message.from_user.id) # Init user
    text = (
        "Привет! Я бот для транскрибации аудио с помощью мощной нейросети AssemblyAI.\n\n"
        "Отправь мне аудиофайл или перешли голосовое сообщение, "
        "и я переведу его в текст. Ты также можешь выбрать опцию разделения по спикерам.\n\n"
        "⚡️ В данный момент бот работает полностью бесплатно и без ограничений!"
    )
    await message.answer(text)

@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено. Вы можете отправить новый файл.")

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>Как пользоваться ботом:</b>\n"
        "1. Загрузите аудиофайл в чат или перешлите мне голосовое сообщение.\n"
        "2. Бот предложит выбрать язык аудиозаписи. Если не уверены, выбирайте «Автоопределение».\n"
        "3. Выберите, нужно ли делить текст по спикерам.\n"
        "4. Подождите, пока нейросеть обработает файл.\n"
        "5. Вы получите текстовый документ с расшифровкой, а если текст небольшой — бот пришлет его прямо в чат."
    )
    await message.answer(text)

@router.message(F.audio | F.voice | F.document | F.video | F.video_note, StateFilter("*"))
async def handle_audio(message: Message, state: FSMContext, bot: Bot):
    logger.info(f"Received audio/file from user {message.from_user.id}")
    if message.document:
        mime_type = message.document.mime_type
        if mime_type and not mime_type.startswith("audio/") and not mime_type.startswith("video/"):
            await message.answer("Пожалуйста, отправьте аудио- или видеофайл.")
            return
        file_id = message.document.file_id
        file_name = message.document.file_name or "audio.mp3"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"
    elif message.video_note:
        file_id = message.video_note.file_id
        file_name = "video_note.mp4"
    elif message.voice:
        file_id = message.voice.file_id
        file_name = f"voice_message.ogg"
    else:
        return

    # Store file details in FSM
    await state.update_data(file_id=file_id, file_name=file_name)
    await state.set_state(TranscribeProcess.waiting_for_language)

    await message.answer(
        "Выберите язык аудио (или оставьте автоопределение):",
        reply_markup=get_language_keyboard()
    )

@router.callback_query(F.data.startswith("lang_"), TranscribeProcess.waiting_for_language)
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    lang_code = callback.data.split("_")[1]
    await state.update_data(lang_code=lang_code)
    
    await state.set_state(TranscribeProcess.waiting_for_diarization)
    await callback.message.edit_text(
        "Определять разных спикеров (говорящих) на записи?\n\n"
        "Разделение по спикерам делает текст удобнее, но обработка может занять чуть больше времени.",
        reply_markup=get_diarization_keyboard()
    )

@router.callback_query(F.data.startswith("diar_"), TranscribeProcess.waiting_for_diarization)
async def process_diarization_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    diarization = True if callback.data == "diar_yes" else False
    
    await callback.message.edit_text("⏳ Загружаю файл... Это может занять некоторое время.")
    await state.set_state(TranscribeProcess.processing)
    
    data = await state.get_data()
    file_id = data['file_id']
    file_name = data['file_name']
    lang_code = data['lang_code']
    
    try:
        file = await bot.get_file(file_id)
        file_path = os.path.join(DOWNLOAD_DIR, f"{file.file_id}_{file_name}")
        
        await bot.download(file.file_id, destination=file_path)
        
        # Transcribe
        await callback.message.edit_text("⏳ Файл загружен. Идет обработка нейросетью AssemblyAI...")
        transcript = await async_transcribe(file_path, lang_code, diarization)
        
        # Format output
        formatted_text = format_transcript(transcript)
        
        # Save to TXT
        result_filename = f"transcript_{file.file_unique_id}.txt"
        result_path = os.path.join(DOWNLOAD_DIR, result_filename)
        
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(formatted_text)
            
        # Send text to chat if small enough
        if len(formatted_text) <= 4000:
            await callback.message.answer(f"<blockquote>{formatted_text}</blockquote>", parse_mode="HTML")
        else:
            await callback.message.answer("Текст слишком длинный, отправляю файлом.")
            
        # Send TXT file
        document = FSInputFile(result_path, filename=result_filename)
        await callback.message.answer_document(document)
        
    except Exception as e:
        await callback.message.answer(f"❌ Произошла ошибка при обработке: {str(e)}")
    finally:
        # Cleanup
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'result_path' in locals() and os.path.exists(result_path):
            os.remove(result_path)
            
        await state.clear()
        
    await callback.answer()
