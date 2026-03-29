import os
import logging
import asyncio
from typing import Dict, List, Optional
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_TOKEN, USE_LOCAL_API, LOCAL_API_VOLUME_PATH, CHANNEL_ID, MAX_FILE_SIZE_MB
from keyboards.inline import get_language_keyboard, get_diarization_keyboard, get_subscription_keyboard
from handlers.states import TranscribeProcess, BatchTranscribeProcess
from services.transcriber import (
    async_transcribe,
    format_transcript,
    transcribe_user_file,
    cleanup_after_sending,
    FileTooBigError,
    StorageError
)
from services.subscription import check_subscription
import database as db
from debug import log_event, log_error

router = Router()
logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Временное хранилище для сбора файлов из media group
# Ключ: media_group_id, значение: список данных о файлах
_media_group_cache: Dict[str, Dict] = {}
# Время ожидания сбора всех файлов группы (в секундах)
MEDIA_GROUP_WAIT_TIME = 1.5
# Максимальное количество файлов в группе
MAX_FILES_IN_GROUP = 5


def get_file_size_mb(message: Message) -> float:
    """Получает размер файла в МБ из сообщения"""
    file_size = 0
    if message.audio:
        file_size = message.audio.file_size or 0
    elif message.video:
        file_size = message.video.file_size or 0
    elif message.voice:
        file_size = message.voice.file_size or 0
    elif message.document:
        file_size = message.document.file_size or 0
    elif message.video_note:
        file_size = message.video_note.file_size or 0
    
    return file_size / (1024 * 1024)


@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    log_event(message.from_user.id, "CMD_START", {})
    await state.clear()
    db.get_user(message.from_user.id) # Init user
    
    # Проверяем подписку
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Для использования бота необходимо подписаться на наш канал.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    text = (
        "Привет! Я бот для транскрибации аудио с помощью мощной нейросети.\n\n"
        "Отправь мне аудиофайл или перешли голосовое сообщение, "
        "и я переведу его в текст. Ты также можешь выбрать опцию разделения по спикерам.\n\n"
        f"⚡️ Максимальный размер файла: {MAX_FILE_SIZE_MB} МБ"
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
        "5. Вы получите текстовый документ с расшифровкой, а если текст небольшой — бот пришлет его прямо в чат.\n\n"
        f"📄 Максимальный размер файла: {MAX_FILE_SIZE_MB} МБ"
    )
    await message.answer(text)


@router.message(F.audio | F.voice | F.document | F.video | F.video_note, StateFilter("*"))
async def handle_audio(message: Message, state: FSMContext, bot: Bot):
    logger.info(f"HANDLING_AUDIO_START: User {message.from_user.id}")
    
    # Проверяем подписку перед обработкой
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "❌ Для использования бота необходимо подписаться на канал.",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # Проверяем размер файла ДО обработки
    file_size_mb = get_file_size_mb(message)
    logger.info(f"FILE_SIZE: {file_size_mb:.2f} MB for user {message.from_user.id}")
    
    if file_size_mb > MAX_FILE_SIZE_MB:
        await message.answer(
            f"❌ Файл слишком большой: {file_size_mb:.1f} МБ\n"
            f"Максимальный размер: {MAX_FILE_SIZE_MB} МБ\n\n"
            "Попробуйте сжать файл или отправить его частями."
        )
        log_event(message.from_user.id, "FILE_TOO_BIG", {"size_mb": file_size_mb})
        return

    if message.document:
        mime_type = message.document.mime_type
        logger.info(f"DOC_MIME: {mime_type}")
        if mime_type and not mime_type.startswith("audio/") and not mime_type.startswith("video/"):
            await message.answer("Пожалуйста, отправьте аудио- или видеофайл.")
            return
        file_id = message.document.file_id
        file_name = message.document.file_name or "audio.mp3"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
        logger.info(f"AUDIO_FILE: {file_id}")
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"
    elif message.video_note:
        file_id = message.video_note.file_id
        file_name = "video_note.mp4"
    elif message.voice:
        file_id = message.voice.file_id
        file_name = f"voice_message.ogg"
        logger.info(f"VOICE_FILE: {file_id}")
    else:
        logger.warning(f"UNKNOWN_FILE_TYPE: User {message.from_user.id}")
        return

    # Store file details in FSM
    await state.update_data(file_id=file_id, file_name=file_name, file_size_mb=file_size_mb)
    await state.set_state(TranscribeProcess.waiting_for_language)

    keyboard = get_language_keyboard()
    
    logger.info(f"SENDING_REPLY_WITH_KB: User {message.from_user.id}")
    
    try:
        await message.answer(
            "Выберите язык аудио:",
            reply_markup=keyboard
        )
        logger.info(f"SENT_SUCCESSFULLY: User {message.from_user.id}")
    except Exception as e:
        logger.error(f"SEND_FAILED: {str(e)}")


