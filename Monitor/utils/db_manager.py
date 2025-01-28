import os
import sqlite3
import shutil
import time
import threading
from config import DATABASE_PATH, LOCAL_DATABASE_PATH, CACHE_UPDATE_INTERVAL, LOCK_FILE_PATH


class DatabaseManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.update_local_cache()

    def get_connection(self):
        conn = sqlite3.connect(LOCAL_DATABASE_PATH)
        conn.execute('PRAGMA journal_mode=WAL;')
        cursor = conn.cursor()
        return conn, cursor

    def update_local_cache(self):
        while os.path.exists(LOCK_FILE_PATH):
            print("Database is locked, waiting...")
            time.sleep(1)

        try:
            if not os.path.exists(LOCAL_DATABASE_PATH) or not self.is_cache_up_to_date():
                local_cache_dir = os.path.dirname(LOCAL_DATABASE_PATH)
                if not os.path.exists(local_cache_dir):
                    os.makedirs(local_cache_dir)
                shutil.copyfile(DATABASE_PATH, LOCAL_DATABASE_PATH)
                print("Local cache updated.")
        except Exception as e:
            print(f"Error updating local cache: {e}")

    def is_cache_up_to_date(self):
        try:
            if not os.path.exists(LOCAL_DATABASE_PATH):
                return False
            network_mtime = os.path.getmtime(DATABASE_PATH)
            local_mtime = os.path.getmtime(LOCAL_DATABASE_PATH)
            return local_mtime >= network_mtime
        except Exception as e:
            print(f"Error checking cache status: {e}")
            return False

    def periodic_cache_update(self):
        while True:
            try:
                print("Cache Updating...")
                self.update_local_cache()
            except Exception as e:
                print(f"Error in periodic cache update: {e}")
            time.sleep(CACHE_UPDATE_INTERVAL)

