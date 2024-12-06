####################################################################################
##                                BETVIEWERBETA.PY                                    


## FORMAT AND DISPLAY INCOMING BETS, FIND RUNS ON SELECTIONS, TRACK RACE UPDATION,
## DISPLAY NEXT 3 HORSE & GREYHOUND RACES, CREATE DAILY, CLIENT, STAFF REPORTS,
## SCREEN FOR RISK CLIENTS, OTHER VARIOUS QOL IMPROVEMENTS
####################################################################################

import os
import threading
import pyperclip
import fasteners
import subprocess
import json
import sqlite3
import requests
import random
import gspread
import datetime
import shutil
import time
import tkinter as tk
from collections import defaultdict, Counter
from dateutil.relativedelta import relativedelta
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from tkinter import messagebox, simpledialog, IntVar, font, filedialog
from tkcalendar import DateEntry
from googleapiclient.discovery import build
from pytz import timezone
from tkinter import ttk
from tkinter.ttk import *
from datetime import date, datetime, timedelta
from PIL import Image, ImageTk
from dotenv import load_dotenv

load_dotenv()

LOCAL_DATABASE_PATH = os.getenv('LOCAL_DATABASE_PATH')
LOCK_FILE_PATH = os.getenv('LOCK_FILE_PATH')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
PIPEDRIVE_API_KEY = os.getenv('PIPEDRIVE_API_KEY')
X_RAPIDAPI_KEY = os.getenv('X_RAPIDAPI_KEY')

# Global variable for the database path F:\\GB Bet Monitor\\. CHANGE TO C:// FOR MANAGER TERMINAL
DATABASE_PATH = 'C:\\GB Bet Monitor\\wager_database.sqlite'
NETWORK_PATH_PREFIX = 'C:\\GB Bet Monitor\\'

# UNCOMMENT FOR TESTING
DATABASE_PATH = 'wager_database.sqlite'
NETWORK_PATH_PREFIX = ''

CACHE_UPDATE_INTERVAL = 100 * 1


user = ""
USER_NAMES = {
    'GB': 'George B',
    'GM': 'George M',
    'JP': 'Jon',
    'DF': 'Dave',
    'SB': 'Sam',
    'JJ': 'Joji',
    'AE': 'Arch',
    'EK': 'Ed',
    'VO': 'Victor',
    'MF': 'Mark'
}


def user_login():
    global user, full_name
    while True:
        user = simpledialog.askstring("Input", "Please enter your initials:")
        if user and len(user) <= 2:
            user = user.upper()
            if user in USER_NAMES:
                full_name = USER_NAMES[user]                    
                log_notification(f"{user} logged in")
                break
            else:
                messagebox.showerror("Error", "Could not find staff member! Please try again.")
        else:
            messagebox.showerror("Error", "Maximum of 2 characters.")

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

def user_notification():
    if not user:
        user_login()

    def submit():
        message = entry.get()
        message = (user + ": " + message)
        log_notification(message, important=True, pinned=pin_message_var.get())
        window.destroy()

    window = tk.Toplevel(root)
    window.title("Enter Notification")
    window.iconbitmap('src/splash.ico')
    window.geometry("300x170")
    screen_width = window.winfo_screenwidth()
    window.geometry(f"+{screen_width - 350}+50")

    label = ttk.Label(window, text="Enter your message:")
    label.pack(padx=5, pady=5)

    entry = ttk.Entry(window, width=50)
    entry.pack(padx=5, pady=5)
    entry.focus_set()
    entry.bind('<Return>', lambda event=None: submit())

    pin_message_var = tk.BooleanVar()
    pin_message_checkbutton = ttk.Checkbutton(window, text="Pin this message", variable=pin_message_var)
    pin_message_checkbutton.pack(padx=5, pady=5)

    button = ttk.Button(window, text="Submit", command=submit)
    button.pack(padx=5, pady=10)

class BetDataFetcher:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BetDataFetcher, cls).__new__(cls)
            cls._instance.data = {}
            cls._instance.lock = threading.Lock()
        return cls._instance

    def update_data(self):
        with self.lock:
            with open(os.path.join(NETWORK_PATH_PREFIX, 'src', 'data.json'), 'r') as file:
                self.data = json.load(file)

    def get_data(self):
        with self.lock:
            return self.data

    def get_newreg_clients(self):
        with self.lock:
            return self.data.get('new_registrations', [])

    def get_vip_clients(self):
        with self.lock:
            return self.data.get('vip_clients', [])

    def get_reporting_data(self):
        with self.lock:
            return {
                'daily_turnover': self.data.get('daily_turnover', 0),
                'daily_profit': self.data.get('daily_profit', 0),
                'daily_profit_percentage': self.data.get('daily_profit_percentage', 0),
                'last_updated_time': self.data.get('last_updated_time', ''),
                # 'total_deposits': self.data.get('deposits_summary', {}).get('total_deposits', 0),
                # 'total_sum': self.data.get('deposits_summary', {}).get('total_sum', 0),
                'enhanced_places': self.data.get('enhanced_places', [])
            }

    def get_todays_oddsmonkey_selections(self):
        with self.lock:
            return self.data.get('todays_oddsmonkey_selections', [])

def schedule_data_updates():
    fetcher = BetDataFetcher()
    print("Starting data updates...")   
    while True:
        fetcher.update_data()
        time.sleep(60)

def access_data():
    fetcher = BetDataFetcher()
    vip_clients = fetcher.get_vip_clients()
    newreg_clients = fetcher.get_newreg_clients()
    today_oddsmonkey_selections = fetcher.get_todays_oddsmonkey_selections()
    reporting_data = fetcher.get_reporting_data()
    return vip_clients, newreg_clients, today_oddsmonkey_selections, reporting_data

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

database_manager = DatabaseManager()
threading.Thread(target=database_manager.periodic_cache_update, daemon=True).start()

class BetFeed:
    def __init__(self, root):
        self.root = root
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None, 'selection': None, 'type': None}
        self.feed_lock = threading.Lock()
        self.last_update_time = None
        self.previous_selected_date = None 
        self.initialize_ui()
        self.initialize_text_tags()
        self.start_feed_update()

    def initialize_ui(self):
        self.feed_frame = ttk.LabelFrame(self.root, style='Card', text="Bet Feed")
        self.feed_frame.place(x=5, y=5, width=520, height=640)
        self.feed_frame.grid_columnconfigure(0, weight=1)
        self.feed_frame.grid_columnconfigure(1, weight=0)
        self.feed_frame.grid_rowconfigure(0, weight=1)

        self.limit_bets_var = tk.BooleanVar(value=True)

        self.feed_text = tk.Text(self.feed_frame, font=("Helvetica", 10, "bold"), wrap='word', padx=10, pady=10, bd=0, fg="#000000")
        self.feed_text.config(state='disabled')
        self.feed_text.grid(row=0, column=0, sticky='nsew')
        
        self.feed_scroll = ttk.Scrollbar(self.feed_frame, orient='vertical', command=self.feed_text.yview, cursor="hand2")
        self.feed_scroll.grid(row=0, column=1, sticky='ns')
        self.feed_text.configure(yscrollcommand=self.feed_scroll.set)

        self.filter_frame = ttk.Frame(self.feed_frame)
        self.filter_frame.grid(row=1, column=0, sticky='ew', pady=(3, 0), padx=(11, 0))

        self.filter_frame.grid_rowconfigure(0, weight=1)
        self.filter_frame.grid_rowconfigure(1, weight=1)
        self.filter_frame.grid_rowconfigure(2, weight=1)
        self.filter_frame.grid_columnconfigure(0, weight=0)
        self.filter_frame.grid_columnconfigure(1, weight=0)
        self.filter_frame.grid_columnconfigure(2, weight=1)
        self.filter_frame.grid_columnconfigure(3, weight=2)
        self.filter_frame.grid_columnconfigure(4, weight=1)
        self.filter_frame.grid_columnconfigure(5, weight=1)
        self.filter_frame.grid_columnconfigure(6, weight=1)
        self.filter_frame.grid_columnconfigure(7, weight=1)
        self.filter_frame.grid_columnconfigure(8, weight=1)
        self.filter_frame.grid_columnconfigure(9, weight=1)

        self.date_entry = DateEntry(self.filter_frame, width=8, background='#fecd45', foreground='white', borderwidth=1, date_pattern='dd/mm/yyyy')
        self.date_entry.grid(row=1, column=7, pady=(2, 4), padx=4, sticky='ew', columnspan=2)
        self.date_entry.bind("<<DateEntrySelected>>", lambda event: self.bet_feed())

        self.username_filter_entry = ttk.Entry(self.filter_frame, width=8)
        self.username_filter_entry.grid(row=0, column=0, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.username_filter_entry, 'Client')

        self.unit_stake_filter_entry = ttk.Entry(self.filter_frame, width=3)
        self.unit_stake_filter_entry.grid(row=0, column=1, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.unit_stake_filter_entry, '£')

        self.risk_category_combobox_values = ["", "Any", "M", "W", "C"]
        self.risk_category_filter_entry = ttk.Combobox(self.filter_frame, values=self.risk_category_combobox_values, width=3)
        self.risk_category_filter_entry.grid(row=0, column=2, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.risk_category_filter_entry, 'Risk')

        self.type_combobox_values = ["", "Bet", "Knockback", "SMS"]
        self.type_combobox_entry = ttk.Combobox(self.filter_frame, values=self.type_combobox_values, width=5)
        self.type_combobox_entry.grid(row=0, column=3, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.type_combobox_entry, 'Type')

        self.selection_filter_entry = ttk.Entry(self.filter_frame, width=6)
        self.selection_filter_entry.grid(row=1, column=0, pady=(0, 2), padx=4, sticky='ew', columnspan=3)
        self.set_placeholder(self.selection_filter_entry, 'Selection')

        self.sport_combobox_values = ["", "Horses", "Dogs", "Other"]
        self.sport_combobox_entry = ttk.Combobox(self.filter_frame, values=self.sport_combobox_values, width=5)
        self.sport_combobox_entry.grid(row=1, column=3, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.sport_combobox_entry, 'Sport')

        self.tick_button = ttk.Button(self.filter_frame, text='✔', command=self.apply_filters, width=2)
        self.tick_button.grid(row=0, column=5, sticky='ew', padx=2, pady=(0, 3))
        
        self.reset_button = ttk.Button(self.filter_frame, text='✖', command=self.reset_filters, width=2)
        self.reset_button.grid(row=1, column=5, sticky='ew', padx=2, pady=(0, 3)) 

        self.separator = ttk.Separator(self.filter_frame, orient='vertical')
        self.separator.grid(row=0, column=6, rowspan=2, sticky='ns', pady=1, padx=(12, 5))

        style = ttk.Style()
        large_font = font.Font(size=13)
        style.configure('Large.TButton', font=large_font)

        self.refresh_button = ttk.Button(self.filter_frame, text='⟳', command=self.bet_feed, width=2, style='Large.TButton')
        self.refresh_button.grid(row=0, column=7, padx=2, pady=2)

        self.limit_bets_checkbox = ttk.Checkbutton(self.filter_frame, text="[:200]", variable=self.limit_bets_var)
        self.limit_bets_checkbox.grid(row=0, column=8, pady=(2, 4), padx=4, sticky='e')

        self.activity_frame = ttk.LabelFrame(self.root, style='Card', text="Status")
        self.activity_frame.place(x=530, y=5, width=365, height=150)
        
        self.activity_text = tk.Text(self.activity_frame, font=("Helvetica", 10, "bold"), wrap='word', padx=5, pady=5, bd=0, fg="#000000")
        self.activity_text.config(state='disabled')
        self.activity_text.pack(fill='both', expand=True)        

    def start_feed_update(self):
        scroll_pos = self.feed_text.yview()[0]
        if scroll_pos <= 0.05:
            if self.date_entry.get_date().strftime('%d/%m/%Y') == datetime.today().strftime('%d/%m/%Y'):
                self.bet_feed()
        else:
            pass
        
        self.feed_frame.after(16000, self.start_feed_update)
        
    def bet_feed(self, date_str=None):
        def fetch_and_display_bets():
            if not self.feed_lock.acquire(blocking=False):
                print("Feed update already in progress. Skipping this update.")
                return
            try:
                print("Refreshing feed...")
                vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
                retry_attempts = 2
                for attempt in range(retry_attempts):
                    conn, cursor = database_manager.get_connection()
                    if conn is not None:
                        break
                    elif attempt < retry_attempts - 1:
                        print("Error finding bets. Retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        self.feed_text.config(state="normal")
                        self.feed_text.delete('1.0', tk.END)
                        self.feed_text.insert('end', "Error finding bets. Please try refreshing.", "center")
                        self.feed_text.config(state="disabled")
                        return
    
                selected_date = self.date_entry.get_date().strftime('%d/%m/%Y')
                if self.previous_selected_date != selected_date:
                    self.last_update_time = None
                    self.previous_selected_date = selected_date
    
                self.update_activity_frame(reporting_data, cursor, selected_date)
    
                filters_active = any([
                    self.current_filters['username'],
                    self.current_filters['unit_stake'],
                    self.current_filters['risk_category'],
                    self.current_filters['sport'],
                    self.current_filters['selection'],
                    self.current_filters['type']
                ])
    
                if not filters_active and self.last_update_time and selected_date == datetime.today().strftime('%d/%m/%Y'):
                    cursor.execute("SELECT MAX(time) FROM database WHERE date = ?", (selected_date,))
                    latest_time = cursor.fetchone()[0]
                    if latest_time <= self.last_update_time:
                        return
    
                username = self.current_filters['username']
                unit_stake = self.current_filters['unit_stake']
                risk_category = self.current_filters['risk_category']
                sport = self.current_filters['sport']
                selection_search_term = self.current_filters['selection']
                type_filter = self.current_filters['type']
    
                sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
                sport_value = sport_mapping.get(sport)
    
                type_mapping = {'Bet': 'BET', 'Knockback': 'WAGER KNOCKBACK', 'SMS': 'SMS WAGER'}
                type_value = type_mapping.get(type_filter)
    
                query = "SELECT * FROM database WHERE date = ?"
                params = [selected_date]
    
                if username:
                    query += " AND customer_ref = ?"
                    params.append(username.upper())
                if unit_stake:
                    query += " AND unit_stake = ?"
                    params.append(unit_stake)
                if risk_category and risk_category != 'Any':
                    query += " AND risk_category = ?"
                    params.append(risk_category)
                elif risk_category == 'Any':
                    query += " AND risk_category != '-'"
                if sport_value is not None:
                    query += " AND EXISTS (SELECT 1 FROM json_each(database.sports) WHERE json_each.value = ?)"
                    params.append(sport_value)
                    print(sport_value)
                if selection_search_term:
                    query += " AND selections LIKE ?"
                    params.append(f"%{selection_search_term}%")
                if type_value:
                    query += " AND type = ?"
                    params.append(type_value)
    
                query += " ORDER BY time DESC"
    
                cursor.execute(query, params)
                filtered_bets = cursor.fetchall()
    
                self.feed_text.config(state="normal")
                self.feed_text.delete('1.0', tk.END)
                separator = '-------------------------------------------------------------------------------------------------\n'
                column_names = [desc[0] for desc in cursor.description]
    
                if not filtered_bets:
                    self.feed_text.insert('end', "No bets found with the current filters or date.", 'center')
                else:
                    if self.limit_bets_var.get():
                        filtered_bets = filtered_bets[:200]
    
                    text_to_insert = []
                    tags_to_apply = []
    
                    for bet in filtered_bets:
                        bet_dict = dict(zip(column_names, bet))
    
                        if bet_dict['type'] != 'SMS WAGER' and bet_dict['selections'] is not None:
                            bet_dict['selections'] = json.loads(bet_dict['selections']) 
    
                        text_segments = self.format_bet_text(bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data)
    
                        for text, tag in text_segments:
                            start_idx = sum(len(segment) for segment in text_to_insert)
                            text_to_insert.append(text)
                            end_idx = start_idx + len(text)
                            if tag:
                                tags_to_apply.append((tag, start_idx, end_idx))
    
                        sep_start_idx = sum(len(segment) for segment in text_to_insert)
                        text_to_insert.append(separator)
                        sep_end_idx = sep_start_idx + len(separator)
                        tags_to_apply.append(("bold", sep_start_idx, sep_end_idx))
    
                    self.feed_text.insert('end', ''.join(text_to_insert))
    
                    optimized_tags = []
                    if tags_to_apply:
                        current_tag, current_start, current_end = tags_to_apply[0]
                        for tag, start, end in tags_to_apply[1:]:
                            if tag == current_tag and start == current_end:
                                current_end = end
                            else:
                                optimized_tags.append((current_tag, current_start, current_end))
                                current_tag, current_start, current_end = tag, start, end
                        optimized_tags.append((current_tag, current_start, current_end))
    
                    for tag, start_idx, end_idx in optimized_tags:
                        start_idx = f"1.0 + {start_idx}c"
                        end_idx = f"1.0 + {end_idx}c"
                        self.feed_text.tag_add(tag, start_idx, end_idx)
    
                self.feed_text.config(state="disabled")
    
                if filtered_bets:
                    self.last_update_time = max(bet[2] for bet in filtered_bets)
            finally:
                self.feed_lock.release()
                conn.close()
    
        threading.Thread(target=fetch_and_display_bets, daemon=True).start()

    def update_activity_frame(self, reporting_data, cursor, selected_date_str):
        try:
            current_date = datetime.strptime(selected_date_str, '%d/%m/%Y')
            previous_date = current_date - timedelta(days=7)
            current_time = datetime.now().strftime('%H:%M:%S')
            
            current_date_str = current_date.strftime('%d/%m/%Y')
            previous_date_str = previous_date.strftime('%d/%m/%Y')
            today_date_str = datetime.today().strftime('%d/%m/%Y')
            is_today = selected_date_str == today_date_str
    
            retry_attempts = 3
            for attempt in range(retry_attempts):
                try:
                    query = """
                        SELECT 
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET' AND (? IS NULL OR time <= ?)) AS current_bets,
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET' AND (? IS NULL OR time <= ?)) AS previous_bets,
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND (? IS NULL OR time <= ?)) AS current_knockbacks,
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND (? IS NULL OR time <= ?)) AS previous_knockbacks,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (? IS NULL OR time <= ?)) AS current_total_unique_clients,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'M' AND (? IS NULL OR time <= ?)) AS current_unique_m_clients,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'W' AND (? IS NULL OR time <= ?)) AS current_unique_w_clients,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (? IS NULL OR time <= ?) AND (risk_category = '-' OR risk_category IS NULL)) AS current_unique_norisk_clients
                    """
                    params = [
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        previous_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        previous_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None
                    ]
                    cursor.execute(query, params)
                    (
                        current_bets, previous_bets, current_knockbacks, previous_knockbacks,
                        current_total_unique_clients, current_unique_m_clients, current_unique_w_clients,
                        current_unique_norisk_clients
                    ) = cursor.fetchone()
    
                    cursor.execute(
                        "SELECT sports, COUNT(*) FROM database WHERE date = ? AND type = 'BET' " + ("AND time <= ? GROUP BY sports" if is_today else "GROUP BY sports"),
                        (current_date_str, current_time) if is_today else (current_date_str,)
                    )
                    current_sport_counts = cursor.fetchall()
    
                    break
    
                except sqlite3.DatabaseError as e:
                    if attempt < retry_attempts - 1:
                        print(f"Database error: {e}. Retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        print(f"Database error: {e}. No more retries.")
                        raise
    
            if previous_bets > 0:
                percentage_change_bets = ((current_bets - previous_bets) / previous_bets) * 100
            else:
                percentage_change_bets = 0
    
            if previous_knockbacks > 0:
                percentage_change_knockbacks = ((current_knockbacks - previous_knockbacks) / previous_knockbacks) * 100
            else:
                percentage_change_knockbacks = 0
    
            horse_bets = 0
            dog_bets = 0
            other_bets = 0
    
            sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
            for sport, count in current_sport_counts:
                sport_list = eval(sport)
                if sport_mapping['Horses'] in sport_list:
                    horse_bets += count
                if sport_mapping['Dogs'] in sport_list:
                    dog_bets += count
                if sport_mapping['Other'] in sport_list:
                    other_bets += count
    
            knockback_percentage = (current_knockbacks / current_bets * 100) if current_bets > 0 else 0
            previous_knockback_percentage = (previous_knockbacks / previous_bets * 100) if previous_bets > 0 else 0
    
            daily_turnover = reporting_data.get('daily_turnover', 'N/A')
            daily_profit = reporting_data.get('daily_profit', 'N/A')
            daily_profit_percentage = reporting_data.get('daily_profit_percentage', 'N/A')
            full_name = USER_NAMES.get(user, user)
    
            bet_change_indicator = "↑" if current_bets > previous_bets else "↓" if current_bets < previous_bets else "→"
            knockback_change_indicator = "↑" if current_knockbacks > previous_knockbacks else "↓" if current_knockbacks < previous_knockbacks else "→"
    
            turnover_profit_line = (
                f"Turnover: {daily_turnover} | Profit: {daily_profit} ({daily_profit_percentage})"
                if is_today else ''
            )
    
            current_day_name = current_date.strftime('%A')
            previous_day_name = previous_date.strftime('%a')
    
            self.activity_text.config(state='normal')
            self.activity_text.delete('1.0', tk.END)
    
            # Line 1: Date and User
            self.activity_text.insert(tk.END, f"{current_day_name} {selected_date_str} {'  |  ' + full_name if user else ''}\n", 'bold')

            # Line 2: Bets
            self.activity_text.insert(tk.END, f"Bets: {current_bets:,} ")
            self.activity_text.insert(tk.END, f"{bet_change_indicator}{percentage_change_bets:.2f}% ", 'green' if percentage_change_bets > 0 else 'red')
            self.activity_text.insert(tk.END, f"({previous_day_name}: {previous_bets:,})\n")

            # Line 3: Knockbacks
            self.activity_text.insert(tk.END, f"Knockbacks: {current_knockbacks:,} ")
            self.activity_text.insert(tk.END, f"{knockback_change_indicator}{percentage_change_knockbacks:.2f}% ", 'red' if percentage_change_knockbacks > 0 else 'green')
            self.activity_text.insert(tk.END, f"({previous_day_name}: {previous_knockbacks:,})\n")

            # Line 4: Knockback Percentage
            self.activity_text.insert(tk.END, f"Knockback %: {knockback_percentage:.2f}% ")
            self.activity_text.insert(tk.END, f"({previous_day_name}: {previous_knockback_percentage:.2f}%)\n")

            # Line 5: Turnover Profit Line
            self.activity_text.insert(tk.END, f"{turnover_profit_line}\n")

            # Line 6: Clients
            self.activity_text.insert(tk.END, f"Clients: {current_total_unique_clients:,} | M: {current_unique_m_clients:,} | W: {current_unique_w_clients:,} | --: {current_unique_norisk_clients:,}\n")

            # Line 7: Bets by Type
            self.activity_text.insert(tk.END, f"Horses: {horse_bets:,} | Dogs: {dog_bets:,} | Other: {other_bets:,}")

            self.activity_text.tag_add('center', '1.0', 'end')
    
            self.activity_text.config(state='disabled')
    
        except sqlite3.DatabaseError as e:
            print(f"Database error: {e}")
            self.activity_text.config(state='normal')
            self.activity_text.delete('1.0', tk.END)
            self.activity_text.insert(tk.END, "An error occurred while updating the activity frame. Please try refreshing the feed.")
            self.activity_text.config(state='disabled')
        except Exception as e:
            print(f"Unexpected error: {e}")
            self.activity_text.config(state='normal')
            self.activity_text.delete('1.0', tk.END)
            self.activity_text.insert(tk.END, "An unexpected error occurred. Please try refreshing the feed.")
            self.activity_text.config(state='disabled')

    def initialize_text_tags(self):
        self.feed_text.tag_configure("risk", foreground="#ad0202")
        self.feed_text.tag_configure("watchlist", foreground="#e35f00")
        self.feed_text.tag_configure("newreg", foreground="purple")
        self.feed_text.tag_configure("vip", foreground="#009685")
        self.feed_text.tag_configure("sms", foreground="#6CCFF6")
        self.feed_text.tag_configure("knockback", foreground="#FF006E")
        self.feed_text.tag_configure('center', justify='center')
        self.feed_text.tag_configure("oddsmonkey", foreground="#ff00e6", justify='center')
        self.feed_text.tag_configure('bold', font=('Helvetica', 11, 'bold'), foreground='#d0cccc')
        self.feed_text.tag_configure('customer_ref_vip', font=('Helvetica', 11, 'bold'), foreground='#009685')
        self.feed_text.tag_configure('customer_ref_newreg', font=('Helvetica', 11, 'bold'), foreground='purple')
        self.feed_text.tag_configure('customer_ref_risk', font=('Helvetica', 11, 'bold'), foreground='#ad0202')
        self.feed_text.tag_configure('customer_ref_watchlist', font=('Helvetica', 11, 'bold'), foreground='#e35f00')
        self.feed_text.tag_configure('customer_ref_default', font=('Helvetica', 11, 'bold'), foreground='#000000')
        self.feed_text.tag_configure('black', foreground='#000000')
        self.activity_text.tag_configure('red', foreground='#ad0202')
        self.activity_text.tag_configure('green', foreground='#009685')
        self.activity_text.tag_configure('center', justify='center')

    def format_bet_text(self, bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data):
        enhanced_places = reporting_data.get('enhanced_places', [])
        text_segments = []
        
        if bet_dict['type'] == 'SMS WAGER':
            wager_number = bet_dict.get('id', '')  
            customer_reference = bet_dict.get('customer_ref', '')  
            sms_wager_text = bet_dict.get('text_request', '') 

            # Remove surrounding quotes and replace \n with actual newlines
            if sms_wager_text.startswith('"') and sms_wager_text.endswith('"'):
                sms_wager_text = sms_wager_text[1:-1]
            sms_wager_text = sms_wager_text.replace('\\n', '\n')

            tag = f"customer_ref_{self.get_customer_tag(customer_reference, vip_clients, newreg_clients)}"
            text_segments.append((f"{customer_reference} {wager_number}", tag))
            text_segments.append((f" - SMS WAGER:", "sms"))
            text_segments.append((f"\n{sms_wager_text}\n", "black"))
            
        elif bet_dict['type'] == 'WAGER KNOCKBACK':
            customer_ref = bet_dict.get('customer_ref', '') 
            knockback_id = bet_dict.get('id', '') 
            knockback_id = knockback_id.rsplit('-', 1)[0]
            knockback_details = bet_dict.get('selections', {}) 
            timestamp = bet_dict.get('time', '')  
    
            if isinstance(knockback_details, dict):
                formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items() if key not in ['Selections', 'Knockback ID', 'Time', 'Customer Ref', 'Error Message']])
                formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' for selection in knockback_details.get('Selections', [])])
            elif isinstance(knockback_details, list):
                formatted_knockback_details = ''
                formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' for selection in knockback_details])
            else:
                formatted_knockback_details = ''
                formatted_selections = ''
    
            formatted_knockback_details += '\n   ' + formatted_selections
            error_message = bet_dict.get('error_message', '') 
            if 'Maximum stake available' in error_message:
                error_message = error_message.replace(', Maximum stake available', '\n   Maximum stake available')
            formatted_knockback_details = f"Error Message: {error_message}   {formatted_knockback_details}"
            
            tag = f"customer_ref_{self.get_customer_tag(customer_ref, vip_clients, newreg_clients)}"
            text_segments.append((f"{customer_ref} {timestamp} - {knockback_id}", tag))
            text_segments.append((f" - WAGER KNOCKBACK:\n", "knockback"))
            text_segments.append((f"{formatted_knockback_details}\n", "black"))
        else:
            bet_no = bet_dict.get('id', '')  
            details = bet_dict.get('selections', []) 
            if isinstance(details, list) and all(isinstance(item, list) for item in details):
                parsed_selections = details
            else:
                parsed_selections = []
            timestamp = bet_dict.get('time', '')  
            customer_reference = bet_dict.get('customer_ref', '')  
            customer_risk_category = bet_dict.get('risk_category', '')  
            bet_details = bet_dict.get('bet_details', '') 
            unit_stake = bet_dict.get('unit_stake', 0.0)  
            bet_type = bet_dict.get('bet_type', '')
            
            selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
            formatted_unit_stake = f"£{unit_stake:.2f}"
            text = f"{formatted_unit_stake} {bet_details}, {bet_type}:\n{selection}\n"
            tag = f"customer_ref_{self.get_customer_tag(customer_reference, vip_clients, newreg_clients, customer_risk_category)}"
            text_segments.append((f"{customer_reference} ({customer_risk_category}) {timestamp} - {bet_no}", tag))
            text_segments.append((f" - {text}", "black"))
        
            for sel in parsed_selections:
                for event_name, om_selections in todays_oddsmonkey_selections.items():
                    if ' - ' in sel[0]:
                        selection_parts = sel[0].split(' - ')
                        if len(selection_parts) > 1:
                            bet_event_name = selection_parts[0].strip()
                            bet_selection_name = selection_parts[1].strip()
                            om_event_name = event_name.strip()
                            
                            if ',' in bet_event_name:
                                bet_event_name = bet_event_name.replace(', ', ' ', 1)
                            
                            
                            if bet_event_name == om_event_name:
                                for om_selection, lay_odds in om_selections:
                                    if bet_selection_name == om_selection.strip():
                                        if sel[1] == 'evs':
                                            sel[1] = '2.0'
                                        if sel[1] != 'SP' and float(sel[1]) >= float(lay_odds):
                                            oddsmonkey_text = f"{sel[0]}  |  Lay Odds: {lay_odds}\n"
                                            text_segments.append((oddsmonkey_text, "oddsmonkey"))
            
                parts = sel[0].split(' - ')
                if len(parts) > 1:
                    meeting_info = parts[0].split(', ')
                    if len(meeting_info) > 1 and ':' in meeting_info[1]:
                        meeting_time = meeting_info[1]
                        if f"{meeting_info[0]}, {meeting_time}" in enhanced_places:
                            enhanced_text = f"{sel[0]}  |  Enhanced Race\n"
                            text_segments.append((enhanced_text, "oddsmonkey"))
            
        return text_segments
    
    def get_customer_tag(self, customer_reference, vip_clients, newreg_clients, customer_risk_category=None):
        if customer_reference in vip_clients:
            return "vip"
        elif customer_reference in newreg_clients:
            return "newreg"
        elif customer_risk_category == 'W':
            return "watchlist"
        elif customer_risk_category == 'M' or customer_risk_category == 'C':
            return "risk"
        else:
            return "default"
    
    def apply_filters(self):
        self.current_filters['username'] = '' if self.username_filter_entry.get() == 'Client' else self.username_filter_entry.get()
        self.current_filters['unit_stake'] = '' if self.unit_stake_filter_entry.get() == '£' else self.unit_stake_filter_entry.get()
        self.current_filters['risk_category'] = '' if self.risk_category_filter_entry.get() == 'Risk' else self.risk_category_filter_entry.get()
        self.current_filters['sport'] = '' if self.sport_combobox_entry.get() == 'Sport' else self.sport_combobox_entry.get()
        self.current_filters['selection'] = '' if self.selection_filter_entry.get() == 'Selection' else self.selection_filter_entry.get()
        self.current_filters['type'] = '' if self.type_combobox_entry.get() == 'Type' else self.type_combobox_entry.get()

        filters_applied = any(value not in [None, '', 'none'] for value in self.current_filters.values())
    
        if filters_applied:
            self.tick_button.configure(style='Accent.TButton')
        else:
            self.tick_button.configure(style='TButton')
    
        self.bet_feed()

    def set_placeholder(self, widget, placeholder):
        widget.insert(0, placeholder)
        widget.config(foreground='grey')
        widget.bind("<FocusIn>", lambda event: self.clear_placeholder(event, placeholder))
        widget.bind("<FocusOut>", lambda event: self.add_placeholder(event, placeholder))

    def clear_placeholder(self, event, placeholder):
        if event.widget.get() == placeholder:
            event.widget.delete(0, tk.END)
            event.widget.config(foreground='black')

    def add_placeholder(self, event, placeholder):
        if not event.widget.get():
            event.widget.insert(0, placeholder)
            event.widget.config(foreground='grey')

    def reset_filters(self):
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None, 'selection': None, 'type': None}
        self.username_filter_entry.delete(0, tk.END)
        self.unit_stake_filter_entry.delete(0, tk.END)
        self.risk_category_filter_entry.delete(0, tk.END)
        self.sport_combobox_entry.set('')
        self.selection_filter_entry.delete(0, tk.END)
        self.type_combobox_entry.set('')
        self.set_placeholder(self.username_filter_entry, 'Client')
        self.set_placeholder(self.unit_stake_filter_entry, '£')
        self.set_placeholder(self.risk_category_filter_entry, 'Risk')
        self.set_placeholder(self.selection_filter_entry, 'Selection')
        self.set_placeholder(self.sport_combobox_entry, 'Sport')
        self.set_placeholder(self.type_combobox_entry, 'Type')

        self.tick_button.configure(style='TButton')

        self.bet_feed()

