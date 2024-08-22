####################################################################################
##                                BETVIEWERBETA.PY                                    


## FORMAT AND DISPLAY INCOMING BETS, FIND RUNS ON SELECTIONS, TRACK RACE UPDATION,
## DISPLAY NEXT 3 HORSE & GREYHOUND RACES, CREATE DAILY, CLIENT, STAFF REPORTS,
## SCREEN FOR RISK CLIENTS, OTHER VARIOUS QOL IMPROVEMENTS
####################################################################################

import os
import re
import threading
import pyperclip
import fasteners
import json
import requests
import random
import gspread
import datetime
import time
import tkinter as tk
from collections import defaultdict, Counter
from dateutil.relativedelta import relativedelta
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from tkinter import messagebox, filedialog, simpledialog, Text, scrolledtext, IntVar
from functools import lru_cache
from googleapiclient.discovery import build
from pytz import timezone
from tkinter import ttk
from tkinter.ttk import *
from datetime import date, datetime, timedelta
from PIL import Image, ImageTk

current_database = None
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

current_database = None
last_cache_time = None
cached_data = None

def load_database_data(json_file_path):
    try:
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        data.reverse()
        return data
    except FileNotFoundError:
        print(f"No bet data available for {json_file_path}.")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from file: {json_file_path}.")
    except Exception as e:
        print(f"An error occurred: {e}")
    return []

def get_database_cached():
    global current_database, last_cache_time, cached_data

    if last_cache_time is None or datetime.now() - last_cache_time > timedelta(seconds=15):
        last_cache_time = datetime.now()
        date_str = current_database if current_database else datetime.now().strftime('%Y-%m-%d')
        if not date_str.endswith('-wager_database.json'):
            date_str += '-wager_database.json'
        json_file_path = f"database/{date_str}"

        cached_data = load_database_data(json_file_path)

        if not cached_data:
            print("Database returned nothing. Retrying...")
            time.sleep(2)
            cached_data = load_database_data(json_file_path)
    else:
        pass

    return cached_data

def get_database():
    return get_database_cached()

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
    # Get the current time
    time_str = datetime.now().strftime('%H:%M:%S')
    file_lock = fasteners.InterProcessLock('notifications.lock')
    try:
        with file_lock:
            try:
                with open('notifications.json', 'r') as f:
                    notifications = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                notifications = []

            # If the notification is pinned, remove the existing pinned notification
            if pinned:
                notifications = [notification for notification in notifications if not notification.get('pinned', False)]
            
            # Insert the new notification at the beginning
            notifications.insert(0, {'time': time_str, 'message': message, 'important': important, 'pinned': pinned})
            
            # Write to a temporary file first
            temp_filename = 'notifications_temp.json'
            with open(temp_filename, 'w') as f:
                json.dump(notifications, f, indent=4)
            
            # Small delay to ensure the file system is ready
            time.sleep(0.1)
            
            # Rename the temporary file to the actual file
            os.replace(temp_filename, 'notifications.json')
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
            with open('src/data.json', 'r') as file:
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
                'total_deposits': self.data.get('deposits_summary', {}).get('total_deposits', 0),
                'total_sum': self.data.get('deposits_summary', {}).get('total_sum', 0),
                'enhanced_places': self.data.get('enhanced_places', [])
            }
    def get_oddsmonkey_selections(self):
        with self.lock:
            return self.data.get('oddsmonkey_selections', [])

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
    oddsmonkey_selections = fetcher.get_oddsmonkey_selections()
    today_oddsmonkey_selections = fetcher.get_todays_oddsmonkey_selections()
    reporting_data = fetcher.get_reporting_data()
    return vip_clients, newreg_clients, oddsmonkey_selections, today_oddsmonkey_selections, reporting_data

class BetFeed:
    def __init__(self, root):
        self.root = root
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None, 'selection': None}
        self.initialize_ui()
        self.start_feed_update()

    def initialize_ui(self):
        self.feed_frame = ttk.LabelFrame(self.root, style='Card', text="Bet Feed")
        self.feed_frame.place(x=5, y=5, width=550, height=640)
        self.feed_frame.grid_columnconfigure(0, weight=1)
        self.feed_frame.grid_columnconfigure(1, weight=0)
        self.feed_frame.grid_rowconfigure(0, weight=1)
        
        self.feed_text = tk.Text(self.feed_frame, font=("Helvetica", 11, "bold"), wrap='word', padx=10, pady=10, bd=0, fg="#000000")
        self.feed_text.config(state='disabled')
        self.feed_text.grid(row=0, column=0, sticky='nsew')
        
        self.feed_scroll = ttk.Scrollbar(self.feed_frame, orient='vertical', command=self.feed_text.yview, cursor="hand2")
        self.feed_scroll.grid(row=0, column=1, sticky='ns')
        self.feed_text.configure(yscrollcommand=self.feed_scroll.set)

        self.filter_frame = ttk.Frame(self.feed_frame)
        self.filter_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))

        self.username_filter_label = ttk.Label(self.filter_frame, text='Client:')
        self.username_filter_label.grid(row=0, column=0, sticky='e', padx=5)
        self.username_filter_entry = ttk.Entry(self.filter_frame, width=8)
        self.username_filter_entry.grid(row=0, column=1, pady=(0, 3), sticky='ew')

        self.unit_stake_filter_label = ttk.Label(self.filter_frame, text='Unit Stake:')
        self.unit_stake_filter_label.grid(row=0, column=2, sticky='e', padx=5)
        self.unit_stake_filter_entry = ttk.Entry(self.filter_frame, width=3)
        self.unit_stake_filter_entry.grid(row=0, column=3, pady=(0, 3), sticky='ew')

        self.risk_category_filter = ttk.Label(self.filter_frame, text='Risk Category:')
        self.risk_category_filter.grid(row=0, column=4, sticky='e', padx=5)
        self.risk_category_combobox_values = ["", "Any", "M", "W", "S", "O", "X"]
        self.risk_category_filter_entry = ttk.Combobox(self.filter_frame, values=self.risk_category_combobox_values, width=3)
        self.risk_category_filter_entry.grid(row=0, column=5, pady=(0, 3), sticky='ew')

        
        self.selection_filter_label = ttk.Label(self.filter_frame, text='Selection:')
        self.selection_filter_label.grid(row=1, column=0, sticky='e', padx=5)
        self.selection_filter_entry = ttk.Entry(self.filter_frame, width=8)
        self.selection_filter_entry.grid(row=1, column=1, pady=(0, 3), sticky='ew', columnspan=3)

        self.sport_filter = ttk.Label(self.filter_frame, text='Sport:')
        self.sport_filter.grid(row=1, column=4, sticky='e', padx=5)
        self.sport_combobox_values = ["", "Horses", "Dogs", "Other"]
        self.sport_combobox_entry = ttk.Combobox(self.filter_frame, values=self.sport_combobox_values, width=5)
        self.sport_combobox_entry.grid(row=1, column=5, pady=(0, 3), sticky='ew')

        self.tick_button = ttk.Button(self.filter_frame, text='✔', command=self.apply_filters, width=2)
        self.tick_button.grid(row=0, column=8, padx=(10, 0), sticky='ew', pady=(0, 3)) 

        self.reset_button = ttk.Button(self.filter_frame, text='X', command=self.reset_filters, width=2)
        self.reset_button.grid(row=1, column=8, padx=(10, 0), sticky='ew', pady=(0, 3)) 

        self.separator = ttk.Separator(self.filter_frame, orient='vertical')
        self.separator.grid(row=0, column=7, rowspan=2, sticky='ns')

        self.filter_frame.grid_rowconfigure(0, weight=1)
        self.filter_frame.grid_rowconfigure(1, weight=1)
        self.filter_frame.grid_columnconfigure(0, weight=0)
        self.filter_frame.grid_columnconfigure(1, weight=0)
        self.filter_frame.grid_columnconfigure(2, weight=1)
        self.filter_frame.grid_columnconfigure(3, weight=1)
        self.filter_frame.grid_columnconfigure(4, weight=1)
        self.filter_frame.grid_columnconfigure(5, weight=1)
        self.filter_frame.grid_columnconfigure(6, weight=1)
        self.filter_frame.grid_columnconfigure(7, weight=1)
        self.filter_frame.grid_columnconfigure(8, weight=1)
        self.filter_frame.grid_columnconfigure(9, weight=1)

        self.activity_frame = ttk.LabelFrame(self.root, style='Card', text="Status")
        self.activity_frame.place(x=560, y=5, width=335, height=150)
        
        self.activity_text = tk.Text(self.activity_frame, font=("Helvetica", 10, "bold"), wrap='word', padx=10, pady=10, bd=0, fg="#000000")
        self.activity_text.config(state='disabled')
        self.activity_text.pack(fill='both', expand=True)

    def start_feed_update(self):
        scroll_pos = self.feed_text.yview()[0]
        
        if scroll_pos <= 0.05:
            self.bet_feed()
        else:
            pass
        
        self.feed_frame.after(12000, self.start_feed_update)

    def bet_feed(self, date_str=None):
        self.total_bets = 0
        self.total_knockbacks = 0
        self.total_sms_wagers = 0
        self.m_clients = set()
        self.w_clients = set()
        self.norisk_clients = set()

        self.data = get_database()

        if self.data is None:
            self.feed_text.config(state="normal")
            self.feed_text.delete('1.0', tk.END)
            self.feed_text.insert('end', "No bet data available for the selected date or the database can't be found.", "notices")
            self.feed_text.config(state="disabled")
            return 

        username = self.current_filters['username']
        unit_stake = self.current_filters['unit_stake']
        risk_category = self.current_filters['risk_category']
        sport = self.current_filters['sport']
        selection_search_term = self.current_filters['selection']


        filters_active = any([
            username,
            unit_stake,
            risk_category,
            sport,
            selection_search_term
        ])

        if filters_active:
            filtered_bets = self.filter_bets(self.data, username, unit_stake, risk_category, sport, selection_search_term)
        else:
            filtered_bets = self.data

        self.initialize_text_tags()

        self.feed_text.config(state="normal")
        self.feed_text.delete('1.0', tk.END)

        if not filtered_bets:
            self.feed_text.insert('end', "No bets found with the current filters.", 'center')
        else:
            separator = '\n-------------------------------------------------------------------------------------------------------\n'
            self.vip_clients, self.newreg_clients, self.oddsmonkey_selections, self.todays_oddsmonkey_selections, reporting_data = access_data()

            for bet in filtered_bets:
                self.display_bet(bet)
                self.feed_text.insert('end', separator, "notices")
            
            self.sport_count = self.count_sport(self.data)
            self.update_activity_frame(reporting_data, self.sport_count)
        
        self.feed_text.config(state="disabled")

    def apply_filters(self):
        self.current_filters['username'] = self.username_filter_entry.get()
        self.current_filters['unit_stake'] = self.unit_stake_filter_entry.get()
        self.current_filters['risk_category'] = self.risk_category_filter_entry.get()
        self.current_filters['sport'] = self.sport_combobox_entry.get()
        self.current_filters['selection'] = self.selection_filter_entry.get()

        filters_applied = any(value not in [None, '', 'none'] for value in self.current_filters.values())

        if filters_applied:
            self.tick_button.configure(style='Accent.TButton')
        else:
            self.tick_button.configure(style='TButton')

        self.bet_feed()

    def reset_filters(self):
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None, 'selection': None}
        self.username_filter_entry.delete(0, tk.END) 
        self.unit_stake_filter_entry.delete(0, tk.END) 
        self.risk_category_filter_entry.delete(0, tk.END) 
        self.sport_combobox_entry.set('') 
        self.selection_filter_entry.delete(0, tk.END) 
        
        self.tick_button.configure(style='TButton')

        self.bet_feed()

    def filter_bets(self, bets, username, unit_stake_filter, risk_category, sport, selection_search_term=None):
        filtered_bets = []        
        sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
        
        sport_number = sport_mapping.get(sport, -1)

        if unit_stake_filter:
            try:
                unit_stake_filter_value = float(unit_stake_filter.replace('£', ''))
            except ValueError:
                unit_stake_filter_value = None
        else:
            unit_stake_filter_value = None

        specific_filters_applied = unit_stake_filter_value is not None or sport_number != -1 or (risk_category and risk_category not in ['Any', ''])
        for bet in bets:
            if isinstance(bet.get('details'), dict):
                selections = bet['details'].get('selections', [])
                selection_match = False
                if selection_search_term:
                    if bet.get('type') == "WAGER KNOCKBACK":
                        for selection in selections:
                            meeting_name = selection.get("- Meeting Name", "")
                            selection_name = selection.get("- Selection Name", "")
                            selection_str = f"{meeting_name}, {selection_name}"
                            if selection_search_term.lower() in selection_str.lower():
                                selection_match = True
                                break
                    else: 
                        for selection in selections:
                            if isinstance(selection, list) and selection_search_term.lower() in selection[0].lower():
                                selection_match = True
                                break
                            elif isinstance(selection, dict):
                                selection_str = selection.get("Selection Name", "") 
                                if selection_search_term.lower() in selection_str.lower():
                                    selection_match = True
                                    break
                else:
                    selection_match = True 

                if not selection_match:
                    continue  

                unit_stake_str = bet['details'].get('unit_stake', '£0')
                try:
                    unit_stake_value = float(unit_stake_str.replace('£', ''))
                except ValueError:
                    continue

                if unit_stake_filter_value is not None and unit_stake_value < unit_stake_filter_value:
                    continue

                if username and bet.get('customer_ref') != username.upper():
                    continue 

                risk_category_value = bet.get('details', {}).get('risk_category', '-')

                include_bet = False
                if risk_category is None or risk_category == '':
                    include_bet = True
                elif risk_category == 'Any' and risk_category_value != '-':
                    include_bet = True
                elif risk_category_value == risk_category:
                    include_bet = True

                if include_bet and (sport_number == -1 or sport_number in bet.get('Sport', [])):
                    filtered_bets.append(bet)
            elif bet.get('type') == 'SMS WAGER':
                if specific_filters_applied:
                    continue

                if username and bet.get('customer_ref') != username.upper():
                    continue 
                
                if selection_search_term and selection_search_term.lower() not in bet.get('details', '').lower():
                    continue  
                
                filtered_bets.append(bet)
        
        return filtered_bets


    def count_sport(self, data):
        sport_counts = {0: 0, 1: 0, 2: 0}

        for bet in data:
            if "Sport" in bet:
                for sport in bet["Sport"]:
                    if sport in sport_counts:
                        sport_counts[sport] += 1
        return sport_counts

    def insert_feed_text(self, text, tag=None):
        if tag:
            self.feed_text.insert('end', text, tag)
        else:
            self.feed_text.insert('end', text)

    def initialize_text_tags(self):
        self.feed_text.tag_configure("risk", foreground="#8f0000")
        self.feed_text.tag_configure("newreg", foreground="purple")
        self.feed_text.tag_configure("vip", foreground="#009685")
        self.feed_text.tag_configure("sms", foreground="orange")
        self.feed_text.tag_configure("Oddsmonkey", foreground="#ff00e6")
        self.feed_text.tag_configure("notices", font=("Helvetica", 11, "normal"))
        self.feed_text.tag_configure('center', justify='center')


    def display_bet(self, bet):
        wager_type = bet.get('type', '').lower()
        if wager_type == 'wager knockback':
            self.display_wager_knockback(bet)
        elif wager_type == 'sms wager':
            self.display_sms_wager(bet)
        elif wager_type == 'bet':
            self.display_regular_bet(bet)


    def display_wager_knockback(self, bet):
        customer_ref = bet.get('customer_ref', '')
        knockback_id = bet.get('id', '')
        knockback_id = knockback_id.rsplit('-', 1)[0]
        knockback_details = bet.get('details', {})
        time = bet.get('time', '') 
        formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items() if key not in ['Selections', 'Knockback ID', 'Time', 'Customer Ref', 'Error Message']])
        formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' for i, selection in enumerate(knockback_details.get('Selections', []))])
        formatted_knockback_details += '\n   ' + formatted_selections
        error_message = knockback_details.get('Error Message', '')
        if 'Maximum stake available' in error_message:
            error_message = error_message.replace(', Maximum stake available', '\n   Maximum stake available')
        formatted_knockback_details = f"Error Message: {error_message}\n   {formatted_knockback_details}"
        if customer_ref in self.vip_clients:
            tag = "vip"
        elif customer_ref in self.newreg_clients:
            tag = "newreg"
        else:
            tag = None
        
        self.insert_feed_text(f"{time} - {knockback_id} - {customer_ref} - WAGER KNOCKBACK:\n   {formatted_knockback_details}", tag)
        self.total_knockbacks += 1

    def display_sms_wager(self, bet):
        wager_number = bet.get('id', '')
        customer_reference = bet.get('customer_ref', '')
        sms_wager_text = bet.get('details', '')
        self.insert_feed_text(f"{customer_reference} - {wager_number} SMS WAGER:\n{sms_wager_text}", "sms")
        self.total_sms_wagers += 1

    def display_regular_bet(self, bet):
        bet_no = bet.get('id', '')
        details = bet.get('details', {})
        parsed_selections = details.get('selections', [])
        timestamp = bet.get('time', '')
        customer_reference = bet.get('customer_ref', '')
        customer_risk_category = details.get('risk_category', '')
        bet_details = details.get('bet_details', '')
        unit_stake = details.get('unit_stake', '')
        bet_type = details.get('bet_type', '')
        
        if customer_reference in self.vip_clients:
            tag = "vip"
            self.norisk_clients.add(customer_reference)
        elif customer_reference in self.newreg_clients:
            tag = "newreg"
            self.norisk_clients.add(customer_reference)
        elif customer_risk_category and customer_risk_category != '-':
            tag = "risk"
            if customer_risk_category == 'M':
                self.m_clients.add(customer_reference)
            elif customer_risk_category == 'W':
                self.w_clients.add(customer_reference)
        else:
            tag = None
            self.norisk_clients.add(customer_reference)

        selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])

        self.insert_feed_text(f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}", tag)

        if any(' - ' in sel[0] and sel[0].split(' - ')[1].strip() == om_sel[1][0].strip() for sel in parsed_selections for om_sel in self.oddsmonkey_selections.items()):
            self.insert_feed_text(f"\n ^ Oddsmonkey Selection Detected ^ ", "Oddsmonkey")
        
        self.total_bets += 1


    def update_activity_frame(self, reporting_data, sport_count):
        global current_database
        unique_m_clients = len(self.m_clients)
        unique_w_clients = len(self.w_clients)
        unique_norisk_clients = len(self.norisk_clients)
        total_unique_clients = len(self.m_clients.union(self.w_clients, self.norisk_clients))
        knockback_percentage = (self.total_knockbacks / self.total_bets * 100) if self.total_bets > 0 else 0

        daily_turnover = reporting_data.get('daily_turnover', 'N/A')
        daily_profit = reporting_data.get('daily_profit', 'N/A')
        daily_profit_percentage = reporting_data.get('daily_profit_percentage', 'N/A')
        total_deposits = reporting_data.get('total_deposits', 'N/A')
        total_sum_deposits = reporting_data.get('total_sum', 'N/A')
        horse_bets = sport_count.get(0, 0)
        dog_bets = sport_count.get(1, 0)
        other_bets = sport_count.get(2, 0)

        filters_applied = any(value not in [None, '', 'none'] for value in self.current_filters.values())

        avg_deposit = total_sum_deposits / total_deposits if total_deposits else 0

        current_date_str = datetime.now().strftime("%A %d %B")

        status_text = (
            f"{'-- Viewing Database From ' + current_database + ' --' if current_database != None else f'{current_date_str}'}\n"
            f"Bets: {self.total_bets} | Knockbacks: {self.total_knockbacks} ({knockback_percentage:.2f}%){'**' if filters_applied else ''}\n"
            f"Turnover: {daily_turnover} | Profit: {daily_profit} ({daily_profit_percentage})\n"
            f"Deposits: {total_deposits} | Total: £{total_sum_deposits:,.2f} (~£{avg_deposit:,.2f})\n"
            f"Clients: {total_unique_clients} | M: {unique_m_clients} | W: {unique_w_clients} | --: {unique_norisk_clients}{'**' if filters_applied else ''}\n"
            f"Horses: {horse_bets} | Dogs: {dog_bets} | Other: {other_bets}\n"
            f"{'**Feed Filters Currently Applied!' if filters_applied else ''}"
        )

        self.activity_text.config(state='normal') 
        self.activity_text.delete('1.0', tk.END)  
        
        self.activity_text.tag_configure('center', justify='center')
        self.activity_text.insert(tk.END, status_text, 'center')  
        
        self.activity_text.config(state='disabled')

