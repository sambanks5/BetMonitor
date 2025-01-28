import sqlite3

def load_database():
    print("\nLoading database")
    conn = sqlite3.connect('wager_database.sqlite')
    conn.execute('PRAGMA journal_mode=WAL;')  # Enable WAL mode
    return conn
