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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount_seconds INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
def deduct_balance(user_id: int, duration_seconds: int) -> bool:
    user = get_user(user_id)
    current_month = datetime.datetime.now().strftime("%Y-%m")
    
    # Reset free limits if new month
    if user['last_free_reset_month'] != current_month:
        user['free_minutes_used'] = 0
        user['last_free_reset_month'] = current_month
        conn = sqlite3.connect(DB_FILE)
        conn.cursor().execute(
            'UPDATE users SET free_minutes_used = 0, last_free_reset_month = ? WHERE user_id = ?', 
            (current_month, user_id)
        )
        conn.commit()
        conn.close()

    free_seconds_left = max(0, 5 * 60 - (user['free_minutes_used'] * 60))
    
    if free_seconds_left >= duration_seconds:
        # Cover by free tier entirely
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET free_minutes_used = free_minutes_used + ? WHERE user_id = ?', 
                       (duration_seconds / 60, user_id))
        conn.commit()
        conn.close()
        return True
    
    # Part or all from balance
    seconds_to_deduct_from_balance = duration_seconds - free_seconds_left
    if user['balance_seconds'] >= seconds_to_deduct_from_balance:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # update free minutes used to max (5 mins) if we used up the free tier
        new_free_used = user['free_minutes_used'] + (free_seconds_left / 60)
        
        cursor.execute('''
            UPDATE users 
            SET balance_seconds = balance_seconds - ?,
                free_minutes_used = ?
            WHERE user_id = ?
        ''', (seconds_to_deduct_from_balance, new_free_used, user_id))
        conn.commit()
        conn.close()
        return True
        
    return False

def can_process_audio(user_id: int, duration_seconds: int) -> bool:
    user = get_user(user_id)
    current_month = datetime.datetime.now().strftime("%Y-%m")
    
    free_minutes_used = user['free_minutes_used']
    if user['last_free_reset_month'] != current_month:
        free_minutes_used = 0
        
    free_seconds_left = max(0, 5 * 60 - (free_minutes_used * 60))
    total_available_seconds = free_seconds_left + user['balance_seconds']
    
    return total_available_seconds >= duration_seconds

def create_payment(payment_id: str, user_id: int, seconds: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO payments (id, user_id, amount_seconds) VALUES (?, ?, ?)', (payment_id, user_id, seconds))
    conn.commit()
    conn.close()

def get_payment(payment_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM payments WHERE id = ?', (payment_id,))
    payment = cursor.fetchone()
    conn.close()
    if payment:
        return {'id': payment[0], 'user_id': payment[1], 'amount_seconds': payment[2], 'status': payment[3], 'created_at': payment[4]}
    return None

def complete_payment(payment_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE payments SET status = "completed" WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
