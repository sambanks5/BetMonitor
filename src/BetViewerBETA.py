import os
import psutil
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
from oauth2client.service_account import ServiceAccountCredentials
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tkinter import messagebox, filedialog, simpledialog, Text, scrolledtext, IntVar
from dateutil.relativedelta import relativedelta
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pytz import timezone
from tkinter import ttk
from tkinter.ttk import *
from datetime import date, datetime, timedelta
from PIL import Image, ImageTk

user = ""
USER_NAMES = {
    'GB': 'George',
    'JP': 'Jon',
    'DF': 'Dave',
    'SB': 'Sam',
    'JJ': 'Joji',
    'AE': 'Arch',
    'EK': 'Ed',
}

def get_database(date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    if not date_str.endswith('-wager_database.json'):
        date_str += '-wager_database.json'
    json_file_path = f"database/{date_str}"

    try:
        with open(json_file_path, 'r') as json_file:
            data = json.load(json_file)
        data.reverse()
        return data
    except FileNotFoundError:
        print(f"No bet data available for {date_str}.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from file: {json_file_path}.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def user_login():
    global user, full_name
    while True:
        user = simpledialog.askstring("Input", "Please enter your initials:")
        if user and len(user) <= 2:
            user = user.upper()
            if user in USER_NAMES:
                full_name = USER_NAMES[user]
                # log_notification(f"{user} logged in")
                break
            else:
                messagebox.showerror("Error", "Could not find staff member! Please try again.")
        else:
            messagebox.showerror("Error", "Maximum of 2 characters.")

    # login_label.config(text=f'Logged in as {full_name}')

def user_notification():
    if not user:
        user_login()

    def submit():
        message = entry.get()
        message = (user + ": " + message)
        # Read the state of the pin_message_var to determine if the message should be pinned
        log_notification(message, important=True, pinned=pin_message_var.get())
        window.destroy()

    window = tk.Toplevel(root)
    window.title("Enter Notification")
    window.iconbitmap('src/splash.ico')
    window.geometry("300x150")  # Adjusted height to accommodate the checkbox
    screen_width = window.winfo_screenwidth()
    window.geometry(f"+{screen_width - 350}+50")

    label = ttk.Label(window, text="Enter your message:")
    label.pack(padx=5, pady=5)

    entry = ttk.Entry(window, width=50)
    entry.pack(padx=5, pady=5)
    entry.focus_set()
    entry.bind('<Return>', lambda event=None: submit())

    # BooleanVar to track the state of the checkbox
    pin_message_var = tk.BooleanVar()
    # Checkbutton for the user to select if they want to pin the message
    pin_message_checkbutton = ttk.Checkbutton(window, text="Pin this message", variable=pin_message_var)
    pin_message_checkbutton.pack(padx=5, pady=5)

    button = ttk.Button(window, text="Submit", command=submit)
    button.pack(padx=5, pady=10)

def log_notification(message, important=False, pinned=False):
    # Get the current time
    time = datetime.now().strftime('%H:%M:%S')

    file_lock = fasteners.InterProcessLock('notifications.lock')

    try:
        with file_lock:
            with open('notifications.json', 'r') as f:
                notifications = json.load(f)
    except FileNotFoundError:
        notifications = []

    # If the notification is pinned, remove the existing pinned notification
    if pinned:
        notifications = [notification for notification in notifications if not notification.get('pinned', False)]

    # Insert the new notification at the beginning
    notifications.insert(0, {'time': time, 'message': message, 'important': important, 'pinned': pinned})

    with file_lock:
        with open('notifications.json', 'w') as f:
            json.dump(notifications, f, indent=4)

class BetDataFetcher:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BetDataFetcher, cls).__new__(cls)
            cls._instance.data = {}
            cls._instance.lock = threading.Lock()
        return cls._instance

    def update_data(self):
        # Simulate data fetching, e.g., loading from a file or making a network request
        with self.lock:
            with open('src/data.json', 'r') as file:
                self.data = json.load(file)

    def get_data(self):
        # Return the latest data
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
        time.sleep(60)  # Update every minute

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
        # BET FEED UI Setup
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

        # ACTIVITY STATUS UI Setup
        self.activity_frame = ttk.LabelFrame(self.root, style='Card', text="Status")
        self.activity_frame.place(x=560, y=5, width=335, height=150)
        
        # Replace labels with a Text widget for activity status
        self.activity_text = tk.Text(self.activity_frame, font=("Helvetica", 10, "bold"), wrap='word', padx=10, pady=10, bd=0, fg="#000000")
        self.activity_text.config(state='disabled')
        self.activity_text.pack(fill='both', expand=True)

    def start_feed_update(self):
        # Get the current scroll position
        scroll_pos = self.feed_text.yview()[0]
        
        # Check if the scroll position is at the top (or close to the top)
        if scroll_pos <= 0.05:
            # The view is at the top, safe to refresh
            print("Refreshing feed...")
            self.bet_feed()
        else:
            # The view is not at the top, skip refresh or handle differently
            pass  # You can decide to do something else here if needed
        
        # Schedule start_feed_update to be called again after 5 seconds
        self.feed_frame.after(5000, self.start_feed_update)

    def apply_filters(self):
        # Retrieve current filter values from the UI elements
        self.current_filters['username'] = self.username_filter_entry.get()
        self.current_filters['unit_stake'] = self.unit_stake_filter_entry.get()
        self.current_filters['risk_category'] = self.risk_category_filter_entry.get()
        self.current_filters['sport'] = self.sport_combobox_entry.get()
        self.current_filters['selection'] = self.selection_filter_entry.get()

        # Check if any filters are applied
        filters_applied = any(value not in [None, '', 'none'] for value in self.current_filters.values())

        # Update the tick button style based on whether any filters are applied
        if filters_applied:
            self.tick_button.configure(style='Accent.TButton')
        else:
            self.tick_button.configure(style='TButton')  # Assuming 'TButton' is your default style

        # Call bet_feed with the current filters
        self.bet_feed()

    def reset_filters(self):
        # Reset the stored filters
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None, 'selection': None}
        # You might want to clear the UI elements for filters here as well
        self.username_filter_entry.delete(0, tk.END)  # Clear the username filter entry
        self.unit_stake_filter_entry.delete(0, tk.END)  # Clear the unit stake filter entry
        self.risk_category_filter_entry.delete(0, tk.END)  # Clear the risk category filter entry
        self.sport_combobox_entry.set('')  # Reset the sport combobox to its default state or an empty string
        self.selection_filter_entry.delete(0, tk.END)  # Clear the selection filter entry
        
        self.tick_button.configure(style='TButton')

        self.bet_feed()

    def filter_bets(self, bets, username, unit_stake_filter, risk_category, sport, selection_search_term=None):
        filtered_bets = []        
        # Mapping for sport names to numbers
        sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
        
        # Convert sport to its corresponding number using the mapping
        sport_number = sport_mapping.get(sport, -1)  # Default to -1 if sport is not found

        # Convert unit_stake_filter from string to float
        if unit_stake_filter:
            try:
                unit_stake_filter_value = float(unit_stake_filter.replace('£', ''))
            except ValueError:
                # Handle the case where the conversion fails
                unit_stake_filter_value = None
        else:
            unit_stake_filter_value = None

        for bet in bets:
            if isinstance(bet.get('details'), dict):
                selections = bet['details'].get('selections', [])
                selection_match = False
                if selection_search_term:
                    if bet.get('type') == "WAGER KNOCKBACK":  # Check if it's a knockback
                        for selection in selections:
                            # Construct the selection string for knockbacks
                            meeting_name = selection.get("- Meeting Name", "")
                            selection_name = selection.get("- Selection Name", "")
                            selection_str = f"{meeting_name}, {selection_name}"
                            if selection_search_term.lower() in selection_str.lower():
                                selection_match = True
                                break
                    else:  # For other bet types
                        for selection in selections:
                            if isinstance(selection, list) and selection_search_term.lower() in selection[0].lower():
                                selection_match = True
                                break
                            elif isinstance(selection, dict):  # Fallback for unexpected dict format in non-knockback bets
                                selection_str = selection.get("Selection Name", "")  # Assuming a similar key exists
                                if selection_search_term.lower() in selection_str.lower():
                                    selection_match = True
                                    break
                else:
                    selection_match = True  # If no search term is provided, don't filter out based on selections

                if not selection_match:
                    continue  # Skip this bet if it doesn't match the selection search term

                #Access 'unit_stake' from the nested 'details' dictionary and convert it to float
                unit_stake_str = bet['details'].get('unit_stake', '£0')
                try:
                    unit_stake_value = float(unit_stake_str.replace('£', ''))
                except ValueError:
                    # If conversion fails, skip this bet
                    continue

                # Check if the bet's unit_stake is equal to or greater than the filter value
                if unit_stake_filter_value is not None and unit_stake_value < unit_stake_filter_value:
                    continue  # Skip this bet if it doesn't meet the unit stake criteria

                # Check if the bet's customer_ref matches the username filter
                if username and bet.get('customer_ref') != username.upper():
                    continue  # Skip this bet if it doesn't match the username filter

                # Access 'risk_category' from the nested 'details' dictionary
                risk_category_value = bet.get('details', {}).get('risk_category', '-')

                # Determine if the bet should be included based on the risk category filter
                include_bet = False
                if risk_category is None or risk_category == '':
                    include_bet = True
                elif risk_category == 'Any' and risk_category_value != '-':
                    include_bet = True
                elif risk_category_value == risk_category:
                    include_bet = True

                # Apply sport filter
                if include_bet and (sport_number == -1 or sport_number in bet.get('Sport', [])):
                    filtered_bets.append(bet)
            elif bet.get('type') == 'SMS WAGER':
                # Apply username filter
                if username and bet.get('customer_ref') != username.upper():
                    continue  # Skip if it doesn't match the username filter
                
                # Check for selection search term in the details string
                if selection_search_term and selection_search_term.lower() not in bet.get('details', '').lower():
                    continue  # Skip if the search term is not found
                
                # Since 'unit_stake' and 'risk_category' cannot be directly applied, and sport is not specified, add the bet directly
                filtered_bets.append(bet)
        
        return filtered_bets

    def bet_feed(self, date_str=None):
        self.total_bets = 0
        self.total_knockbacks = 0
        self.total_sms_wagers = 0
        self.m_clients = set()
        self.w_clients = set()
        self.norisk_clients = set()

        self.data = get_database(date_str)

        if self.data is None:
            self.feed_text.config(state="normal")
            self.feed_text.delete('1.0', tk.END)  # Clear existing text
            self.feed_text.insert('end', "No bet data available for the selected date or the database can't be found.", "notices")
            self.feed_text.config(state="disabled")
            return  # Exit the function early

        # Retrieve current filter values
        username = self.current_filters['username']
        unit_stake = self.current_filters['unit_stake']
        risk_category = self.current_filters['risk_category']
        sport = self.current_filters['sport']
        selection_search_term = self.current_filters['selection']

        # Filter bets based on current filter settings
        filtered_bets = self.filter_bets(self.data, username, unit_stake, risk_category, sport, selection_search_term)
        # Initialize text tags for different categories
        self.initialize_text_tags()

        # Enable text widget for updates
        self.feed_text.config(state="normal")
        self.feed_text.delete('1.0', tk.END)  # Clear existing text

        if not filtered_bets:  # Check if filtered_bets is empty
            self.feed_text.insert('end', "No bets found with the current filters.", 'center')
        else:
            separator = '\n-------------------------------------------------------------------------------------------------------\n'
            # Access additional data needed for display
            self.vip_clients, self.newreg_clients, self.oddsmonkey_selections, self.todays_oddsmonkey_selections, reporting_data = access_data()

            for bet in filtered_bets:  # Iterate through each filtered bet
                self.display_bet(bet)
                self.feed_text.insert('end', separator, "notices")
            
            self.sport_count = self.count_sport(self.data)
            self.update_activity_frame(reporting_data, self.sport_count)
        
        # Disable the text widget to prevent user edits
        self.feed_text.config(state="disabled")


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
        payment = details.get('payment', '')
        bet_type = details.get('bet_type', '')
        
        if customer_risk_category and customer_risk_category != '-':
            tag = "risk"
            if customer_risk_category == 'M':
                self.m_clients.add(customer_reference)
            elif customer_risk_category == 'W':
                self.w_clients.add(customer_reference)
        else:
            tag = None
            self.norisk_clients.add(customer_reference)

        if customer_reference in self.vip_clients:
            tag = "vip"
        elif customer_reference in self.newreg_clients:
            tag = "newreg"
        else:
            tag = None

        # Prepare the selection text
        selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])

        # Use insert_feed_text for inserting the text with the appropriate tag
        self.insert_feed_text(f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}", tag)

        # Check for Oddsmonkey selections and insert them with the "Oddsmonkey" tag
        if any(' - ' in sel[0] and sel[0].split(' - ')[1].strip() == om_sel[1][0].strip() for sel in parsed_selections for om_sel in self.oddsmonkey_selections.items()):
            self.insert_feed_text(f"\n ^ Oddsmonkey Selection Detected ^ ", "Oddsmonkey")
        
        self.total_bets += 1


    def update_activity_frame(self, reporting_data, sport_count):
        unique_m_clients = len(self.m_clients)
        unique_w_clients = len(self.w_clients)
        unique_norisk_clients = len(self.norisk_clients)
        total_unique_clients = len(self.m_clients.union(self.w_clients, self.norisk_clients))
        knockback_percentage = (self.total_knockbacks / self.total_bets * 100) if self.total_bets > 0 else 0

        daily_turnover = reporting_data.get('daily_turnover', 'N/A')
        daily_profit = reporting_data.get('daily_profit', 'N/A')
        daily_profit_percentage = reporting_data.get('daily_profit_percentage', 'N/A')
        #last_updated_time = reporting_data.get('last_updated_time', 'N/A')
        total_deposits = reporting_data.get('total_deposits', 'N/A')
        total_sum_deposits = reporting_data.get('total_sum', 'N/A')
        horse_bets = sport_count.get(0, 0)
        dog_bets = sport_count.get(1, 0)
        other_bets = sport_count.get(2, 0)

        filters_applied = any(value not in [None, '', 'none'] for value in self.current_filters.values())

        avg_deposit = total_sum_deposits / total_deposits if total_deposits else 0

        status_text = (
            f"Bets: {self.total_bets} | Knockbacks: {self.total_knockbacks} ({knockback_percentage:.2f}%){'**' if filters_applied else ''}\n"
            f"Turnover: {daily_turnover} | Profit: {daily_profit} ({daily_profit_percentage})\n"
            f"Deposits: {total_deposits} | Total: £{total_sum_deposits:,.2f} (~£{avg_deposit:,.2f})\n"
            f"Clients: {total_unique_clients} | M: {unique_m_clients} | W: {unique_w_clients} | --: {unique_norisk_clients}{'**' if filters_applied else ''}\n"
            f"Horses: {horse_bets} | Dogs: {dog_bets} | Other: {other_bets}\n\n"
            f"{'Feed Filters Currently Applied!' if filters_applied else 'Bet Viewer v10.0'}"
        )

        self.activity_text.config(state='normal')  # Enable the widget for editing
        self.activity_text.delete('1.0', tk.END)  # Clear existing text
        
        self.activity_text.tag_configure('center', justify='center')
        self.activity_text.insert(tk.END, status_text, 'center')  # Insert the updated status text and apply the 'center' tag
        
        self.activity_text.config(state='disabled')  # Disable editing

























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

        self.spinbox_label.grid(row=0, column=0, sticky='e', padx=6)  # Adjusted sticky to 'ew'
        self.spinbox.grid(row=0, column=1, pady=(0, 3), sticky='ew') 
        self.num_run_bets_var.set("2")
        self.spinbox.grid(row=0, column=1, pady=(0, 3), sticky='w')
        self.num_run_bets_var.trace("w", self.set_num_run_bets)

        self.combobox_label = ttk.Label(self.spinbox_frame, text=' Num bets: ')
        self.combobox_label.grid(row=0, column=2, sticky='e', padx=6)  # Adjusted sticky to 'ew'

        self.combobox_values = [20, 50, 100, 300, 1000, 2000]
        self.combobox = ttk.Combobox(self.spinbox_frame, textvariable=self.combobox_var, values=self.combobox_values, width=4)
        self.combobox_var.trace("w", self.set_recent_bets)
        self.combobox.grid(row=0, column=3, pady=(0, 3), sticky='ew')  # Adjusted sticky to 'ew'
        self.runs_scroll = ttk.Scrollbar(self.runs_frame, orient='vertical', command=self.runs_text.yview, cursor="hand2")
        self.runs_scroll.grid(row=0, column=1, sticky='ns')
        self.runs_text.configure(yscrollcommand=self.runs_scroll.set)

    def set_recent_bets(self, *args):  # Ensure this method can be used as a callback
        # Directly update the instance attribute based on the combobox value
        self.num_recent_files = self.combobox_var.get()
        self.refresh_bets()

    def set_num_run_bets(self, *args):
        try:
            self.num_run_bets = int(self.num_run_bets_var.get())
            self.refresh_bets()
        except ValueError:
            # Handle the case where the conversion fails (e.g., input is not a number)
            pass

    def bet_runs(self, num_bets, num_run_bets):
        database_data = get_database()
        
        if database_data is None:
            self.runs_text.config(state="normal")
            self.runs_text.delete('1.0', tk.END)  # Clear existing text
            self.runs_text.insert('end', "No bet data available for the selected date or the database can't be found.")
            self.runs_text.config(state="disabled")
            return  # Exit the function early if data is not as expected

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

                # Extract the meeting name and time from the selection
                meeting_time = ' '.join(selection.split(' ')[:2])

                # Check if the meeting name and time is in the enhanced_places list
                if meeting_time in enhanced_places:
                    self.runs_text.insert(tk.END, 'Enhanced Place Race\n', "oddsmonkey")
                
                self.runs_text.insert(tk.END, f"\n")

        self.runs_text.config(state=tk.DISABLED)

    def refresh_bets(self):
        # Method to refresh bets every 10 seconds
        num_bets = self.num_recent_files
        num_run_bets = self.num_run_bets

        self.bet_runs(num_bets, num_run_bets)

        # Use threading to call this method again after 10 seconds
        self.root.after(10000, self.refresh_bets)        


























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

    def get_courses(self):
        today = date.today()
        courses = set()
        api_data = []  # Initialize api_data as an empty list

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

        self.display_courses()
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
        for widget in self.race_updation_frame.winfo_children():
            widget.destroy()

        with open('update_times.json', 'r') as f:
            data = json.load(f)

        courses = list(data['courses'].keys())
        courses.sort(key=lambda x: (x=="SIS Greyhounds", x=="TRP Greyhounds"))
        start = self.current_page * self.courses_per_page
        end = start + self.courses_per_page
        courses_page = courses[start:end]

        button_frame = ttk.Frame(self.race_updation_frame)
        button_frame.grid(row=len(courses_page), column=0, padx=2, sticky='ew')

        # Create the add button and align it to the left of the Frame
        add_button = ttk.Button(button_frame, text="+", command=self.add_course, width=2, cursor="hand2")
        add_button.pack(side='left')

        # Add an indicator in the middle
        update_indicator = ttk.Label(button_frame, text="\u2022", foreground='red', font=("Helvetica", 24))
        update_indicator.pack(side='left', padx=2, expand=True)

        # Create the remove button and align it to the right of the Frame
        remove_button = ttk.Button(button_frame, text="-", command=self.remove_course, width=2, cursor="hand2")
        remove_button.pack(side='right')

        for i, course in enumerate(courses_page):
            # Replace the course label with a button
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

        # Check if any course on other pages needs updating
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
        # Open a dialog box to get the course name
        course = simpledialog.askstring("Remove Course", "Enter the course name:")
        
        with open('update_times.json', 'r') as f:
            data = json.load(f)
        if course in data['courses']:
            del data['courses'][course]

        with open('update_times.json', 'w') as f:
            json.dump(data, f)

        # log_notification(f"'{course}' removed by {user}")

        self.display_courses()

    def add_course(self):
        course_name = simpledialog.askstring("Add Course", "Enter the course name:")
        if course_name:
            with open('update_times.json', 'r') as f:
                data = json.load(f)

            data['courses'][course_name] = ""

            with open('update_times.json', 'w') as f:
                json.dump(data, f)

            # log_notification(f"'{course_name}' added by {user}")

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











