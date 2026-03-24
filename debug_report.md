# Детальный отчет о проблемах в коде Telegram-бота

## Резюме

Проведен анализ 5 ключевых файлов проекта. Выявлено **4 критических проблемы** и **3 потенциальные проблемы**, которые могут вызывать глюки и некорректную работу бота.

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### 1. Клавиатура выбора языка определена, но НЕ используется

**Файл:** [`keyboards/inline.py`](keyboards/inline.py:4)

**Проблема:** Функция [`get_language_keyboard()`](keyboards/inline.py:4) определена с 6 языками (ru, en, auto, es, fr, de), но в [`handlers/user_handlers.py`](handlers/user_handlers.py:84) создается **своя собственная** клавиатура только с 3 языками.

**В keyboards/inline.py (строки 6-19):**
```python
def get_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Автоопределение", callback_data="lang_auto")],
            [InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
            [InlineKeyboardButton(text="English", callback_data="lang_en")],
            [InlineKeyboardButton(text="Español", callback_data="lang_es")],      # Не показывается
            [InlineKeyboardButton(text="Français", callback_data="lang_fr")],     # Не показывается
            [InlineKeyboardButton(text="Deutsch", callback_data="lang_de")]     # Не показывается
        ]
    )
```

**В user_handlers.py (строки 84-89):**
```python
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="🤖 Автоопределение", callback_data="lang_auto")]
    ]
)
```

**Влияние:** Код избыточен, но работает. Однако если в будущем использовать `get_language_keyboard()`, обработчики для `lang_es`, `lang_fr`, `lang_de` должны работать корректно (они обрабатываются одним фильтром `F.data.startswith("lang_")`).

---

### 2. Файл services/lavatop.py удалён

**Файл:** `services/lavatop.py`

**Проблема:** Файл `services/lavatop.py` был удалён из проекта. Ранее этот файл содержал функции для интеграции с платёжным сервисом Lava.top:
- `create_payment_link()` — создание платёжных ссылок
- `check_payment_status()` — проверка статуса платежа

**Влияние:** Функционал оплаты полностью отсутствует. Бот работает в бесплатном режиме без ограничений.

---

### 3. Используется MemoryStorage без персистентности

**Файл:** [`main.py`](main.py:36)

**Проблема:** FSM использует [`MemoryStorage()`](main.py:36), который не сохраняет состояние между перезапусками бота.

**Код:**
```python
dp = Dispatcher(storage=MemoryStorage())
```

**Влияние:** Если бот перезапустится во время процесса транскрибации (пользователь нажал кнопку языка, но еще не выбрал диаризацию), пользователь застрянет в неопределенном состоянии. После перезапуска FSM состояние будет потеряно.

---

### 4. Неиспользуемые функции в database.py

**Файл:** [`database.py`](database.py:46)

**Проблема:** В [`database.py`](database.py:46) определены функции `deduct_balance()` и `can_process_audio()`, но они **нигде не вызываются** в проекте.

**Код:**
```python
def deduct_balance(user_id: int, duration_seconds: int) -> bool:
    # ... логика списания баланса ...

def can_process_audio(user_id: int, duration_seconds: int) -> bool:
    # ... проверка возможности обработки ...
```

**Влияние:** Код избыточен и не используется. Бот работает в бесплатном режиме без ограничений по балансу.

---

## 🟡 ПОТЕНЦИАЛЬНЫЕ ПРОБЛЕМЫ

### 5. Возможная утечка памяти при ошибках

**Файл:** [`handlers/user_handlers.py`](handlers/user_handlers.py:159)

**Проблема:** В блоке finally (строки 161-168) переменные `file_path` и `result_path` проверяются через `in locals()`, но если исключение произойдет раньше (до создания этих переменных), переменные не будут определены и могут возникнуть NameError.

**Код:**
```python
finally:
    if 'file_path' in locals() and os.path.exists(file_path):  # ⚠️
        os.remove(file_path)
    if 'result_path' in locals() and os.path.exists(result_path):  # ⚠️
        os.remove(result_path)
```

**Рекомендация:** Использовать `getattr()` или try-except вместо проверки через `in locals()`.

---

### 6. Директория загрузки не очищается

**Файл:** [`handlers/user_handlers.py`](handlers/user_handlers.py:17)

**Проблема:** Директория `downloads/` создается при старте, но никогда не очищается. Со временем там накопятся тысячи файлов.

**Код:**
```python
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
```

**Влияние:** Заполнение диска, замедление работы бота.

---

### 7. Нет обработки ошибок в callback

**Файл:** [`handlers/user_handlers.py`](handlers/user_handlers.py:103)

**Проблема:** В обработчике [`process_language_selection()`](handlers/user_handlers.py:103) нет вызова `await callback.answer()`.

**Код:**
```python
@router.callback_query(F.data.startswith("lang_"), StateFilter(TranscribeProcess.waiting_for_language))
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    lang_code = callback.data.split("_")[1]
    await state.update_data(lang_code=lang_code)
    await state.set_state(TranscribeProcess.waiting_for_diarization)
    # ...
    # НЕТ await callback.answer()!
```

**Влияние:** Некоторые клиенты Telegram могут показывать "часы" на кнопке, пока обработчик выполняется.

---

## 📊 Сводная таблица проблем

| # | Проблема | Файл | Строки | Критичность |
|---|-----------|------|--------|-------------|
| 1 | Неиспользуемая клавиатура языков | inline.py | 4-19 | 🟡 Низкая |
| 2 | Файл services/lavatop.py удалён | lavatop.py | - | 🔴 Критическая |
| 3 | MemoryStorage без персистентности | main.py | 36 | 🟡 Средняя |
| 4 | Неиспользуемые функции в database.py | database.py | 46, 95 | 🟡 Низкая |
| 5 | Потенциальная утечка памяти | user_handlers.py | 161-168 | 🟡 Низкая |
| 6 | Директория не очищается | user_handlers.py | 17-18 | 🟡 Низкая |
| 7 | Нет callback.answer() | user_handlers.py | 103 | 🟡 Низкая |

---

## ✅ Рекомендуемые действия

1. **Важно:** Удалить неиспользуемую функцию `get_language_keyboard()` из `keyboards/inline.py`
2. **Важно:** Удалить неиспользуемые функции `deduct_balance()` и `can_process_audio()` из `database.py`
3. **Важно:** Заменить MemoryStorage на Redis или SQLite-based storage
4. **Важно:** Добавить `await callback.answer()` во все обработчики
5. **Важно:** Добавить автоматическую очистку папки downloads/
6. **Важно:** Исправить проверку переменных в блоке finally (использовать try-except)

---

## 📝 Вывод

Код содержит несколько проблем,大部分 которых носят низкий приоритет. Бот работает в **бесплатном режиме** без ограничений по балансу. Основные задачи по улучшению — удаление неиспользуемого кода, замена MemoryStorage на персистентное хранилище и добавление обработки ошибок.
