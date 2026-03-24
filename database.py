import sqlite3
import datetime

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