class BetRuns:
    def __init__(self, root):
        self.num_run_bets_var = tk.StringVar()
        self.combobox_var = tk.IntVar(value=50)
        self.num_run_bets = 2
        self.num_recent_files = 50
        self.root = root
        self.bet_runs_lock = threading.Lock()
        self.initialize_ui()
        self.initialize_text_tags()
        self.refresh_bets() 
    
    def initialize_ui(self):
        self.runs_frame = ttk.LabelFrame(self.root, style='Card', text="Runs on Selections")
        self.runs_frame.place(x=530, y=160, width=365, height=485)
        self.runs_frame.grid_columnconfigure(0, weight=1)
        self.runs_frame.grid_rowconfigure(0, weight=1)
        self.runs_frame.grid_columnconfigure(1, weight=0)

        self.runs_text = tk.Text(self.runs_frame, font=("Arial", 10), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
        self.runs_text.config(state='disabled') 
        self.runs_text.grid(row=0, column=0, sticky='nsew')

        self.spinbox_frame = ttk.Frame(self.runs_frame)
        self.spinbox_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))

        self.spinbox_frame.grid(row=1, column=0, sticky='ew')
        self.spinbox_frame.grid_columnconfigure(0, weight=1)
        self.spinbox_frame.grid_columnconfigure(1, weight=1)
        self.spinbox_frame.grid_columnconfigure(2, weight=1)

        self.spinbox = ttk.Spinbox(self.spinbox_frame, from_=2, to=10, textvariable=self.num_run_bets_var, width=2)
        self.num_run_bets_var.set("2")
        self.spinbox.grid(row=0, column=0, pady=(0, 3))
        self.num_run_bets_var.trace("w", self.set_num_run_bets)

        self.combobox_values = [20, 50, 100, 300, 1000, 2000]
        self.combobox = ttk.Combobox(self.spinbox_frame, textvariable=self.combobox_var, values=self.combobox_values, width=4)
        self.combobox_var.trace("w", self.set_recent_bets)
        self.combobox.grid(row=0, column=1, pady=(0, 3))

        style = ttk.Style()
        large_font = font.Font(size=13)
        style.configure('Large.TButton', font=large_font)

        self.refresh_button = ttk.Button(self.spinbox_frame, text='⟳', command=self.manual_refresh_bets, width=2, style='Large.TButton')
        self.refresh_button.grid(row=0, column=2, pady=(0, 3))

        self.runs_scroll = ttk.Scrollbar(self.runs_frame, orient='vertical', command=self.runs_text.yview, cursor="hand2")
        self.runs_scroll.grid(row=0, column=1, sticky='ns')
        self.runs_text.configure(yscrollcommand=self.runs_scroll.set)

    def set_recent_bets(self, *args):
        self.num_recent_files = self.combobox_var.get()
        self.manual_refresh_bets()

    def set_num_run_bets(self, *args):
        try:
            self.num_run_bets = int(self.num_run_bets_var.get())
            self.manual_refresh_bets()
        except ValueError:
            pass

    def bet_runs(self, num_bets, num_run_bets):
        def fetch_and_process_bets():
            if not self.bet_runs_lock.acquire(blocking=False):
                print("Bet runs update already in progress. Skipping this update.")
                return

            try:
                retry_attempts = 3
                conn = None
                cursor = None

                for attempt in range(retry_attempts):
                    try:
                        conn, cursor = database_manager.get_connection()
                        if conn is not None and cursor is not None:
                            break
                    except Exception as e:
                        print(f"Attempt {attempt + 1}: Failed to connect to the database. Error: {e}")
                        if attempt < retry_attempts - 1:
                            print("Retrying in 2 seconds...")
                            time.sleep(2)
                        else:
                            self.update_ui_with_message("Failed to connect to the database after multiple attempts.")
                            return

                if conn is None or cursor is None:
                    self.update_ui_with_message("Failed to establish a database connection.")
                    return

                for attempt in range(retry_attempts):
                    try:
                        current_date = datetime.now().strftime('%d/%m/%Y')
                        cursor.execute("SELECT id, selections FROM database WHERE date = ? ORDER BY time DESC LIMIT ?", (current_date, num_bets,))
                        database_data = cursor.fetchall()

                        if not database_data:
                            self.update_ui_with_message("No bets found for the current date or database not found.")
                            return

                        selection_to_bets = defaultdict(list)

                        for bet in database_data:
                            bet_id = bet[0] 
                            if ':' in bet_id:
                                continue 
                            selections = bet[1] 
                            if selections:
                                try:
                                    selections = json.loads(selections) 
                                except json.JSONDecodeError:
                                    continue  
                                for selection in selections:
                                    selection_name = selection[0]
                                    selection_to_bets[selection_name].append(bet_id)

                        sorted_selections = sorted(selection_to_bets.items(), key=lambda item: len(item[1]), reverse=True)

                        self.update_ui_with_selections(sorted_selections, num_run_bets, cursor)
                        break 
                    except Exception as e:
                        print(f"Attempt {attempt + 1}: An error occurred while processing bets. Error: {e}")
                        if attempt < retry_attempts - 1:
                            print("Retrying in 2 seconds...")
                            time.sleep(2)
                        else:
                            self.update_ui_with_message(f"An error occurred after multiple attempts: {e}\nPlease try refreshing.")
                            return
            finally:
                if conn:
                    conn.close()
                self.bet_runs_lock.release()
        threading.Thread(target=fetch_and_process_bets, daemon=True).start()

    def update_ui_with_message(self, message):
        self.runs_text.config(state="normal")
        self.runs_text.delete('1.0', tk.END)
        self.runs_text.insert('end', message)
        self.runs_text.config(state="disabled")
    
    def update_ui_with_selections(self, sorted_selections, num_run_bets, cursor):
        vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
        enhanced_places = reporting_data.get('enhanced_places', [])
        self.runs_text.config(state="normal")
        self.runs_text.delete('1.0', tk.END)
        
        for selection, bet_numbers in sorted_selections:
            if len(bet_numbers) >= num_run_bets:
                selection_name = selection.split(' - ')[1] if ' - ' in selection else selection
        
                matched_odds = None
                for om_event, om_selections in todays_oddsmonkey_selections.items():
                    for om_sel in om_selections:
                        if selection_name == om_sel[0]:
                            matched_odds = float(om_sel[1])
                            break
                    if matched_odds is not None:
                        break
        
                if matched_odds is not None:
                    self.runs_text.insert(tk.END, f"{selection} | OM Lay: {matched_odds}\n", "oddsmonkey")
                else:
                    self.runs_text.insert(tk.END, f"{selection}\n")
        
                for bet_number in bet_numbers:
                    cursor.execute("SELECT time, customer_ref, risk_category, selections FROM database WHERE id = ?", (bet_number,))
                    bet_info = cursor.fetchone()
                    if bet_info:
                        bet_time = bet_info[0]
                        customer_ref = bet_info[1]
                        risk_category = bet_info[2]
                        selections = bet_info[3]
                        if selections:
                            try:
                                selections = json.loads(selections) 
                            except json.JSONDecodeError:
                                continue 
                            for sel in selections:
                                if selection == sel[0]:
                                    if risk_category == 'M' or risk_category == 'C':
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "risk")
                                    elif risk_category == 'W':
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "watchlist")
                                    elif customer_ref in vip_clients:
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "vip")
                                    elif customer_ref in newreg_clients:
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "newreg")
                                    else:
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n")
        
                meeting_time = ' '.join(selection.split(' ')[:2])
        
                if meeting_time in enhanced_places:
                    self.runs_text.insert(tk.END, 'Enhanced Place Race\n', "oddsmonkey")
                
                self.runs_text.insert(tk.END, f"\n")
    
        self.runs_text.config(state=tk.DISABLED)

    def initialize_text_tags(self):
        self.runs_text.tag_configure("risk", foreground="#ad0202")
        self.runs_text.tag_configure("watchlist", foreground="#e35f00")
        self.runs_text.tag_configure("vip", foreground="#009685")
        self.runs_text.tag_configure("newreg", foreground="purple")
        self.runs_text.tag_configure("oddsmonkey", foreground="#ff00e6")

    def manual_refresh_bets(self):
        num_bets = self.num_recent_files
        num_run_bets = self.num_run_bets
        self.bet_runs(num_bets, num_run_bets)
        
    def refresh_bets(self):
        scroll_pos = self.runs_text.yview()[0]

        num_bets = self.num_recent_files
        num_run_bets = self.num_run_bets

        if scroll_pos <= 0.04:
            self.bet_runs(num_bets, num_run_bets)
        else:
            pass

        self.root.after(20000, self.refresh_bets)

