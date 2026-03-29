# Project Context: Telegram Транскрибатор

> **Последнее обновление:** 2026-03-29  
> **Версия документации:** 1.1

---

## 📋 Обзор проекта

### Назначение
Telegram бот для транскрибации аудио и видео файлов в текст с использованием нейросети AssemblyAI. Поддерживает определение спикеров, автоопределение языка и пакетную обработку файлов.

### Технологический стек
- **Python 3.11** — основной язык
- **aiogram 3.x** — асинхронный фреймворк для Telegram Bot API
- **AssemblyAI API** — нейросеть для транскрибации
- **SQLite** — база данных пользователей
- **Docker & docker-compose** — контейнеризация

### Режимы работы
| Режим | Лимит файла | Описание |
|-------|-------------|----------|
| Обычный | 20 МБ | Стандартный Telegram Bot API |
| Локальный API | 200 МБ | Local Telegram Bot API сервер |

---

## 🏗️ Архитектура

### Структура файлов

```
telegram-transcriber/
├── main.py                 # Точка входа, инициализация бота
├── config.py               # Конфигурация из переменных окружения
├── database.py             # Работа с SQLite базой данных
├── debug.py                # Логирование событий
├── requirements.txt        # Python зависимости
├── Dockerfile              # Docker образ бота
├── docker-compose.yml      # Оркестрация контейнеров
├── deploy.sh               # Скрипт деплоя
├── .env.example            # Пример конфигурации
│
├── handlers/
│   ├── __init__.py         # Экспорт роутеров
│   ├── states.py           # FSM состояния
│   └── user_handlers.py    # Основные обработчики сообщений
│
├── services/
│   ├── transcriber.py      # Сервис транскрибации
│   ├── subscription.py     # Проверка подписки на канал
│   └── cleanup.py          # Очистка временных файлов
│
├── keyboards/
│   └── inline.py           # Inline клавиатуры
│
├── plans/                   # Документация планов развития
│   ├── migration_to_local_api.md
│   └── subscription_and_large_files.md
│
└── temp_files/             # Временные файлы (создаётся автоматически)
    └── {user_id}/          # Папка для каждого пользователя
```

### Основные модули

#### [`config.py`](config.py)
Загружает переменные окружения через `python-dotenv` и определяет:
- Токены API (BOT_TOKEN, ASSEMBLYAI_API_KEY)
- Настройки локального API (USE_LOCAL_API, LOCAL_API_URL)
- Параметры канала подписки (CHANNEL_ID, CHANNEL_URL)
- Лимиты файлов (MAX_FILE_SIZE_MB, MAX_STORAGE_GB)

#### [`main.py`](main.py)
- Инициализация бота и диспетчера
- Настройка сессии (обычная или локальный API)
- Регистрация роутеров обработчиков
- Установка команд бота

#### [`handlers/user_handlers.py`](handlers/user_handlers.py)
Все обработчики сообщений и callback-запросов:
- `/start` — приветствие с проверкой подписки
- `/help` — справка
- Обработка аудио/видео файлов
- Пакетная обработка групп файлов (media groups)
- Выбор языка и режима диаризации

#### [`services/transcriber.py`](services/transcriber.py)
Бизнес-логика транскрибации:
- Скачивание файлов с Telegram
- Интеграция с AssemblyAI API
- Форматирование результатов
- Управление временными файлами

#### [`services/subscription.py`](services/subscription.py)
Проверка подписки пользователя на канал через `get_chat_member`.

#### [`services/cleanup.py`](services/cleanup.py)
Менеджер дискового пространства:
- Контроль использования диска
- Автоматическая очистка старых файлов
- Статистика хранилища

---

## 🔧 Конфигурация

### Переменные окружения (.env)

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `BOT_TOKEN` | ✅ | Токен бота от @BotFather |
| `ASSEMBLYAI_API_KEY` | ✅ | Ключ AssemblyAI API |
| `USE_LOCAL_API` | ❌ | `true` для локального API (200MB) |
| `LOCAL_API_URL` | ❌ | URL локального API сервера |
| `API_ID` | ⚠️ | Telegram API ID (обязательно если USE_LOCAL_API=true) |
| `API_HASH` | ⚠️ | Telegram API Hash (обязательно если USE_LOCAL_API=true) |
| `LOCAL_API_VOLUME_PATH` | ❌ | Путь к файлам локального API |
| `CHANNEL_ID` | ❌ | ID канала для проверки подписки |
| `CHANNEL_URL` | ❌ | URL канала для кнопки подписки |
| `MAX_FILE_SIZE_MB` | ❌ | Макс. размер файла (по умолчанию 200) |
| `MAX_STORAGE_GB` | ❌ | Лимит хранилища (по умолчанию 10) |

