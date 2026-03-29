import sqlite3
import datetime
from typing import Optional, List, Dict, Any

DB_FILE = 'bot.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance_seconds INTEGER DEFAULT 0,
            free_minutes_used INTEGER DEFAULT 0,
            last_free_reset_month TEXT
        )
    ''')
    # Таблица статистики использования
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_size_mb REAL NOT NULL,
            duration_sec INTEGER,
            language TEXT,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        current_month = datetime.datetime.now().strftime("%Y-%m")
        cursor.execute('INSERT INTO users (user_id, last_free_reset_month) VALUES (?, ?)', (user_id, current_month))
        conn.commit()
        # Fetch again
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    conn.close()
    
    # Dict mapping
    keys = ['user_id', 'balance_seconds', 'free_minutes_used', 'last_free_reset_month']
    return dict(zip(keys, user))


def update_user_balance(user_id: int, seconds: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance_seconds = balance_seconds + ? WHERE user_id = ?', (seconds, user_id))
    conn.commit()
    conn.close()


# =====================
# Функции для статистики использования
# =====================

def add_usage_stat(
    user_id: int,
    file_size_mb: float,
    language: Optional[str] = None,
    duration_sec: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None
):
    """Добавляет запись о статистике использования"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO usage_stats (user_id, file_size_mb, duration_sec, language, success, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, file_size_mb, duration_sec, language, 1 if success else 0, error_message))
    conn.commit()
    conn.close()


def get_stats_summary() -> Dict[str, Any]:
    """Возвращает общую статистику для админ панели"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Общее количество пользователей
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    # Общее количество запросов
    cursor.execute('SELECT COUNT(*) FROM usage_stats')
    total_requests = cursor.fetchone()[0]
    
    # Общий объём файлов в MB
    cursor.execute('SELECT COALESCE(SUM(file_size_mb), 0) FROM usage_stats')
    total_size_mb = cursor.fetchone()[0]
    
    # Процент успешных запросов
    cursor.execute('SELECT AVG(success) * 100 FROM usage_stats')
    success_rate = cursor.fetchone()[0] or 0
    
    # Активность за последние 24 часа
    yesterday = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()
    cursor.execute('SELECT COUNT(*) FROM usage_stats WHERE created_at >= ?', (yesterday,))
    active_today = cursor.fetchone()[0]
    
    # Топ языков
    cursor.execute('''
        SELECT language, COUNT(*) as count 
        FROM usage_stats 
        WHERE language IS NOT NULL
        GROUP BY language 
        ORDER BY count DESC 
        LIMIT 3
    ''')
    top_languages = cursor.fetchall()
    
    # Количество ошибок
    cursor.execute('SELECT COUNT(*) FROM usage_stats WHERE success = 0')
    errors_count = cursor.fetchone()[0]
    
    # Средний размер файла
    cursor.execute('SELECT COALESCE(AVG(file_size_mb), 0) FROM usage_stats')
    avg_size = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_requests': total_requests,
        'total_size_mb': total_size_mb,
        'success_rate': success_rate,
        'active_today': active_today,
        'top_languages': top_languages,
        'errors_count': errors_count,
        'avg_size': avg_size
    }