# =====================
# Пакетная обработка группы аудио файлов (до 5 штук)
# =====================

@router.message(F.audio, F.media_group_id)
async def handle_audio_album(message: Message, state: FSMContext, bot: Bot):
    """
    Обработка группы аудио файлов (album/grouped media).
    Файлы приходят отдельными сообщениями с одинаковым media_group_id.
    Собираем все файлы и затем запускаем обработку.
    """
    user_id = message.from_user.id
    media_group_id = message.media_group_id
    file_size_mb = get_file_size_mb(message)
    
    logger.info(f"MEDIA_GROUP_RECEIVED: User {user_id}, group_id={media_group_id}, file_size={file_size_mb:.2f}MB")
    
    # Проверяем подписку (только для первого файла в группе)
    if media_group_id not in _media_group_cache:
        if not await check_subscription(bot, user_id):
            await message.answer(
                "❌ Для использования бота необходимо подписаться на канал.",
                reply_markup=get_subscription_keyboard()
            )
            return
        # Инициализируем запись для группы
        _media_group_cache[media_group_id] = {
            "user_id": user_id,
            "files": [],
            "message_id": message.message_id,  # ID первого сообщения для ответа
            "checked": False
        }
    
    cache_entry = _media_group_cache[media_group_id]
    
    # Проверяем, что группа принадлежит тому же пользователю
    if cache_entry["user_id"] != user_id:
        logger.warning(f"MEDIA_GROUP_USER_MISMATCH: Expected {cache_entry['user_id']}, got {user_id}")
        return
    
    # Проверяем лимит файлов
    if len(cache_entry["files"]) >= MAX_FILES_IN_GROUP:
        await message.answer(f"⚠️ Максимум {MAX_FILES_IN_GROUP} файлов в одной группе. Лишние файлы проигнорированы.")
        return
    
    # Проверяем размер файла
    if file_size_mb > MAX_FILE_SIZE_MB:
        await message.answer(
            f"❌ Файл слишком большой: {file_size_mb:.1f} МБ\n"
            f"Максимальный размер: {MAX_FILE_SIZE_MB} МБ\n"
            f"Этот файл будет пропущен."
        )
        log_event(user_id, "BATCH_FILE_TOO_BIG", {"size_mb": file_size_mb})
        return
    
    # Добавляем файл в кэш
    file_data = {
        "file_id": message.audio.file_id,
        "file_name": message.audio.file_name or f"audio_{len(cache_entry['files']) + 1}.mp3",
        "file_size_mb": file_size_mb,
        "message_id": message.message_id
    }
    cache_entry["files"].append(file_data)
    
    logger.info(f"MEDIA_GROUP_FILE_ADDED: group={media_group_id}, total_files={len(cache_entry['files'])}")
    
    # Если это первый файл, запускаем таймер для сбора остальных
    if len(cache_entry["files"]) == 1:
        # Ждём получения всех файлов группы
        await asyncio.sleep(MEDIA_GROUP_WAIT_TIME)
        
        # Проверяем, что запись ещё существует (не была удалена другим обработчиком)
        if media_group_id not in _media_group_cache:
            return
        
        final_cache = _media_group_cache[media_group_id]
        files_count = len(final_cache["files"])
        
        if files_count == 0:
            del _media_group_cache[media_group_id]
            return
        
        # Сохраняем данные в FSM
        await state.update_data(
            batch_files=final_cache["files"],
            batch_count=files_count,
            batch_message_id=final_cache["message_id"]
        )
        await state.set_state(BatchTranscribeProcess.waiting_for_language)
        
        log_event(user_id, "BATCH_FILES_COLLECTED", {"count": files_count})
        
        # Отправляем сообщение с выбором языка
        try:
            await message.answer(
                f"🎵 Получено {files_count} файл(ов) для транскрибации.\n\n"
                f"Выберите язык аудио (применится ко всем файлам):",
                reply_markup=get_language_keyboard()
            )
        except Exception as e:
            logger.error(f"BATCH_SEND_FAILED: {str(e)}")
        
        # Удаляем из кэша
        del _media_group_cache[media_group_id]