class Settings:
    def __init__(self, root):
        self.root = root
        self.initialize_ui()
        self.import_logo()
    
    def initialize_ui(self):
        self.settings_frame = ttk.Frame(root, style='Card')
        self.settings_frame.place(x=714, y=652, width=180, height=266)

    def import_logo(self):
        logo_image = Image.open('src/splash.ico')
        logo_image = logo_image.resize((60, 60))
        self.company_logo = ImageTk.PhotoImage(logo_image)
        self.logo_label = ttk.Label(self.settings_frame, image=self.company_logo)
        self.logo_label.pack(pady=10)












class Notebook:
    def __init__(self, root):
        self.root = root
        self.last_notification = None
        self.generated_string = None
        self.initialize_ui()
        self.update_notifications()

    def initialize_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.place(x=238, y=653, width=470, height=266)
        ### RISK BETS TAB
        tab_1 = ttk.Frame(self.notebook)
        tab_1.grid_rowconfigure(0, weight=1)
        tab_1.grid_columnconfigure(0, weight=3)  # Text widget column
        tab_1.grid_columnconfigure(1, weight=0)  # Separator column, minimal weight
        tab_1.grid_columnconfigure(2, weight=1)  # Buttons frame column
        self.notebook.add(tab_1, text="Staff Feed")

        self.staff_feed = tk.Text(tab_1, font=("Helvetica", 10), bd=0, wrap='word', padx=2, pady=2, fg="#000000", bg="#ffffff")
        self.staff_feed.grid(row=0, column=0, sticky="nsew")  # Make the text widget expand in all directions
        self.staff_feed.tag_configure("spacing", spacing1=5, spacing3=5)
        self.staff_feed.tag_add("spacing", "1.0", "end")


        self.staff_feed_buttons_frame = ttk.Frame(tab_1)
        separator = ttk.Separator(tab_1, orient='vertical')
        separator.grid(row=0, column=1, sticky='ns')

        self.staff_feed_buttons_frame.grid(row=0, column=2, sticky='nsew')
        self.pinned_message_frame = ttk.Frame(self.staff_feed_buttons_frame, style='Card')
        self.pinned_message_frame.pack(side="top", pady=5, padx=(5, 0))
        self.pinned_message = tk.Text(self.pinned_message_frame, font=("Helvetica", 11, 'bold'), bd=0, wrap='word', pady=2, fg="#000000", bg="#ffffff", height=3, width=40)  # Adjust height as needed
        self.pinned_message.insert('1.0', "Pinned Notifications: No pinned notifications")  # Example pinned message
        self.pinned_message.config(state='disabled')  # Make the text widget read-only if the pinned message should not be editable
        self.pinned_message.pack(side="top", pady=5, padx=5)  # Place it under the post message button
        self.post_message_button = ttk.Button(self.staff_feed_buttons_frame, text="Post Message", command=user_notification, cursor="hand2", width=15)
        self.post_message_button.pack(side="top", pady=(10, 5))

        self.separator = ttk.Separator(self.staff_feed_buttons_frame, orient='horizontal')
        self.separator.pack(side="top", fill='x', pady=(15, 5))

        self.copy_button = ttk.Button(self.staff_feed_buttons_frame, text="Generate Password", command=self.copy_to_clipboard, cursor="hand2", width=15)
        self.copy_button.pack(side="top", pady=(20, 5))

        self.password_result_label = ttk.Label(self.staff_feed_buttons_frame, text="GB000000", font=("Helvetica", 12), wraplength=200)
        self.password_result_label.pack(side="top", pady=2)
        
        ### REPORT TAB
        tab_2 = ttk.Frame(self.notebook)
        self.notebook.add(tab_2, text="Reports/Screener")
        tab_2.grid_rowconfigure(0, weight=1)
        tab_2.grid_rowconfigure(1, weight=1)
        tab_2.grid_columnconfigure(0, weight=1)
        self.report_ticket = tk.Text(tab_2, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
        self.report_ticket.tag_configure("center", justify='center')
        self.report_ticket.insert('1.0', "User Report\nGenerate a report for a specific client, including their bet history.\n\nStaff Report\nGenerate a report on staff activity.\n\nDaily Report\nGenerate a report for the days betting activity.", "center")    
        self.report_ticket.config(state='disabled')
        self.report_ticket.grid(row=0, column=0, sticky="nsew")


    def generate_random_string(self):
        random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        generated_string = 'GB' + random_numbers
        
        return generated_string

    ### COPY PASSWORD TO CLIPBOARD
    def copy_to_clipboard(self):
        self.generated_string = self.generate_random_string()
        
        pyperclip.copy(self.generated_string)
        
        self.password_result_label.config(text=f"{self.generated_string}")
        self.copy_button.config(state=tk.NORMAL)

    def update_notifications(self):
        self.staff_feed.tag_configure("important", font=("TkDefaultFont", 10, "bold"))
        self.staff_feed.config(state='normal')  # Temporarily enable editing to update text
        file_lock = fasteners.InterProcessLock('notifications.lock')

        with file_lock:
            try:
                with open('notifications.json', 'r') as f:
                    notifications = json.load(f)

                # Separate pinned notifications from regular notifications
                pinned_notifications = [n for n in notifications if n.get('pinned', False)]
                regular_notifications = [n for n in notifications if not n.get('pinned', False)]

                # Update the pinned_message widget with pinned notifications
                self.pinned_message.config(state='normal')  # Temporarily enable editing to update text
                self.pinned_message.delete('1.0', 'end')  # Clear existing text
                for notification in pinned_notifications:
                    self.pinned_message.insert('end', f"{notification['time']}: {notification['message']}\n")
                self.pinned_message.config(state='disabled')  # Disable editing after updating

                # Update the staff_feed widget with regular notifications
                if regular_notifications and (self.last_notification is None or self.last_notification != regular_notifications[0]):
                    last_index = next((index for index, notification in enumerate(regular_notifications) if notification == self.last_notification), len(regular_notifications))
                    for notification in reversed(regular_notifications[:last_index]):
                        time = notification['time']
                        message = notification['message']
                        important = notification.get('important', False)
                        if important:
                            message = f'{time}: {message}\n'
                            self.staff_feed.insert('1.0', message, "important")
                        else:
                            self.staff_feed.insert('1.0', f'{time}: {message}\n')
                    self.last_notification = regular_notifications[0] if regular_notifications else None

            except FileNotFoundError:
                pass
        self.staff_feed.config(state='disabled')  # Disable editing after updating
        # Schedule the next update
        self.staff_feed.after(1000, self.update_notifications)



















class Next3Panel:
    def __init__(self, root):
        self.root = root
        _, _, _, _, reporting_data = access_data()
        self.enhanced_places = reporting_data.get('enhanced_places', [])
        self.horse_url = 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h,o'  # Default URL
        self.initialize_ui()
        self.run_display_next_3()
    
    def run_display_next_3(self):
        self.display_next_3()
        print("Running next 3")
        self.root.after(10000, self.run_display_next_3)

    def toggle_horse_url(self, event=None):
        # Toggle the URL when the horses_frame is clicked
        if self.horse_url == 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h,o':
            self.horse_url = 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h'
            print("Horse URL changed to:", self.horse_url)
        else:
            self.horse_url = 'https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h,o'
            print("Horse URL changed to:", self.horse_url)
        self.display_next_3()  # Refresh the display after changing the URL


    def initialize_ui(self):
        next_races_frame = ttk.Frame(self.root)
        next_races_frame.place(x=5, y=927, width=890, height=55)

        horses_frame = ttk.Frame(next_races_frame, style='Card', cursor="hand2")
        horses_frame.place(relx=0, rely=0.05, relwidth=0.5, relheight=0.9)
        horses_frame.bind("<Button-1>", self.toggle_horse_url)  # Bind click event

        greyhounds_frame = ttk.Frame(next_races_frame, style='Card')
        greyhounds_frame.place(relx=0.51, rely=0.05, relwidth=0.49, relheight=0.9)


        # Create the labels for the horse data
        self.horse_labels = [ttk.Label(horses_frame, justify='center', font=("Helvetica", 9, "bold")) for _ in range(3)]
        for i, label in enumerate(self.horse_labels):
            label.grid(row=0, column=i, padx=0, pady=5)
            horses_frame.columnconfigure(i, weight=1)

        # Create the labels for the greyhound data
        self.greyhound_labels = [ttk.Label(greyhounds_frame, justify='center', font=("Helvetica", 9, "bold")) for _ in range(3)]
        for i, label in enumerate(self.greyhound_labels):
            label.grid(row=1, column=i, padx=0, pady=5)
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
            
            ## Map ptype to a more readable format
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

            # Create a label for each meeting and place it in the grid
            labels[i].config(text=f"{race} ({ptype})\n{status}")

    def display_next_3(self):
        headers = {
            "User-Agent": "Mozilla/5.0 ..."
        }

        horse_response = requests.get(self.horse_url, headers=headers)  # Use the updated horse_url
        greyhound_response = requests.get('https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=g', headers=headers)

        # Check if the responses are not empty and have a status code of 200 (OK)
        if horse_response.status_code == 200 and greyhound_response.status_code == 200:

            horse_data = horse_response.json()
            greyhound_data = greyhound_response.json()

            # Process the horse and greyhound data
            self.process_data(horse_data, 'horse')
            self.process_data(greyhound_data, 'greyhound')    

        else:
            print("Error: The response from the API is not OK.")
            return   
            





class BetViewerApp:
    def __init__(self, root):
        self.root = root
        # Start the scheduler in a background thread
        threading.Thread(target=schedule_data_updates, daemon=True).start()
        self.initialize_ui()
        self.bet_feed = BetFeed(root)  # Integrate BetFeed into BetViewerApp
        self.bet_runs = BetRuns(root)  # Integrate BetRuns into BetViewerApp
        self.race_updation = RaceUpdaton(root)  # Integrate RaceUpdaton into BetViewerApp
        # self.next3_panel = Next3Panel(root)  # Integrate Next3Panel into BetViewerApp
        self.notebook = Notebook(root)  # Integrate Notebook into BetViewerApp
        self.settings = Settings(root)  # Integrate Settings into BetViewerApp

    def initialize_ui(self):
        self.root.title("Bet Viewer v8.5")
        self.root.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
        ttk.Style().theme_use('forest-light')
        style = ttk.Style(self.root)
        width = 900
        height = 1005
        screenwidth = self.root.winfo_screenwidth()
        screenheight = self.root.winfo_screenheight()
        # self.root.configure(bg='#ffffff')
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
        options_menu.add_command(label="Refresh", command=self.refresh_display, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Settings", command=self.open_settings, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Set User Initials", command=self.user_login, foreground="#000000", background="#ffffff")
        options_menu.add_separator(background="#ffffff")
        options_menu.add_command(label="Exit", command=self.root.quit, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Options", menu=options_menu)
        
        # Additional Features Menu
        features_menu = tk.Menu(menu_bar, tearoff=0)
        features_menu.add_command(label="Report Freebet", command=self.report_freebet, foreground="#000000", background="#ffffff")
        features_menu.add_command(label="Add notification", command=self.user_notification, foreground="#000000", background="#ffffff")
        features_menu.add_command(label="Add Factoring", command=self.open_factoring_wizard, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Features", menu=features_menu)
        
        # Help Menu
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="How to use", command=self.howTo, foreground="#000000", background="#ffffff")
        help_menu.add_command(label="About", command=self.about, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Help", menu=help_menu, foreground="#000000", background="#ffffff")
        
        self.root.config(menu=menu_bar)

    # Placeholder methods for menu commands
    def refresh_display(self):
        pass

    def open_settings(self):
        pass

    def user_login(self):
        pass

    def report_freebet(self):
        pass

    def user_notification(self):
        user_notification()
        

    def open_factoring_wizard(self):

        pass

    def howTo(self):
        pass
        

    def about(self):
        messagebox.showinfo("About", "Geoff Banks Bet Monitoring v10.0")










if __name__ == "__main__":
    root = tk.Tk()
    app = BetViewerApp(root)
    root.mainloop()