class BetRuns:
    def __init__(self, root):
        self.num_run_bets_var = tk.StringVar()
        self.combobox_var = tk.IntVar(value=50)
        self.num_run_bets = 2
        self.num_recent_files = 50

        self.root = root
        self.initialize_ui()
        self.refresh_bets()
    
    def initialize_ui(self):
        self.runs_frame = ttk.LabelFrame(root, style='Card', text="Runs on Selections")
        self.runs_frame.place(x=560, y=160, width=335, height=485)
        self.runs_frame.grid_columnconfigure(0, weight=1)
        self.runs_frame.grid_rowconfigure(0, weight=1)
        self.runs_frame.grid_columnconfigure(1, weight=0)

        self.runs_text = tk.Text(self.runs_frame, font=("Arial", 10), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
        self.runs_text.config(state='disabled') 
        self.runs_text.grid(row=0, column=0, sticky='nsew')

        self.spinbox_frame = ttk.Frame(self.runs_frame)
        self.spinbox_frame.grid(row=1, column=0, sticky='ew', pady=(5, 0))
        self.spinbox_label = ttk.Label(self.spinbox_frame, text='Run: ')
        self.spinbox = ttk.Spinbox(self.spinbox_frame, from_=2, to=10, textvariable=self.num_run_bets_var, width=2)
        self.spinbox_frame.grid(row=1, column=0, sticky='ew')
        self.spinbox_frame.grid_columnconfigure(0, weight=1)
        self.spinbox_frame.grid_columnconfigure(1, weight=1)
        self.spinbox_frame.grid_columnconfigure(2, weight=1)
        self.spinbox_frame.grid_columnconfigure(3, weight=1)

        self.spinbox_label.grid(row=0, column=0, sticky='e', padx=6) 
        self.spinbox.grid(row=0, column=1, pady=(0, 3), sticky='ew') 
        self.num_run_bets_var.set("2")
        self.spinbox.grid(row=0, column=1, pady=(0, 3), sticky='w')
        self.num_run_bets_var.trace("w", self.set_num_run_bets)

        self.combobox_label = ttk.Label(self.spinbox_frame, text=' Num bets: ')
        self.combobox_label.grid(row=0, column=2, sticky='e', padx=6)

        self.combobox_values = [20, 50, 100, 300, 1000, 2000]
        self.combobox = ttk.Combobox(self.spinbox_frame, textvariable=self.combobox_var, values=self.combobox_values, width=4)
        self.combobox_var.trace("w", self.set_recent_bets)
        self.combobox.grid(row=0, column=3, pady=(0, 3), sticky='ew')
        self.runs_scroll = ttk.Scrollbar(self.runs_frame, orient='vertical', command=self.runs_text.yview, cursor="hand2")
        self.runs_scroll.grid(row=0, column=1, sticky='ns')
        self.runs_text.configure(yscrollcommand=self.runs_scroll.set)

    def set_recent_bets(self, *args):
        self.num_recent_files = self.combobox_var.get()
        self.refresh_bets()

    def set_num_run_bets(self, *args):
        try:
            self.num_run_bets = int(self.num_run_bets_var.get())
            self.refresh_bets()
        except ValueError:
            pass

    def bet_runs(self, num_bets, num_run_bets):
        database_data = get_database()
        
        if database_data is None:
            self.runs_text.config(state="normal")
            self.runs_text.delete('1.0', tk.END) 
            self.runs_text.insert('end', "No bet data available for the selected date or the database can't be found.")
            self.runs_text.config(state="disabled")
            return 

        selection_bets = database_data[:num_bets]        
        selection_to_bets = defaultdict(list)

        for bet in selection_bets:
            if isinstance(bet['details'], dict):
                selections = [selection[0] for selection in bet['details'].get('selections', [])]
                for selection in selections:
                    selection_to_bets[selection].append(bet['id'])

        sorted_selections = sorted(selection_to_bets.items(), key=lambda item: len(item[1]), reverse=True)
        
        self.update_ui_with_selections(sorted_selections, selection_bets, num_run_bets)


    def update_ui_with_selections(self, sorted_selections, selection_bets, num_run_bets):
        vip_clients, newreg_clients, _, todays_oddsmonkey_selections, reporting_data = access_data()
        enhanced_places = reporting_data.get('enhanced_places', [])

        self.runs_text.tag_configure("risk", foreground="#8f0000")
        self.runs_text.tag_configure("vip", foreground="#009685")
        self.runs_text.tag_configure("newreg", foreground="purple")
        self.runs_text.tag_configure("oddsmonkey", foreground="#ff00e6")
        self.runs_text.config(state="normal")
        self.runs_text.delete('1.0', tk.END)

        for selection, bet_numbers in sorted_selections:
            skip_selection = False

            if skip_selection:
                continue

            if len(bet_numbers) >= num_run_bets:
                selection_name = selection.split(' - ')[1] if ' - ' in selection else selection

                matched_odds = None
                for om_sel in todays_oddsmonkey_selections.values():
                    if selection_name == om_sel[0]:
                        matched_odds = float(om_sel[1])
                        break

                if matched_odds is not None:
                    self.runs_text.insert(tk.END, f"{selection} | OM Lay: {matched_odds}\n", "oddsmonkey")
                else:
                    self.runs_text.insert(tk.END, f"{selection}\n")

                for bet_number in bet_numbers:
                    bet_info = next((bet for bet in selection_bets if bet['id'] == bet_number), None)
                    if bet_info:
                        for sel in bet_info['details']['selections']:
                            if selection == sel[0]:
                                if 'risk_category' in bet_info['details'] and bet_info['details']['risk_category'] != '-':
                                    self.runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n", "risk")
                                elif bet_info['customer_ref'] in vip_clients:
                                    self.runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n", "vip")
                                elif bet_info['customer_ref'] in newreg_clients:
                                    self.runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n", "newreg")
                                else:
                                    self.runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n")

                meeting_time = ' '.join(selection.split(' ')[:2])

                if meeting_time in enhanced_places:
                    self.runs_text.insert(tk.END, 'Enhanced Place Race\n', "oddsmonkey")
                
                self.runs_text.insert(tk.END, f"\n")

        self.runs_text.config(state=tk.DISABLED)

    def refresh_bets(self):
        scroll_pos = self.runs_text.yview()[0]

        num_bets = self.num_recent_files
        num_run_bets = self.num_run_bets

        if scroll_pos <= 0.04:
            self.bet_runs(num_bets, num_run_bets)
        else:
            pass

        self.root.after(15000, self.refresh_bets)       

class RaceUpdaton:
    def __init__(self, root):
        self.root = root
        self.current_page = 0
        self.courses_per_page = 6
        self.initialize_ui()
        self.get_courses()
    
    def initialize_ui(self):
        self.race_updation_frame = ttk.LabelFrame(root, style='Card', text="Race Updation")
        self.race_updation_frame.place(x=5, y=647, width=227, height=273)

    def display_courses_periodic(self):
        self.display_courses()
        self.root.after(15000, self.display_courses_periodic)

    def get_courses(self):
        today = date.today()
        courses = set()
        api_data = []

        try:
            response = requests.get('https://globalapi.geoffbanks.bet/api/Geoff/GetSportApiData?sportcode=H,h')
            response.raise_for_status()
            api_data = response.json()
        except requests.RequestException as e:
            print("Error fetching data from GB API for Courses.")
        except json.JSONDecodeError:
            print("Error decoding JSON from GB API response.")

        if api_data:
            for event in api_data:
                for meeting in event['meetings']:
                    courses.add(meeting['meetinName'])

        courses.add("Football")
        courses.add("SIS Greyhounds")
        courses.add("TRP Greyhounds")

        courses = list(courses)
        print("Courses:", courses)

        try:
            with open('update_times.json', 'r') as f:
                update_data = json.load(f)
        except FileNotFoundError:
            update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {}}
            with open('update_times.json', 'w') as f:
                json.dump(update_data, f)

        if update_data['date'] != today.strftime('%Y-%m-%d'):
            update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {course: "" for course in courses}}
            with open('update_times.json', 'w') as f:
                json.dump(update_data, f)

        self.display_courses_periodic()
        return courses


    def reset_update_times(self):
        if os.path.exists('update_times.json'):
            os.remove('update_times.json')

        update_data = {'date': '', 'courses': {}}
        with open('update_times.json', 'w') as f:
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

        if course in ["SIS Greyhounds", "TRP Greyhounds", "Football"]:
            return time_diff >= 60
        else:
            return time_diff >= 25

    def display_courses(self):
        with open('update_times.json', 'r') as f:
            data = json.load(f)

        courses = list(data['courses'].keys())
        courses.sort(key=lambda x: (x=="SIS Greyhounds", x=="TRP Greyhounds"))
        start = self.current_page * self.courses_per_page
        end = start + self.courses_per_page
        courses_page = courses[start:end]

        for widget in self.race_updation_frame.winfo_children():
            widget.destroy()
        
        button_frame = ttk.Frame(self.race_updation_frame)
        button_frame.grid(row=len(courses_page), column=0, padx=2, sticky='ew')

        add_button = ttk.Button(button_frame, text="+", command=self.add_course, width=2, cursor="hand2")
        add_button.pack(side='left')

        update_indicator = ttk.Label(button_frame, text="\u2022", foreground='red', font=("Helvetica", 24))
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

            if course in ["SIS Greyhounds", "TRP Greyhounds"]:
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
        if any(self.course_needs_update(course, data) for course in other_courses):
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

    def remove_course(self):
        course = simpledialog.askstring("Remove Course", "Enter the course name:")
        
        
        with open('update_times.json', 'r') as f:
            data = json.load(f)
        if course in data['courses']:
            del data['courses'][course]

        with open('update_times.json', 'w') as f:
            json.dump(data, f)

        if course:
            log_notification(f"'{course}' removed by {user}")

        self.display_courses()

    def add_course(self):
        course_name = simpledialog.askstring("Add Course", "Enter the course name:")
        if course_name:
            with open('update_times.json', 'r') as f:
                data = json.load(f)

            data['courses'][course_name] = ""

            with open('update_times.json', 'w') as f:
                json.dump(data, f)

            log_notification(f"'{course_name}' added by {user}")

            self.display_courses()

    def back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_courses()

    def forward(self):
        with open('update_times.json', 'r') as f:
            data = json.load(f)
        total_courses = len(data['courses'].keys())
        if (self.current_page + 1) * self.courses_per_page < total_courses:
            self.current_page += 1
            self.display_courses()

    def update_course(self, course):
        global user
        if not user:
            user_login()

        now = datetime.now()
        time_string = now.strftime('%H:%M')

        with open('update_times.json', 'r') as f:
            data = json.load(f)

        data['courses'][course] = f"{time_string} - {user}"
        with open('update_times.json', 'w') as f:
            json.dump(data, f)

        self.log_update(course, time_string, user)
        self.display_courses()

    def log_update(self, course, time, user):
        now = datetime.now()
        date_string = now.strftime('%d-%m-%Y')
        log_file = f'logs/updatelogs/update_log_{date_string}.txt'

        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                data = f.readlines()
        else:
            data = []

        update = f"{time} - {user}\n"

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

        log_message = f"{user} updated {course}"
        log_notification(log_message)

        with open(log_file, 'w') as f:
            f.writelines(data)