### Флаги конфигурации

```python
# Включение локального API для файлов до 200 МБ
USE_LOCAL_API=True

# Стандартный режим (до 20 МБ)
USE_LOCAL_API=False
```

---

## 📦 Сервисы

### [`services/transcriber.py`](services/transcriber.py:1)

#### Классы исключений
- [`FileTooBigError`](services/transcriber.py:24) — файл превышает лимит размера
- [`StorageError`](services/transcriber.py:29) — недостаточно места на диске

#### Основные функции

| Функция | Назначение |
|---------|------------|
| [`sync_transcribe()`](services/transcriber.py:34) | Синхронная транскрибация через AssemblyAI |
| [`async_transcribe()`](services/transcriber.py:53) | Асинхронная обёртка с ThreadPoolExecutor |
| [`format_transcript()`](services/transcriber.py:59) | Форматирование результата с разделением по спикерам |
| [`download_telegram_file()`](services/transcriber.py:76) | Скачивание файла с проверками размера и места |
| [`transcribe_user_file()`](services/transcriber.py:144) | Полный цикл: скачать → транскрибировать → сохранить |
| [`cleanup_after_sending()`](services/transcriber.py:194) | Удаление файла результата после отправки |

#### Особенности скачивания файлов
1. **Локальный API**: файл копируется напрямую с диска (быстро)
2. **Стандартный API**: скачивание через HTTP или bot.download()
3. Проверка размера файла ПЕРЕД скачиванием
4. Проверка свободного места с запасом 50%

### [`services/subscription.py`](services/subscription.py:1)

#### Функция [`check_subscription()`](services/subscription.py:8)
```python
async def check_subscription(bot: Bot, user_id: int) -> bool:
    """
    Проверяет подписку пользователя на канал.
    
    Возвращает:
    - True: пользователь подписан
    - False: не подписан
    
    Fail-open: при ошибке API возвращает True (разрешает доступ)
    """
```

**Статусы подписки:**
- `member` — обычный подписчик
- `administrator` — администратор канала
- `creator` — создатель канала

### [`services/cleanup.py`](services/cleanup.py:1)

#### Константы
- `TEMP_DIR = "temp_files"` — папка для временных файлов
- `MAX_FILES_PER_USER = 100` — лимит файлов на пользователя

#### Основные функции

| Функция | Назначение |
|---------|------------|
| [`get_storage_usage()`](services/cleanup.py:33) | Возвращает (использовано_МБ, всего_МБ) |
| [`cleanup_old_files()`](services/cleanup.py:50) | Удаляет файлы старше N часов |
| [`ensure_storage_available()`](services/cleanup.py:97) | Проверяет и освобождает место |
| [`get_user_temp_dir()`](services/cleanup.py:125) | Создаёт папку пользователя |
| [`cleanup_user_files()`](services/cleanup.py:141) | Удаляет все файлы пользователя |
| [`get_storage_stats()`](services/cleanup.py:161) | Полная статистика хранилища |

#### Стратегия очистки
1. При нехватке места удаляются файлы старше 1 часа
2. Если недостаточно — удаляются файлы старше 30 минут
3. Автоматически удаляются пустые директории

---

## 🔄 Потоки данных

### Обработка одиночного файла

```
Пользователь отправляет аудио
         ↓
    Проверка подписки
         ↓ (подписан)
    Проверка размера файла
         ↓ (OK)
    Сохранение file_id в FSM
         ↓
    Выбор языка (inline keyboard)
         ↓
    Выбор диаризации (inline keyboard)
         ↓
    Скачивание файла
         ↓
    Проверка свободного места
         ↓ (OK)
    Транскрибация через AssemblyAI
         ↓
    Форматирование результата
         ↓
    Отправка текста в чат
         ↓
    Отправка TXT файла
         ↓
    Удаление временных файлов
```

### Пакетная обработка (media group)

```
Пользователь отправляет группу аудио (до 5 шт)
         ↓
    Сбор файлов в _media_group_cache
         ↓ (ожидание 1.5 сек)
    Проверка подписки (один раз)
         ↓
    Выбор языка (для всех файлов)
         ↓
    Выбор диаризации (для всех файлов)
         ↓
    Цикл обработки каждого файла:
    ├── Скачивание
    ├── Транскрибация
    ├── Отправка результата
    └── Очистка
         ↓
    Итоговое сообщение со статистикой
```

---

## 🚀 Деплой

### Dockerfile ([`Dockerfile`](Dockerfile))
- Базовый образ: `python:3.11-slim`
- Системные зависимости: `ffmpeg`, `build-essential`
- Непривилегированный пользователь: `appuser`
- Рабочая директория: `/app`