class RaceUpdaton:
    def __init__(self, root):
        self.root = root
        self.current_page = 0
        self.courses_per_page = 6
        self.initialize_ui()
        self.get_courses()
        self.display_courses_periodic()
    
    def initialize_ui(self):
        self.race_updation_frame = ttk.LabelFrame(root, style='Card', text="Race Updation")
        self.race_updation_frame.place(x=5, y=647, width=227, height=273)

    def display_courses_periodic(self):
        self.display_courses()
        self.root.after(15000, self.display_courses_periodic)

    def get_courses(self):
        today = date.today()
        self.courses = set()
        self.dog_courses = set()
        self.others_courses = set()
        api_data = []
        dogs_api_data = []
        others_api_data = []

        try:
            url = os.getenv('GET_COURSES_HORSES_API_URL')
            if not url:
                raise ValueError("GET_COURSES_HORSES_API_URL environment variable is not set")
            response = requests.get(url)
            response.raise_for_status()
            api_data = response.json()
        except requests.RequestException as e:
            print("Error fetching data from GB API for Courses.")
        except json.JSONDecodeError:
            print("Error decoding JSON from GB API response.")

        if api_data:
            for event in api_data:
                for meeting in event['meetings']:
                    self.courses.add(meeting['meetinName'])

        try:
            url = os.getenv('DOGS_API_URL')
            if not url:
                raise ValueError("DOGS_API_URL environment variable is not set")
            dogs_response = requests.get(url)
            dogs_response.raise_for_status()
            dogs_api_data = dogs_response.json()
        except requests.RequestException as e:
            print("Error fetching data from GB API for Dogs.")
        except json.JSONDecodeError:
            print("Error decoding JSON from GB API response.")

        if dogs_api_data:
            for event in dogs_api_data:
                if ' AUS ' not in event['eventName']:
                    for meeting in event['meetings']:
                        meeting_name = meeting['meetinName']
                        if not meeting_name.endswith(' Dg'):
                            meeting_name += ' Dg'
                        self.dog_courses.add(meeting_name)

        try:
            url = os.getenv('OTHERS_API_URL')
            if not url:
                raise ValueError("OTHERS_API_URL environment variable is not set")
            others_response = requests.get(url)
            others_response.raise_for_status()
            others_api_data = others_response.json()
        except requests.RequestException as e:
            print("Error fetching data from GB API for International Courses.")
        except json.JSONDecodeError:
            print("Error decoding JSON from GB API response.")

        if others_api_data:
            for event in others_api_data:
                for meeting in event['meetings']:
                    self.others_courses.add(meeting['meetinName'])

        self.courses = list(self.courses)
        print("Courses:", self.courses)

        update_times_path = os.path.join(NETWORK_PATH_PREFIX, 'update_times.json')

        try:
            with open(update_times_path, 'r') as f:
                update_data = json.load(f)
        except FileNotFoundError:
            update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {}}
            with open(update_times_path, 'w') as f:
                json.dump(update_data, f)

        if update_data['date'] != today.strftime('%Y-%m-%d'):
            update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {course: "" for course in self.courses}}
            with open(update_times_path, 'w') as f:
                json.dump(update_data, f)

        self.display_courses()
        return self.courses

    def display_courses(self):
        update_times_path = os.path.join(NETWORK_PATH_PREFIX, 'update_times.json')
        
        with open(update_times_path, 'r') as f:
            data = json.load(f)
    
        courses = list(data['courses'].keys())
        courses.sort(key=lambda x: (x.endswith(" Dg"), x))
    
        start = self.current_page * self.courses_per_page
        end = start + self.courses_per_page
        courses_page = courses[start:end]
    
        for widget in self.race_updation_frame.winfo_children():
            widget.destroy()
        
        button_frame = ttk.Frame(self.race_updation_frame)
        button_frame.grid(row=len(courses_page), column=0, padx=2, sticky='ew')
        
        add_button = ttk.Button(button_frame, text="+", command=self.add_course, width=2, cursor="hand2")
        add_button.pack(side='left')
        
        update_indicator = ttk.Label(button_frame, text="", foreground='red', font=("Helvetica", 12))
        update_indicator.pack(side='left', padx=2, expand=True)
        
        remove_button = ttk.Button(button_frame, text="-", command=self.remove_course, width=2, cursor="hand2")
        remove_button.pack(side='right')
        
        for i, course in enumerate(courses_page):
            course_button = ttk.Button(self.race_updation_frame, text=course, command=lambda course=course: self.update_course(course), width=15, cursor="hand2")
            course_button.grid(row=i, column=0, padx=5, pady=2, sticky="w")
        
            if course in data['courses'] and data['courses'][course]:
                last_updated_time = data['courses'][course].split(' ')[0]
                last_updated = datetime.strptime(last_updated_time, '%H:%M').time()
            else:
                last_updated = datetime.now().time()
        
            now = datetime.now().time()
        
            time_diff = (datetime.combine(date.today(), now) - datetime.combine(date.today(), last_updated)).total_seconds() / 60
        
            if course.endswith(" Dg"):
                if 60 <= time_diff < 90:
                    color = 'Orange'
                elif time_diff >= 90:
                    color = 'red'
                else:
                    color = 'black'
            else:
                if 25 <= time_diff < 35:
                    color = 'Orange'
                elif time_diff >= 35:
                    color = 'red'
                else:
                    color = 'black'
        
            if course in data['courses'] and data['courses'][course]:
                time_text = data['courses'][course]
            else:
                time_text = "Not updated"
        
            time_label = ttk.Label(self.race_updation_frame, text=time_text, foreground=color)
            time_label.grid(row=i, column=1, padx=5, pady=2, sticky="w")
        
        navigation_frame = ttk.Frame(self.race_updation_frame)
        navigation_frame.grid(row=len(courses_page), column=1, padx=2, pady=2, sticky='ew')
        
        back_button = ttk.Button(navigation_frame, text="<", command=self.back, width=2, cursor="hand2")
        back_button.grid(row=0, column=0, padx=2, pady=2)
        
        forward_button = ttk.Button(navigation_frame, text=">", command=self.forward, width=2, cursor="hand2")
        forward_button.grid(row=0, column=1, padx=2, pady=2)
        
        other_courses = [course for i, course in enumerate(courses) if i < start or i >= end]
        courses_needing_update = [course for course in other_courses if self.course_needs_update(course, data)]
        if courses_needing_update:
            update_indicator.config(text=str(len(courses_needing_update)))
            update_indicator.pack()
        else:
            update_indicator.pack_forget()
        
        if self.current_page == 0:
            back_button.config(state='disabled')
        else:
            back_button.config(state='normal')
        
        if self.current_page == len(courses) // self.courses_per_page:
            forward_button.config(state='disabled')
        else:
            forward_button.config(state='normal')

    def reset_update_times(self):
        update_times_path = os.path.join(NETWORK_PATH_PREFIX, 'update_times.json')
        
        if os.path.exists(update_times_path):
            os.remove(update_times_path)

        update_data = {'date': '', 'courses': {}}
        with open(update_times_path, 'w') as f:
            json.dump(update_data, f)
        
        self.display_courses()

    def course_needs_update(self, course, data):
        if course in data['courses'] and data['courses'][course]:
            last_updated_time = data['courses'][course].split(' ')[0]
            last_updated = datetime.strptime(last_updated_time, '%H:%M').time()
        else:
            last_updated = datetime.now().time()

        now = datetime.now().time()

        time_diff = (datetime.combine(date.today(), now) - datetime.combine(date.today(), last_updated)).total_seconds() / 60

        if course.endswith(" Dg"):
            return time_diff >= 60
        else:
            return time_diff >= 25

    def log_update(self, course, time, user, last_update_time):
        now = datetime.now()
        date_string = now.strftime('%d-%m-%Y')
        log_file = os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', f'update_log_{date_string}.txt')
        score = 0.0

        search_course = course.replace(' Dg', '')

        try:
            if course.endswith(" Dg"):
                url = os.getenv('DOGS_API_URL')
            else:
                url = os.getenv('HORSES_API_URL')

            if not url:
                raise ValueError("API URL environment variable is not set")

            response = requests.get(url)
            response.raise_for_status()
            api_data = response.json()
        except requests.RequestException as e:
            print(f"Error fetching data from API: {e}")
            messagebox.showerror("Error", f"Failed to fetch courses data from API. You will be allocated 0.1 score for this update.")
            score = 0.1
            api_data = None
        except json.JSONDecodeError:
            print("Error decoding JSON from API response.")
            messagebox.showerror("Error", f"Failed to decode JSON from API response. You will be allocated 0.1 score for this update.")
            score = 0.1
            api_data = None
    
        try:
            if api_data:
                today = now.strftime('%A')
                tomorrow = (now + timedelta(days=1)).strftime('%A')
                morning_finished = False
    
                if course.endswith(" Dg"):
                    for event in api_data:
                        if today in event['eventName']:
                            for meeting in event['meetings']:
                                if search_course == meeting['meetinName'] or course == meeting['meetinName']:
                                    all_results = all(race['status'] == 'Result' for race in meeting['events'])
                                    if all_results:
                                        morning_finished = True
                                    else:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.1
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                    break
                            if morning_finished:
                                break
    
                    if morning_finished:
                        for event in api_data:
                            if today in event['eventName']:
                                for meeting in event['meetings']:
                                    if search_course + '1' == meeting['meetinName']:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.1
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                        break
    
                else:
                    print("Horse Race")
                    for event in api_data:
                        if today in event['eventName']:
                            for meeting in event['meetings']:
                                if search_course == meeting['meetinName']:
                                    all_results = all(race['status'] == 'Result' for race in meeting['events'])
                                    if all_results:
                                        morning_finished = True
                                    else:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.2
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                    break
                            if morning_finished:
                                print("breaking")
                                break
    
                    if morning_finished:
                        for event in api_data:
                            if tomorrow in event['eventName']:
                                for meeting in event['meetings']:
                                    if search_course == meeting['meetinName']:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.2
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                        break
    
            surge_start = datetime.strptime('13:00', '%H:%M').time()
            surge_end = datetime.strptime('16:00', '%H:%M').time()
            if surge_start <= now.time() <= surge_end:
                score += 0.1
    
            score = round(score, 2)
            print(f"Score: {score}")
    
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        data = f.readlines()
                except IOError as e:
                    print(f"Error reading log file: {e}")
                    data = []
            else:
                data = []
    
            if last_update_time:
                last_updated = last_update_time.time()
                now_time = now.time()
                time_diff = (datetime.combine(date.today(), now_time) - datetime.combine(date.today(), last_updated)).total_seconds() / 60
                print(f"Time difference: {time_diff}")
                if time_diff < 10:
                    score *= 0.7
    
            update = f"{time} - {user} - {score:.2f}\n"
            log_notification(f"{user} updated {course} ({score:.2f})")
    
            course_index = None
            for i, line in enumerate(data):
                if line.strip() == course + ":":
                    course_index = i
                    break
    
            if course_index is not None:
                data.insert(course_index + 1, update)
            else:
                data.append(f"\n{course}:\n")
                data.append(update)
    
            try:
                with open(log_file, 'w') as f:
                    f.writelines(data)
                print(f"Log updated for {course}")
            except IOError as e:
                print(f"Error writing to log file: {e}")
    
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def update_course(self, course):
        global user
        if not user:
            user_login()
    
        now = datetime.now()
        time_string = now.strftime('%H:%M')
    
        with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
            data = json.load(f)
    
        last_update_time = data['courses'].get(course, None)
        if last_update_time and last_update_time != "Not updated":
            last_update_time = last_update_time.split(' ')[0]
            try:
                last_update_time = datetime.strptime(last_update_time, '%H:%M')
            except ValueError:
                last_update_time = None
        else:
            last_update_time = None
    
        data['courses'][course] = f"{time_string} - {user}"
        with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'w') as f:
            json.dump(data, f)
    
        threading.Thread(target=self.log_update, args=(course, time_string, user, last_update_time), daemon=True).start()
        self.display_courses()

    def remove_course(self):
        def fetch_courses():
            with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                data = json.load(f)
    
            courses = [course for course in data['courses']]
    
            combobox['values'] = courses
            combobox.set('')
            loading_bar.stop()
            loading_bar.pack_forget()
            select_button.pack(pady=10)
    
        def on_select():
            selected_course = combobox.get()
            if selected_course:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                    data = json.load(f)

                del data['courses'][selected_course]
    
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'w') as f:
                    json.dump(data, f)
    
                log_notification(f"'{selected_course}' removed by {user}")
    
                self.display_courses()
                top.destroy()

        top = tk.Toplevel(self.root)
        top.title("Remove Course")
        top.geometry("300x120")
        top.iconbitmap('src/splash.ico')
        screen_width = top.winfo_screenwidth()
        top.geometry(f"+{screen_width - 400}+200")

        combobox = ttk.Combobox(top, state='readonly')
        combobox.pack(fill=tk.BOTH, padx=10, pady=10)
    
        loading_bar = ttk.Progressbar(top, mode='indeterminate')
        loading_bar.pack(fill=tk.BOTH, padx=10, pady=10)
        loading_bar.start()
    
        select_button = ttk.Button(top, text="Select", command=on_select)
        select_button.pack_forget() 
    
        threading.Thread(target=fetch_courses, daemon=True).start()

    def add_course(self):
        def fetch_courses():
            self.get_courses()
    
            all_courses = sorted(set(self.courses) | self.dog_courses | self.others_courses)
            with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                data = json.load(f)
    
            all_courses = [course for course in all_courses if course not in data['courses']]
    
            combobox['values'] = all_courses
            combobox.set('')
            loading_bar.stop()
            loading_bar.pack_forget()
            select_button.pack(pady=10)
    
        def on_select():
            selected_course = combobox.get()
            if selected_course:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                    data = json.load(f)
    
                data['courses'][selected_course] = ""
    
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'w') as f:
                    json.dump(data, f)
    
                log_notification(f"'{selected_course}' added by {user}")
    
                self.display_courses()
                top.destroy()
    
        top = tk.Toplevel(self.root)
        top.title("Add Course")
        top.geometry("300x120")
        top.iconbitmap('src/splash.ico')
        screen_width = top.winfo_screenwidth()
        top.geometry(f"+{screen_width - 400}+200")
    
        combobox = ttk.Combobox(top, state='readonly')
        combobox.pack(fill=tk.BOTH, padx=10, pady=10)
    
        loading_bar = ttk.Progressbar(top, mode='indeterminate')
        loading_bar.pack(fill=tk.BOTH, padx=10, pady=10)
        loading_bar.start()
    
        select_button = ttk.Button(top, text="Select", command=on_select)
        select_button.pack_forget()  
    
        threading.Thread(target=fetch_courses, daemon=True).start()

    def back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_courses()

    def forward(self):
        with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
            data = json.load(f)
        total_courses = len(data['courses'].keys())
        if (self.current_page + 1) * self.courses_per_page < total_courses:
            self.current_page += 1
            self.display_courses()