class Notebook:
    def __init__(self, root):
        self.root = root
        self.last_notification = None
        self.generated_string = None
        self.confirm_betty_update_bool = tk.BooleanVar()
        self.confirm_betty_update_bool.set(False)
        self.send_confirmation_email_bool = tk.BooleanVar()
        self.send_confirmation_email_bool.set(True) 
        self.archive_email_bool = tk.BooleanVar()
        self.archive_email_bool.set(False)

        with open('src/creds.json') as f:
            data = json.load(f)
        
        _, _, _, _, reporting_data = access_data()
        self.enhanced_places = reporting_data.get('enhanced_places', [])

        self.pipedrive_api_token = data['pipedrive_api_key']
        self.pipedrive_api_url = f'https://api.pipedrive.com/v1/itemSearch?api_token={self.pipedrive_api_token}'
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(data, scope)
        self.gc = gspread.authorize(credentials)

        self.initialize_ui()
        self.update_notifications()
        self.display_closure_requests()
        self.run_factoring_sheet_thread()

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
        self.pinned_message = tk.Text(self.pinned_message_frame, font=("Helvetica", 10, 'bold'), bd=0, wrap='word', pady=2, fg="#000000", bg="#ffffff", height=5, width=35)  # Adjust height as needed
        self.pinned_message.config(state='disabled') 
        self.pinned_message.pack(side="top", pady=5, padx=5) 
        self.post_message_button = ttk.Button(self.staff_feed_buttons_frame, text="Post", command=user_notification, cursor="hand2", width=10)
        self.post_message_button.pack(side="top", pady=(10, 5))

        separator = ttk.Separator(self.staff_feed_buttons_frame, orient='horizontal')
        separator.pack(side="top", fill='x', pady=(12, 8), padx=5)

        self.copy_frame = ttk.Frame(self.staff_feed_buttons_frame)
        self.copy_frame.pack(side="top", pady=(5, 0))
        self.copy_button = ttk.Button(self.copy_frame, text="↻", command=self.copy_to_clipboard, cursor="hand2", width=2)
        self.copy_button.grid(row=0, column=0)
        self.password_result_label = ttk.Label(self.copy_frame, text="GB000000", font=("Helvetica", 12), wraplength=200)
        self.password_result_label.grid(row=0, column=1, padx=(5, 5))
        
        tab_2 = ttk.Frame(self.notebook)
        self.notebook.add(tab_2, text="Reports/Screener")
        tab_2.grid_rowconfigure(0, weight=1)
        tab_2.grid_rowconfigure(1, weight=1)
        tab_2.grid_columnconfigure(0, weight=3)
        tab_2.grid_columnconfigure(1, weight=0) 
        tab_2.grid_columnconfigure(2, weight=1)
        self.report_ticket = tk.Text(tab_2, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
        self.report_ticket.tag_configure("center", justify='center')
        self.report_ticket.insert('1.0', "Daily Report\nGenerate a report for the days betting activity.\n\nStaff Report\nGenerate a report on staff activity.\n\nTraders Screener\nScan for potential 'risk' users.\n\nRG Screener\nScan for indicators of irresponsible gambling.", "center")    
        self.report_ticket.config(state='disabled')
        self.report_ticket.grid(row=0, column=0, sticky="nsew") 
        separator_tab_2 = ttk.Separator(tab_2, orient='vertical')
        separator_tab_2.grid(row=0, column=1, sticky='ns')
        self.report_buttons_frame = ttk.Frame(tab_2)
        self.report_buttons_frame.grid(row=0, column=2, sticky='nsew')
        self.report_combobox = ttk.Combobox(self.report_buttons_frame, values=["Daily Report", "Staff Report", "Traders Screener", "RG Screener"], width=30, state='readonly')
        self.report_combobox.pack(side="top", pady=(10, 5), padx=(5, 0))
        self.report_button = ttk.Button(self.report_buttons_frame, text="Generate", command=self.generate_report, cursor="hand2", width=30)
        self.report_button.pack(side="top", pady=(5, 10), padx=(5, 0))
        self.progress = ttk.Progressbar(self.report_buttons_frame, orient='horizontal', length=200, mode='determinate')
        self.progress.pack(side="top", pady=(20, 10), padx=(5, 0))

        tab_3 = ttk.Frame(self.notebook)
        self.notebook.add(tab_3, text="Factoring Diary")

        self.tree = ttk.Treeview(tab_3)
        columns = ["A", "B", "C", "D", "E", "F"]
        headings = ["Date", "Time", "User", "Risk", "Rating", ""]
        self.tree["columns"] = columns
        for col, heading in enumerate(headings):
            self.tree.heading(columns[col], text=heading)
            self.tree.column(columns[col], width=84, stretch=tk.NO)
        self.tree.column("A", width=75, stretch=tk.NO)
        self.tree.column("B", width=60, stretch=tk.NO)
        self.tree.column("C", width=83, stretch=tk.NO)
        self.tree.column("D", width=40, stretch=tk.NO)
        self.tree.column("E", width=40, stretch=tk.NO)
        self.tree.column("F", width=32, stretch=tk.NO)
        self.tree.column("#0", width=10, stretch=tk.NO)
        self.tree.heading("#0", text="", anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        tab_3.grid_columnconfigure(0, weight=1)
        tab_3.grid_rowconfigure(0, weight=1)
        tab_3.grid_columnconfigure(1, weight=0) 

        factoring_buttons_frame = ttk.Frame(tab_3)
        factoring_buttons_frame.grid(row=0, column=1, sticky='ns', padx=(10, 0))

        add_restriction_button = ttk.Button(factoring_buttons_frame, text="Add", command=self.open_factoring_wizard, cursor="hand2")
        add_restriction_button.pack(side="top", pady=(10, 5))
        refresh_factoring_button = ttk.Button(factoring_buttons_frame, text="Refresh", command=self.run_factoring_sheet_thread, cursor="hand2")
        refresh_factoring_button.pack(side="top", pady=(10, 5))
        self.last_refresh_label = ttk.Label(factoring_buttons_frame, text=f"Last Refresh:\n---")
        self.last_refresh_label.pack(side="top", pady=(10, 5))

        self.tab_4 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_4, text="Closure Requests")

        self.requests_frame = ttk.Frame(self.tab_4)
        self.requests_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    def update_notifications(self):
        self.staff_feed.tag_configure("important", font=("TkDefaultFont", 10, "bold"))
        self.staff_feed.config(state='normal')  
        file_lock = fasteners.InterProcessLock('notifications.lock')

        with file_lock:
            try:
                with open('notifications.json', 'r') as f:
                    notifications = json.load(f)

                pinned_notifications = [n for n in notifications if n.get('pinned', False)]
                regular_notifications = [n for n in notifications if not n.get('pinned', False)]

                self.pinned_message.config(state='normal') 
                self.pinned_message.delete('1.0', 'end')  
                if not pinned_notifications:
                    self.pinned_message.insert('end', "No pinned message.\n")
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

    def generate_report(self):
        report_type = self.report_combobox.get()
        if report_type == "Daily Report":
            self.create_daily_report()
        elif report_type == "Staff Report":
            self.create_staff_report()
        elif report_type == "Traders Screener":
            self.update_traders_report()
        elif report_type == "RG Screener":
            self.update_rg_report()
        else:
            pass

    def create_daily_report(self):
        data = get_database()
        report_output = ""
        
        time = datetime.now()
        date = time.strftime("%d/%m/%Y")
        formatted_time = time.strftime("%H:%M:%S")

        # Bets Report
        total_bets = 0
        total_stakes = 0.0
        total_horse_racing_bets = 0
        total_greyhound_bets = 0
        total_other_bets = 0
        # Clients Report
        active_clients = []
        customer_payments = {}
        active_clients_set = set()
        w_clients = set()
        total_w_clients = 0
        m_clients = set()
        total_m_clients = 0
        norisk_clients = set()
        total_norisk_clients = 0
        # List of timestamps to find busiest time of day
        timestamps = []
        hour_ranges = {}
        # Wageralert Report
        total_wageralerts = 0
        price_change = 0
        event_ended = 0
        user_restriction = 0
        price_type_disallowed = 0
        sport_disallowed = 0
        max_stake_exceeded = 0
        other_alert = 0
        liability_exceeded = 0
        wageralert_clients = []
        # SMS Report
        total_sms = 0
        sms_clients = []
        self.progress["maximum"] = len(data)
        self.progress["value"] = 0
        root.update_idletasks()

        for i, bet in enumerate(data):
            self.progress["value"] = i + 1
            root.update_idletasks()

            bet_type = bet['type'].lower()
            is_sms = bet_type == 'sms wager'
            is_bet = bet_type == 'bet'
            is_wageralert = bet_type == 'wager knockback'

            if is_bet:
                bet_customer_reference = bet['customer_ref']
                customer_risk_category = bet['details']['risk_category']
                payment = bet['details']['payment']
                timestamp = bet['time']

                timestamps.append(timestamp)

                if customer_risk_category == 'M':
                    m_clients.add(bet_customer_reference)
                    total_m_clients = len(m_clients)

                elif customer_risk_category == 'W':
                    w_clients.add(bet_customer_reference)
                    total_w_clients = len(w_clients)

                elif customer_risk_category == '-':
                    norisk_clients.add(bet_customer_reference)
                    total_norisk_clients = len(norisk_clients)

                payment_value = float(payment[1:].replace(',', ''))
                total_stakes += payment_value 
                if bet_customer_reference in customer_payments:
                    customer_payments[bet_customer_reference] += payment_value
                else:
                    customer_payments[bet_customer_reference] = payment_value
                active_clients_set.add(bet_customer_reference)
                total_clients = len(active_clients_set)
                active_clients.append(bet_customer_reference)
                total_bets += 1
                
                selection_name = bet['details']['selections'][0][0]

                if re.search(r'\d{2}:\d{2}', selection_name) and 'trap' not in selection_name:  # if the selection name contains a time, it's horse racing
                    total_horse_racing_bets += 1
                elif 'trap' in selection_name.lower():  # if the selection name contains 'trap', it's greyhounds
                    total_greyhound_bets += 1
                else:  # otherwise, it's other sports
                    total_other_bets += 1

            if is_wageralert:
                wageralert_customer_reference = bet['customer_ref']
                knockback_details = bet['details']
                is_alert = False
                for key, value in knockback_details.items():
                    if key == 'Error Message':
                        if 'Price Has Changed' in value:
                            price_change += 1
                            is_alert = True
                        elif 'Liability Exceeded: True' in value:
                            liability_exceeded += 1
                            is_alert = True
                        elif 'Event Has Ended' in value:
                            event_ended += 1
                            is_alert = True
                        elif 'Price Type Disallowed' in value:
                            user_restriction += 1
                            price_type_disallowed += 1
                            is_alert = True
                        elif 'Sport Disallowed' in value:
                            user_restriction += 1
                            sport_disallowed += 1
                            is_alert = True
                        elif 'User Max Stake Exceeded' in value:
                            user_restriction += 1
                            max_stake_exceeded += 1
                            is_alert = True
                            
                if not is_alert:
                    other_alert += 1
                wageralert_clients.append(wageralert_customer_reference)
                total_wageralerts += 1

            if is_sms:
                sms_customer_reference = bet['customer_ref']
                sms_clients.append(sms_customer_reference)
                total_sms += 1

        total_sport_bets = total_horse_racing_bets + total_greyhound_bets + total_other_bets
        percentage_horse_racing = (total_horse_racing_bets / total_sport_bets) * 100
        percentage_greyhound = (total_greyhound_bets / total_sport_bets) * 100
        percentage_other = (total_other_bets / total_sport_bets) * 100

        top_spenders = Counter(customer_payments).most_common(5)
        client_bet_counter = Counter(active_clients)
        top_client_bets = client_bet_counter.most_common(5)
        timestamp_hours = [timestamp.split(':')[0] + ":00" for timestamp in timestamps]
        hour_counts = Counter(timestamp_hours)
        wageralert_counter = Counter(wageralert_clients)
        top_wageralert_clients = wageralert_counter.most_common(3)
        sms_counter = Counter(sms_clients)
        top_sms_clients = sms_counter.most_common(5)


        report_output += f"\tDAILY REPORT TICKET\n\t Generated at {formatted_time}\n"

        report_output += f"\nStakes: £{total_stakes:,.2f} (~£{total_stakes / total_bets:,.2f})\n"
        report_output += f"Bets: {total_bets} | Knockbacks {total_wageralerts} ({total_wageralerts / total_bets * 100:.2f}%)\n"
        report_output += f"Horses: {percentage_horse_racing:.2f}% | Dogs: {percentage_greyhound:.2f}% | Other: {percentage_other:.2f}%\n"

        report_output += f"Clients: {total_clients} | --: {total_norisk_clients} | M: {total_m_clients} | W: {total_w_clients} ({total_m_clients / total_clients * 100:.2f}%)\n"

        report_output += "\nHighest Stakes:\n"
        for rank, (customer, spend) in enumerate(top_spenders, start=1):
            report_output += f"\t{rank}. {customer} - Stakes: £{spend:,.2f}\n"

        report_output += "\nMost Bets:\n"
        for rank, (client, count) in enumerate(top_client_bets, start=1):
            report_output += f"\t{rank}. {client} - Bets: {count}\n"

        report_output += f"\nMost Knockbacks:\n"
        for rank, (client, count) in enumerate(top_wageralert_clients, start=1):
            report_output += f"\t{rank}. {client} - Knockbacks: {count}\n"

        report_output += f"\nBets Per Hour:\n"
        for hour, count in hour_counts.items():
            start_hour = hour
            end_hour = f"{int(start_hour.split(':')[0])+1:02d}:00"
            hour_range = f"{start_hour} - {end_hour}"
            if hour_range in hour_ranges:
                hour_ranges[hour_range] += count
            else:
                hour_ranges[hour_range] = count

        for hour_range, count in hour_ranges.items():
            report_output += f"\t{hour_range} - Bets {count}\n"

        report_output += f"\nKnockbacks by Type:"
        report_output += f"\nLiability: {liability_exceeded}  |  "
        report_output += f"Price Change: {price_change}  |  "
        report_output += f"Event Ended: {event_ended}"

        report_output += f"\n\nUser Restrictions: {user_restriction}\n"
        report_output += f"Price Type: {price_type_disallowed}  |  "
        report_output += f"Sport: {sport_disallowed}  |  "
        report_output += f"Max Stake: {max_stake_exceeded}"

        report_output += f"\n\nTextbets: {total_sms}"
        report_output += f"\n\nMost Textbets: \n"
        for rank, (client, count) in enumerate(top_sms_clients, start=1):
            report_output += f"\t{rank}. {client} - TEXTS: {count}\n"

        report_output += f"\nAll active clients by risk\n\n"

        report_output += f"M Clients: \n"
        for client in m_clients:
            report_output += f"{client}\n"
        report_output += f"\n\nW Clients: \n"
        for client in w_clients:
            report_output += f"{client}\n"
        report_output += f"\n\nNo Risk Clients: \n"
        for client in norisk_clients:
            report_output += f"{client}\n"
        report_output += f"\n\n"

        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)
        self.report_ticket.insert('1.0', report_output)
        self.report_ticket.config(state="disabled")
    
    def create_staff_report(self):
        global USER_NAMES

        report_output = ""
        course_updates = Counter()
        staff_updates = Counter()
        staff_updates_today = Counter()
        factoring_updates = Counter()
        offenders = Counter()
        today = datetime.now().date()
        current_date = datetime.now().date()
        month_ago = current_date.replace(day=1)

        log_files = os.listdir('logs/updatelogs')
        log_files.sort(key=lambda file: os.path.getmtime('logs/updatelogs/' + file))
        self.progress["maximum"] = len(log_files)
        self.progress["value"] = 0
        # Read all the log files from the past month
        for i, log_file in enumerate(log_files):

            self.progress["value"] = i + 1
            root.update_idletasks()

            file_date = datetime.fromtimestamp(os.path.getmtime('logs/updatelogs/' + log_file)).date()
            if month_ago <= file_date <= current_date:
                with open('logs/updatelogs/' + log_file, 'r') as file:
                    lines = file.readlines()

                update_counts = {}

                for line in lines:
                    if line.strip() == '':
                        continue

                    parts = line.strip().split(' - ')

                    if len(parts) == 1 and parts[0].endswith(':'):
                        course = parts[0].replace(':', '')
                        continue

                    if len(parts) == 2:
                        time, staff_initials = parts
                        staff_name = USER_NAMES.get(staff_initials, staff_initials)
                        course_updates[course] += 1
                        staff_updates[staff_name] += 1

                        if file_date == today:
                            current_time = datetime.strptime(time, '%H:%M')
                            if course not in update_counts:
                                update_counts[course] = {}
                            if staff_name not in update_counts[course]:
                                update_counts[course][staff_name] = Counter()
                            update_counts[course][staff_name][current_time] += 1

                            if update_counts[course][staff_name][current_time] > 1:
                                offenders[staff_name] += 1

                            staff_updates_today[staff_name] += 1

        factoring_log_file = os.listdir('logs/factoringlogs')
        factoring_log_file.sort(key=lambda file: os.path.getmtime('logs/factoringlogs/' + file))

        for log_file in factoring_log_file:
            with open('logs/factoringlogs/' + log_file, 'r') as file:
                lines = file.readlines()

            for line in lines:
                if line.strip() == '':
                    continue

                data = json.loads(line)
                staff_initials = data['Staff']
                staff_name = USER_NAMES.get(staff_initials, staff_initials)
                factoring_updates[staff_name] += 1

        report_output += f"\t    STAFF REPORT\n"

        employee_of_the_month, _ = staff_updates.most_common(1)[0]
        report_output += f"\nEmployee Of The Month: {employee_of_the_month}"

        factoring_employee_of_the_month, _ = factoring_updates.most_common(1)[0]
        report_output += f"\nAll Time Factoring Leader: {factoring_employee_of_the_month}\n"

        report_output += "\nToday's Staff Updates:\n"
        for staff, count in sorted(staff_updates_today.items(), key=lambda item: item[1], reverse=True):
            report_output += f"\t{staff}  |  {count}\n"

        report_output += "\nTotal Staff Updates Since " + month_ago.strftime('%d-%m') + ":\n"
        for staff, count in sorted(staff_updates.items(), key=lambda item: item[1], reverse=True):
            report_output += f"\t{staff}  |  {count}\n"

        report_output += "\nAll Time Staff Factoring:\n"
        for staff, count in sorted(factoring_updates.items(), key=lambda item: item[1], reverse=True):
            report_output += f"\t{staff}  |  {count}\n"
        
        report_output += "\nUpdation Offenders Today:\n"
        for staff, count in sorted(offenders.items(), key=lambda item: item[1], reverse=True):
            report_output += f"\t{staff}  |  {count}\n"

        report_output += "\nCourse Updates:\n"
        for course, count in sorted(course_updates.items(), key=lambda item: item[1], reverse=True)[:10]:
            report_output += f"\t{course}  |  {count}\n"

        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)
        self.report_ticket.insert('1.0', report_output)
        self.report_ticket.config(state="disabled")

    def create_rg_report(self):

        data = get_database()
        user_scores = {}
        virtual_events = ['Portman Park', 'Sprintvalley', 'Steepledowns', 'Millersfield', 'Brushwood']

        self.progress["maximum"] = len(data)
        self.progress["value"] = 0

        for bet in data:
            self.progress["value"] += 1

            wager_type = bet.get('type', '').lower()
            if wager_type == 'bet':
                details = bet.get('details', {})
                bet_time = datetime.strptime(bet.get('time', ''), "%H:%M:%S")
                customer_reference = bet.get('customer_ref', '')
                stake = float(details.get('unit_stake', '£0').replace('£', '').replace(',', ''))

                if customer_reference not in user_scores:
                    user_scores[customer_reference] = {
                        'bets': [],
                        'odds': [],
                        'total_bets': 0,
                        'score': 0,
                        'average_stake': 0,
                        'max_stake': 0,
                        'min_stake': float('inf'),
                        'deposits': [],  # New field for storing deposits
                        'min_deposit': None,  # Initialize to None
                        'max_deposit': 0,
                        'total_deposit': 0,
                        'total_stake': 0,
                        'virtual_bets': 0,
                        'early_bets': 0,
                        'scores': {
                            'num_bets': 0,
                            'long_period': 0,
                            'stake_increase': 0,
                            'high_total_stake': 0,
                            'virtual_events': 0,
                            'chasing_losses': 0,
                            'early_hours': 0,
                            'high_deposit_total': 0,
                            'frequent_deposits': 0,
                            'increasing_deposits': 0,
                            'changed_payment_type': 0,
                    }
                }

                # Add the bet to the user's list of bets
                user_scores[customer_reference]['bets'].append((bet_time.strftime("%H:%M:%S"), stake))

                # Add the odds to the user's list of odds
                selections = details.get('selections', [])
                for selection in selections:
                    odds = selection[1]
                    if isinstance(odds, str):
                        if odds.lower() == 'evs':
                            odds = 2.0
                        elif odds.lower() == 'sp':
                            continue
                        else:
                            try:
                                odds = float(odds)
                            except ValueError:
                                continue
                    user_scores[customer_reference]['odds'].append(odds)
                    if any(event in selection[0] for event in virtual_events):
                        user_scores[customer_reference]['virtual_bets'] += 1
                        break

                # Increase the total number of bets
                user_scores[customer_reference]['total_bets'] += 1

                # Update the total stake
                user_scores[customer_reference]['total_stake'] += stake

                # Skip this iteration if the user has placed fewer than 6 bets
                if len(user_scores[customer_reference]['bets']) < 6:
                    continue

                # Update the max and min stakes
                user_scores[customer_reference]['max_stake'] = max(user_scores[customer_reference]['max_stake'], stake)
                user_scores[customer_reference]['min_stake'] = min(user_scores[customer_reference]['min_stake'], stake)

                # Calculate the new average stake
                total_stake = sum(stake for _, stake in user_scores[customer_reference]['bets'])
                user_scores[customer_reference]['average_stake'] = total_stake / len(user_scores[customer_reference]['bets'])

                # Add a point if the user has placed more than 10 bets
                if len(user_scores[customer_reference]['bets']) > 10 and user_scores[customer_reference]['scores']['num_bets'] == 0:
                    user_scores[customer_reference]['scores']['num_bets'] = 1

                # Add a point if the user has been gambling for a long period of time
                first_bet_time = datetime.strptime(user_scores[customer_reference]['bets'][0][0], "%H:%M:%S")
                if (bet_time - first_bet_time).total_seconds() > 2 * 60 * 60 and user_scores[customer_reference]['scores']['long_period'] == 0:  # 2 hours
                    user_scores[customer_reference]['scores']['long_period'] = 1

                # Add a point if the user has increased their stake over the average
                half = len(user_scores[customer_reference]['bets']) // 2
                first_half_stakes = [stake for _, stake in user_scores[customer_reference]['bets'][:half]]
                second_half_stakes = [stake for _, stake in user_scores[customer_reference]['bets'][half:]]
                if len(first_half_stakes) > 0 and len(second_half_stakes) > 0:
                    first_half_avg = sum(first_half_stakes) / len(first_half_stakes)
                    second_half_avg = sum(second_half_stakes) / len(second_half_stakes)
                    if second_half_avg > first_half_avg and user_scores[customer_reference]['scores']['stake_increase'] == 0:
                        user_scores[customer_reference]['scores']['stake_increase'] = 1

                # Add a point if the user's total stake is over £1000
                if user_scores[customer_reference]['total_stake'] > 1000 and user_scores[customer_reference]['scores']['high_total_stake'] == 0:
                    user_scores[customer_reference]['scores']['high_total_stake'] = 1

                # Add a point if the user has placed a bet on a virtual event
                if user_scores[customer_reference]['virtual_bets'] > 0 and user_scores[customer_reference]['scores']['virtual_events'] == 0:
                    user_scores[customer_reference]['scores']['virtual_events'] = 1

                # Check if the bet is placed during early hours
                if 0 <= bet_time.hour < 7:
                    user_scores[customer_reference]['early_bets'] += 1


        now_local = datetime.now(timezone('Europe/London'))
        today_filename = f'logs/depositlogs/deposits_{now_local.strftime("%Y-%m-%d")}.json'

        # Load the existing messages from the JSON file for today's date
        if os.path.exists(today_filename):
            with open(today_filename, 'r') as f:
                deposits = json.load(f)
            
        # Create a dictionary to store deposit information for each user
        deposit_info = defaultdict(lambda: {'total': 0, 'times': [], 'amounts': [], 'types': set()})

        # Iterate over the deposits
        for deposit in deposits:
            username = deposit['Username'].upper()
            amount = float(deposit['Amount'])
            time = datetime.strptime(deposit['Time'], "%Y-%m-%d %H:%M:%S")
            type_ = deposit['Type']

            # Check if the user exists in the user_scores dictionary
            if username not in user_scores:
                user_scores[username] = {
                    'bets': [],
                    'odds': [],
                    'total_bets': 0,
                    'score': 0,
                    'average_stake': 0,
                    'max_stake': 0,
                    'min_stake': float('inf'),
                    'deposits': [],  # New field for storing deposits
                    'min_deposit': None,  # Initialize to None
                    'max_deposit': 0,
                    'total_deposit': 0,
                    'total_stake': 0,
                    'virtual_bets': 0,
                    'early_bets': 0,
                    'scores': {
                        'num_bets': 0,
                        'long_period': 0,
                        'stake_increase': 0,
                        'high_total_stake': 0,
                        'virtual_events': 0,
                        'chasing_losses': 0,
                        'early_hours': 0,
                        'high_deposit_total': 0,
                        'frequent_deposits': 0,
                        'increasing_deposits': 0,
                        'changed_payment_type': 0,
                    }
                }

            # Update the user's deposit information
            deposit_info[username]['total'] += amount
            deposit_info[username]['times'].append(time)
            deposit_info[username]['amounts'].append(amount)
            deposit_info[username]['types'].add(type_)

            user_scores[username]['deposits'].append(amount)

            # Check if the user's total deposit amount is over £500
            if deposit_info[username]['total'] > 500:
                if username not in user_scores:
                    user_scores[username] = {
                        'scores': {
                            'high_deposit_total': 0,
                            # Initialize other fields as needed
                        }
                    }
                user_scores[username]['scores']['high_deposit_total'] = 1

            # Check if the user has deposited more than 4 times in an hour
            deposit_info[username]['times'].sort()
            for i in range(4, len(deposit_info[username]['times'])):
                if (deposit_info[username]['times'][i] - deposit_info[username]['times'][i-4]).total_seconds() <= 3600:
                    if username not in user_scores:
                        user_scores[username] = {'scores': {'frequent_deposits': 0}}
                    user_scores[username]['scores']['frequent_deposits'] = 1
                    break

            # Check if the user's deposits have increased more than twice
            increases = 0
            for i in range(2, len(deposit_info[username]['amounts'])):
                if deposit_info[username]['amounts'][i] > deposit_info[username]['amounts'][i-1] > deposit_info[username]['amounts'][i-2]:
                    increases += 1
            if increases >= 2:
                if username not in user_scores:
                    user_scores[username] = {'scores': {'increasing_deposits': 0}}
                user_scores[username]['scores']['increasing_deposits'] = 1

            # Check if the user has changed payment type
            if len(deposit_info[username]['types']) > 1:
                if username not in user_scores:
                    user_scores[username] = {'scores': {'changed_payment_type': 0}}
                user_scores[username]['scores']['changed_payment_type'] = 1

        for username, info in user_scores.items():
            if info['deposits']:  # Check if the list is not empty
                info['min_deposit'] = min(info['deposits'])
                info['max_deposit'] = max(info['deposits'])
            else:
                info['min_deposit'] = 0
                info['max_deposit'] = 0
            info['total_deposit'] = deposit_info[username]['total']


        # After processing all bets, calculate the early hours score
        for user, scores in user_scores.items():
            if scores['early_bets'] > 3:
                scores['scores']['early_hours'] = 1

        # After processing all bets, calculate the chasing losses score
        for user, scores in user_scores.items():
            num_bets = len(scores['bets'])
            if num_bets >= 5:  # Only calculate if the user has placed at least 5 bets
                split_index = int(num_bets * 0.7)  # Calculate the index to split at 70%
                early_odds = scores['odds'][:split_index]
                late_odds = scores['odds'][split_index:]
                if early_odds and late_odds:  # Check that both lists are not empty
                    early_avg = sum(early_odds) / len(early_odds)
                    late_avg = sum(late_odds) / len(late_odds)
                    if late_avg - early_avg > 4:  # Set the threshold as needed
                        scores['scores']['chasing_losses'] = 1


        # Update the total score
        for user, scores in user_scores.items():
            scores['score'] = sum(scores['scores'].values())
                
        # Filter out the users who have a score of 0
        user_scores = {user: score for user, score in user_scores.items() if score['score'] > 0}

        return user_scores

    def create_traders_report(self):
        # Load today's Oddsmonkey selections
        with open('src/data.json', 'r') as file:
            data = json.load(file)

        todays_oddsmonkey_selections = data['todays_oddsmonkey_selections']

        data = get_database()
        results = []
        selection_to_users = {}
        selection_to_odds = {}
        users_without_risk_category = set()
        enhanced_bets_counter = {}

        self.progress["maximum"] = len(data)
        self.progress["value"] = 0

        for bet in data:
            self.progress["value"] += 1
            wager_type = bet.get('type', '').lower()
            if wager_type == 'bet':
                details = bet.get('details', {})
                bet_time = datetime.strptime(bet.get('time', ''), "%H:%M:%S")
                customer_reference = bet.get('customer_ref', '')
                customer_risk_category = details.get('risk_category', '')

                for selection in details['selections']:
                    selection_name = selection[0]
                    odds = selection[1]

                    # Check if the selection is in the enhanced_places list
                    race_meeting = selection_name.split(' - ')[0]
                    if race_meeting in self.enhanced_places:
                        if customer_reference not in enhanced_bets_counter:
                            enhanced_bets_counter[customer_reference] = 0
                        enhanced_bets_counter[customer_reference] += 1


                    if isinstance(odds, str):
                        if odds == 'SP':
                            continue  
                        elif odds.lower() == 'evs':
                            odds = 2.0  
                        else:
                            odds = float(odds)  

                    selection_tuple = (selection_name,)
                    if selection_tuple not in selection_to_users:
                        selection_to_users[selection_tuple] = set()
                        selection_to_odds[selection_tuple] = []
                    selection_to_users[selection_tuple].add((customer_reference, customer_risk_category))
                    selection_to_odds[selection_tuple].append((customer_reference, odds))

                    actual_selection = selection_name.split(' - ')[-1] if ' - ' in selection_name else selection_name.split(', ')[-1]

                    selection_names = [selection[0] for selection in todays_oddsmonkey_selections.values()]

                    if actual_selection in selection_names:
                        for event, selection in todays_oddsmonkey_selections.items():
                            if selection[0] == actual_selection:
                                if odds > float(selection[1]):
                                    results.append({
                                        'username': customer_reference,
                                        'selection_name': actual_selection,
                                        'user_odds': odds,
                                        'oddsmonkey_odds': float(selection[1])
                                    })

        for selection, users in selection_to_users.items():
            users_with_risk_category = {user for user in users if user[1] and user[1] != '-'}
            users_without_risk_category_for_selection = {user for user in users if not user[1] or user[1] == '-'}

            if len(users_with_risk_category) / len(users) > 0.5:
                users_without_risk_category.update(users_without_risk_category_for_selection)
        
        users_without_risk_category = {user for user in users_without_risk_category}

        return users_without_risk_category, results, enhanced_bets_counter

    def update_rg_report(self):
        print("Updating RG Report")
        user_scores = self.create_rg_report()
        print("RG Report Updated")
        user_scores = dict(sorted(user_scores.items(), key=lambda item: item[1]['score'], reverse=True))
        key_descriptions = {
            'num_bets': 'High Number of Bets',
            'stake_increase': 'Stakes Increasing',
            'virtual_events': 'Bets on Virtual events',
            'chasing_losses': 'Odds Increasing, Possibly Chasing Losses',
            'high_total_stake': 'High Total Stake',
            'early_hours': 'Active in the Early Hours',
            'high_deposit_total': 'Total Deposits Over £500',
            'frequent_deposits': 'More than 4 Deposits in an Hour',
            'increasing_deposits': 'Deposits Increasing',
            'changed_payment_type': 'Changed Payment Type'
        }

        report_output = ""
        report_output += f"\tRG SCREENER\n\n"

        for user, scores in user_scores.items():
            if scores['score'] > 1:
                report_output += f"\n{user} - Risk Score: {scores['score']}\n"
                report_output += f"This score is due to:\n"
                for key, value in scores['scores'].items():
                    if value == 1:
                        report_output += f"- {key_descriptions.get(key, key)}\n"
                report_output += f"\nBets: {scores['total_bets']}  |  "
                report_output += f"Total Stake: £{scores['total_stake']:.2f}\n"
                report_output += f"Avg Stake: £{scores['average_stake']:.2f}  |  "
                report_output += f"Max: £{scores['max_stake']:.2f}  |  "
                report_output += f"Min: £{scores['min_stake']:.2f}\n"
                report_output += f"Virtual Bets: {scores['virtual_bets']}  |  "
                report_output += f"Early Hours Bets: {scores['early_bets']}\n"
                report_output += f"Deposits: £{scores['total_deposit']:.2f}  |  "
                report_output += f"Max: £{scores['max_deposit']:.2f}  |  "
                report_output += f"Min: £{scores['min_deposit']:.2f}\n"
                report_output += "\n"

        self.report_ticket.config(state='normal')
        self.report_ticket.delete('1.0', tk.END)
        self.report_ticket.insert(tk.END, report_output)
        self.report_ticket.config(state='disabled')

    def update_traders_report(self):
        users_without_risk_category, oddsmonkey_traders, enhanced_bets_counter = self.create_traders_report()

        username_counts = Counter(trader['username'] for trader in oddsmonkey_traders)
        top_users = username_counts.most_common(6)
        top_enhanced_users = {user for user, count in enhanced_bets_counter.items() if count > 3}


        users_without_risk_category_str = '  |  '.join(user[0] for user in users_without_risk_category)

        self.report_ticket.config(state='normal')
        self.report_ticket.delete('1.0', tk.END)
        self.report_ticket.insert(tk.END, "\tTRADERS SCREENER\n\n")

        self.report_ticket.insert(tk.END, "Please do your own research before taking any action.\n\n")

        self.report_ticket.insert(tk.END, "Clients backing selections shown on OddsMonkey above the lay price:\n")
        for user, count in top_users:
            self.report_ticket.insert(tk.END, f"\t{user}, Count: {count}\n")

        self.report_ticket.insert(tk.END, "\nClients wagering frequently on Extra Place Races:\n\n")
        for user in sorted(top_enhanced_users, key=enhanced_bets_counter.get, reverse=True):  # Sort by count
            self.report_ticket.insert(tk.END, f"\t{user}, Count: {enhanced_bets_counter[user]}\n")

        self.report_ticket.insert(tk.END, "\nClients wagering on selections containing multiple risk users:\n\n")
        self.report_ticket.insert(tk.END, users_without_risk_category_str)

        #traders_report_ticket.insert(tk.END, "\n\nList of users taking higher odds than Oddsmonkey:\n")
        #for trader in oddsmonkey_traders:
        #    traders_report_ticket.insert(tk.END, f"{trader['username']}, Selection: {trader['selection_name']}\nOdds Taken: {trader['user_odds']}, Lay Odds: {trader['oddsmonkey_odds']}\n\n")

        self.report_ticket.config(state='disabled')

    def run_factoring_sheet_thread(self):
        self.factoring_thread = threading.Thread(target=self.factoring_sheet)
        self.factoring_thread.start()

    def factoring_sheet(self):
        self.tree.delete(*self.tree.get_children())
        spreadsheet = self.gc.open('Factoring Diary')
        print("Getting Factoring Sheet")
        worksheet = spreadsheet.get_worksheet(4)
        data = worksheet.get_all_values()
        print("Retrieving factoring data")
        self.last_refresh_label.config(text=f"Last Refresh:\n{datetime.now().strftime('%H:%M:%S')}")
        for row in data[2:]:
            self.tree.insert("", "end", values=[row[5], row[0], row[1], row[2], row[3], row[4]])

    def open_factoring_wizard(self):
        global user
        if not user:
            user_login()

        progress = IntVar()
        progress.set(0)

        def handle_submit():
            current_time = datetime.now().strftime("%H:%M:%S")
            current_date = datetime.now().strftime("%d/%m/%Y")

            if not entry1.get() or not entry3.get():
                messagebox.showerror("Error", "Please make sure all fields are completed.")
                return
            
            try:
                float(entry3.get())
            except ValueError:
                messagebox.showerror("Error", "Assessment rating should be a number.")
                return
            
            params = {
                'term': entry1.get(),
                'item_types': 'person',
                'fields': 'custom_fields',
                'exact_match': 'true',
            }

            progress.set(10)

            copy_string = ""
            if entry2.get() in ["W - WATCHLIST", "M - BP ONLY NO OFFERS", "X - SP ONLY NO OFFERS", "S - SP ONLY", "D - BP ONLY", "O - NO OFFERS"]:
                copy_string = f"{current_date} - {entry2.get().split(' - ')[1]} {user}"

            pyperclip.copy(copy_string)

            factoring_note.config(text="Applying to User on Pipedrive...\n\n", anchor='center', justify='center')
            response = requests.get(self.pipedrive_api_url, params=params)
            progress.set(20)
            if response.status_code == 200:
                persons = response.json()['data']['items']
                if not persons:
                    messagebox.showerror("Error", f"No persons found for username: {entry1.get()}. Please make sure the username is correct, or enter the risk category in pipedrive manually.")
                    return

                for person in persons:
                    person_id = person['item']['id']

                    update_url = f'https://api.pipedrive.com/v1/persons/{person_id}?api_token={self.pipedrive_api_token}'
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
            
            progress.set(30)

            factoring_note.config(text="Factoring Applied on Pipedrive.\nReporting on Factoring Log...\n", anchor='center', justify='center')

            spreadsheet = self.gc.open('Factoring Diary')
            worksheet = spreadsheet.get_worksheet(4)
            
            factoring_note.config(text="Adding entry to Factoring Log...\n\n", anchor='center', justify='center')

            next_row = len(worksheet.col_values(1)) + 1
            progress.set(40)
            entry2_value = entry2.get().split(' - ')[0]
            worksheet.update_cell(next_row, 1, current_time)
            worksheet.update_cell(next_row, 2, entry1.get().upper())
            worksheet.update_cell(next_row, 3, entry2_value)
            worksheet.update_cell(next_row, 4, entry3.get())
            worksheet.update_cell(next_row, 5, user) 
            worksheet.update_cell(next_row, 6, current_date)

            worksheet3 = spreadsheet.get_worksheet(3)
            username = entry1.get().upper()
            factoring_note.config(text="Trying to find user in Factoring Diary...\n\n", anchor='center', justify='center')
            matching_cells = worksheet3.findall(username, in_column=2)
            progress.set(50)

            if not matching_cells:
                messagebox.showerror("Error", f"No client found for username: {username} in factoring diary. This may be due to them being a recent registration. Factoring reported to log, but not to diary.")
            else:
                factoring_note.config(text="Found user in factoring Diary.\nUpdating...\n", anchor='center', justify='center')
                cell = matching_cells[0]
                row = cell.row
                worksheet3.update_cell(row, 9, entry2_value)  # Column I
                worksheet3.update_cell(row, 10, entry3.get())  # Column J
                worksheet3.update_cell(row, 12, current_date)  # Column L
            progress.set(60)
            factoring_note.config(text="Factoring Added Successfully.\n\n", anchor='center', justify='center')
            self.tree.insert("", "end", values=[current_date, current_time, entry1.get().upper(), entry2_value, entry3.get(), user])
            progress.set(70)
            data = {
                'Time': current_time,
                'Username': entry1.get().upper(),
                'Risk Category': entry2_value,
                'Assessment Rating': entry3.get(),
                'Staff': user
            }
            progress.set(80)
            with open(f'logs/factoringlogs/factoring.json', 'a') as file:
                file.write(json.dumps(data) + '\n')

            log_notification(f"{user} Factored {entry1.get().upper()} - {entry2_value} - {entry3.get()}")
            progress.set(100)
            time.sleep(.5)
            wizard_window.destroy()

        wizard_window = tk.Toplevel(root)
        wizard_window.geometry("270x370")
        wizard_window.title("Add Factoring")
        wizard_window.iconbitmap('src/splash.ico')

        screen_width = wizard_window.winfo_screenwidth()
        wizard_window.geometry(f"+{screen_width - 350}+50")

        wizard_window_frame = ttk.Frame(wizard_window, style='Card')
        wizard_window_frame.place(x=5, y=5, width=260, height=360)

        username = ttk.Label(wizard_window_frame, text="Client Username")
        username.pack(padx=5, pady=5)
        entry1 = ttk.Entry(wizard_window_frame)
        entry1.pack(padx=5, pady=5)

        riskcat = ttk.Label(wizard_window_frame, text="Risk Category")
        riskcat.pack(padx=5, pady=5)

        options = ["", "W - WATCHLIST", "M - BP ONLY NO OFFERS", "X - SP ONLY NO OFFERS", "S - SP ONLY", "D - BP ONLY", "O - NO OFFERS"]
        entry2 = ttk.Combobox(wizard_window_frame, values=options, state="readonly")
        entry2.pack(padx=5, pady=5)
        entry2.set(options[0])
        
        ass_rating = ttk.Label(wizard_window_frame, text="Assessment Rating")
        ass_rating.pack(padx=5, pady=5)
        entry3 = ttk.Entry(wizard_window_frame)
        entry3.pack(padx=5, pady=5)

        factoring_note = ttk.Label(wizard_window_frame, text="Risk Category will be updated in Pipedrive.\n\n", anchor='center', justify='center')
        factoring_note.pack(padx=5, pady=5)

        submit_button = ttk.Button(wizard_window_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2")
        submit_button.pack(padx=5, pady=5)

        progress_bar = ttk.Progressbar(wizard_window_frame, length=200, mode='determinate', variable=progress)
        progress_bar.pack(padx=5, pady=5)

    def display_closure_requests(self):
        for widget in self.requests_frame.winfo_children():
            widget.destroy()

        def handle_request(request):
            log_notification(f"{user} Handling {request['Restriction']} request for {request['Username']} ")

            restriction_mapping = {
                'Further Options': 'Self Exclusion'
            }

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
                if self.confirm_betty_update_bool.get():
                    try:
                        if self.send_confirmation_email_bool.get():
                            threading.Thread(target=self.send_email, args=(request['Username'], request['Restriction'], request['Length'])).start()
                    except Exception as e:
                        print(f"Error sending email: {e}")

                    try:
                        if self.archive_email_bool.get():
                            threading.Thread(target=self.archive_email, args=(request['email_id'],)).start()
                    except Exception as e:
                        print(f"Error archiving email: {e}")

                    try:
                        threading.Thread(target=self.report_closure_requests, args=(request['Restriction'], request['Username'], request['Length'])).start()
                    except Exception as e:
                        print(f"Error reporting closure requests: {e}")

                    request['completed'] = True

                    with open('src/data.json', 'w') as f:
                        json.dump(data, f, indent=4)

                    handle_closure_request.destroy()

                    if request['completed']:
                        self.display_closure_requests()

                else:
                    messagebox.showerror("Error", "Please confirm that the client has been updated in Betty.")


            handle_closure_request = tk.Toplevel(root)
            handle_closure_request.geometry("270x410")
            handle_closure_request.title("Closure Request")
            handle_closure_request.iconbitmap('src/splash.ico')
            screen_width = handle_closure_request.winfo_screenwidth()
            handle_closure_request.geometry(f"+{screen_width - 350}+50")
            
            handle_closure_request_frame = ttk.Frame(handle_closure_request, style='Card')
            handle_closure_request_frame.place(x=5, y=5, width=260, height=400)

            username = ttk.Label(handle_closure_request_frame, text=f"Username: {request['Username']}\nRestriction: {request['Restriction']}\nLength: {request['Length'] if request['Length'] not in [None, 'Null'] else '-'}",  anchor='center', justify='center')
            username.pack(padx=5, pady=5)

            confirm_betty_update = ttk.Checkbutton(handle_closure_request_frame, text='Confirm Closed on Betty', variable=self.confirm_betty_update_bool, onvalue=True, offvalue=False, cursor="hand2")
            confirm_betty_update.place(x=10, y=80)

            send_confirmation_email = ttk.Checkbutton(handle_closure_request_frame, text='Send Pipedrive Confirmation Email', variable=self.send_confirmation_email_bool, onvalue=True, offvalue=False, cursor="hand2")
            send_confirmation_email.place(x=10, y=110)

            if user == 'DF':
                archive_email_check = ttk.Checkbutton(handle_closure_request_frame, text='Archive Email Request', variable=self.archive_email_bool, onvalue=True, offvalue=False, cursor="hand2")
                archive_email_check.place(x=10, y=140)

            submit_button = ttk.Button(handle_closure_request_frame, text="Submit", command=handle_submit, cursor="hand2")
            submit_button.place(x=80, y=190)

            closure_request_label = ttk.Label(handle_closure_request_frame, text=f"Close on Betty before anything else!\n\nPlease double check:\n- Request details above are correct\n- Confirmation email was sent to client.\n\nReport to Sam any errors.", anchor='center', justify='center')
            closure_request_label.place(x=10, y=240)

        with open('src/data.json', 'r') as f:
            data = json.load(f)
            requests = [request for request in data.get('closures', []) if not request.get('completed', False)]

        if not requests:
            ttk.Label(self.requests_frame, text="No exclusion/deactivation requests.", anchor='center', justify='center').grid(row=0, column=1, padx=10, pady=2)
        
        restriction_mapping = {
            'Account Deactivation': 'Deactivation',
            'Further Options': 'Self Exclusion'
        }

        for i, request in enumerate(requests):
            restriction = restriction_mapping.get(request['Restriction'], request['Restriction'])

            length = request['Length'] if request['Length'] not in [None, 'Null'] else ''

            request_label = ttk.Label(self.requests_frame, text=f"{restriction} | {request['Username']} | {length}", width=40)
            request_label.grid(row=i, column=1, padx=10, pady=2, sticky="w")

            tick_button = ttk.Button(self.requests_frame, text="✔", command=lambda request=request: handle_request(request), width=2, cursor="hand2")
            tick_button.grid(row=i, column=0, padx=3, pady=2)

        root.after(20000, self.display_closure_requests)

    def update_person(self, update_url, update_data, person_id):
        update_response = requests.put(update_url, json=update_data)
        print(update_url, update_data, person_id)

        if update_response.status_code == 200:
            print(f'Successfully updated person {person_id}')
        else:
            print(f'Error updating person {person_id}: {update_response.status_code}')
            print(f'Response: {update_response.json()}')

    def send_email(self, username, restriction, length):
        print(username, restriction, length)

        params = {
            'term': username,
            'item_types': 'person',
            'fields': 'custom_fields',
            'exact_match': 'true',
        }

        try:
            response = requests.get(self.pipedrive_api_url, params=params)
            response.raise_for_status()
        except requests.exceptions.HTTPError as errh:
            print ("Http Error:",errh)
            return
        except requests.exceptions.ConnectionError as errc:
            print ("Error Connecting:",errc)
            return
        except requests.exceptions.Timeout as errt:
            print ("Timeout Error:",errt)
            return
        except requests.exceptions.RequestException as err:
            print ("Something went wrong",err)
            return

        persons = response.json()['data']['items']
        if not persons:
            messagebox.showerror("Error", f"No persons found for username: {username}. Please make sure the username is correct, or apply the exclusion manually.")
            return

        ## This is Ridiculous
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

        for person in persons:
            person_id = person['item']['id']
            update_url = f'https://api.pipedrive.com/v1/persons/{person_id}?api_token={self.pipedrive_api_token}'

            if restriction == 'Account Deactivation':
                update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': "Deactivated"}
                self.update_person(update_url, update_data, person_id)

            elif restriction == 'Further Options':
                if length.split()[0] in number_mapping:
                    digit_length = length.replace(length.split()[0], number_mapping[length.split()[0]])
                    update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'SE {digit_length}'}
                    self.update_person(update_url, update_data, person_id)
                else:
                    print("Error: Invalid length")

            elif restriction == 'Take-A-Break':
                if length.split()[0] in number_mapping:
                    digit_length = length.replace(length.split()[0], number_mapping[length.split()[0]])
                    update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'TAB {digit_length}'}
                    self.update_person(update_url, update_data, person_id)
                else:
                    print("Error: Invalid length")
        
    def archive_email(self, msg_id):
        creds = None

        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json')
        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.modify'])
                    creds = flow.run_local_server(port=0)
            except RefreshError:
                print("The access token has expired or been revoked. Please re-authorize the app.")
                flow = InstalledAppFlow.from_client_secrets_file(
                    'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.modify'])
                creds = flow.run_local_server(port=0)

            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        service = build('gmail', 'v1', credentials=creds)

        message = service.users().messages().get(userId='me', id=msg_id).execute()
        current_labels = message['labelIds']

        return service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={
            'removeLabelIds': current_labels
        }
        ).execute()

    def report_closure_requests(self, restriction, username, length):
        current_date = datetime.now().strftime("%d/%m/%Y")  


        try:
            spreadsheet = self.gc.open("Management Tool")
        except gspread.SpreadsheetNotFound:
            messagebox.showerror("Error", f"Spreadsheet 'Management Tool' not found. Please notify Sam, or enter the exclusion details manually.")
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

    def generate_random_string(self):
        random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        generated_string = 'GB' + random_numbers
        
        return generated_string

    def copy_to_clipboard(self):
        self.generated_string = self.generate_random_string()
        
        pyperclip.copy(self.generated_string)
        
        self.password_result_label.config(text=f"{self.generated_string}")
        self.copy_button.config(state=tk.NORMAL)

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

        self.version_label = ttk.Label(self.settings_frame, text="v10.2", font=("Helvetica", 10))
        self.version_label.pack(pady=(0, 7))
        
        self.separator = ttk.Separator(self.settings_frame, orient='horizontal')
        self.separator.pack(fill='x', pady=5)

        self.current_user_label = ttk.Label(self.settings_frame, text="", font=("Helvetica", 10))
        self.current_user_label.pack()

        if user:
            self.current_user_label.config(text=f"Logged in as: {user}")

        self.separator = ttk.Separator(self.settings_frame, orient='horizontal')
        self.separator.pack(fill='x', pady=5)
        
        self.set_database_label = ttk.Label(self.settings_frame, text="Set Database", font=("Helvetica", 10))
        self.set_database_label.pack(pady=(6, 0))

        database_files = [f for f in os.listdir('database') if f.endswith('.json')]
        formatted_dates = [f.split('-wager_database')[0] for f in database_files]
        formatted_dates.sort(reverse=True) 

        self.databases_frame = ttk.Frame(self.settings_frame)
        self.databases_frame.pack(pady=5)

        self.databases_combobox = ttk.Combobox(self.databases_frame, values=formatted_dates, width=10, state='readonly')
        self.databases_combobox.grid(row=0, column=0, padx=(0, 3))
        self.databases_combobox.bind("<<ComboboxSelected>>", self.update_current_database)

        self.reset_database_button = ttk.Button(self.databases_frame, text="↻", command=self.reset_database, cursor="hand2", width=2)
        self.reset_database_button.grid(row=0, column=1)

        self.separator = ttk.Separator(self.settings_frame, orient='horizontal')
        self.separator.pack(fill='x', pady=5)

        self.view_events_button = ttk.Button(self.settings_frame, text="Live Events", command=self.show_live_events, cursor="hand2", width=12)
        self.view_events_button.pack(pady=(4, 0))

    def update_current_database(self, event):
        global current_database
        current_database = self.databases_combobox.get()

    def reset_database(self):
        global current_database
        current_database = None
        self.databases_combobox.set('')

    def fetch_and_save_events(self):
        url = 'https://globalapi.geoffbanks.bet/api/Geoff/GetSportApiData?sportcode=f,s,N,t,m,G,C,K,v,R,r,l,I,D,j,S,q,a,p,T,e,k,E,b,A,Y,n,c,y,M,F'
        
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

        if os.path.exists('events.json'):
            with open('events.json', 'r') as f:
                existing_data = json.load(f)
        else:
            messagebox.showerror("Error", "Events file not found.")
            return None

        existing_data_map = {event['eventName']: event for event in existing_data}

        for event in data:
            existing_event = existing_data_map.get(event['eventName'])
            if existing_event:
                event['lastUpdate'] = existing_event.get('lastUpdate', '-')
                event['user'] = existing_event.get('user', '-')
            else:
                event['lastUpdate'] = '-'
                event['user'] = '-'

        with open('events.json', 'w') as f:
            json.dump(data, f, indent=4)

        return data

    def show_live_events(self):
        data = self.fetch_and_save_events()

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

            tree["columns"] = ("eventFile", "numChildren", "eventDate", "lastUpdate", "user")
            tree.column("#0", width=200, minwidth=200)
            tree.column("eventFile", width=50, minwidth=50)
            tree.column("numChildren", width=50, minwidth=50)
            tree.column("eventDate", width=50, minwidth=50)
            tree.column("lastUpdate", width=120, minwidth=120)
            tree.column("user", width=10, minwidth=10)
            tree.heading("#0", text="Event Name", anchor=tk.W)
            tree.heading("eventFile", text="Event File", anchor=tk.W)
            tree.heading("numChildren", text="Markets", anchor=tk.W)
            tree.heading("eventDate", text="Event Date", anchor=tk.W)
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
                        if event['eventName'] == event_name:
                            event['lastUpdate'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                            event['user'] = user
                            log_notification(f"{user} updated {event_name}")
                            self.log_update(event_name, event['lastUpdate'], user)
                            break

                with open('events.json', 'w') as f:
                    json.dump(data, f, indent=4)

                self.populate_tree(tree, data)

            action_button = ttk.Button(live_events_frame, text="Update Event", command=on_button_click)
            action_button.pack(pady=10)
            update_events_label = ttk.Label(live_events_frame, text="Select an event (or multiple) and click 'Update Event' to log latest refresh.", wraplength=600)
            update_events_label.pack(pady=5)
            not_included_events_label = ttk.Label(live_events_frame, text="Not included: AUS Soccer, Bowls, GAA, US Motorsport, Numbers (49s), Special/Other, Virtuals.", wraplength=600)
            not_included_events_label.pack(pady=2)
        else:
            messagebox.showerror("Error", "Failed to fetch events. Please tell Sam.")

    def populate_tree(self, tree, data):
        # Clear existing tree items
        for item in tree.get_children():
            tree.delete(item)

        sorted_data = self.sort_events(data)

        for event in sorted_data:
            event_name = event["eventName"]
            event_file = event["meetings"][0]["eventFile"] if event["meetings"] else ""
            num_children = len(event["meetings"])
            last_update = event.get("lastUpdate", "-")
            user = event.get("user", "-")
            parent_id = tree.insert("", "end", text=event_name, values=(event_file, num_children, "", last_update, user))
            for meeting in event["meetings"]:
                meeting_name = meeting["meetinName"]
                event_date = meeting["eventDate"]
                tree.insert(parent_id, "end", text=meeting_name, values=("", "", event_date, "", ""))

    def sort_events(self, data):
        antepost_events = [event for event in data if len(event["meetings"]) > 0 and event["meetings"][0]["eventFile"][3:5].lower() == 'ap']
        non_antepost_events = [event for event in data if not (len(event["meetings"]) > 0 and event["meetings"][0]["eventFile"][3:5].lower() == 'ap')]
        return antepost_events + non_antepost_events

    def log_update(self, course, full_time, user):
        # Extract just the time in HH:MM format
        log_time = datetime.strptime(full_time, '%d-%m-%Y %H:%M:%S').strftime('%H:%M')

        now = datetime.now()
        date_string = now.strftime('%d-%m-%Y')
        log_file = f'logs/updatelogs/update_log_{date_string}.txt'

        # Ensure the directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                data = f.readlines()
        else:
            data = []

        update = f"{log_time} - {user}\n"

        course_index = None
        for i, line in enumerate(data):
            if line.strip() == course + ":":
                course_index = i
                break

        if course_index is not None:
            data.insert(course_index + 1, update)
        else:
            if data and not data[-1].endswith('\n'):
                data.append('\n')
            data.append(f"{course}:\n")
            data.append(update)

        with open(log_file, 'w') as f:
            f.writelines(data)

class Next3Panel:
    def __init__(self, root):
        self.root = root
        self.last_click_time = 0 
        _, _, _, _, reporting_data = access_data()
        self.enhanced_places = reporting_data.get('enhanced_places', [])
        self.horse_url = 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h,o'
        self.horse_url_indicator = ' ALL'
        self.initialize_ui()
        self.run_display_next_3()
    
    def run_display_next_3(self):
        threading.Thread(target=self.display_next_3, daemon=True).start()
        self.root.after(10000, self.run_display_next_3)

    def toggle_horse_url(self, event=None):
        current_time = time.time()

        if current_time - self.last_click_time < 1.5:
            print("Click too fast, ignoring.")
            return
        
        self.last_click_time = current_time

        if self.horse_url == 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h,o':
            self.horse_url_indicator = 'UK/IR'
            self.horse_url = 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h'
        else:
            self.horse_url_indicator = ' ALL'
            self.horse_url = 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h,o'
            
        print("Horse URL changed to:", self.horse_url)
        self.display_next_3()
        self.update_horse_url_indicator()
    
    def initialize_ui(self):
        next_races_frame = ttk.Frame(self.root)
        next_races_frame.place(x=5, y=927, width=890, height=55)

        horses_frame = ttk.Frame(next_races_frame, style='Card', cursor="hand2")
        horses_frame.place(relx=0, rely=0.05, relwidth=0.55, relheight=0.9)
        horses_frame.bind("<Button-1>", self.toggle_horse_url)

        horses_frame.columnconfigure(0, weight=1)
        horses_frame.columnconfigure(1, weight=1)
        horses_frame.columnconfigure(2, weight=1)
        horses_frame.columnconfigure(3, weight=1) 
        horses_frame.columnconfigure(4, weight=1)

        horses_frame.rowconfigure(0, weight=1)

        self.horse_labels = [ttk.Label(horses_frame, justify='center', font=("Helvetica", 8, "bold")) for _ in range(3)]
        for i, label in enumerate(self.horse_labels):
            label.grid(row=0, column=i)  
            label.bind("<Button-1>", self.toggle_horse_url) 

        Separator = ttk.Separator(horses_frame, orient='vertical')
        Separator.grid(row=0, column=3, sticky='ns')

        self.horse_url_indicator_label = ttk.Label(horses_frame, text=self.horse_url_indicator, font=("Helvetica", 9, "bold"), width=3, cursor="hand2", justify='center')
        self.horse_url_indicator_label.grid(row=0, column=4, sticky='ew', padx=1) 
        self.horse_url_indicator_label.bind("<Button-1>", self.toggle_horse_url)

        greyhounds_frame = ttk.Frame(next_races_frame, style='Card')
        greyhounds_frame.place(relx=0.56, rely=0.05, relwidth=0.44, relheight=0.9)

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


    def update_horse_url_indicator(self):
        self.horse_url_indicator_label.config(text=self.horse_url_indicator)

    def display_next_3(self):
        headers = {"User-Agent": "Mozilla/5.0 ..."}
        horse_response = requests.get(self.horse_url, headers=headers)
        greyhound_response = requests.get('https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=g', headers=headers)

        if horse_response.status_code == 200 and greyhound_response.status_code == 200:
            horse_data = horse_response.json()
            greyhound_data = greyhound_response.json()

            self.root.after(0, self.process_data, horse_data, 'horse')
            self.root.after(0, self.process_data, greyhound_data, 'greyhound')
        else:
            print("Error: The response from the API is not OK.")
                 
class BetViewerApp:
    def __init__(self, root):
        self.root = root

        # Initialize Google Sheets API client
        self.initialize_gspread()

        threading.Thread(target=schedule_data_updates, daemon=True).start()
        self.initialize_ui()
        user_login()
        self.bet_feed = BetFeed(root)
        self.bet_runs = BetRuns(root)
        self.race_updation = RaceUpdaton(root)
        self.next3_panel = Next3Panel(root)
        self.notebook = Notebook(root)
        self.settings = Settings(root)

    def initialize_gspread(self):
        with open('src/creds.json') as f:
            data = json.load(f)
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(data, scope)
        self.gc = gspread.authorize(credentials)

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
        self.root.resizable(True, True)
        self.import_logo()
        self.setup_menu_bar()

    def import_logo(self):
        logo_image = Image.open('src/splash.ico')
        logo_image.thumbnail((70, 70))
        self.company_logo = ImageTk.PhotoImage(logo_image)
        self.root.iconbitmap('src/splash.ico')

    def setup_menu_bar(self):
        menu_bar = tk.Menu(self.root)
        # Options Menu
        options_menu = tk.Menu(menu_bar, tearoff=0)
        options_menu.add_command(label="Set User Initials", command=self.user_login, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Settings", command=self.open_settings, foreground="#000000", background="#ffffff")
        options_menu.add_separator(background="#ffffff")
        options_menu.add_command(label="Exit", command=root.quit, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Options", menu=options_menu)
        
        # Additional Features Menu
        menu_bar.add_command(label="Report Freebet", command=self.report_freebet, foreground="#000000", background="#ffffff")
        menu_bar.add_command(label="Send RG Popup", command=self.display_rg_popup, foreground="#000000", background="#ffffff")
        menu_bar.add_command(label="About", command=self.about, foreground="#000000", background="#ffffff")

        self.root.config(menu=menu_bar)

    def user_login(self):
        user_login()

    def report_freebet(self):
        current_month = datetime.now().strftime('%B')
        global user
        if not user:
            user_login()

        progress = IntVar()
        progress.set(0)

        def handle_submit():
            if not entry1.get() or not entry2.get() or not entry3.get():
                messagebox.showerror("Error", "Please make sure all fields are completed.")
                return 
            
            try:
                float(entry3.get())
            except ValueError:
                messagebox.showerror("Error", "Freebet amount should be a number.")
                return

            spreadsheet_name = 'Reporting ' + current_month
            try:
                spreadsheet = self.gc.open(spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                messagebox.showerror("Error", f"Spreadsheet '{spreadsheet_name}' not found. Please make sure the spreadsheet is available, or enter the freebet details manually.")
                return

            progress.set(20)

            freebet_note.config(text=f"Found {spreadsheet_name}.\nFree bet for {entry1.get().upper()} being added.\n", anchor='center', justify='center')

            worksheet = spreadsheet.get_worksheet(5)
            next_row = len(worksheet.col_values(2)) + 1

            progress.set(50)

            current_date = datetime.now().strftime("%d/%m/%Y")  
            worksheet.update_cell(next_row, 2, current_date)
            progress.set(60)
            worksheet.update_cell(next_row, 5, entry1.get().upper())
            progress.set(70)
            worksheet.update_cell(next_row, 3, entry2.get().upper())
            progress.set(80)
            worksheet.update_cell(next_row, 6, entry3.get())
            progress.set(100)

            freebet_note.config(text=f"Free bet for {entry1.get().upper()} added successfully.\n\n", anchor='center', justify='center')
            log_notification(f"{user} applied £{entry3.get()} {entry2.get().capitalize()} to {entry1.get().upper()}")
            time.sleep(.5)
            report_freebet_window.destroy()

        report_freebet_window = tk.Toplevel(root)
        report_freebet_window.geometry("270x370")
        report_freebet_window.title("Report a Free Bet")
        report_freebet_window.iconbitmap('src/splash.ico')
        screen_width = report_freebet_window.winfo_screenwidth()
        report_freebet_window.geometry(f"+{screen_width - 350}+50")
        
        report_freebet_frame = ttk.Frame(report_freebet_window, style='Card')
        report_freebet_frame.place(x=5, y=5, width=260, height=360)

        username = ttk.Label(report_freebet_frame, text="Client Username")
        username.pack(padx=5, pady=5)
        entry1 = ttk.Entry(report_freebet_frame)
        entry1.pack(padx=5, pady=5)

        type = ttk.Label(report_freebet_frame, text="Free bet Type")
        type.pack(padx=5, pady=5)
        options = ["", "FREE BET", "DEPOSIT BONUS", "10MIN BLAST", "OTHER"]
        entry2 = ttk.Combobox(report_freebet_frame, values=options, state="readonly")
        entry2.pack(padx=5, pady=5)
        entry2.set(options[0])

        amount = ttk.Label(report_freebet_frame, text="Amount")
        amount.pack(padx=5, pady=5)
        entry3 = ttk.Entry(report_freebet_frame)
        entry3.pack(padx=5, pady=5)

        freebet_note = ttk.Label(report_freebet_frame, text=f"Free bet will be added to reporting {current_month}.\n\n", anchor='center', justify='center')
        freebet_note.pack(padx=5, pady=5)

        submit_button = ttk.Button(report_freebet_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2")    
        submit_button.pack(padx=5, pady=5)

        progress_bar = ttk.Progressbar(report_freebet_frame, length=200, mode='determinate', variable=progress)
        progress_bar.pack(padx=5, pady=5)

    def display_rg_popup(self):
        # Load credentials and Pipedrive API token
        with open('src/creds.json') as f:
            data = json.load(f)
        pipedrive_api_token = data['pipedrive_api_key']

        custom_field_id = 'acb5651370e1c1efedd5209bda3ff5ceece09633'  # Your custom field ID

        def handle_submit():
            today = date.today()

            if not entry1.get():
                messagebox.showerror("Error", "Please make sure you enter a username.")
                return 
            
            # Get the provided username
            username = entry1.get().strip()
            
            # Search for the person using the provided username
            search_url = f'https://api.pipedrive.com/v1/persons/search?api_token={pipedrive_api_token}'
            params = {
                'term': username,
                'item_types': 'person',
                'fields': 'custom_fields',
                'exact_match': 'true'
            }

            response = requests.get(search_url, params=params)
            if response.status_code == 200:
                persons = response.json().get('data', {}).get('items', [])

                if not persons:
                    messagebox.showerror("Error", f"No persons found for username: {username}. Please make sure the username is correct, or enter the risk category in Pipedrive manually.")
                    return

                for person in persons:
                    person_id = person['item']['id']
                    update_url = f'https://api.pipedrive.com/v1/persons/{person_id}?api_token={pipedrive_api_token}'
                    update_data = {
                        custom_field_id: today.strftime('%m/%d/%Y')
                    }
                    update_response = requests.put(update_url, json=update_data)
                    if update_response.status_code == 200:
                        wizard_window.destroy()
                        log_notification(f"{user} applied RG Popup to {username.upper()}", True)
                        self.report_rg_notification(username.upper())
                    else:
                        messagebox.showerror("Error", f"Error updating person {person_id}: {update_response.status_code}")
            else:
                print(f'Error: {response.status_code}')

        def fetch_usernames_and_compliance_dates():
            filter_id = 65  # Your filter ID
            filter_url = f'https://api.pipedrive.com/v1/persons?filter_id={filter_id}&api_token={pipedrive_api_token}'
            response = requests.get(filter_url)
            if response.status_code == 200:
                persons = response.json().get('data', [])
                user_data = [(person['c1f84d7067cae06931128f22af744701a07b29c6'], person.get(custom_field_id, 'N/A')) for person in persons]
                
                # Sort the data by 'Compliance Popup' date in descending order
                user_data.sort(key=lambda x: x[1], reverse=True)
                
                return user_data
            else:
                messagebox.showerror("Error", f"Error fetching persons from filter: {response.status_code}")
                return []

        wizard_window = tk.Toplevel(root)
        wizard_window.geometry("270x450")
        wizard_window.title("Apply RG Popup")
        wizard_window.iconbitmap('src/splash.ico')

        screen_width = wizard_window.winfo_screenwidth()
        wizard_window.geometry(f"+{screen_width - 350}+50")
        wizard_window_frame = ttk.Frame(wizard_window, style='Card')
        wizard_window_frame.place(x=5, y=5, width=260, height=440)

        username_label = ttk.Label(wizard_window_frame, text="Username")
        username_label.pack(padx=5, pady=5)
        entry1 = ttk.Entry(wizard_window_frame)
        entry1.pack(padx=5, pady=5)

        popup_note = ttk.Label(wizard_window_frame, text="Enter a username above to apply popup on next login.", wraplength=200, anchor='center', justify='center')
        popup_note.pack(padx=5, pady=5)

        submit_button = ttk.Button(wizard_window_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2")
        submit_button.pack(padx=5, pady=5)

        Separator = ttk.Separator(wizard_window_frame, orient='horizontal')
        Separator.pack(fill='x', pady=5)

        user_data = fetch_usernames_and_compliance_dates()
        tree = ttk.Treeview(wizard_window_frame, columns=('Username', 'Compliance Popup'), show='headings')
        tree.heading('Username', text='Username')
        tree.heading('Compliance Popup', text='Popup Date')
        tree.column('Username', width=30) 
        tree.column('Compliance Popup', width=30) 

        for username, compliance_date in user_data:
            tree.insert('', tk.END, values=(username, compliance_date))
        tree.pack(padx=5, pady=5, fill='both', expand=True)

    def report_rg_notification(self, username):
        global user
        try:
            spreadsheet = self.gc.open("Compliance Diary")
        except gspread.SpreadsheetNotFound:
            messagebox.showerror("Error", f"Spreadsheet 'Compliance Diary' not found. Please make sure the spreadsheet is available, or enter the freebet details manually.")
            return
        
        worksheet = spreadsheet.get_worksheet(11)
        next_row = len(worksheet.col_values(1)) + 1
        current_date = datetime.now().strftime("%d/%m/%Y")
        worksheet.update_cell(next_row, 1, username)
        worksheet.update_cell(next_row, 2, current_date)
        worksheet.update_cell(next_row, 3, user)

    def open_settings(self):
        settings_window = tk.Toplevel(root)
        settings_window.geometry("270x370")
        settings_window.title("Settings")
        settings_window.iconbitmap('src/splash.ico')
        screen_width = settings_window.winfo_screenwidth()
        settings_window.geometry(f"+{screen_width - 350}+50")
        
        settings_frame = ttk.Frame(settings_window, style='Card')
        settings_frame.place(x=5, y=5, width=260, height=360)
        
    def user_notification(self):
        user_notification()

    def about(self):
        messagebox.showinfo("About", "Geoff Banks Bet Monitoring v10.2")


if __name__ == "__main__":
    root = tk.Tk()
    app = BetViewerApp(root)
    root.mainloop()