@router.callback_query(F.data.startswith("lang_"), StateFilter(BatchTranscribeProcess.waiting_for_language))
async def process_batch_language_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора языка для группы файлов"""
    await callback.answer()
    log_event(callback.from_user.id, "BATCH_LANGUAGE_SELECTION", {"lang": callback.data})
    
    lang_code = callback.data.split("_")[1]
    await state.update_data(lang_code=lang_code)
    
    await state.set_state(BatchTranscribeProcess.waiting_for_diarization)
    
    data = await state.get_data()
    files_count = data.get("batch_count", 1)
    
    await callback.message.edit_text(
        f"🎵 {files_count} файл(ов) в очереди.\n\n"
        "Определять разных спикеров (говорящих) на записи?\n\n"
        "Разделение по спикерам делает текст удобнее, но обработка может занять чуть больше времени.",
        reply_markup=get_diarization_keyboard()
    )


@router.callback_query(F.data.startswith("diar_"), StateFilter(BatchTranscribeProcess.waiting_for_diarization))
async def process_batch_diarization_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора диаризации и запуск транскрибации для всех файлов группы"""
    await callback.answer()
    log_event(callback.from_user.id, "BATCH_DIARIZATION_SELECTION", {"diar": callback.data})
    
    diarization = callback.data == "diar_yes"
    
    data = await state.get_data()
    batch_files = data.get("batch_files", [])
    lang_code = data.get("lang_code", "auto")
    
    if not batch_files:
        await callback.message.edit_text("❌ Ошибка: файлы не найдены. Попробуйте отправить снова.")
        await state.clear()
        return
    
    files_count = len(batch_files)
    await callback.message.edit_text(
        f"⏳ Начинаю обработку {files_count} файл(ов)...\n\n"
        "Результаты будут отправлены по мере готовности."
    )
    
    await state.set_state(BatchTranscribeProcess.processing)
    
    # Обрабатываем каждый файл
    successful = 0
    failed = 0
    
    for i, file_data in enumerate(batch_files, 1):
        file_id = file_data["file_id"]
        file_name = file_data["file_name"]
        
        try:
            # Отправляем статус для текущего файла
            status_msg = await callback.message.answer(
                f"📁 [{i}/{files_count}] Обрабатываю: {file_name}"
            )
            
            # Транскрибируем файл
            formatted_text, result_path = await transcribe_user_file(
                bot=bot,
                file_id=file_id,
                user_id=callback.from_user.id,
                file_name=file_name,
                language_code=lang_code,
                diarization=diarization
            )
            
            # Удаляем статус
            await status_msg.delete()
            
            # Отправляем результат
            result_header = f"📄 Результат: {file_name}\n\n"
            
            if len(formatted_text) <= 3500:
                try:
                    await callback.message.answer(
                        f"{result_header}<blockquote>{formatted_text}</blockquote>",
                        parse_mode="HTML"
                    )
                except Exception as text_error:
                    log_error(callback.from_user.id, "BATCH_SEND_TEXT_ERROR", str(text_error))
            else:
                await callback.message.answer(f"{result_header}Текст слишком длинный, отправляю файлом.")
            
            # Отправляем TXT файл
            try:
                document = FSInputFile(str(result_path), filename=f"transcript_{file_name}")
                await callback.message.answer_document(document)
            except Exception as doc_error:
                error_str = str(doc_error)
                if "file is too big" not in error_str.lower():
                    log_error(callback.from_user.id, "BATCH_SEND_DOC_ERROR", error_str)
            
            successful += 1
            log_event(callback.from_user.id, "BATCH_FILE_SUCCESS", {"file": file_name, "index": i})
            
            # Записываем успешную статистику
            db.add_usage_stat(
                user_id=callback.from_user.id,
                file_size_mb=file_data.get("file_size_mb", 0),
                language=lang_code,
                success=True
            )
            
            # Очищаем файл результата
            await cleanup_after_sending(result_path, callback.from_user.id)
            
        except FileTooBigError as e:
            failed += 1
            db.add_usage_stat(
                user_id=callback.from_user.id,
                file_size_mb=file_data.get("file_size_mb", 0),
                language=lang_code,
                success=False,
                error_message=str(e)
            )
            await callback.message.answer(f"❌ [{i}/{files_count}] {file_name}: {str(e)}")
            log_error(callback.from_user.id, "BATCH_FILE_TOO_BIG", str(e))
            
        except StorageError as e:
            failed += 1
            db.add_usage_stat(
                user_id=callback.from_user.id,
                file_size_mb=file_data.get("file_size_mb", 0),
                language=lang_code,
                success=False,
                error_message=str(e)
            )
            await callback.message.answer(f"❌ [{i}/{files_count}] {file_name}: Недостаточно места на сервере")
            log_error(callback.from_user.id, "BATCH_STORAGE_ERROR", str(e))
            
        except Exception as e:
            failed += 1
            error_str = str(e)
            
            db.add_usage_stat(
                user_id=callback.from_user.id,
                file_size_mb=file_data.get("file_size_mb", 0),
                language=lang_code,
                success=False,
                error_message=error_str
            )
            
            if "file is too big" in error_str.lower():
                await callback.message.answer(
                    f"❌ [{i}/{files_count}] {file_name}: Файл слишком большой для загрузки"
                )
            else:
                await callback.message.answer(
                    f"❌ [{i}/{files_count}] {file_name}: Ошибка обработки - {error_str}"
                )
            log_error(callback.from_user.id, "BATCH_FILE_ERROR", f"{file_name}: {error_str}")
    
    # Итоговое сообщение
    await callback.message.answer(
        f"✅ Обработка завершена!\n\n"
        f"Успешно: {successful}\n"
        f"Ошибок: {failed}"
    )
    
    await state.clear()
    log_event(callback.from_user.id, "BATCH_COMPLETE", {"successful": successful, "failed": failed})