class Notebook:
    def __init__(self, root):
        self.root = root
        self.last_notification = None
        self.generated_string = None

        _, _, _, reporting_data = access_data()
        self.enhanced_places = reporting_data.get('enhanced_places', [])

        self.pipedrive_api_token = os.getenv('PIPEDRIVE_API_KEY')
        self.pipedrive_api_url = os.getenv('PIPEDRIVE_API_URL')

        if not self.pipedrive_api_url:
            raise ValueError("PIPEDRIVE_API_URL environment variable is not set")

        self.pipedrive_api_url = f'{self.pipedrive_api_url}?api_token={self.pipedrive_api_token}'

        google_creds = {
            "type": os.getenv('GOOGLE_SERVICE_ACCOUNT_TYPE'),
            "project_id": os.getenv('GOOGLE_PROJECT_ID'),
            "private_key_id": os.getenv('GOOGLE_PRIVATE_KEY_ID'),
            "private_key": os.getenv('GOOGLE_PRIVATE_KEY').replace('\\n', '\n'),
            "client_email": os.getenv('GOOGLE_CLIENT_EMAIL'),
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "auth_uri": os.getenv('GOOGLE_AUTH_URI'),
            "token_uri": os.getenv('GOOGLE_TOKEN_URI'),
            "auth_provider_x509_cert_url": os.getenv('GOOGLE_AUTH_PROVIDER_X509_CERT_URL'),
            "client_x509_cert_url": os.getenv('GOOGLE_CLIENT_X509_CERT_URL')
        }
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/analytics.readonly']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        self.gc = gspread.authorize(credentials)
        self.analytics_credentials = service_account.Credentials.from_service_account_info(google_creds, scopes=scope)

        self.initialize_ui()
        self.initialize_text_tags()
        self.update_notifications()
        self.start_live_users_thread() 
        self.run_factoring_sheet_thread()
        self.run_freebet_sheet_thread()
        self.run_popup_sheet_thread()

    def initialize_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.place(x=238, y=655, width=470, height=265)
        tab_1 = ttk.Frame(self.notebook)
        tab_1.grid_rowconfigure(0, weight=1)
        tab_1.grid_columnconfigure(0, weight=3) 
        tab_1.grid_columnconfigure(1, weight=0) 
        tab_1.grid_columnconfigure(2, weight=1)
        self.notebook.add(tab_1, text="Staff Feed")
        self.staff_feed = tk.Text(tab_1, font=("Helvetica", 10), bd=0, wrap='word', padx=2, pady=2, fg="#000000", bg="#ffffff")
        self.staff_feed.grid(row=0, column=0, sticky="nsew")
        self.staff_feed.tag_configure("spacing", spacing1=5, spacing3=5)
        self.staff_feed.tag_add("spacing", "1.0", "end")
        self.staff_feed_buttons_frame = ttk.Frame(tab_1)
        separator = ttk.Separator(tab_1, orient='vertical')
        separator.grid(row=0, column=1, sticky='ns')
        self.staff_feed_buttons_frame.grid(row=0, column=2, sticky='nsew')
        self.pinned_message_frame = ttk.Frame(self.staff_feed_buttons_frame, style='Card')
        self.pinned_message_frame.pack(side="top", pady=5, padx=(5, 0))
        self.pinned_message = tk.Text(self.pinned_message_frame, font=("Helvetica", 10, 'bold'), bd=0, wrap='word', pady=2, fg="#000000", bg="#ffffff", height=3, width=30)  # Adjust height as needed
        self.pinned_message.config(state='disabled')
        self.pinned_message.pack(side="top", pady=5, padx=5) 
        self.post_message_button = ttk.Button(self.staff_feed_buttons_frame, text="Post", command=user_notification, cursor="hand2", width=8)
        self.post_message_button.pack(side="top", pady=(5, 5))

        self.separator = ttk.Separator(self.staff_feed_buttons_frame, orient='horizontal')
        self.separator.pack(side="top", fill='x', pady=(5, 5))
        
        live_users_label = ttk.Label(self.staff_feed_buttons_frame, text=" Active Clients", font=("Helvetica", 10, 'bold'), wraplength=150)
        live_users_label.pack(side="top", pady=(18, 5))

        self.live_users_label = ttk.Label(self.staff_feed_buttons_frame, text="---", font=("Helvetica", 10))
        self.live_users_label.pack(side="top", pady=(5, 5))

        tab_2 = ttk.Frame(self.notebook)
        self.notebook.add(tab_2, text="Reporting")
        tab_2.grid_rowconfigure(0, weight=1)
        tab_2.grid_rowconfigure(1, weight=1)
        tab_2.grid_columnconfigure(0, weight=3)
        tab_2.grid_columnconfigure(1, weight=0) 
        tab_2.grid_columnconfigure(2, weight=1)
        self.report_ticket = tk.Text(tab_2, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
        self.report_ticket.insert('1.0', "Daily Report\nGenerate a report for the days' betting activity.\n\nMonthly Report\nGenerate a report on the months' betting activity.\n\nStaff Report\nGenerate a report on staff activity.\n\nTraders Screener\nScan for potential 'risk' users.\n\nRG Screener\nScan for indicators of irresponsible gambling.", "c")    
        self.report_ticket.config(state='disabled')
        self.report_ticket.grid(row=0, column=0, sticky="nsew") 
        separator_tab_2 = ttk.Separator(tab_2, orient='vertical')
        separator_tab_2.grid(row=0, column=1, sticky='ns')
        self.report_buttons_frame = ttk.Frame(tab_2)
        self.report_buttons_frame.grid(row=0, column=2, sticky='nsew')
        self.report_combobox = ttk.Combobox(self.report_buttons_frame, values=["Daily Report", "Monthly Report", "Staff Report", "Traders Screener", "RG Screener", "Client Report"], width=30, state='readonly')
        self.report_combobox.pack(side="top", pady=(10, 5), padx=(5, 0))
        self.report_combobox.bind("<<ComboboxSelected>>", self.on_report_combobox_select)
        self.report_button = ttk.Button(self.report_buttons_frame, text="Generate", command=self.generate_report, cursor="hand2", width=30)
        self.report_button.pack(side="top", pady=(5, 10), padx=(5, 0))
    
        self.progress_label = ttk.Label(self.report_buttons_frame, text="---", wraplength=150)
        self.progress_label.pack(side="top", pady=(20, 10), padx=(5, 0))
    
        tab_3 = ttk.Frame(self.notebook)
        self.notebook.add(tab_3, text="Factoring Log")
    
        self.factoring_tree = ttk.Treeview(tab_3)
        columns = ["A", "B", "C", "D", "E", "F"]
        headings = ["Date", "Time", "User", "Risk", "Rating", ""]
        self.factoring_tree["columns"] = columns
        for col, heading in enumerate(headings):
            self.factoring_tree.heading(columns[col], text=heading)
            self.factoring_tree.column(columns[col], width=84, stretch=tk.NO)
        self.factoring_tree.column("A", width=75, stretch=tk.NO)
        self.factoring_tree.column("B", width=60, stretch=tk.NO)
        self.factoring_tree.column("C", width=83, stretch=tk.NO)
        self.factoring_tree.column("D", width=40, stretch=tk.NO)
        self.factoring_tree.column("E", width=40, stretch=tk.NO)
        self.factoring_tree.column("F", width=32, stretch=tk.NO)
        self.factoring_tree.column("#0", width=10, stretch=tk.NO)
        self.factoring_tree.heading("#0", text="", anchor="w")
        self.factoring_tree.grid(row=0, column=0, sticky="nsew")
        tab_3.grid_columnconfigure(0, weight=1)
        tab_3.grid_rowconfigure(0, weight=1)
        tab_3.grid_columnconfigure(1, weight=0) 
    
        factoring_buttons_frame = ttk.Frame(tab_3)
        factoring_buttons_frame.grid(row=0, column=1, sticky='ns', padx=(10, 0))
    
        add_restriction_button = ttk.Button(factoring_buttons_frame, text="Add", command=lambda: ClientWizard(self.root, "Factoring"), cursor="hand2")
        add_restriction_button.pack(side="top", pady=(10, 5))
        refresh_factoring_button = ttk.Button(factoring_buttons_frame, text="Refresh", command=self.run_factoring_sheet_thread, cursor="hand2")
        refresh_factoring_button.pack(side="top", pady=(10, 5))
        self.last_refresh_label = ttk.Label(factoring_buttons_frame, text=f"Last Refresh:\n---")
        self.last_refresh_label.pack(side="top", pady=(10, 5))
    
        self.client_id_frame = ttk.Frame(self.report_buttons_frame)
        self.client_id_label = ttk.Label(self.client_id_frame, text="Username:")
        self.client_id_label.pack(side="top", padx=(5, 5))  
        self.client_id_entry = ttk.Entry(self.client_id_frame, width=15)
        self.client_id_entry.pack(side="top", padx=(5, 5)) 
        self.client_id_frame.pack(side="top", pady=(5, 10), padx=(5, 0))
        self.client_id_frame.pack_forget()  

        tab_4 = ttk.Frame(self.notebook)
        self.notebook.add(tab_4, text="Freebet Log")

        self.freebet_tree = ttk.Treeview(tab_4)
        columns = ["A", "B", "C", "E", "F"]
        headings = ["Date", "Time", "User", "Amount", ""]
        self.freebet_tree["columns"] = columns
        for col, heading in enumerate(headings):
            self.freebet_tree.heading(columns[col], text=heading)
            self.freebet_tree.column(columns[col], width=84, stretch=tk.NO)
        self.freebet_tree.column("A", width=75, stretch=tk.NO)
        self.freebet_tree.column("B", width=60, stretch=tk.NO)
        self.freebet_tree.column("C", width=83, stretch=tk.NO)
        self.freebet_tree.column("E", width=65, stretch=tk.NO)
        self.freebet_tree.column("F", width=32, stretch=tk.NO)
        self.freebet_tree.column("#0", width=10, stretch=tk.NO)
        self.freebet_tree.heading("#0", text="", anchor="w")
        self.freebet_tree.grid(row=0, column=0, sticky="nsew")
        tab_4.grid_columnconfigure(0, weight=1)
        tab_4.grid_rowconfigure(0, weight=1)
        tab_4.grid_columnconfigure(1, weight=0) 
    
        freebet_buttons_frame = ttk.Frame(tab_4)
        freebet_buttons_frame.grid(row=0, column=1, sticky='ns', padx=(10, 0))
    
        add_freebet_button = ttk.Button(freebet_buttons_frame, text="Add", command=lambda: ClientWizard(self.root, "Freebet"), cursor="hand2")
        add_freebet_button.pack(side="top", pady=(10, 5))
        refresh_freebets_button = ttk.Button(freebet_buttons_frame, text="Refresh", command=self.run_freebet_sheet_thread, cursor="hand2")
        refresh_freebets_button.pack(side="top", pady=(10, 5))
        self.last_refresh_freebets_label = ttk.Label(freebet_buttons_frame, text=f"Last Refresh:\n---")
        self.last_refresh_freebets_label.pack(side="top", pady=(10, 5))

        tab_5 = ttk.Frame(self.notebook)
        self.notebook.add(tab_5, text="Popup Log")

        self.popup_tree = ttk.Treeview(tab_5)
        columns = ["A", "B"]
        headings = ["User", "Date Applied"]
        self.popup_tree["columns"] = columns
        for col, heading in enumerate(headings):
            self.popup_tree.heading(columns[col], text=heading)
            self.popup_tree.column(columns[col], width=84, stretch=tk.NO)
        self.popup_tree.column("A", width=150, stretch=tk.NO)
        self.popup_tree.column("B", width=150, stretch=tk.NO)
        self.popup_tree.column("#0", width=10, stretch=tk.NO)
        self.popup_tree.heading("#0", text="", anchor="w")
        self.popup_tree.grid(row=0, column=0, sticky="nsew")
        tab_5.grid_columnconfigure(0, weight=1)
        tab_5.grid_rowconfigure(0, weight=1)
        tab_5.grid_columnconfigure(1, weight=0)
    
        popup_buttons_frame = ttk.Frame(tab_5)
        popup_buttons_frame.grid(row=0, column=1, sticky='ns', padx=(10, 0))
    
        add_popup_button = ttk.Button(popup_buttons_frame, text="Add", command=lambda: ClientWizard(self.root, "Popup"), cursor="hand2")
        add_popup_button.pack(side="top", pady=(10, 5))
        refresh_popup_button = ttk.Button(popup_buttons_frame, text="Refresh", command=self.run_popup_sheet_thread, cursor="hand2")
        refresh_popup_button.pack(side="top", pady=(10, 5))
        self.last_refresh_popup_label = ttk.Label(popup_buttons_frame, text=f"Last Refresh:\n---")
        self.last_refresh_popup_label.pack(side="top", pady=(10, 5))

    def initialize_text_tags(self):
        self.pinned_message.tag_configure('center', justify='center')
        self.report_ticket.tag_configure("risk", foreground="#ad0202")
        self.report_ticket.tag_configure("watchlist", foreground="#e35f00")
        self.report_ticket.tag_configure("newreg", foreground="purple")
        self.report_ticket.tag_configure('center', justify='center', font=('Helvetica', 10, 'bold'))
        self.report_ticket.tag_configure('c', justify='center')
        self.report_ticket.tag_configure('bold', font=('Helvetica', 10, 'bold'))

    def update_notifications(self):
        self.staff_feed.tag_configure("important", font=("TkDefaultFont", 10, "bold"))
        self.staff_feed.config(state='normal')  
        file_lock = fasteners.InterProcessLock(os.path.join(NETWORK_PATH_PREFIX, 'notifications.lock'))

        with file_lock:
            try:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'notifications.json'), 'r') as f:
                    notifications = json.load(f)

                pinned_notifications = [n for n in notifications if n.get('pinned', False)]
                regular_notifications = [n for n in notifications if not n.get('pinned', False)]

                self.pinned_message.config(state='normal') 
                self.pinned_message.delete('1.0', 'end')  
                if not pinned_notifications:
                    self.pinned_message.insert('end', "No bulletin message\n", "center")
                for notification in pinned_notifications:
                    self.pinned_message.insert('end', f"{notification['message']}\n")
                self.pinned_message.config(state='disabled') 

                if regular_notifications and (self.last_notification is None or self.last_notification != regular_notifications[0]):
                    last_index = next((index for index, notification in enumerate(regular_notifications) if notification == self.last_notification), len(regular_notifications))
                    for notification in reversed(regular_notifications[:last_index]):
                        time_str = notification['time']
                        message = notification['message']
                        important = notification.get('important', False)
                        if important:
                            message = f'{time_str}: {message}\n'
                            self.staff_feed.insert('1.0', message, "important")
                        else:
                            self.staff_feed.insert('1.0', f'{time_str}: {message}\n')
                    self.last_notification = regular_notifications[0] if regular_notifications else None

            except (FileNotFoundError, json.JSONDecodeError):
                pass
        self.staff_feed.config(state='disabled') 
        self.staff_feed.after(1500, self.update_notifications)

    def on_report_combobox_select(self, event):
        selected_report = self.report_combobox.get()
        if selected_report == "Client Report":
            self.client_id_frame.pack(side="top", pady=(5, 10), padx=(5, 0))
        else:
            self.client_id_frame.pack_forget()

    def generate_report(self):
        report_type = self.report_combobox.get()
        if report_type == "Daily Report":
            self.report_thread = threading.Thread(target=self.create_daily_report)
        elif report_type == "Monthly Report":
            self.report_thread = threading.Thread(target=self.create_monthly_report)
        elif report_type == "Staff Report":
            self.report_thread = threading.Thread(target=self.create_staff_report)
        elif report_type == "Traders Screener":
            self.report_thread = threading.Thread(target=self.update_traders_report)
        elif report_type == "RG Screener":
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "RG Screener not currently available")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        elif report_type == "Client Report":
            client_id = self.client_id_entry.get()
            self.report_thread = threading.Thread(target=self.create_client_report, args=(client_id,))
        else:
            return
        self.report_thread.start()

    def create_daily_report(self):
        try:
            conn, cursor = database_manager.get_connection()
            _, _, _, reporting_data = access_data()

            time = datetime.now()
            current_date_str = time.strftime("%d/%m/%Y")
            formatted_time = time.strftime("%H:%M:%S")

            current_date_obj = datetime.strptime(current_date_str, "%d/%m/%Y")
            current_date_iso = current_date_obj.strftime("%Y-%m-%d")
            start_of_current_week = current_date_obj - timedelta(days=current_date_obj.weekday())
            start_of_current_week_iso = start_of_current_week.strftime("%Y-%m-%d")
            start_of_previous_week = start_of_current_week - timedelta(days=7)
            start_of_previous_week_iso = start_of_previous_week.strftime("%Y-%m-%d")
            # total_deposits = reporting_data.get('total_deposits', 'N/A')
            # total_sum_deposits = reporting_data.get('total_sum', 'N/A')

            self.progress_label.config(text=f"Finding clients data")

            # Fetch the count of unique clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ?", (current_date_str,))
            total_unique_clients = cursor.fetchone()[0]
        
            # Fetch the count of M clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'M'", (current_date_str,))
            unique_m_clients = cursor.fetchone()[0]
        
            # Fetch the count of W clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'W'", (current_date_str,))
            unique_w_clients = cursor.fetchone()[0]
        
            # Fetch the count of no risk clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (risk_category = '-' OR risk_category IS NULL)", (current_date_str,))
            unique_norisk_clients = cursor.fetchone()[0]
        
            # Fetch the average count of unique clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_unique_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_unique_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of unique clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_unique_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_unique_clients_previous_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of M clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_m_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'M'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_m_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of M clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_m_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'M'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_m_clients_previous_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of W clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_w_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'W'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_w_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of W clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_w_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'W'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_w_clients_previous_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of no-risk clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_norisk_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND (risk_category = '-' OR risk_category IS NULL)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_norisk_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of no-risk clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_norisk_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND (risk_category = '-' OR risk_category IS NULL)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_norisk_clients_previous_week = cursor.fetchone()[0] or 0.0

            self.progress_label.config(text=f"Finding bets data")

            # Fetch the count of bets for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
            total_bets = cursor.fetchone()[0]
        
            # Fetch the count of knockbacks for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK'", (current_date_str,))
            total_wageralerts = cursor.fetchone()[0]
        
            # Fetch the count of SMS for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'SMS WAGER'", (current_date_str,))
            total_sms = cursor.fetchone()[0]
        
            # Fetch the count of bets for each sport for the current day
            cursor.execute("SELECT sports, COUNT(*) FROM database WHERE date = ? AND type = 'BET' GROUP BY sports", (current_date_str,))
            sport_counts = cursor.fetchall()
        
            self.progress_label.config(text=f"Finding knockback data")

            # Fetch the count of different types of wager alerts
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Has Changed%'", (current_date_str,))
            price_change = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Liability Exceeded: True%'", (current_date_str,))
            liability_exceeded = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Event Has Ended%'", (current_date_str,))
            event_ended = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Type Disallowed%'", (current_date_str,))
            price_type_disallowed = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Sport Disallowed%'", (current_date_str,))
            sport_disallowed = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%User Max Stake Exceeded%'", (current_date_str,))
            max_stake_exceeded = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message NOT LIKE '%Price Has Changed%' AND error_message NOT LIKE '%Liability Exceeded: True%' AND error_message NOT LIKE '%Event Has Ended%' AND error_message NOT LIKE '%Price Type Disallowed%' AND error_message NOT LIKE '%Sport Disallowed%' AND error_message NOT LIKE '%User Max Stake Exceeded%'", (current_date_str,))
            other_alert = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Type Disallowed%' OR error_message LIKE '%Sport Disallowed%' OR error_message LIKE '%User Max Stake Exceeded%'", (current_date_str,))
            user_restriction = cursor.fetchone()[0]
        
            self.progress_label.config(text=f"Calculating stakes")

            # Fetch the total stakes for the current day
            cursor.execute("SELECT SUM(total_stake) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
            total_stakes = cursor.fetchone()[0] or 0.0
        
            # Fetch the top 5 highest stakes
            cursor.execute("SELECT customer_ref, SUM(total_stake) as total FROM database WHERE date = ? AND type = 'BET' GROUP BY customer_ref ORDER BY total DESC LIMIT 5", (current_date_str,))
            top_spenders = cursor.fetchall()
        
            # Fetch the top 5 clients with most bets
            cursor.execute("SELECT customer_ref, COUNT(*) as total FROM database WHERE date = ? AND type = 'BET' GROUP BY customer_ref ORDER BY total DESC LIMIT 5", (current_date_str,))
            top_client_bets = cursor.fetchall()
        
            # Fetch the top 3 clients with most knockbacks
            cursor.execute("SELECT customer_ref, COUNT(*) as total FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' GROUP BY customer_ref ORDER BY total DESC LIMIT 3", (current_date_str,))
            top_wageralert_clients = cursor.fetchall()
        
            # Fetch the count of bets per hour for the current day
            cursor.execute("SELECT strftime('%H:00', time) as hour, COUNT(*) FROM database WHERE date = ? AND type = 'BET' GROUP BY hour", (current_date_str,))
            bets_per_hour = cursor.fetchall()
            
            self.progress_label.config(text=f"Calculating averages")

            # Fetch the average number of daily bets, knockbacks, and SMS text bets for the current week
            cursor.execute("""
                SELECT 
                    AVG(bets) as avg_bets, 
                    AVG(knockbacks) as avg_knockbacks, 
                    AVG(sms_bets) as avg_sms_bets
                FROM (
                    SELECT 
                        date,
                        COUNT(CASE WHEN type = 'BET' THEN 1 END) as bets,
                        COUNT(CASE WHEN type = 'WAGER KNOCKBACK' THEN 1 END) as knockbacks,
                        COUNT(CASE WHEN type = 'SMS WAGER' THEN 1 END) as sms_bets
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY date
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_day_bets, avg_day_knockbacks, avg_day_sms_bets = cursor.fetchone()
            
            # Handle None values
            avg_day_bets = avg_day_bets if avg_day_bets is not None else 0
            avg_day_knockbacks = avg_day_knockbacks if avg_day_knockbacks is not None else 0
            avg_day_sms_bets = avg_day_sms_bets if avg_day_sms_bets is not None else 0
            
            # Fetch the average number of daily bets, knockbacks, and SMS text bets for the previous week
            cursor.execute("""
                SELECT 
                    AVG(bets) as avg_bets, 
                    AVG(knockbacks) as avg_knockbacks, 
                    AVG(sms_bets) as avg_sms_bets
                FROM (
                    SELECT 
                        date,
                        COUNT(CASE WHEN type = 'BET' THEN 1 END) as bets,
                        COUNT(CASE WHEN type = 'WAGER KNOCKBACK' THEN 1 END) as knockbacks,
                        COUNT(CASE WHEN type = 'SMS WAGER' THEN 1 END) as sms_bets
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY date
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_bets, avg_knockbacks, avg_sms_bets = cursor.fetchone()
            
            # Handle None values
            avg_bets = avg_bets if avg_bets is not None else 0
            avg_knockbacks = avg_knockbacks if avg_knockbacks is not None else 0
            avg_sms_bets = avg_sms_bets if avg_sms_bets is not None else 0
        
            # Fetch the average total stakes for the current week
            cursor.execute("""
                SELECT AVG(daily_total) as avg_total_stake
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        SUM(total_stake) as daily_total
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND type = 'BET'
                    GROUP BY day
                ) as daily_totals
            """, (start_of_current_week_iso, current_date_iso))
            avg_total_stake_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average total stakes for the previous week
            cursor.execute("""
                SELECT AVG(daily_total) as avg_total_stake
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        SUM(total_stake) as daily_total
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND type = 'BET'
                    GROUP BY day
                ) as daily_totals
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_total_stake_previous_week = cursor.fetchone()[0] or 0.0

            conn.close()

            # Initialize sport counts
            horse_bets = 0
            dog_bets = 0
            other_bets = 0
            
            # Map the sport counts
            sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
            for sport, count in sport_counts:
                sport_list = eval(sport)
                if sport_mapping['Horses'] in sport_list:
                    horse_bets += count
                if sport_mapping['Dogs'] in sport_list:
                    dog_bets += count
                if sport_mapping['Other'] in sport_list:
                    other_bets += count
            

            total_sport_bets = horse_bets + dog_bets + other_bets
            percentage_horse_racing = (horse_bets / total_sport_bets) * 100
            percentage_greyhound = (dog_bets / total_sport_bets) * 100
            percentage_other = (other_bets / total_sport_bets) * 100

        except Exception as e:
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "An error occurred while generating the report.\nPlease try again.")
            self.progress_label.config(text="Error with Daily Report")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        finally:
            if conn:
                conn.close()

        separator = "-" * 69

        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)

        self.report_ticket.insert(tk.END, f"DAILY REPORT\nGenerated at {formatted_time}\n", 'center')
        self.report_ticket.insert(tk.END, f"{separator}\n")

        self.report_ticket.insert(tk.END, f"Today's Activity:\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets {total_bets:,} | KB {total_wageralerts:,} | KB % {total_wageralerts / total_bets * 100:.2f}%\n", 'c')
        self.report_ticket.insert(tk.END, f"This week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets {int(avg_day_bets):,} | KB {int(avg_day_knockbacks):,} | KB % {(avg_day_knockbacks / avg_day_bets * 100):.2f}%\n", 'c')
        self.report_ticket.insert(tk.END, f"Last week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets {int(avg_bets):,} | KB {int(avg_knockbacks):,} | KB % {(avg_knockbacks / avg_bets * 100):.2f}%\n", 'c')

        self.report_ticket.insert(tk.END, f"\nToday's Stakes:\n", 'center')
        self.report_ticket.insert(tk.END, f"Stakes £{total_stakes:,.2f} | Average Stake ~£{total_stakes / total_bets:,.2f}\n", 'c')
        self.report_ticket.insert(tk.END, f"This week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Stakes £{avg_total_stake_current_week:,.2f}  | Average Stake ~£{avg_total_stake_current_week / avg_day_bets:,.2f}\n", 'c')
        self.report_ticket.insert(tk.END, f"Last week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Stakes £{avg_total_stake_previous_week:,.2f}  | Average Stake ~£{avg_total_stake_previous_week / avg_bets:,.2f}\n", 'c')

        self.report_ticket.insert(tk.END, f"\nToday's Clients:\n", 'center')
        self.report_ticket.insert(tk.END, f"Total: {total_unique_clients:,} | --: {unique_norisk_clients:,} | M: {unique_m_clients:,} | W: {unique_w_clients:,}\n", 'c')
        self.report_ticket.insert(tk.END, f"This week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Total: {int(avg_unique_clients_current_week):,} | --: {int(avg_norisk_clients_current_week):,} | M: {int(avg_m_clients_current_week):,} | W: {int(avg_w_clients_current_week):,}\n", 'c')
        self.report_ticket.insert(tk.END, f"Last week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Total: {int(avg_unique_clients_previous_week):,} | --: {int(avg_norisk_clients_previous_week):,} | M: {int(avg_m_clients_previous_week):,} | W: {int(avg_w_clients_previous_week):,}\n", 'c')
        # self.report_ticket.insert(tk.END, f"\nToday's Deposits:\n", 'center')
        # self.report_ticket.insert(tk.END, f"Total: {total_deposits} | Total: £{total_sum_deposits:,.2f}\n", 'c')

        self.report_ticket.insert(tk.END, f"\nToday's Sports:\n", 'center')
        self.report_ticket.insert(tk.END, f"Horses: {horse_bets} ({percentage_horse_racing:.2f}%) | Dogs: {dog_bets} ({percentage_greyhound:.2f}%) | Other: {other_bets} ({percentage_other:.2f}%)\n", 'c')
        
        self.report_ticket.insert(tk.END, "\nHighest Stakes:\n", 'center')
        for rank, (customer, spend) in enumerate(top_spenders, start=1):
            self.report_ticket.insert(tk.END, f"\t{rank}. {customer} - Stakes: £{spend:,.2f}\n", 'c')

        self.report_ticket.insert(tk.END, "\nMost Bets:\n", 'center')
        for rank, (client, count) in enumerate(top_client_bets, start=1):
            self.report_ticket.insert(tk.END, f"\t{rank}. {client} - Bets: {count:,}\n", 'c')

        self.report_ticket.insert(tk.END, f"\nMost Knockbacks:\n", 'center')
        for rank, (client, count) in enumerate(top_wageralert_clients, start=1):
            self.report_ticket.insert(tk.END, f"\t{rank}. {client} - Knockbacks: {count:,}\n", 'c')


        self.report_ticket.insert(tk.END, f"\nKnockbacks by Type:", 'center')
        self.report_ticket.insert(tk.END, f"\nLiability: {liability_exceeded}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Price Change: {price_change}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Event Ended: {event_ended}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Price Type: {price_type_disallowed}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Sport: {sport_disallowed}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Max Stake: {max_stake_exceeded}", 'c')

        self.report_ticket.insert(tk.END, f"\n\nBets Per Hour:\n", 'center')
        for hour, count in bets_per_hour:
            self.report_ticket.insert(tk.END, f"\t{hour} - Bets: {count}\n", 'c')

        self.progress_label.config(text=f"---")

        self.report_ticket.config(state="disabled")
    
    def create_monthly_report(self):
        try:
            conn, cursor = database_manager.get_connection()
            report_output = ""
        
            # Get today's date
            today = datetime.now()
            formatted_time = today.strftime("%d/%m/%Y %H:%M:%S")
        
            # Calculate the date 30 days ago
            start_date = today - timedelta(days=30)
            separator = "-" * 69
        
            # Header for the monthly report
            report_output += f"MONTHLY REPORT TICKET\n Generated at {formatted_time}\n"
            report_output += f"{separator}\n"
        
            # Loop through each day in the last 30 days, starting from today
            for i in range(30):
                current_date = today - timedelta(days=i)
                current_date_str = current_date.strftime("%d/%m/%Y")

                self.progress_label.config(text=f"Generating {current_date_str}")
        
                # Fetch the count of bets for the current day
                cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
                total_bets = cursor.fetchone()[0]
        
                # Fetch the count of knockbacks for the current day
                cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK'", (current_date_str,))
                total_knockbacks = cursor.fetchone()[0]
        
                # Fetch the count of unique clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ?", (current_date_str,))
                total_unique_clients = cursor.fetchone()[0]
        
                # Fetch the count of M clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'M'", (current_date_str,))
                unique_m_clients = cursor.fetchone()[0]
        
                # Fetch the count of W clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'W'", (current_date_str,))
                unique_w_clients = cursor.fetchone()[0]
        
                # Fetch the count of no risk clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (risk_category = '-' OR risk_category IS NULL)", (current_date_str,))
                unique_norisk_clients = cursor.fetchone()[0]
        
                # Fetch the count of bets for each sport for the current day
                cursor.execute("SELECT sports, COUNT(*) FROM database WHERE date = ? AND type = 'BET' GROUP BY sports", (current_date_str,))
                sport_counts = cursor.fetchall()
        
                # Initialize sport counts
                horse_bets = 0
                dog_bets = 0
                other_bets = 0
        
                # Map the sport counts
                sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
                for sport, count in sport_counts:
                    sport_list = eval(sport)
                    if sport_mapping['Horses'] in sport_list:
                        horse_bets += count
                    if sport_mapping['Dogs'] in sport_list:
                        dog_bets += count
                    if sport_mapping['Other'] in sport_list:
                        other_bets += count
        
                # Fetch the total stakes for the current day
                cursor.execute("SELECT SUM(total_stake) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
                total_stakes = cursor.fetchone()[0] or 0.0


                # Append the data for the current day to the report output
                report_output += f"Date: {current_date_str}\n"
                report_output += "----------------------------------------\n"
                report_output += f" - Bets  |  Knockbacks  |  Knockback % - \n"
                report_output += f"{total_bets:,}      |      {total_knockbacks:,}      |      {total_knockbacks / total_bets * 100:.2f}%\n"
                report_output += f"\n - Stakes   |   Average Stake - \n"
                report_output += f"£{total_stakes:,.2f}     |     ~£{total_stakes / total_bets:,.2f}\n"
                report_output += f"\nClients: {total_unique_clients:,} | --: {unique_norisk_clients:,} | M: {unique_m_clients:,} | W: {unique_w_clients:,}\n"
                report_output += f"\nHorses: {horse_bets} | Dogs: {dog_bets} | Other: {other_bets}\n\n"
            
            conn.close()

            self.progress_label.config(text=f"---")

            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', report_output)
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")

        except Exception as e:
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "An error occurred while generating the report.\nPlease try again.")
            self.progress_label.config(text="Error with Monthly Report")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        
        finally:
            if conn:
                conn.close()

    def create_client_report(self, client_id):
        try:
            conn, cursor = database_manager.get_connection()
            client_id = client_id.upper()
            
            # Get the current date in string format
            current_date_str = datetime.now().strftime("%d/%m/%Y")
            formatted_time = datetime.now().strftime("%H:%M:%S")
    
            self.progress_label.config(text=f"Finding client data")
    
            # Fetch the count of bets for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'BET'", (client_id, current_date_str))
            total_bets = cursor.fetchone()[0]
            
            # Fetch the total stakes for the client for the current day
            cursor.execute("SELECT SUM(total_stake) FROM database WHERE customer_ref = ? AND date = ? AND type = 'BET'", (client_id, current_date_str))
            total_stakes = cursor.fetchone()[0] or 0.0
            
            # Fetch the count of knockbacks for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK'", (client_id, current_date_str))
            total_wageralerts = cursor.fetchone()[0]
            
            # Fetch the count of SMS for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'SMS WAGER'", (client_id, current_date_str))
            total_sms = cursor.fetchone()[0]
            
            # Fetch the count of bets for each sport for the client for the current day
            cursor.execute("SELECT sports, COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'BET' GROUP BY sports", (client_id, current_date_str))
            sport_counts = cursor.fetchall()
            
            self.progress_label.config(text=f"Finding knockback data")
    
            # Fetch the count of different types of wager alerts for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Has Changed%'", (client_id, current_date_str))
            price_change = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Liability Exceeded: True%'", (client_id, current_date_str))
            liability_exceeded = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Event Has Ended%'", (client_id, current_date_str))
            event_ended = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Type Disallowed%'", (client_id, current_date_str))
            price_type_disallowed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Sport Disallowed%'", (client_id, current_date_str))
            sport_disallowed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%User Max Stake Exceeded%'", (client_id, current_date_str))
            max_stake_exceeded = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message NOT LIKE '%Price Has Changed%' AND error_message NOT LIKE '%Liability Exceeded: True%' AND error_message NOT LIKE '%Event Has Ended%' AND error_message NOT LIKE '%Price Type Disallowed%' AND error_message NOT LIKE '%Sport Disallowed%' AND error_message NOT LIKE '%User Max Stake Exceeded%'", (client_id, current_date_str))
            other_alert = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND (error_message LIKE '%Price Type Disallowed%' OR error_message LIKE '%Sport Disallowed%' OR error_message LIKE '%User Max Stake Exceeded%')", (client_id, current_date_str))
            user_restriction = cursor.fetchone()[0]
            
            self.progress_label.config(text=f"Calculating stakes")
    
            conn.close()
    
            # Initialize sport counts
            horse_bets = 0
            dog_bets = 0
            other_bets = 0
            
            # Map the sport counts
            sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
            for sport, count in sport_counts:
                sport_list = eval(sport)
                if sport_mapping['Horses'] in sport_list:
                    horse_bets += count
                if sport_mapping['Dogs'] in sport_list:
                    dog_bets += count
                if sport_mapping['Other'] in sport_list:
                    other_bets += count
            
            total_sport_bets = horse_bets + dog_bets + other_bets
            percentage_horse_racing = (horse_bets / total_sport_bets) * 100 if total_sport_bets else 0
            percentage_greyhound = (dog_bets / total_sport_bets) * 100 if total_sport_bets else 0
            percentage_other = (other_bets / total_sport_bets) * 100 if total_sport_bets else 0
    
        except Exception as e:
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "An error occurred while generating the report.\nPlease try again.")
            self.progress_label.config(text="Error with Client Report")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        finally:
            if conn:
                conn.close()
    
        separator = "-" * 69

        if total_bets > 0:
            knockback_percentage = f"{total_wageralerts / total_bets * 100:.2f}%"
        else:
            knockback_percentage = "N/A"

        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)
    
        self.report_ticket.insert(tk.END, f"CLIENT REPORT\nGenerated at {formatted_time}\n", 'center')
        self.report_ticket.insert(tk.END, f"{client_id} - {current_date_str}\n", 'center')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{total_bets}\n", 'c')
        self.report_ticket.insert(tk.END, f"Knockbacks: ", 'center')
        self.report_ticket.insert(tk.END, f"{total_wageralerts}\n", 'c')
        self.report_ticket.insert(tk.END, f"Knockback %: ", 'center')
        self.report_ticket.insert(tk.END, f"{knockback_percentage}\n", 'c')
        self.report_ticket.insert(tk.END, f"SMS Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{total_sms}\n", 'c')
        self.report_ticket.insert(tk.END, f"Stakes: ", 'center')
        self.report_ticket.insert(tk.END, f"£{total_stakes:,}\n", 'c')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
        self.report_ticket.insert(tk.END, f"Knockbacks:\n", 'center')
        self.report_ticket.insert(tk.END, f"Price Change: ", 'center')
        self.report_ticket.insert(tk.END, f"{price_change}\n", 'c')
        self.report_ticket.insert(tk.END, f"Liability Exceeded: ", 'center')
        self.report_ticket.insert(tk.END, f"{liability_exceeded}\n", 'c')
        self.report_ticket.insert(tk.END, f"Event Ended: ", 'center')
        self.report_ticket.insert(tk.END, f"{event_ended}\n", 'c')
        self.report_ticket.insert(tk.END, f"Price Type Disallowed: ", 'center')
        self.report_ticket.insert(tk.END, f"{price_type_disallowed}\n", 'c')
        self.report_ticket.insert(tk.END, f"Sport Disallowed: ", 'center')
        self.report_ticket.insert(tk.END, f"{sport_disallowed}\n", 'c')
        self.report_ticket.insert(tk.END, f"Max Stake Exceeded: ", 'center')
        self.report_ticket.insert(tk.END, f"{max_stake_exceeded}\n", 'c')
        self.report_ticket.insert(tk.END, f"Other: ", 'center')
        self.report_ticket.insert(tk.END, f"{other_alert}\n", 'c')
        self.report_ticket.insert(tk.END, f"User Restriction: ", 'center')
        self.report_ticket.insert(tk.END, f"{user_restriction}\n", 'c')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
        self.report_ticket.insert(tk.END, f"Horse Racing Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{horse_bets} ({percentage_horse_racing:.2f}%)\n", 'c')
        self.report_ticket.insert(tk.END, f"Greyhound Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{dog_bets} ({percentage_greyhound:.2f}%)\n", 'c')
        self.report_ticket.insert(tk.END, f"Other Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{other_bets} ({percentage_other:.2f}%)\n", 'c')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
    
        self.report_ticket.config(state="disabled")
    
    def create_staff_report(self):
        global USER_NAMES
    
        course_updates = Counter()
        staff_updates = Counter()
        staff_updates_today = Counter()
        staff_updates_count_today = Counter()
        staff_updates_count_month = Counter()  # New counter for total updates for the month
        factoring_updates = Counter()
        offenders = Counter()
        daily_updates = Counter()
        individual_update_scores = []  # List to track individual update scores
        today = datetime.now().date()
        current_date = datetime.now().date()
        month_ago = current_date.replace(day=1)
        days_in_month = (current_date - month_ago).days + 1
    
        log_files = os.listdir(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs'))
        log_files.sort(key=lambda file: os.path.getmtime(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', file)))
        # Read all the log files from the past month
        for i, log_file in enumerate(log_files):
            file_date = datetime.fromtimestamp(os.path.getmtime(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', log_file))).date()
            if month_ago <= file_date <= current_date:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', log_file), 'r') as file:
                    lines = file.readlines()
    
                update_counts = {}
    
                for line in lines:
                    if line.strip() == '':
                        continue
    
                    parts = line.strip().split(' - ')
    
                    if len(parts) == 1 and parts[0].endswith(':'):
                        course = parts[0].replace(':', '')
                        continue
    
                    if len(parts) == 3:
                        time, staff_initials, score = parts
                        score = float(score)
                        staff_name = USER_NAMES.get(staff_initials, staff_initials)
                        course_updates[course] += score
                        staff_updates[staff_name] += score
                        daily_updates[(staff_name, file_date)] += score
    
                        # Track individual update scores
                        individual_update_scores.append((staff_name, score))
    
                        if file_date == today:
                            current_time = datetime.strptime(time, '%H:%M')
                            if course not in update_counts:
                                update_counts[course] = {}
                            if staff_name not in update_counts[course]:
                                update_counts[course][staff_name] = Counter()
                            update_counts[course][staff_name][current_time] += 1
    
                            if update_counts[course][staff_name][current_time] > 1:
                                offenders[staff_name] += 1
    
                            staff_updates_today[staff_name] += score
                            staff_updates_count_today[staff_name] += 1  # Increment the count for today's updates
    
                        # Increment the count for the month's updates
                        staff_updates_count_month[staff_name] += 1
    
        # Filter out non-staff members from staff_updates_today and staff_updates
        staff_updates_today = Counter({staff: count for staff, count in staff_updates_today.items() if staff in USER_NAMES.values()})
        staff_updates = Counter({staff: count for staff, count in staff_updates.items() if staff in USER_NAMES.values()})
    
        # Calculate average updates per day for each staff member
        average_updates_per_day = Counter()
        for (staff, date), count in daily_updates.items():
            if staff in USER_NAMES.values():
                average_updates_per_day[staff] += count
    
        for staff in average_updates_per_day:
            average_updates_per_day[staff] /= days_in_month
    
        factoring_log_files = os.listdir(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs'))
        factoring_log_files.sort(key=lambda file: os.path.getmtime(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs', file)))
    
        for log_file in factoring_log_files:
            with open(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs', log_file), 'r') as file:
                lines = file.readlines()
    
            for line in lines:
                if line.strip() == '':
                    continue
    
                data = json.loads(line)
                staff_initials = data['Staff']
                staff_name = USER_NAMES.get(staff_initials, staff_initials)
                factoring_updates[staff_name] += 1
    
        # Calculate the ratio of score to updates for each user for the current month
        score_to_updates_ratio = {}
        for staff in staff_updates_count_month:
            if staff_updates_count_month[staff] > 0:
                ratio = staff_updates[staff] / staff_updates_count_month[staff]
                score_to_updates_ratio[staff] = ratio
    
        # Find the user with the lowest ratio (busiest idiot)
        busiest_idiot = min(score_to_updates_ratio, key=score_to_updates_ratio.get)
    
        # Find the user with the highest ratio (playing the system)
        playing_the_system = max(score_to_updates_ratio, key=score_to_updates_ratio.get)
    
        # Find the user with the highest single update score
        highest_single_update_score = max(individual_update_scores, key=lambda item: item[1])
    
        # Find the user with the lowest single update score
        lowest_single_update_score = min(individual_update_scores, key=lambda item: item[1])
    
        # Find the top 3 highest daily total scores
        top_daily_total_scores = sorted(daily_updates.items(), key=lambda item: item[1], reverse=True)[:3]
    
        # Find the day with the most points claimed
        daily_total_scores = Counter()
        for (staff, date), score in daily_updates.items():
            daily_total_scores[date] += score
    
        day_with_most_points = daily_total_scores.most_common(1)[0]
        day_with_most_points_date = day_with_most_points[0]
        day_with_most_points_score = day_with_most_points[1]
    
        # Calculate the percentage share of points for each user on the day with the most points
        points_share = {}
        for (staff, date), score in daily_updates.items():
            if date == day_with_most_points_date:
                points_share[staff] = (score / day_with_most_points_score) * 100
    
        separator = "-" * 69
    
        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)
    
        self.report_ticket.insert(tk.END, "STAFF REPORT\n", 'center')
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
    
        employee_of_the_month, _ = staff_updates.most_common(1)[0]
        self.report_ticket.insert(tk.END, f"Employee Of The Month:\n", 'center')
        self.report_ticket.insert(tk.END, f"{employee_of_the_month}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
        self.report_ticket.insert(tk.END, "Current Day", 'center')    
        self.report_ticket.insert(tk.END, "\nToday's Staff Scores:\n", 'center')
        for staff, count in sorted(staff_updates_today.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nToday's Staff Updates:\n", 'center')
        for staff, count in sorted(staff_updates_count_today.items(), key=lambda item: item[1], reverse=True):  # Use the new counter
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
        
        if offenders:
            self.report_ticket.insert(tk.END, "\nUpdation Offenders Today:\n", 'center')
            for staff, count in sorted(offenders.items(), key=lambda item: item[1], reverse=True):
                self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
    
        self.report_ticket.insert(tk.END, "Current Month", 'center')    
        self.report_ticket.insert(tk.END, f"\nScores:\n", 'center')
        for staff, count in sorted(staff_updates.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"\nUpdates:\n", 'center')  # New section for total updates
        for staff, count in sorted(staff_updates_count_month.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"\nAverage Daily Score:\n", 'center')
        for staff, avg_count in sorted(average_updates_per_day.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {avg_count:.2f}\n", 'c')
        
        self.report_ticket.insert(tk.END, "\nTop 3 Highest Daily Total Scores:\n", 'center')
        for (staff, date), score in top_daily_total_scores:
            formatted_date = date.strftime('%d/%m')
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {formatted_date}  |  {score:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nDay with Most Points Claimed:\n", 'center')
        formatted_date = day_with_most_points_date.strftime('%d/%m')
        self.report_ticket.insert(tk.END, f"\t{formatted_date}  |  {day_with_most_points_score:.2f}\n", 'c')
        self.report_ticket.insert(tk.END, "Points Share:\n", 'c')
        for staff, share in sorted(points_share.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {share:.2f}%\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nBusiest Idiot:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{busiest_idiot}\n", 'c')
    
        self.report_ticket.insert(tk.END, "Playing the System:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{playing_the_system}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nHighest Single Update Score:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{highest_single_update_score[0]}  |  {highest_single_update_score[1]:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "Lowest Single Update Score:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{lowest_single_update_score[0]}  |  {lowest_single_update_score[1]:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nScores Per Event:\n", 'center')
        for course, count in sorted(course_updates.items(), key=lambda item: item[1], reverse=True)[:10]:
            self.report_ticket.insert(tk.END, f"\t{course}  |  {count:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
    
        self.report_ticket.insert(tk.END, "All Time Staff Factoring:\n", 'center')
        for staff, count in sorted(factoring_updates.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
    
        self.progress_label.config(text=f"---")
        self.report_ticket.config(state="disabled")

    # def create_rg_report(self):

    #     data = get_database()
    #     user_scores = {}
    #     virtual_events = ['Portman Park', 'Sprintvalley', 'Steepledowns', 'Millersfield', 'Brushwood']

    #     self.progress["maximum"] = len(data)
    #     self.progress["value"] = 0

    #     for bet in data:
    #         self.progress["value"] += 1

    #         wager_type = bet.get('type', '').lower()
    #         if wager_type == 'bet':
    #             details = bet.get('details', {})
    #             bet_time = datetime.strptime(bet.get('time', ''), "%H:%M:%S")
    #             customer_reference = bet.get('customer_ref', '')
    #             stake = float(details.get('unit_stake', '£0').replace('£', '').replace(',', ''))

    #             if customer_reference not in user_scores:
    #                 user_scores[customer_reference] = {
    #                     'bets': [],
    #                     'odds': [],
    #                     'total_bets': 0,
    #                     'score': 0,
    #                     'average_stake': 0,
    #                     'max_stake': 0,
    #                     'min_stake': float('inf'),
    #                     'deposits': [],  # New field for storing deposits
    #                     'min_deposit': None,  # Initialize to None
    #                     'max_deposit': 0,
    #                     'total_deposit': 0,
    #                     'total_stake': 0,
    #                     'virtual_bets': 0,
    #                     'early_bets': 0,
    #                     'scores': {
    #                         'num_bets': 0,
    #                         'long_period': 0,
    #                         'stake_increase': 0,
    #                         'high_total_stake': 0,
    #                         'virtual_events': 0,
    #                         'chasing_losses': 0,
    #                         'early_hours': 0,
    #                         'high_deposit_total': 0,
    #                         'frequent_deposits': 0,
    #                         'increasing_deposits': 0,
    #                         'changed_payment_type': 0,
    #                 }
    #             }

    #             # Add the bet to the user's list of bets
    #             user_scores[customer_reference]['bets'].append((bet_time.strftime("%H:%M:%S"), stake))

    #             # Add the odds to the user's list of odds
    #             selections = details.get('selections', [])
    #             for selection in selections:
    #                 odds = selection[1]
    #                 if isinstance(odds, str):
    #                     if odds.lower() == 'evs':
    #                         odds = 2.0
    #                     elif odds.lower() == 'sp':
    #                         continue
    #                     else:
    #                         try:
    #                             odds = float(odds)
    #                         except ValueError:
    #                             continue
    #                 user_scores[customer_reference]['odds'].append(odds)
    #                 if any(event in selection[0] for event in virtual_events):
    #                     user_scores[customer_reference]['virtual_bets'] += 1
    #                     break

    #             # Increase the total number of bets
    #             user_scores[customer_reference]['total_bets'] += 1

    #             # Update the total stake
    #             user_scores[customer_reference]['total_stake'] += stake

    #             # Skip this iteration if the user has placed fewer than 6 bets
    #             if len(user_scores[customer_reference]['bets']) < 6:
    #                 continue

    #             # Update the max and min stakes
    #             user_scores[customer_reference]['max_stake'] = max(user_scores[customer_reference]['max_stake'], stake)
    #             user_scores[customer_reference]['min_stake'] = min(user_scores[customer_reference]['min_stake'], stake)

    #             # Calculate the new average stake
    #             total_stake = sum(stake for _, stake in user_scores[customer_reference]['bets'])
    #             user_scores[customer_reference]['average_stake'] = total_stake / len(user_scores[customer_reference]['bets'])

    #             # Add a point if the user has placed more than 10 bets
    #             if len(user_scores[customer_reference]['bets']) > 10 and user_scores[customer_reference]['scores']['num_bets'] == 0:
    #                 user_scores[customer_reference]['scores']['num_bets'] = 1

    #             # Add a point if the user has been gambling for a long period of time
    #             first_bet_time = datetime.strptime(user_scores[customer_reference]['bets'][0][0], "%H:%M:%S")
    #             if (bet_time - first_bet_time).total_seconds() > 2 * 60 * 60 and user_scores[customer_reference]['scores']['long_period'] == 0:  # 2 hours
    #                 user_scores[customer_reference]['scores']['long_period'] = 1

    #             # Add a point if the user has increased their stake over the average
    #             half = len(user_scores[customer_reference]['bets']) // 2
    #             first_half_stakes = [stake for _, stake in user_scores[customer_reference]['bets'][:half]]
    #             second_half_stakes = [stake for _, stake in user_scores[customer_reference]['bets'][half:]]
    #             if len(first_half_stakes) > 0 and len(second_half_stakes) > 0:
    #                 first_half_avg = sum(first_half_stakes) / len(first_half_stakes)
    #                 second_half_avg = sum(second_half_stakes) / len(second_half_stakes)
    #                 if second_half_avg > first_half_avg and user_scores[customer_reference]['scores']['stake_increase'] == 0:
    #                     user_scores[customer_reference]['scores']['stake_increase'] = 1

    #             # Add a point if the user's total stake is over £1000
    #             if user_scores[customer_reference]['total_stake'] > 1000 and user_scores[customer_reference]['scores']['high_total_stake'] == 0:
    #                 user_scores[customer_reference]['scores']['high_total_stake'] = 1

    #             # Add a point if the user has placed a bet on a virtual event
    #             if user_scores[customer_reference]['virtual_bets'] > 0 and user_scores[customer_reference]['scores']['virtual_events'] == 0:
    #                 user_scores[customer_reference]['scores']['virtual_events'] = 1

    #             # Check if the bet is placed during early hours
    #             if 0 <= bet_time.hour < 7:
    #                 user_scores[customer_reference]['early_bets'] += 1


    #     now_local = datetime.now(timezone('Europe/London'))
    #     today_filename = f'logs/depositlogs/deposits_{now_local.strftime("%Y-%m-%d")}.json'

    #     # Load the existing messages from the JSON file for today's date
    #     if os.path.exists(today_filename):
    #         with open(today_filename, 'r') as f:
    #             deposits = json.load(f)
            
    #     # Create a dictionary to store deposit information for each user
    #     deposit_info = defaultdict(lambda: {'total': 0, 'times': [], 'amounts': [], 'types': set()})

    #     # Iterate over the deposits
    #     for deposit in deposits:
    #         username = deposit['Username'].upper()
    #         amount = float(deposit['Amount'])
    #         time = datetime.strptime(deposit['Time'], "%Y-%m-%d %H:%M:%S")
    #         type_ = deposit['Type']

    #         # Check if the user exists in the user_scores dictionary
    #         if username not in user_scores:
    #             user_scores[username] = {
    #                 'bets': [],
    #                 'odds': [],
    #                 'total_bets': 0,
    #                 'score': 0,
    #                 'average_stake': 0,
    #                 'max_stake': 0,
    #                 'min_stake': float('inf'),
    #                 'deposits': [],  # New field for storing deposits
    #                 'min_deposit': None,  # Initialize to None
    #                 'max_deposit': 0,
    #                 'total_deposit': 0,
    #                 'total_stake': 0,
    #                 'virtual_bets': 0,
    #                 'early_bets': 0,
    #                 'scores': {
    #                     'num_bets': 0,
    #                     'long_period': 0,
    #                     'stake_increase': 0,
    #                     'high_total_stake': 0,
    #                     'virtual_events': 0,
    #                     'chasing_losses': 0,
    #                     'early_hours': 0,
    #                     'high_deposit_total': 0,
    #                     'frequent_deposits': 0,
    #                     'increasing_deposits': 0,
    #                     'changed_payment_type': 0,
    #                 }
    #             }

    #         # Update the user's deposit information
    #         deposit_info[username]['total'] += amount
    #         deposit_info[username]['times'].append(time)
    #         deposit_info[username]['amounts'].append(amount)
    #         deposit_info[username]['types'].add(type_)

    #         user_scores[username]['deposits'].append(amount)

    #         # Check if the user's total deposit amount is over £500
    #         if deposit_info[username]['total'] > 500:
    #             if username not in user_scores:
    #                 user_scores[username] = {
    #                     'scores': {
    #                         'high_deposit_total': 0,
    #                         # Initialize other fields as needed
    #                     }
    #                 }
    #             user_scores[username]['scores']['high_deposit_total'] = 1

    #         # Check if the user has deposited more than 4 times in an hour
    #         deposit_info[username]['times'].sort()
    #         for i in range(4, len(deposit_info[username]['times'])):
    #             if (deposit_info[username]['times'][i] - deposit_info[username]['times'][i-4]).total_seconds() <= 3600:
    #                 if username not in user_scores:
    #                     user_scores[username] = {'scores': {'frequent_deposits': 0}}
    #                 user_scores[username]['scores']['frequent_deposits'] = 1
    #                 break

    #         # Check if the user's deposits have increased more than twice
    #         increases = 0
    #         for i in range(2, len(deposit_info[username]['amounts'])):
    #             if deposit_info[username]['amounts'][i] > deposit_info[username]['amounts'][i-1] > deposit_info[username]['amounts'][i-2]:
    #                 increases += 1
    #         if increases >= 2:
    #             if username not in user_scores:
    #                 user_scores[username] = {'scores': {'increasing_deposits': 0}}
    #             user_scores[username]['scores']['increasing_deposits'] = 1

    #         # Check if the user has changed payment type
    #         if len(deposit_info[username]['types']) > 1:
    #             if username not in user_scores:
    #                 user_scores[username] = {'scores': {'changed_payment_type': 0}}
    #             user_scores[username]['scores']['changed_payment_type'] = 1

    #     for username, info in user_scores.items():
    #         if info['deposits']:  # Check if the list is not empty
    #             info['min_deposit'] = min(info['deposits'])
    #             info['max_deposit'] = max(info['deposits'])
    #         else:
    #             info['min_deposit'] = 0
    #             info['max_deposit'] = 0
    #         info['total_deposit'] = deposit_info[username]['total']


    #     # After processing all bets, calculate the early hours score
    #     for user, scores in user_scores.items():
    #         if scores['early_bets'] > 3:
    #             scores['scores']['early_hours'] = 1

    #     # After processing all bets, calculate the chasing losses score
    #     for user, scores in user_scores.items():
    #         num_bets = len(scores['bets'])
    #         if num_bets >= 5:  # Only calculate if the user has placed at least 5 bets
    #             split_index = int(num_bets * 0.7)  # Calculate the index to split at 70%
    #             early_odds = scores['odds'][:split_index]
    #             late_odds = scores['odds'][split_index:]
    #             if early_odds and late_odds:  # Check that both lists are not empty
    #                 early_avg = sum(early_odds) / len(early_odds)
    #                 late_avg = sum(late_odds) / len(late_odds)
    #                 if late_avg - early_avg > 4:  # Set the threshold as needed
    #                     scores['scores']['chasing_losses'] = 1


    #     # Update the total score
    #     for user, scores in user_scores.items():
    #         scores['score'] = sum(scores['scores'].values())
                
    #     # Filter out the users who have a score of 0
    #     user_scores = {user: score for user, score in user_scores.items() if score['score'] > 0}

    #     return user_scores
    
    # def update_rg_report(self):
    #     print("Updating RG Report")
    #     user_scores = self.create_rg_report()
    #     print("RG Report Updated")
    #     user_scores = dict(sorted(user_scores.items(), key=lambda item: item[1]['score'], reverse=True))
    #     key_descriptions = {
    #         'num_bets': 'High Number of Bets',
    #         'stake_increase': 'Stakes Increasing',
    #         'virtual_events': 'Bets on Virtual events',
    #         'chasing_losses': 'Odds Increasing, Possibly Chasing Losses',
    #         'high_total_stake': 'High Total Stake',
    #         'early_hours': 'Active in the Early Hours',
    #         'high_deposit_total': 'Total Deposits Over £500',
    #         'frequent_deposits': 'More than 4 Deposits in an Hour',
    #         'increasing_deposits': 'Deposits Increasing',
    #         'changed_payment_type': 'Changed Payment Type'
    #     }

    #     report_output = ""
    #     report_output += f"\tRG SCREENER\n\n"

    #     for user, scores in user_scores.items():
    #         if scores['score'] > 1:
    #             report_output += f"\n{user} - Risk Score: {scores['score']}\n"
    #             report_output += f"This score is due to:\n"
    #             for key, value in scores['scores'].items():
    #                 if value == 1:
    #                     report_output += f"- {key_descriptions.get(key, key)}\n"
    #             report_output += f"\nBets: {scores['total_bets']}  |  "
    #             report_output += f"Total Stake: £{scores['total_stake']:.2f}\n"
    #             report_output += f"Avg Stake: £{scores['average_stake']:.2f}  |  "
    #             report_output += f"Max: £{scores['max_stake']:.2f}  |  "
    #             report_output += f"Min: £{scores['min_stake']:.2f}\n"
    #             report_output += f"Virtual Bets: {scores['virtual_bets']}  |  "
    #             report_output += f"Early Hours Bets: {scores['early_bets']}\n"
    #             report_output += f"Deposits: £{scores['total_deposit']:.2f}  |  "
    #             report_output += f"Max: £{scores['max_deposit']:.2f}  |  "
    #             report_output += f"Min: £{scores['min_deposit']:.2f}\n"
    #             report_output += "\n"

    #     self.report_ticket.config(state='normal')
    #     self.report_ticket.delete('1.0', tk.END)
    #     self.report_ticket.insert(tk.END, report_output)
    #     self.report_ticket.config(state='disabled')

    def create_traders_report(self):
        self.progress_label.config(text="Retrieving database")
        self.report_button.config(state="disabled")
        vip_clients, _, _, _ = access_data()
        conn = None
        cursor = None
        try:
            retry_attempts = 2
            for attempt in range(retry_attempts):
                conn, cursor = database_manager.get_connection()
                if conn is not None:
                    break
                elif attempt < retry_attempts - 1:
                    print("Error finding bets. Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    self.feed_text.config(state="normal")
                    self.feed_text.delete('1.0', tk.END)
                    self.feed_text.insert('end', "Error finding bets. Please try refreshing.", "center")
                    self.feed_text.config(state="disabled")
                    return
            
            self.progress_label.config(text=f"Finding users beating the SP...")
            current_date = datetime.now().strftime('%d/%m/%Y')
            cursor.execute("SELECT DISTINCT customer_ref FROM database WHERE date = ?", (current_date,))
            customer_refs = [row[0] for row in cursor.fetchall()]
            print(f"Customer refs: {customer_refs}")
                
            self.progress_label.config(text=f"Retrieving client wagers...")
            client_wagers = self.get_client_wagers(conn, customer_refs)
            self.progress_label.config(text=f"Getting Results...")
            data = self.get_results_json()
            self.progress_label.config(text=f"Comparing odds to SP...")
            results = self.compare_odds(client_wagers, data)
            print(f"Results: {results}")
    
            # Initialize new lists
            selection_to_users = defaultdict(list)
            users_without_risk_category = set()
            
            self.progress_label.config(text=f"Finding potential W users...")
            cursor.execute("SELECT * FROM database WHERE date = ?", (current_date,))
            database_data = cursor.fetchall()
    
            for bet in database_data:
                try:
                    wager_type = bet[5]
                    if wager_type == 'BET':
                        # Parse the selections from the JSON string stored in the database
                        details = json.loads(bet[10])
                        customer_reference = bet[3]
                        customer_risk_category = bet[4]
                    
                        for selection in details:
                            selection_name = selection[0]
                            odds = selection[1]
                    
                            if isinstance(odds, str):
                                if odds == 'SP':
                                    continue  
                                elif odds.lower() == 'evs':
                                    odds = 2.0  
                                else:
                                    odds = float(odds)  
                    
                            selection_to_users[selection_name].append((customer_reference, customer_risk_category))
                except Exception as e:
                    print(f"Error processing bet: {bet}, Error: {e}")
                            
            for selection, users in selection_to_users.items():
                users_with_risk_category = [user for user in users if user[1] and user[1] != '-']
                users_without_risk_category_for_selection = [user for user in users if not user[1] or user[1] == '-']
            
                if len(users_with_risk_category) / len(users) > 0.6:
                    users_without_risk_category.update(users_without_risk_category_for_selection)
            
            # Exclude VIP clients from users_without_risk_category
            users_without_risk_category = {user for user in users_without_risk_category if user[0] not in vip_clients}
            print(f"Users without risk category: {users_without_risk_category}")
    
            self.progress_label.config(text=f"---")
            self.report_button.config(state="normal")
    
            return results, users_without_risk_category
                    
        except Exception as e:
            print(f"An error occurred: {e}")
            return [], set()
        finally:
            if conn:
                conn.close()
    
    def update_traders_report(self):
        results, users_without_risk_category = self.create_traders_report()
        self.initialize_text_tags()
    
        separator = "-" * 69
    
        self.report_ticket.config(state='normal')
        self.report_ticket.delete('1.0', tk.END)
        self.report_ticket.insert(tk.END, "TRADERS SCREENER\n", 'center')
        self.report_ticket.insert(tk.END, f"{separator}\n")
        self.report_ticket.insert(tk.END, "Please do your own research before taking any action.\n\n")
    
        self.report_ticket.insert(tk.END, "- Users beating the SP -\n", 'center')
        self.report_ticket.insert(tk.END, "Users who have placed > 5 bets and > 50% of their selections beat the SP - Horses & Dogs.\n")
        self.report_ticket.insert(tk.END, f"For best results, run this function at the end of the day when all results are in.\n\n")
        if results:
            # Sort results by percentage_beaten in descending order
            sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
            for customer_ref, percentage_beaten, total_bets in sorted_results:
                self.report_ticket.insert(tk.END, f"{customer_ref}: ", 'bold')
                self.report_ticket.insert(tk.END, f"{total_bets} slns, {percentage_beaten:.2f}% beat the SP.\n")
        else:
            self.report_ticket.insert(tk.END, "No users currently significantly beating the SP. This could be because\n- Results not yet available\n- Users not meeting criteria (over 5 bets, over 50% selections beat SP)\n\n")            
    
        self.report_ticket.insert(tk.END, f"\n{separator}\n")
        self.report_ticket.insert(tk.END, "- Clients wagering on selections containing multiple risk users -\n", 'center')
        self.report_ticket.insert(tk.END, "Clients who have wagered on selections where > 60% of other bets are from risk users.\nThis excludes any user from our 'VIP' list.\n\n")
    
        users_without_risk_category_str = '  |  '.join(user[0] for user in users_without_risk_category)
        self.report_ticket.insert(tk.END, users_without_risk_category_str)
    
        self.report_ticket.config(state='disabled')

    def compare_odds(self, client_wagers, race_results):
        results = []
        for customer_ref, wagers in client_wagers.items():
            total_bets = 0
            bets_beaten = 0 

            for betID, selections in wagers:
                for selection in selections:
                    if len(selection) >= 2:
                        race_name = selection[0]
                        placed_odds = selection[1]
                        
                        if " - " not in race_name:
                            continue
                        
                        total_bets += 1
                        
                        race_name_parts = race_name.split(" - ")
                        race_time = race_name_parts[0].split(", ")[1]
                        selection_name = race_name_parts[1]
                        
                        for event in race_results:
                            for meeting in event['meetings']:
                                for race in meeting['events']:
                                    if race['status'] == 'Result':
                                        race_start_time = race['startDateTime'].split('T')[1][:5]
                                        race_full_name = f"{meeting['meetinName']}, {race_start_time}"
                                        
                                        if race_full_name.lower() == race_name_parts[0].lower():
                                            for race_selection in race['selections']:
                                                if meeting['sportCode'] == 'g':
                                                    trap_number = 'Trap ' + race_selection['runnerNumber']
                                                    
                                                    if trap_number.lower() == selection_name.lower():
                                                        last_price_fractional = race_selection['lastPrice']
                                                        last_price_decimal = self.fractional_to_decimal(last_price_fractional)
                                                        
                                                        if placed_odds == 'SP':
                                                            placed_odds = last_price_decimal
                                                        if placed_odds == 'evs':
                                                            placed_odds = 2.0
                                                        
                                                        if placed_odds > last_price_decimal:
                                                            bets_beaten += 1
                                                else:
                                                    if race_selection['name'].lower() == selection_name.lower():
                                                        last_price_fractional = race_selection['lastPrice']
                                                        last_price_decimal = self.fractional_to_decimal(last_price_fractional)
                                                        
                                                        if placed_odds == 'SP':
                                                            placed_odds = last_price_decimal
                                                        if placed_odds == 'evs':
                                                            placed_odds = 2.0
                                                        
                                                        if placed_odds > last_price_decimal:
                                                            bets_beaten += 1
            
            if total_bets > 5:
                percentage_beaten = (bets_beaten / total_bets) * 100
                if percentage_beaten >= 50.0:
                    results.append((customer_ref, percentage_beaten, total_bets))
        
        return results
    
    def get_results_json(self):
        url = os.getenv('RESULTS_API_URL')

        # Ensure the API URL is loaded correctly
        if not url:
            raise ValueError("RESULTS_API_URL environment variable is not set")

        response = requests.get(url)
        response.raise_for_status()  # Ensure we raise an error for bad responses
        data = response.json()
        return data
    
    def get_client_wagers(self, conn, customer_refs):
        current_date_str = datetime.now().strftime("%d/%m/%Y")
        cursor = conn.cursor()
        
        # Convert customer_refs to a tuple for use in SQL IN clause
        customer_refs_tuple = tuple(customer_refs)
        
        # Construct the SQL query with the appropriate number of placeholders
        placeholders = ','.join(['?'] * len(customer_refs_tuple))
        query = f"SELECT * FROM database WHERE customer_ref IN ({placeholders}) AND date = ?"
        
        # Execute the query with the customer_refs and current_date_str as parameters
        cursor.execute(query, (*customer_refs_tuple, current_date_str))
        wagers = cursor.fetchall()
        
        # Process the results
        client_wagers = defaultdict(list)
        for bet in wagers:
            if bet[5] == 'BET':
                betID = bet[0]
                customer_ref = bet[3]
                selections = json.loads(bet[10])
                client_wagers[customer_ref].append((betID, selections))
        
        return client_wagers

    def fractional_to_decimal(self, fractional_odds):
        if fractional_odds.lower() == 'evens':
            return 2.0
        numerator, denominator = map(int, fractional_odds.split('-'))
        return (numerator / denominator) + 1
    
    def factoring_sheet(self):
        try:
            self.factoring_tree.delete(*self.factoring_tree.get_children())
            spreadsheet = self.gc.open('Factoring Diary')
            worksheet = spreadsheet.get_worksheet(4)
            data = worksheet.get_all_values()
            self.last_refresh_label.config(text=f"Last Refresh:\n{datetime.now().strftime('%H:%M:%S')}")
            for row in data[2:][::-1]: 
                self.factoring_tree.insert("", "end", values=[row[5], row[0], row[1], row[2], row[3], row[4]])
        except Exception as e:
            print(f"Error in factoring_sheet: {e}")
    
    def freebet_sheet(self):
        try:
            current_month = datetime.now().strftime('%B')
            spreadsheet_name = 'Reporting ' + current_month
            self.freebet_tree.delete(*self.freebet_tree.get_children())
            spreadsheet = self.gc.open(spreadsheet_name)
            worksheet = spreadsheet.get_worksheet(5)
            data = worksheet.get_all_values()
            self.last_refresh_freebets_label.config(text=f"Last Refresh:\n{datetime.now().strftime('%H:%M:%S')}")
            for row in data[2:][::-1]:
                if row[2]: 
                    self.freebet_tree.insert("", "end", values=[row[1], row[3], row[4], row[5], row[10]])
        except Exception as e:
            print(f"Error in freebet_sheet: {e}")

    def popup_sheet(self):
        try:
            filter_id = 65
            custom_field_id = 'acb5651370e1c1efedd5209bda3ff5ceece09633'
            pipedrive_persons_api_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')

            # Ensure the API URL is loaded correctly
            if not pipedrive_persons_api_url:
                raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

            filter_url = f'{pipedrive_persons_api_url}?filter_id={filter_id}&api_token={self.pipedrive_api_token}'
            response = requests.get(filter_url)
            if response.status_code == 200:
                persons = response.json().get('data', [])
                user_data = [(person['c1f84d7067cae06931128f22af744701a07b29c6'], person.get(custom_field_id, 'N/A')) for person in persons]
                self.last_refresh_popup_label.config(text=f"Last Refresh:\n{datetime.now().strftime('%H:%M:%S')}")

                user_data.sort(key=lambda x: x[1], reverse=True)
                for username, compliance_date in user_data:
                    self.popup_tree.insert('', tk.END, values=(username, compliance_date))
        except Exception as e:
            print(f"Error in popup_sheet: {e}")

    def get_realtime_users(self):
        analytics = build('analyticsdata', 'v1beta', credentials=self.analytics_credentials)
        response = analytics.properties().runRealtimeReport(
            property='properties/409643682',  # Replace with your Google Analytics Property ID
            body=
                {
                "metrics": [
                    {
                    "name": "activeUsers"
                    }
                ],
                "minuteRanges": [
                    {
                    "startMinutesAgo": 5,
                    "endMinutesAgo": 0
                    }
                ]
                }
        ).execute()
        return response

    def update_live_users(self):
        try:
            response = self.get_realtime_users()
            active_users = response['rows'][0]['metricValues'][0]['value']
            self.root.after(0, self.update_live_users_label, active_users)
        except Exception as e:
            print(f"Failed to update live users: {e}")
            self.root.after(0, self.update_live_users_label, "---")

    def update_live_users_label(self, active_users):
        self.live_users_label.config(text=active_users)

    def live_users_loop(self):
        while True:
            self.update_live_users()
            time.sleep(20)

    def start_live_users_thread(self):
        threading.Thread(target=self.live_users_loop, daemon=True).start()

    def run_factoring_sheet_thread(self):
        self.factoring_thread = threading.Thread(target=self.factoring_sheet, daemon=True)
        self.factoring_thread.start()
    
    def run_freebet_sheet_thread(self):
        self.freebet_thread = threading.Thread(target=self.freebet_sheet, daemon=True)
        self.freebet_thread.start()

    def run_popup_sheet_thread(self):
        self.popup_thread = threading.Thread(target=self.popup_sheet, daemon=True)
        self.popup_thread.start()

class Settings:
    def __init__(self, root):
        self.root = root
        self.initialize_ui()
    
    def initialize_ui(self):        
        self.settings_frame = ttk.Frame(self.root, style='Card')
        self.settings_frame.place(x=714, y=655, width=180, height=265)

        logo_image = Image.open('src/splash.ico')
        logo_image = logo_image.resize((60, 60))
        self.company_logo = ImageTk.PhotoImage(logo_image)
        self.logo_label = ttk.Label(self.settings_frame, image=self.company_logo)
        self.logo_label.pack(pady=(10, 2))

        self.version_label = ttk.Label(self.settings_frame, text="v11.5", font=("Helvetica", 10))
        self.version_label.pack(pady=(0, 7))
        
        self.separator = ttk.Separator(self.settings_frame, orient='horizontal')
        self.separator.pack(fill='x', pady=5)

        self.current_user_label = ttk.Label(self.settings_frame, text="", font=("Helvetica", 10))
        self.current_user_label.pack()

        if user:
            self.current_user_label.config(text=f"Logged in as: {user}")

        self.separator = ttk.Separator(self.settings_frame, orient='horizontal')
        self.separator.pack(fill='x', pady=5)

        self.view_events_button = ttk.Button(self.settings_frame, text="Live Events", command=self.show_live_events, cursor="hand2", width=13)
        self.view_events_button.pack(pady=(20, 0))

        self.copy_frame = ttk.Frame(self.settings_frame)
        self.copy_frame.pack(pady=(15, 0))
        self.copy_button = ttk.Button(self.copy_frame, text="↻", command=self.copy_to_clipboard, cursor="hand2", width=2)
        self.copy_button.grid(row=0, column=0)
        self.password_result_label = ttk.Label(self.copy_frame, text="GB000000", font=("Helvetica", 10), wraplength=200)
        self.password_result_label.grid(row=0, column=1, padx=(5, 5))

    def fetch_and_save_events(self):
        url = os.getenv('ALL_EVENTS_API_URL')

        if not url:
            raise ValueError("ALL_EVENTS_API_URL environment variable is not set")

        try:
            response = requests.get(url)
            response.raise_for_status() 
            data = response.json()
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch events: {e}")
            return None

        if not data:
            messagebox.showerror("Error", "Couldn't get any events from API")
            return None

        filename = os.path.join(NETWORK_PATH_PREFIX, 'events.json')

        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing_data = json.load(f)
        else:
            messagebox.showerror("Error", "Events file not found.")
            return None

        existing_data_map = {event['EventName']: event for event in existing_data}

        for event in data:
            existing_event = existing_data_map.get(event['EventName'])
            if existing_event:
                event['lastUpdate'] = existing_event.get('lastUpdate', '-')
                event['user'] = existing_event.get('user', '-')
            else:
                event['lastUpdate'] = '-'
                event['user'] = '-'

        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)

        return data

    def show_live_events(self):
        data = self.fetch_and_save_events()
        filename = os.path.join(NETWORK_PATH_PREFIX, 'events.json')
        if data:
            sorted_data = self.sort_events(data)
            live_events_window = tk.Toplevel(self.root)
            live_events_window.geometry("650x700")
            live_events_window.title("Live Events")
            live_events_window.iconbitmap('src/splash.ico')
            screen_width = live_events_window.winfo_screenwidth()
            live_events_window.geometry(f"+{screen_width - 800}+50")
            live_events_window.resizable(False, False)
            live_events_frame = ttk.Frame(live_events_window)
            live_events_frame.pack(fill=tk.BOTH, expand=True)
            live_events_title = ttk.Label(live_events_frame, text="Live Events", font=("Helvetica", 12, "bold"))
            live_events_title.pack(pady=5)
            total_events_label = ttk.Label(live_events_frame, text=f"Total Events: {len(data)}")
            total_events_label.pack(pady=5)
            tree_frame = ttk.Frame(live_events_frame)
            tree_frame.pack(fill=tk.BOTH, expand=True)
            tree_scroll = ttk.Scrollbar(tree_frame)
            tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
            tree.pack(fill=tk.BOTH, expand=True)
            tree_scroll.config(command=tree.yview)
    
            tree["columns"] = ("EventCode", "numChildren", "EventDate", "lastUpdate", "user")
            tree.column("#0", width=200, minwidth=200)
            tree.column("EventCode", width=50, minwidth=50)
            tree.column("numChildren", width=50, minwidth=50)
            tree.column("EventDate", width=50, minwidth=50)
            tree.column("lastUpdate", width=120, minwidth=120)
            tree.column("user", width=10, minwidth=10)
            tree.heading("#0", text="Event Name", anchor=tk.W)
            tree.heading("EventCode", text="Event File", anchor=tk.W)
            tree.heading("numChildren", text="Markets", anchor=tk.W)
            tree.heading("EventDate", text="Event Date", anchor=tk.W)
            tree.heading("lastUpdate", text="Last Update", anchor=tk.W)
            tree.heading("user", text="User", anchor=tk.W)
    
            self.populate_tree(tree, sorted_data)
    
            def on_button_click():
                global user
                selected_items = tree.selection()
                for item_id in selected_items:
                    item = tree.item(item_id)
                    event_name = item['text']
                    for event in data:
                        if event['EventName'] == event_name:
                            markets = len(event["Meetings"])
                            original_last_update = event.get('lastUpdate', None)
                            if original_last_update and original_last_update != '-':
                                try:
                                    original_last_update = datetime.strptime(original_last_update, '%d-%m-%Y %H:%M:%S')
                                except ValueError:
                                    original_last_update = None
                            else:
                                original_last_update = None
                            event['lastUpdate'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                            event['user'] = user
                            if event['Meetings'][0]['EventCode'][3:5].lower() == 'ap':
                                antepost = True
                            else:
                                antepost = False
                            threading.Thread(target=self.log_update, args=(event_name, markets, antepost, original_last_update, user), daemon=True).start()
                            break
            
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=4)
            
                self.populate_tree(tree, data)
    
            action_button = ttk.Button(live_events_frame, text="Update Event", command=on_button_click)
            action_button.pack(pady=10)
            update_events_label = ttk.Label(live_events_frame, text="Select an event (or multiple) and click 'Update Event' to log latest refresh.", wraplength=600)
            update_events_label.pack(pady=5)

        else:
            messagebox.showerror("Error", "Failed to fetch events. Please tell Sam.")

    def log_update(self, event_name, markets, antepost, last_update_time, user):

        if last_update_time:
            log_time = last_update_time.strftime('%H:%M')
        else:
            log_time = datetime.now().strftime('%H:%M')
        event_name = event_name.replace("-", "")
        now = datetime.now()
        date_string = now.strftime('%d-%m-%Y')
        
        big_events = ['Flat Racing Futures', 'National Hunt Futures', 'Cheltenham Festival Futures', 'International Racing Futures', 'Greyhound Futures', 'Football Futures', 'Tennis Futures', 'Golf Futures']
    
        log_file = os.path.join(NETWORK_PATH_PREFIX, f'logs/updatelogs/update_log_{date_string}.txt')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    data = f.readlines()
            except IOError as e:
                print(f"Error reading log file: {e}")
                data = []
        else:
            data = []
    
        if last_update_time:
            time_diff = now - last_update_time
            hours_diff = time_diff.total_seconds() / 3600
        else:
            hours_diff = float('inf') 
    
        if antepost:
            score = round(0.3 * markets, 2)
            if event_name in big_events:
                score += 3
            elif event_name == 'MMA Futures' or event_name == 'Boxing Futures' or event_name == 'Mma Futures':
                score = round(0.08 * markets, 2)
            else:
                score += 1
        else:
            score = round(0.2 * markets, 2)
    
        if hours_diff < 4:
            score *= 0.4
    
        update = f"{log_time} - {user} - {score}\n"
    
        log_notification(f"{user} updated {event_name} ({score:.2f})")
    
        course_index = None
        for i, line in enumerate(data):
            if line.strip() == event_name + ":":
                course_index = i
                break
    
        if course_index is not None:
            data.insert(course_index + 1, update)
        else:
            data.append(f"\n{event_name}:\n")
            data.append(update)
    
        try:
            with open(log_file, 'w') as f:
                f.writelines(data)
        except IOError as e:
            print(f"Error writing to log file: {e}")

    def populate_tree(self, tree, data):
        # Clear existing tree items
        for item in tree.get_children():
            tree.delete(item)
    
        sorted_data = self.sort_events(data)
    
        # Define tags for outdated events and separators
        tree.tag_configure('outdated', background='lightcoral')
        tree.tag_configure('separator', background='lightblue')
    
        # Separate antepost and non-antepost events
        antepost_events = [event for event in sorted_data if len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() == 'ap']
        non_antepost_events = [event for event in sorted_data if not (len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() == 'ap')]
    
        # Insert separator for antepost events
        tree.insert("", "end", text="-- Antepost --", values=("", "", "", "", ""), tags=('separator',))
    
        # Insert antepost events
        for event in antepost_events:
            event_name = event["EventName"]
            event_file = event["Meetings"][0]["EventCode"] if event["Meetings"] else ""
            num_children = len(event["Meetings"])
            last_update = event.get("lastUpdate", "-")
            user = event.get("user", "-")
    
            # Check if the last update is more than two days old for antepost events
            if last_update != "-" and (datetime.now() - datetime.strptime(last_update, '%d-%m-%Y %H:%M:%S')).days > 2:
                tag = 'outdated'
            else:
                tag = ''
    
            parent_id = tree.insert("", "end", text=event_name, values=(event_file, num_children, "", last_update, user), tags=(tag,))
            for meeting in event["Meetings"]:
                meeting_name = meeting["EventName"]
                event_date = meeting["EventDate"]
                tree.insert(parent_id, "end", text=meeting_name, values=("", "", event_date, "", ""))
    
        # Insert separator for non-antepost events
        tree.insert("", "end", text="-- Non-Antepost --", values=("", "", "", "", ""), tags=('separator',))
    
        # Insert non-antepost events
        for event in non_antepost_events:
            event_name = event["EventName"]
            event_file = event["Meetings"][0]["EventCode"] if event["Meetings"] else ""
            num_children = len(event["Meetings"])
            last_update = event.get("lastUpdate", "-")
            user = event.get("user", "-")
    
            # Check if the last update is more than one day old for non-antepost events
            if last_update != "-" and (datetime.now() - datetime.strptime(last_update, '%d-%m-%Y %H:%M:%S')).days > 1:
                tag = 'outdated'
            else:
                tag = ''
    
            parent_id = tree.insert("", "end", text=event_name, values=(event_file, num_children, "", last_update, user), tags=(tag,))
            for meeting in event["Meetings"]:
                meeting_name = meeting["EventName"]
                event_date = meeting["EventDate"]
                tree.insert(parent_id, "end", text=meeting_name, values=("", "", event_date, "", ""))

    def sort_events(self, data):
        antepost_events = [event for event in data if len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() == 'ap']
        non_antepost_events = [event for event in data if not (len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() == 'ap')]
        return antepost_events + non_antepost_events
    
    def generate_random_string(self):
        random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        generated_string = 'GB' + random_numbers
        
        return generated_string

    def copy_to_clipboard(self):
        self.generated_string = self.generate_random_string()
        
        pyperclip.copy(self.generated_string)
        
        self.password_result_label.config(text=f"{self.generated_string}")
        self.copy_button.config(state=tk.NORMAL)

class Next3Panel:
    def __init__(self, root):
        self.root = root
        self.last_click_time = 0 
        _, _, _, reporting_data = access_data()
        self.enhanced_places = reporting_data.get('enhanced_places', [])

        # Load API URLs from environment variables
        self.horse_url = os.getenv('NEXT_3_HORSE_API_URL')
        self.dogs_url = os.getenv('NEXT_3_DOGS_API_URL')

        # Ensure the API URLs are loaded correctly
        if not self.horse_url:
            raise ValueError("NEXT_3_HORSE_API_URL environment variable is not set")
        if not self.dogs_url:
            raise ValueError("NEXT_3_DOGS_API_URL environment variable is not set")

        self.initialize_ui()
        self.run_display_next_3()
    
    def run_display_next_3(self):
        threading.Thread(target=self.display_next_3, daemon=True).start()
        self.root.after(10000, self.run_display_next_3)
    
    def initialize_ui(self):
        next_races_frame = ttk.Frame(self.root)
        next_races_frame.place(x=5, y=925, width=890, height=55)

        horses_frame = ttk.Frame(next_races_frame, style='Card')
        horses_frame.place(relx=0, rely=0.05, relwidth=0.50, relheight=0.9)

        self.horse_labels = [ttk.Label(horses_frame, justify='center', font=("Helvetica", 8, "bold")) for _ in range(3)]
        for i, label in enumerate(self.horse_labels):
            label.grid(row=0, column=i, padx=0, pady=5)
            horses_frame.columnconfigure(i, weight=1)

        greyhounds_frame = ttk.Frame(next_races_frame, style='Card')
        greyhounds_frame.place(relx=0.51, rely=0.05, relwidth=0.49, relheight=0.9)

        self.greyhound_labels = [ttk.Label(greyhounds_frame, justify='center', font=("Helvetica", 8, "bold")) for _ in range(3)]
        for i, label in enumerate(self.greyhound_labels):
            label.grid(row=0, column=i, padx=0, pady=5)
            greyhounds_frame.columnconfigure(i, weight=1)
    
    def process_data(self, data, labels_type):
        labels = self.horse_labels if labels_type == 'horse' else self.greyhound_labels
        for i, event in enumerate(data[:3]):
            meeting_name = event.get('meetingName', '')
            status = event.get('status', '')
            hour = str(event.get('hour', ''))
            ptype = event.get('pType', '')
            minute = str(event.get('minute', '')).zfill(2) 
            time = f"{hour}:{minute}"
            
            if len(meeting_name) > 14:
                meeting_name = meeting_name[:14] + "'"

            if not status:
                status = '-'
            if ptype == 'Board Price':
                ptype = 'BP'
            elif ptype == 'Early Price':
                ptype = 'EP'
            elif ptype == 'S.P. Only':
                ptype = 'SP'
            else:
                ptype = '-'

            race = f"{meeting_name}, {time}"

            if race in self.enhanced_places:
                labels[i].config(foreground='#ff00e6')
            else:
                labels[i].config(foreground='black')

            labels[i].config(text=f"{race} ({ptype})\n{status}")

    def display_next_3(self):
        headers = {"User-Agent": "Mozilla/5.0 ..."}
        horse_response = requests.get(self.horse_url, headers=headers)
        greyhound_response = requests.get(self.dogs_url, headers=headers)

        if horse_response.status_code == 200 and greyhound_response.status_code == 200:
            horse_data = horse_response.json()
            greyhound_data = greyhound_response.json()

            self.root.after(0, self.process_data, horse_data, 'horse')
            self.root.after(0, self.process_data, greyhound_data, 'greyhound')
        else:
            print("Error: The response from the API is not OK.")

class ClientWizard:
    def __init__(self, root, default_tab="Factoring"):
        print(default_tab)
        self.root = root
        self.default_tab = default_tab
        self.toplevel = tk.Toplevel(self.root)
        self.toplevel.title("Client Reporting and Modifications")
        self.toplevel.geometry("600x300")
        self.toplevel.iconbitmap('src/splash.ico')
        screen_width = self.toplevel.winfo_screenwidth()
        self.toplevel.geometry(f"+{screen_width - 1700}+700")
        self.username_entry = None

        # Load environment variables
        self.pipedrive_api_token = os.getenv('PIPEDRIVE_API_KEY')
        self.pipedrive_api_url = os.getenv('PIPEDRIVE_API_URL')

        # Ensure the API URL is loaded correctly
        if not self.pipedrive_api_url:
            raise ValueError("PIPEDRIVE_API_URL environment variable is not set")

        self.pipedrive_api_url = f'{self.pipedrive_api_url}?api_token={self.pipedrive_api_token}'

        # Load Google service account credentials from environment variables
        google_creds = {
            "type": os.getenv('GOOGLE_SERVICE_ACCOUNT_TYPE'),
            "project_id": os.getenv('GOOGLE_PROJECT_ID'),
            "private_key_id": os.getenv('GOOGLE_PRIVATE_KEY_ID'),
            "private_key": os.getenv('GOOGLE_PRIVATE_KEY').replace('\\n', '\n'),
            "client_email": os.getenv('GOOGLE_CLIENT_EMAIL'),
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "auth_uri": os.getenv('GOOGLE_AUTH_URI'),
            "token_uri": os.getenv('GOOGLE_TOKEN_URI'),
            "auth_provider_x509_cert_url": os.getenv('GOOGLE_AUTH_PROVIDER_X509_CERT_URL'),
            "client_x509_cert_url": os.getenv('GOOGLE_CLIENT_X509_CERT_URL')
        }
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        self.gc = gspread.authorize(credentials)

        # Initialize UI components
        self.initialize_ui()

    def initialize_ui(self):
        self.wizard_frame = ttk.Frame(self.toplevel, style='Card')
        self.wizard_frame.place(x=5, y=5, width=590, height=290)

        self.wizard_notebook = ttk.Notebook(self.wizard_frame)
        self.wizard_notebook.pack(fill='both', expand=True)

        self.report_freebet_tab = self.apply_freebet_tab()
        self.rg_popup_tab = self.apply_rg_popup()
        self.closure_requests_tab = self.apply_closure_requests()
        self.add_factoring_tab = self.apply_factoring_tab()

        self.wizard_notebook.add(self.report_freebet_tab, text="Report Freebet")
        self.wizard_notebook.add(self.rg_popup_tab, text="RG Popup")
        self.wizard_notebook.add(self.add_factoring_tab, text="Apply Factoring")
        self.wizard_notebook.add(self.closure_requests_tab, text="Closure Requests")
        self.select_default_tab()

    def select_default_tab(self):
        tab_mapping = {
            "Freebet": 1,
            "Popup": 0,
            "Factoring": 2,
            "Closure": 3
        }
        
        tab_index = tab_mapping.get(self.default_tab, 0)
        print(tab_index)
        self.wizard_notebook.select(tab_index)

    def apply_rg_popup(self):
        custom_field_id = 'acb5651370e1c1efedd5209bda3ff5ceece09633'  # Your custom field ID

        def handle_submit():
            submit_button.config(state=tk.DISABLED)

            if not entry1.get():
                progress_note.config(text="Error: Please make sure all fields are completed.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            username = entry1.get().strip()

            search_url = os.getenv('PIPEDRIVE_PERSONS_SEARCH_API_URL')
            if not search_url:
                raise ValueError("PIPEDRIVE_PERSONS_SEARCH_API_URL environment variable is not set")

            update_base_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')
            if not update_base_url:
                raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

            params = {
                'term': username,
                'item_types': 'person',
                'fields': 'custom_fields',
                'exact_match': 'true',
                'api_token': self.pipedrive_api_token
            }

            response = requests.get(search_url, params=params)
            if response.status_code == 200:
                persons = response.json().get('data', {}).get('items', [])

                if not persons:
                    progress_note.config(text=f"No persons found for username: {username} in Pipedrive.", anchor='center', justify='center')
                    time.sleep(2)
                    submit_button.config(state=tk.NORMAL)
                    progress_note.config(text="---", anchor='center', justify='center')
                    return

                for person in persons:
                    person_id = person['item']['id']
                    update_url = f'{update_base_url}/{person_id}?api_token={self.pipedrive_api_token}'
                    update_data = {
                        custom_field_id: date.today().strftime('%m/%d/%Y')
                    }
                    update_response = requests.put(update_url, json=update_data)
                    if update_response.status_code == 200:
                        log_notification(f"{user} applied RG Popup to {username.upper()}", True)
                        progress_note.config(text=f"Successfully updated {username} in Pipedrive.", anchor='center', justify='center')
                        time.sleep(2)
                        submit_button.config(state=tk.NORMAL)
                        entry1.delete(0, tk.END)
                        progress_note.config(text="---", anchor='center', justify='center')
                        return
                    else:
                        messagebox.showerror("Error", f"Error updating person {person_id}: {update_response.status_code}")
                        progress_note.config(text=f"Error updating {username} in Pipedrive.", anchor='center', justify='center')
                        time.sleep(2)
                        submit_button.config(state=tk.NORMAL)
                        progress_note.config(text="---", anchor='center', justify='center')
                        return
            else:
                print(f'Error: {response.status_code}')
                progress_note.config(text=f"An error occurred.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            # Re-enable the submit button
            submit_button.config(state=tk.NORMAL)

        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height

        # Left section
        left_frame = ttk.Frame(frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_rowconfigure(2, weight=1)  # Ensure the left frame takes up the entire height

        username_label = ttk.Label(left_frame, text="Client Username")
        username_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry1 = ttk.Entry(left_frame)
        entry1.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        submit_button = ttk.Button(left_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2", width=40)
        submit_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        tree_title = ttk.Label(right_frame, text="RG Popup", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        tree_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        tree_description = ttk.Label(right_frame, text="Apply a Responsible Gambling Questionnaire on users next login.", wraplength=200, anchor='center', justify='center')
        tree_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        progress_note.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Add the new tab to the notebook
        self.wizard_notebook.add(frame, text="RG Popup")

        return frame

    def apply_factoring_tab(self):
        def handle_submit():
            global user
            if not user:
                user_login()

            submit_button.config(state=tk.DISABLED)
            current_time = datetime.now().strftime("%H:%M:%S")
            current_date = datetime.now().strftime("%d/%m/%Y")

            if not entry1.get() or not entry3.get():
                progress_note.config(text="Error: Please make sure all fields are completed.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            try:
                float(entry3.get())
            except ValueError:
                progress_note.config(text="Error: Assessment rating should be a number.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            params = {
                'term': entry1.get(),
                'item_types': 'person',
                'fields': 'custom_fields',
                'exact_match': 'true',
                'api_token': self.pipedrive_api_token
            }

            copy_string = ""
            if entry2.get() in ["W - WATCHLIST", "M - BP ONLY NO OFFERS", "C - MAX £100 STAKE"]:
                copy_string = f"{current_date} - {entry2.get().split(' - ')[1]} {user}"
            pyperclip.copy(copy_string)

            progress_note.config(text="Applying to User on Pipedrive...\n\n", anchor='center', justify='center')
            response = requests.get(self.pipedrive_api_url, params=params)
            if response.status_code == 200:
                persons = response.json()['data']['items']
                if not persons:
                    progress_note.config(text=f"Error: No persons found in pipedrive for username: {entry1.get()}", anchor='center', justify='center')
                    time.sleep(2)
                    submit_button.config(state=tk.NORMAL)
                    progress_note.config(text="---", anchor='center', justify='center')
                    return

                for person in persons:
                    person_id = person['item']['id']

                    update_base_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')
                    if not update_base_url:
                        raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

                    update_url = f'{update_base_url}/{person_id}?api_token={self.pipedrive_api_token}'
                    update_data = {
                        'ab6b3b25303ffd7c12940b72125487171b555223': entry2.get()
                    }
                    update_response = requests.put(update_url, json=update_data)

                    if update_response.status_code == 200:
                        print(f'Successfully updated person {person_id}')
                    else:
                        print(f'Error updating person {person_id}: {update_response.status_code}')
            else:
                print(f'Error: {response.status_code}')
                progress_note.config(text=f"Error: {response.status_code}", anchor='center', justify='center')
                time.sleep(1)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')

            progress_note.config(text="Factoring Applied on Pipedrive.\nReporting on Factoring Log...\n", anchor='center', justify='center')

            spreadsheet = self.gc.open('Factoring Diary')
            worksheet = spreadsheet.get_worksheet(4)
            
            progress_note.config(text="Adding entry to Factoring Log...\n\n", anchor='center', justify='center')

            next_row = len(worksheet.col_values(1)) + 1
            entry2_value = entry2.get().split(' - ')[0]
            worksheet.update_cell(next_row, 1, current_time)
            worksheet.update_cell(next_row, 2, entry1.get().upper())
            worksheet.update_cell(next_row, 3, entry2_value)
            worksheet.update_cell(next_row, 4, entry3.get())
            worksheet.update_cell(next_row, 5, user) 
            worksheet.update_cell(next_row, 6, current_date)

            worksheet3 = spreadsheet.get_worksheet(3)
            username = entry1.get().upper()
            progress_note.config(text="Trying to find user in Factoring Diary...\n\n", anchor='center', justify='center')
            matching_cells = worksheet3.findall(username, in_column=2)

            if not matching_cells:
                progress_note.config(text=f"Error: No persons found in factoring diary for client: {username}. Factoring logged, but not updated in diary.", anchor='center', justify='center')
                time.sleep(1)
            else:
                progress_note.config(text="Found user in factoring Diary.\nUpdating...\n", anchor='center', justify='center')
                cell = matching_cells[0]
                row = cell.row
                worksheet3.update_cell(row, 9, entry2_value)  # Column I
                worksheet3.update_cell(row, 10, entry3.get())  # Column J
                worksheet3.update_cell(row, 12, current_date)  # Column L

            data = {
                'Time': current_time,
                'Username': entry1.get().upper(),
                'Risk Category': entry2_value,
                'Assessment Rating': entry3.get(),
                'Staff': user
            }
            with open(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs', 'factoring.json'), 'a') as file:
                file.write(json.dumps(data) + '\n')

            progress_note.config(text="Factoring Added Successfully.\n\n", anchor='center', justify='center')
            log_notification(f"{user} Factored {entry1.get().upper()} - {entry2_value} - {entry3.get()}")
            time.sleep(1)
            submit_button.config(state=tk.NORMAL)
                
            # Clear the fields after successful submission
            entry1.delete(0, tk.END)
            entry2.set(options[0])
            entry3.delete(0, tk.END)

            progress_note.config(text="---", anchor='center', justify='center')

        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height

        # Left section
        left_frame = ttk.Frame(frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_rowconfigure(3, weight=1)  # Ensure the left frame takes up the entire height

        username_label = ttk.Label(left_frame, text="Client Username")
        username_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry1 = ttk.Entry(left_frame)
        entry1.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        riskcat_label = ttk.Label(left_frame, text="Risk Category")
        riskcat_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        options = ["", "W - WATCHLIST", "M - BP ONLY NO OFFERS", "C - MAX £100 STAKE"]
        entry2 = ttk.Combobox(left_frame, values=options, state="readonly")
        entry2.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        entry2.set(options[0])

        ass_rating_label = ttk.Label(left_frame, text="Assessment Rating")
        ass_rating_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        entry3 = ttk.Entry(left_frame)
        entry3.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        submit_button = ttk.Button(left_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2", width=40)
        submit_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        report_freebet_title = ttk.Label(right_frame, text="Modify Client Terms", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        report_freebet_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        tree_description = ttk.Label(right_frame, text="Apply factoring and report new assessment ratings for clients.", wraplength=200, anchor='center', justify='center')
        tree_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        progress_note.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        return frame

    def apply_freebet_tab(self):
        current_month = datetime.now().strftime('%B')
        global user
        if not user:
            user_login()
    
        def handle_submit():
            # Disable the submit button while processing
            submit_button.config(state=tk.DISABLED)
    
            if not entry1.get() or not entry2.get() or not entry3.get():
                progress_note.config(text="Error: Please make sure all fields are completed.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return
            
            try:
                float(entry3.get())
            except ValueError:
                progress_note.config(text="Error: Freebet amount should be a number.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return
    
            progress_note.config(text="Finding Reporting Sheet", anchor='center', justify='center')
    
            spreadsheet_name = 'Reporting ' + current_month
            try:
                spreadsheet = self.gc.open(spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                progress_note.config(text=f"Error: {spreadsheet_name} not found.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return
    
            progress_note.config(text=f"Found {spreadsheet_name}.\nFree bet for {entry1.get().upper()} being added.\n", anchor='center', justify='center')
    
            worksheet = spreadsheet.get_worksheet(5)
            next_row = len(worksheet.col_values(2)) + 1
    
            current_date = datetime.now().strftime("%d/%m/%Y")  
            current_time = datetime.now().strftime("%H:%M:%S")
            worksheet.update_cell(next_row, 2, current_date)
            worksheet.update_cell(next_row, 3, entry2.get().upper())
            worksheet.update_cell(next_row, 4, current_time)
            worksheet.update_cell(next_row, 5, entry1.get().upper())
            worksheet.update_cell(next_row, 6, entry3.get())
            worksheet.update_cell(next_row, 11, user)
    
            progress_note.config(text=f"Free bet for {entry1.get().upper()} added successfully to reporting {current_month}\n", anchor='center', justify='center')
            log_notification(f"{user} applied £{entry3.get()} {entry2.get().capitalize()} to {entry1.get().upper()}")
    
            # Clear the fields after successful submission
            entry1.delete(0, tk.END)
            entry2.set(options[0])
            entry3.delete(0, tk.END)

            time.sleep(2)
            progress_note.config(text="---", anchor='center', justify='center')
            submit_button.config(state=tk.NORMAL)
    
        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height

        # Left section
        left_frame = ttk.Frame(frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_rowconfigure(3, weight=1)  # Ensure the left frame takes up the entire height

        username = ttk.Label(left_frame, text="Client Username")
        username.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry1 = ttk.Entry(left_frame)
        entry1.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
        type = ttk.Label(left_frame, text="Free bet Type")
        type.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        options = ["", "FREE BET", "DEPOSIT BONUS", "10MIN BLAST", "OTHER"]
        entry2 = ttk.Combobox(left_frame, values=options, state="readonly")
        entry2.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        entry2.set(options[0])
    
        amount = ttk.Label(left_frame, text="Amount")
        amount.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        entry3 = ttk.Entry(left_frame)
        entry3.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    
        submit_button = ttk.Button(left_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2", width=40)    
        submit_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    
        report_freebet_title = ttk.Label(right_frame, text="Report a Free Bet", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        report_freebet_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        report_freebet_description = ttk.Label(right_frame, text="Enter the client username, free bet type, and amount to report a free bet.", wraplength=200, anchor='center', justify='center')
        report_freebet_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        progress_note.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        return frame
    
    def apply_closure_requests(self):
        restriction_mapping = {
            'Further Options': 'Self Exclusion'
        }
    
        def load_data():
            with open(os.path.join(NETWORK_PATH_PREFIX, 'src', 'data.json'), 'r') as f:
                return json.load(f)
    
        def save_data(data):
            with open(os.path.join(NETWORK_PATH_PREFIX, 'src', 'data.json'), 'w') as f:
                json.dump(data, f, indent=4)
    
        def handle_request(request):
            # Clear the left_frame
            for widget in self.left_frame.winfo_children():
                widget.destroy()
    
            log_notification(f"{user} Handling {request['Restriction']} request for {request['Username']} ")
    
            request['Restriction'] = restriction_mapping.get(request['Restriction'], request['Restriction'])
    
            current_date = datetime.now()
    
            length_mapping = {
                'One Day': timedelta(days=1),
                'One Week': timedelta(weeks=1),
                'Two Weeks': timedelta(weeks=2),
                'Four Weeks': timedelta(weeks=4),
                'Six Weeks': timedelta(weeks=6),
                'Six Months': relativedelta(months=6),
                'One Year': relativedelta(years=1),
                'Two Years': relativedelta(years=2),
                'Three Years': relativedelta(years=3),
                'Four Years': relativedelta(years=4),
                'Five Years': relativedelta(years=5),
            }
    
            length_in_time = length_mapping.get(request['Length'], timedelta(days=0))
    
            reopen_date = current_date + length_in_time
    
            copy_string = f"{request['Restriction']}"
    
            if request['Length'] not in [None, 'None', 'Null']:
                copy_string += f" {request['Length']}"
    
            copy_string += f" {current_date.strftime('%d/%m/%Y')}"
            copy_string = copy_string.upper()
    
            if request['Restriction'] in ['Take-A-Break', 'Self Exclusion']:
                copy_string += f" (CAN REOPEN {reopen_date.strftime('%d/%m/%Y')})"
    
            copy_string += f" {user}"
    
            pyperclip.copy(copy_string)
    
            def handle_submit():
                username = self.username_entry.get()  # Capture the username before destroying the widgets
    
                for widget in self.left_frame.winfo_children():
                    widget.destroy()
    
                if self.confirm_betty_update_bool.get():
                    try:
                        if self.send_confirmation_email_bool.get():
                            threading.Thread(target=self.send_email, args=(username, request['Restriction'], request['Length'])).start()
                            print(f"Email sent to {username} for {request['Restriction']} request.")
                    except Exception as e:
                        print(f"Error sending email: {e}")
                        # self.progress_note.config(text="Error sending email.", anchor='center', justify='center')
    
                    try:
                        threading.Thread(target=self.report_closure_requests, args=(request['Restriction'], username, request['Length'])).start()
                        print(f"Reported {request['Restriction']} request for {username}.")
                    except Exception as e:
                        print(f"Error reporting closure requests: {e}")
                        self.progress_note.config(text="Error reporting closure requests.", anchor='center', justify='center')

                    request['completed'] = True
    
                    data = load_data()
                    for req in data.get('closures', []):
                        if req['Username'] == request['Username']:
                            req['completed'] = True
                            print(f"Marked {request['Restriction']} request for {username} as completed.")
                            break
                    save_data(data)
    
                    if request['completed']:
                        refresh_closure_requests()
                        self.progress_note.config(text=f"{request['Restriction']} request for {username} has been processed.", anchor='center', justify='center')
    
                else:
                    # messagebox.showerror("Error", "Please confirm that the client has been updated in Betty.")
                    self.progress_note.config(text="Please confirm that the client has been updated in Betty.", anchor='center', justify='center')
                    refresh_closure_requests()
    
            # Editable username entry
            ttk.Label(self.left_frame, text="Client Username").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.username_entry = ttk.Entry(self.left_frame, width=13)
            self.username_entry.insert(0, request['Username'])
            self.username_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
            ttk.Label(self.left_frame, text=f"Restriction: {request['Restriction']}").grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")
            ttk.Label(self.left_frame, text=f"Length: {request['Length'] if request['Length'] not in [None, 'Null'] else '-'}").grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    
            confirm_betty_update = ttk.Checkbutton(self.left_frame, text='Confirm Closed on Betty', variable=self.confirm_betty_update_bool, onvalue=True, offvalue=False, cursor="hand2")
            confirm_betty_update.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    
            send_confirmation_email = ttk.Checkbutton(self.left_frame, text='Send Pipedrive Confirmation Email', variable=self.send_confirmation_email_bool, onvalue=True, offvalue=False, cursor="hand2")
            send_confirmation_email.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    
            submit_button = ttk.Button(self.left_frame, text="Submit", command=handle_submit, cursor="hand2", width=33)
            submit_button.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        def refresh_closure_requests():
            for widget in self.left_frame.winfo_children():
                widget.destroy()
    
            data = load_data()
            requests = [request for request in data.get('closures', []) if not request.get('completed', False)]
            if not requests:
                ttk.Label(self.left_frame, text="No exclusion/deactivation requests.", anchor='center', justify='center', width=34).grid(row=0, column=1, padx=10, pady=2)
    
            for i, request in enumerate(requests):
                restriction = restriction_mapping.get(request['type'], request['type'])
    
                length = request['period'] if request['period'] not in [None, 'Null'] else ''
    
                tick_button = ttk.Button(self.left_frame, text="✔", command=lambda request=request: handle_request(request), width=2, cursor="hand2")
                tick_button.grid(row=i, column=0, padx=3, pady=2)
    
                request_label = ttk.Label(self.left_frame, text=f"{restriction} | {request['username']} | {length}")
                request_label.grid(row=i, column=1, padx=10, pady=2, sticky="w")
    
        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height
    
        # Left section
        self.left_frame = ttk.Frame(frame)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.left_frame.grid_rowconfigure(3, weight=1)  # Ensure the left frame takes up the entire height
    
        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    
        closure_requests_title = ttk.Label(right_frame, text="Closure Requests", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        closure_requests_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        closure_requests_description = ttk.Label(right_frame, text="Deactivation, Take-a-Break and Self Exclusion requests will appear here, ready for processing.", wraplength=200, anchor='center', justify='center')
        closure_requests_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        self.progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        self.progress_note.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        refresh_closure_requests()
    
        return frame

    def update_person(self, update_url, update_data, person_id):
        update_response = requests.put(update_url, json=update_data)
        if update_response.status_code == 200:
            print(f'Successfully updated person {person_id}')
            self.progress_note.config(text=f"Successfully updated in Pipedrive, email confirmation will be sent.", anchor='center', justify='center')
            time.sleep(2)
            self.progress_note.config(text="---", anchor='center', justify='center')
        else:
            print(f'Error updating person {person_id}: {update_response.status_code}')
            self.progress_note.config(text=f"Error updating in Pipedrive. Please send confirmation email manually.", anchor='center', justify='center')
            time.sleep(2)
            self.progress_note.config(text="---", anchor='center', justify='center')

    def send_email(self, username, restriction, length):
        params = {
            'term': username,
            'item_types': 'person',
            'fields': 'custom_fields',
            'exact_match': 'true',
            'api_token': self.pipedrive_api_token
        }

        try:
            response = requests.get(self.pipedrive_api_url, params=params)
            response.raise_for_status()
            print(response.status_code)
        except requests.exceptions.HTTPError as errh:
            print("Http Error:", errh)
            return
        except requests.exceptions.ConnectionError as errc:
            print("Error Connecting:", errc)
            return
        except requests.exceptions.Timeout as errt:
            print("Timeout Error:", errt)
            return
        except requests.exceptions.RequestException as err:
            print("Something went wrong", err)
            return

        persons = response.json()['data']['items']
        if not persons:
            self.progress_note.config(text=f"No persons found in Pipedrive for username: {username}. Please make sure the username is correct.", anchor='center', justify='center')
            time.sleep(2)
            self.progress_note.config(text="---", anchor='center', justify='center')
            return

        number_mapping = {
            'One': '1',
            'Two': '2',
            'Three': '3',
            'Four': '4',
            'Five': '5',
            'Six': '6',
            'Seven': '7',
            'Eight': '8',
            'Nine': '9',
            'Ten': '10'
        }

        update_base_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')
        if not update_base_url:
            raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

        for person in persons:
            person_id = person['item']['id']
            update_url = f'{update_base_url}/{person_id}?api_token={self.pipedrive_api_token}'

            if restriction == 'Account Deactivation':
                update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': "Deactivated"}
                self.update_person(update_url, update_data, person_id)

            elif restriction == 'Self Exclusion':
                if length.split()[0] in number_mapping:
                    digit_length = length.replace(length.split()[0], number_mapping[length.split()[0]])
                    update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'SE {digit_length}'}
                    self.update_person(update_url, update_data, person_id)
                else:
                    print("Error: Invalid length")
                    messagebox.showerror("Error", "Unknown error. Please tell Sam.")

            elif restriction == 'Take-A-Break':
                if length.split()[0] in number_mapping:
                    digit_length = length.replace(length.split()[0], number_mapping[length.split()[0]])
                    update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'TAB {digit_length}'}
                    self.update_person(update_url, update_data, person_id)
                else:
                    print("Error: Invalid length")
                    messagebox.showerror("Error", "Unknown error. Please tell Sam.")
        
    def report_closure_requests(self, restriction, username, length):
        current_date = datetime.now().strftime("%d/%m/%Y")  
        try:
            spreadsheet = self.gc.open("Management Tool")
        except gspread.SpreadsheetNotFound:
            return

        print(restriction, username, length)
        if restriction == 'Account Deactivation':
            worksheet = spreadsheet.get_worksheet(18)
            next_row = len(worksheet.col_values(1)) + 1
            worksheet.update_cell(next_row, 2, username.upper())
            worksheet.update_cell(next_row, 1, current_date)

        elif restriction == 'Take-A-Break':
            worksheet = spreadsheet.get_worksheet(19)
            next_row = len(worksheet.col_values(1)) + 1
            worksheet.update_cell(next_row, 2, username.upper())
            worksheet.update_cell(next_row, 1, current_date)
            worksheet.update_cell(next_row, 3, length.upper())

        elif restriction == 'Self Exclusion':
            worksheet = spreadsheet.get_worksheet(20)
            next_row = len(worksheet.col_values(1)) + 1
            worksheet.update_cell(next_row, 2, username.upper())
            worksheet.update_cell(next_row, 1, current_date)
            worksheet.update_cell(next_row, 3, length)      

        else:
            print("Error: Invalid restriction")
            messagebox.showerror("Error", "Unknown error. Please tell Sam.")

class BetViewerApp:
    def __init__(self, root):
        self.root = root

        # Initialize Google Sheets API client
        self.initialize_ui()
        user_login()

        threading.Thread(target=schedule_data_updates, daemon=True).start()

        self.race_updation = RaceUpdaton(root)
        self.next3_panel = Next3Panel(root)
        self.notebook = Notebook(root)
        self.bet_feed = BetFeed(root)
        self.bet_runs = BetRuns(root)
        self.settings = Settings(root)


    def initialize_ui(self):
        self.root.title("Bet Viewer")
        self.root.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
        ttk.Style().theme_use('forest-light')
        width = 900
        height = 1005
        screenwidth = self.root.winfo_screenwidth()
        screenheight = self.root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width - 10), 0)
        self.root.geometry(alignstr)
        # self.root.resizable(False, False)
        self.import_logo()
        self.setup_menu_bar()

    def import_logo(self):
        logo_image = Image.open('src/splash.ico')
        logo_image.thumbnail((70, 70))
        self.company_logo = ImageTk.PhotoImage(logo_image)
        self.root.iconbitmap('src/splash.ico')

    def setup_menu_bar(self):
        menu_bar = tk.Menu(self.root)
        options_menu = tk.Menu(menu_bar, tearoff=0)
        options_menu.add_command(label="Set User Initials", command=self.user_login, foreground="#000000", background="#ffffff")
        # options_menu.add_command(label="Settings", command=self.open_settings, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Report Monitor Issue", command=self.report_monitor_issue, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Apply Bonus Points", command=self.apply_bonus_points, foreground="#000000", background="#ffffff")
        options_menu.add_separator(background="#ffffff")
        options_menu.add_command(label="Exit", command=self.root.quit, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Options", menu=options_menu)
        menu_bar.add_command(label="Client Options", command=lambda: self.open_client_wizard("Factoring"), foreground="#000000", background="#ffffff")
        menu_bar.add_command(label="About", command=self.about, foreground="#000000", background="#ffffff")

        # Add Client Wizard menu item

        self.root.config(menu=menu_bar)

    def open_client_wizard(self, default_tab="Factoring"):
        ClientWizard(self.root, default_tab)

    def user_login(self):
        user_login()

    def report_monitor_issue(self):
        global user

        def submit_issue():
            issue = issue_textbox.get("1.0", tk.END).strip()
            if issue:
                issues_file_path = os.path.join(NETWORK_PATH_PREFIX, 'issues.txt')
                try:
                    with open(issues_file_path, 'a') as f:
                        f.write(f"{user} - {issue}\n\n")
                    messagebox.showinfo("Submitted", "Your issue/suggestion has been submitted.")
                    issue_window.destroy()
                except FileNotFoundError:
                    messagebox.showerror("File Not Found", f"Could not find the file: {issues_file_path}")
            else:
                messagebox.showwarning("Empty Issue", "Please describe the issue or suggestion before submitting.")

        issue_window = tk.Toplevel(self.root)
        issue_window.title("Report Monitor Issue")
        issue_window.geometry("400x300")

        issue_label = ttk.Label(issue_window, text="Describe issue/suggestion:")
        issue_label.pack(pady=10)

        issue_textbox = tk.Text(issue_window, wrap='word', height=10)
        issue_textbox.pack(padx=10, pady=10, fill='both', expand=True)

        submit_button = ttk.Button(issue_window, text="Submit", command=submit_issue)
        submit_button.pack(pady=10)

    def open_settings(self):
        settings_window = tk.Toplevel(root)
        settings_window.geometry("270x370")
        settings_window.title("Settings")
        settings_window.iconbitmap('src/splash.ico')
        screen_width = settings_window.winfo_screenwidth()
        settings_window.geometry(f"+{screen_width - 350}+50")
        
        settings_frame = ttk.Frame(settings_window, style='Card')
        settings_frame.place(x=5, y=5, width=260, height=360)
        
    def apply_bonus_points(self):
        if user != 'SB' and user != 'DF':
            print(user)
            messagebox.showerror("Error", "You do not have permission to apply bonus points.")
            return
    
        def submit_bonus():
            selected_full_name = users_combobox.get()
            points = points_entry.get()
            if not selected_full_name or not points:
                messagebox.showerror("Error", "Please select a user and enter the points.")
                return
    
            try:
                points = float(points)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number for points.")
                return
    
            selected_user = None
            for key, value in USER_NAMES.items():
                if value == selected_full_name:
                    selected_user = key
                    break
    
            if not selected_user:
                messagebox.showerror("Error", "Selected user not found.")
                return
    
            now = datetime.now()
            date_string = now.strftime('%d-%m-%Y')
            time_string = now.strftime('%H:%M')
            log_file = os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', f'update_log_{date_string}.txt')
    
            update = f"{time_string} - {selected_user} - {points:.2f}\n"
            log_notification(f"{selected_user} received a bonus of {points:.2f} points from {user}", True)
    
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        data = f.readlines()
                except IOError as e:
                    print(f"Error reading log file: {e}")
                    data = []
            else:
                data = []
    
            bonus_index = None
            for i, line in enumerate(data):
                if line.strip() == "Bonus:":
                    bonus_index = i
                    break
    
            if bonus_index is not None:
                # Insert the update under the existing "Bonus:" header
                data.insert(bonus_index + 1, update)
            else:
                # Add a new "Bonus:" header and the update
                data.append(f"\nBonus:\n")
                data.append(update)
    
            try:
                with open(log_file, 'w') as f:
                    f.writelines(data)
                print(f"Bonus points logged for {selected_user}")
                messagebox.showinfo("Success", f"Bonus points logged for {selected_user}")
                bonus_window.destroy()
            except IOError as e:
                print(f"Error writing to log file: {e}")
                messagebox.showerror("Error", "Failed to log bonus points.")
    
        bonus_window = tk.Toplevel(root)
        bonus_window.geometry("270x270")
        bonus_window.title("Apply Bonus")
        bonus_window.iconbitmap('src/splash.ico')
        screen_width = bonus_window.winfo_screenwidth()
        bonus_window.geometry(f"+{screen_width - 350}+50")
        bonus_frame = ttk.Frame(bonus_window, style='Card')
        bonus_frame.place(x=5, y=5, width=260, height=260)
    
        user_label = ttk.Label(bonus_frame, text="Select User:")
        user_label.pack(pady=5)
        users_combobox = ttk.Combobox(bonus_frame, values=list(USER_NAMES.values()), state="readonly")
        users_combobox.pack(pady=10)
    
        points_label = ttk.Label(bonus_frame, text="Enter Points:")
        points_label.pack(pady=5)
        points_entry = ttk.Entry(bonus_frame)
        points_entry.pack(pady=5)
    
        submit_button = ttk.Button(bonus_frame, text="Submit", command=submit_bonus)
        submit_button.pack(pady=20)
    def user_notification(self):
        user_notification()

    def about(self):
        messagebox.showinfo("About", "Geoff Banks Bet Monitoring\n     Sam Banks 2024")

if __name__ == "__main__":
    root = tk.Tk()
    app = BetViewerApp(root)
    root.mainloop()