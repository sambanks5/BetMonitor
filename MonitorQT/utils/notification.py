import os
import json
import fasteners
import time
from datetime import datetime
from config import NETWORK_PATH_PREFIX

def log_notification(message, important=False, pinned=False):
    time_str = datetime.now().strftime('%H:%M:%S')
    file_lock = fasteners.InterProcessLock(os.path.join(NETWORK_PATH_PREFIX, 'notifications.lock'))
    try:
        with file_lock:
            try:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'notifications.json'), 'r') as f:
                    notifications = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                notifications = []

            if pinned:
                notifications = [notification for notification in notifications if not notification.get('pinned', False)]
            
            notifications.insert(0, {'time': time_str, 'message': message, 'important': important, 'pinned': pinned})
            
            temp_filename = os.path.join(NETWORK_PATH_PREFIX, 'notifications_temp.json')
            with open(temp_filename, 'w') as f:
                json.dump(notifications, f, indent=4)
            
            time.sleep(0.1)
            
            os.replace(temp_filename, os.path.join(NETWORK_PATH_PREFIX, 'notifications.json'))
    except Exception as e:
        print(f"Error logging notification: {e}")