# =====================
# Обработка одиночных файлов (продолжение)
# =====================

@router.callback_query(F.data.startswith("lang_"), StateFilter(TranscribeProcess.waiting_for_language))
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # Обязательно отвечаем на callback
    log_event(callback.from_user.id, "LANGUAGE_SELECTION_START", {"lang": callback.data})
    
    lang_code = callback.data.split("_")[1]
    await state.update_data(lang_code=lang_code)
    
    await state.set_state(TranscribeProcess.waiting_for_diarization)
    log_event(callback.from_user.id, "STATE_CHANGE", {"new_state": "waiting_for_diarization"})

    await callback.message.edit_text(
        "Определять разных спикеров (говорящих) на записи?\n\n"
        "Разделение по спикерам делает текст удобнее, но обработка может занять чуть больше времени.",
        reply_markup=get_diarization_keyboard()
    )


@router.callback_query(F.data.startswith("diar_"), StateFilter(TranscribeProcess.waiting_for_diarization))
async def process_diarization_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()  # Обязательно отвечаем на callback
    log_event(callback.from_user.id, "DIARIZATION_SELECTION_START", {"diar": callback.data})
    
    diarization = True if callback.data == "diar_yes" else False
    
    await callback.message.edit_text("⏳ Загружаю файл... Это может занять некоторое время.")
    await state.set_state(TranscribeProcess.processing)
    log_event(callback.from_user.id, "STATE_CHANGE", {"new_state": "processing"})
    
    data = await state.get_data()
    file_id = data['file_id']
    file_name = data['file_name']
    lang_code = data['lang_code']
    
    result_path = None
    
    file_size_mb = data.get('file_size_mb', 0)
    
    try:
        # Используем новую функцию для полного цикла обработки
        formatted_text, result_path = await transcribe_user_file(
            bot=bot,
            file_id=file_id,
            user_id=callback.from_user.id,
            file_name=file_name,
            language_code=lang_code,
            diarization=diarization
        )
        
        # Записываем успешную статистику
        db.add_usage_stat(
            user_id=callback.from_user.id,
            file_size_mb=file_size_mb,
            language=lang_code,
            success=True
        )
        
        # Обновляем статус
        await callback.message.edit_text("⏳ Файл обработан. Отправляю результат...")
        
        # Send text in quote first
        if len(formatted_text) <= 4000:
            try:
                await callback.message.answer(f"<blockquote>{formatted_text}</blockquote>", parse_mode="HTML")
            except Exception as text_error:
                log_error(callback.from_user.id, "SEND_TEXT_ERROR", str(text_error))
        else:
            await callback.message.answer("Текст слишком длинный, отправляю файлом.")
        
        # Send TXT file
        try:
            document = FSInputFile(str(result_path), filename=result_path.name)
            await callback.message.answer_document(document)
        except Exception as doc_error:
            error_str = str(doc_error)
            if "file is too big" in error_str.lower():
                await callback.message.answer(
                    "⚠️ Не удалось отправить файл результата. Текст уже отправлен в чат."
                )
                log_error(callback.from_user.id, "SEND_DOC_ERROR", error_str)
            else:
                raise
        
    except FileTooBigError as e:
        log_error(callback.from_user.id, "FILE_TOO_BIG", str(e))
        db.add_usage_stat(
            user_id=callback.from_user.id,
            file_size_mb=file_size_mb,
            language=lang_code,
            success=False,
            error_message=str(e)
        )
        await callback.message.edit_text(
            f"❌ {str(e)}\n\n"
            "Попробуйте сжать файл или отправить его частями."
        )
        await state.clear()
        return
        
    except StorageError as e:
        log_error(callback.from_user.id, "STORAGE_ERROR", str(e))
        db.add_usage_stat(
            user_id=callback.from_user.id,
            file_size_mb=file_size_mb,
            language=lang_code,
            success=False,
            error_message=str(e)
        )
        await callback.message.edit_text(
            "⚠️ Недостаточно места на сервере.\n\n"
            "Попробуйте позже или обратитесь к администратору."
        )
        await state.clear()
        return
        
    except Exception as e:
        error_str = str(e)
        
        # Проверяем на ошибку "file is too big" от Telegram
        if "file is too big" in error_str.lower() or "too big" in error_str.lower():
            db.add_usage_stat(
                user_id=callback.from_user.id,
                file_size_mb=file_size_mb,
                language=lang_code,
                success=False,
                error_message="File too big to download"
            )
            await callback.message.edit_text(
                "⚠️ Файл слишком большой для загрузки.\n\n"
                "Telegram не позволяет скачать файлы больше ~20MB через стандартный API.\n"
                "Попробуйте переслать файл как аудио или уменьшить размер."
            )
            log_error(callback.from_user.id, "FILE_TOO_BIG_DOWNLOAD", error_str)
            await state.clear()
            return
        
        db.add_usage_stat(
            user_id=callback.from_user.id,
            file_size_mb=file_size_mb,
            language=lang_code,
            success=False,
            error_message=error_str
        )
        log_error(callback.from_user.id, "TRANSCRIBE_ERROR", error_str)
        await callback.message.answer(f"❌ Произошла ошибка при обработке: {error_str}")
        
    finally:
        # Cleanup result file after sending
        if result_path:
            await cleanup_after_sending(result_path, callback.from_user.id)
            
        await state.clear()
        log_event(callback.from_user.id, "HANDLER_END", {})


# Обработчик для проверки подписки (callback от кнопки "Я подписался")
@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot):
    """Проверяет подписку после нажатия кнопки 'Я подписался'"""
    user_id = callback.from_user.id
    
    # Проверяем подписку
    if await check_subscription(bot, user_id):
        # Удаляем сообщение с требованием подписки
        await callback.message.delete()
        # Показываем приветственное сообщение
        await callback.message.answer(
            "✅ Подписка подтверждена!\n\n"
            "Привет! Я бот для транскрибации аудио с помощью мощной нейросети.\n\n"
            "Отправь мне аудиофайл или перешли голосовое сообщение, "
            "и я переведу его в текст. Ты также можешь выбрать опцию разделения по спикерам.\n\n"
            f"⚡️ Максимальный размер файла: {MAX_FILE_SIZE_MB} МБ"
        )
    else:
        await callback.answer(
            "❌ Вы не подписаны на канал. Пожалуйста, подпишитесь и попробуйте снова.",
            show_alert=True
        )


# Обработчик для неизвестных callback_data
@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает неизвестные callback_data"""
    await callback.answer("Неизвестная команда", show_alert=True)
    log_event(callback.from_user.id, "UNKNOWN_CALLBACK", {"callback_data": callback.data})