### docker-compose.yml ([`docker-compose.yml`](docker-compose.yml))

**Сервисы:**
1. **bot** — основной контейнер бота
2. **telegram-api** — Local Telegram Bot API сервер

**Volumes:**
- `telegram_api_data` — файлы локального API (общий между контейнерами)

> ⚠️ **Важно:** Код бота берётся из Docker образа, а не из volume. При обновлении образа новый код применяется автоматически.

**Сеть:**
- `bot-network` — внутренняя сеть для связи бота с API

### deploy.sh ([`deploy.sh`](deploy.sh))
```bash
#!/bin/bash
git pull
docker-compose up -d --build
docker image prune -f
```

### Команды для деплоя

```bash
# Первый запуск
docker-compose up -d --build

# Обновление
./deploy.sh

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

---

## ⚠️ Важные особенности

### Лимиты файлов
- **Стандартный API**: 20 МБ (ограничение Telegram)
- **Локальный API**: 200 МБ (требуется отдельный контейнер)
- Проверка размера происходит ДО скачивания

### Обработка ошибок
Все ошибки логируются через [`debug.py`](debug.py):
- `log_event()` — информационные события
- `log_error()` — ошибки с деталями

### Пакетная обработка
- Максимум **5 файлов** в одной группе
- Ожидание **1.5 секунды** для сбора всех файлов
- Каждый файл обрабатывается независимо
- Итоговая статистика: успешных / ошибок

### FSM (Finite State Machine)
Состояния определены в [`handlers/states.py`](handlers/states.py):

**TranscribeProcess** — одиночный файл:
1. `waiting_for_language`
2. `waiting_for_diarization`
3. `processing`

**BatchTranscribeProcess** — группа файлов:
1. `collecting_files`
2. `waiting_for_language`
3. `waiting_for_diarization`
4. `processing`

### Fail-open подход
- При ошибке проверки подписки — доступ разрешается
- При ошибке API — пользователь получает понятное сообщение

---

## 📝 Правила для агентов

### ⚠️ ВАЖНОЕ ПРАВИЛО

**После каждых правок кода ОБЯЗАТЕЛЬНО обновляй этот файл!**

При внесении изменений в проект:

1. **Обнови соответствующие секции документации**
   - Если добавил новый сервис → обнови секцию "Сервисы"
   - Если изменил конфигурацию → обнови секцию "Конфигурация"
   - Если изменил поток данных → обнови секцию "Потоки данных"

2. **Добавь запись в секцию "История изменений"**
   - Укажи дату
   - Кратко опиши суть изменений
   - Укажи затронутые файлы

3. **Это сэкономит токены будущим агентам**
   - Им не придётся анализировать весь код
   - Они быстро поймут архитектуру проекта
   - Снизится риск внесения некорректных изменений

### Рекомендации по изменениям

- **Новые обработчики**: добавляй в `handlers/user_handlers.py` или создавай новый файл в `handlers/`
- **Новые сервисы**: создавай файлы в `services/` с понятными названиями
- **Новые состояния**: добавляй в `handlers/states.py`
- **Новые клавиатуры**: добавляй в `keyboards/inline.py`
- **Изменения конфигурации**: обновляй `config.py` и `.env.example`

---

## 📜 История изменений

| Дата | Изменение | Файлы |
|------|-----------|-------|
| 2026-03-29 | Исправлен docker-compose: удалён volume bot_data:/app для корректных обновлений образа | `docker-compose.yml` |
| 2026-03-28 | Добавлена система подписки на канал | `services/subscription.py`, `handlers/user_handlers.py`, `keyboards/inline.py` |
| 2026-03-28 | Поддержка файлов до 200 МБ через локальный API | `config.py`, `main.py`, `docker-compose.yml`, `services/transcriber.py` |
| 2026-03-28 | Пакетная отправка до 5 аудио файлов | `handlers/user_handlers.py`, `handlers/states.py` |
| 2026-03-28 | Сервис очистки временных файлов | `services/cleanup.py`, `services/transcriber.py` |
| 2026-03-28 | Исправления из code review | Все файлы |
| 2026-03-28 | Создана документация PROJECT_CONTEXT.md | `PROJECT_CONTEXT.md` |

---

## 🔗 Полезные ссылки

- [AssemblyAI Documentation](https://www.assemblyai.com/docs/)
- [aiogram 3.x Documentation](https://docs.aiogram.dev/en/latest/)
- [Local Telegram Bot API](https://core.telegram.org/bots/api#using-a-local-bot-api-server)
- [Telegram Bot API Limits](https://core.telegram.org/bots/faq#how-do-i-upload-a-large-file)

---

*Документация создана для экономии токенов будущих AI-агентов и обеспечения согласованности развития проекта.*
