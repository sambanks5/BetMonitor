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

# Start the scheduler in a background thread
threading.Thread(target=schedule_data_updates, daemon=True).start()

def access_data():
    fetcher = BetDataFetcher()
    vip_clients = fetcher.get_vip_clients()
    newreg_clients = fetcher.get_newreg_clients()
    oddsmonkey_selections = fetcher.get_oddsmonkey_selections()
    today_oddsmonkey_selections = fetcher.get_todays_oddsmonkey_selections()
    reporting_data = fetcher.get_reporting_data()
    return vip_clients, newreg_clients, oddsmonkey_selections, today_oddsmonkey_selections, reporting_data

def get_database(date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    if not date_str.endswith('-wager_database.json'):
        date_str += '-wager_database.json'
    json_file_path = f"database/{date_str}"

    max_retries = 5
    for attempt in range(max_retries):
        try:
            with open(json_file_path, 'r') as json_file:
                data = json.load(json_file)
            data.reverse()
            return data
        except FileNotFoundError:
            if attempt >= max_retries - 1:
                print(f"No bet data available for {date_str}.")
            time.sleep(1)  # Retry after a delay
        except json.JSONDecodeError:
            if attempt >= max_retries - 1:
                print(f"Error: Could not decode JSON from file: {json_file_path}.")
            time.sleep(1)
        except Exception as e:
            print(f"An error occurred: {e}")
            return []












class BetFeed:
    def __init__(self, root):
        self.root = root
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None}
        self.initialize_ui()
        self.start_feed_update()

    def initialize_ui(self):
        # BET FEED UI Setup
        self.feed_frame = ttk.LabelFrame(self.root, style='Card', text="Bet Feed")
        self.feed_frame.place(x=5, y=5, width=550, height=600)
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
        self.filter_frame.grid(row=1, column=0, sticky='ew')

        self.username_filter_label = ttk.Label(self.filter_frame, text='Client:')
        self.username_filter_label.grid(row=0, column=0, sticky='e', padx=5)
        self.username_filter_entry = ttk.Entry(self.filter_frame, width=8)
        self.username_filter_entry.grid(row=0, column=1, pady=(0, 3), sticky='ew')

        self.unit_stake_filter_label = ttk.Label(self.filter_frame, text='Unit Stk:')
        self.unit_stake_filter_label.grid(row=0, column=2, sticky='e', padx=5)
        self.unit_stake_filter_entry = ttk.Entry(self.filter_frame, width=3)
        self.unit_stake_filter_entry.grid(row=0, column=3, pady=(0, 3), sticky='ew')

        self.risk_category_filter = ttk.Label(self.filter_frame, text='Risk Cat:')
        self.risk_category_filter.grid(row=0, column=4, sticky='e', padx=5)
        self.risk_category_combobox_values = ["", "Any", "M", "W", "S", "O", "X"]
        self.risk_category_filter_entry = ttk.Combobox(self.filter_frame, values=self.risk_category_combobox_values, width=3)
        self.risk_category_filter_entry.grid(row=0, column=5, pady=(0, 3), sticky='ew')

        self.sport_filter = ttk.Label(self.filter_frame, text='Sport:')
        self.sport_filter.grid(row=0, column=6, sticky='e', padx=5)
        self.sport_combobox_values = ["", "Horses", "Dogs", "Other"]
        self.sport_combobox_entry = ttk.Combobox(self.filter_frame, values=self.sport_combobox_values, width=5)
        self.sport_combobox_entry.grid(row=0, column=7, pady=(0, 3), sticky='ew')

        self.tick_button = ttk.Button(self.filter_frame, text='✔', command=self.apply_filters, width=2)
        self.tick_button.grid(row=0, column=8, padx=(10, 0), sticky='ew', pady=(0, 3)) 

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
        self.activity_text = tk.Text(self.activity_frame, height=5, width=40, font=("Helvetica", 10, "bold"), wrap='word', padx=10, pady=10, bd=0, fg="#000000")
        self.activity_text.config(state='disabled')
        self.activity_frame.grid_rowconfigure(0, weight=1)
        self.activity_frame.grid_columnconfigure(0, weight=1)
        self.activity_text.grid(row=0, column=0, sticky='nsew')

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
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None}
        # You might want to clear the UI elements for filters here as well
        self.username_filter_entry.delete(0, tk.END)  # Clear the username filter entry
        self.unit_stake_filter_entry.delete(0, tk.END)  # Clear the unit stake filter entry
        self.risk_category_filter_entry.delete(0, tk.END)  # Clear the risk category filter entry
        self.sport_combobox_entry.set('')  # Reset the sport combobox to its default state or an empty string

        # Call bet_feed to refresh the data without any filters
        self.bet_feed()

    def filter_bets(self, bets, username, unit_stake_filter, risk_category, sport):
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

                # The rest of your filtering logic remains the same...
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
            else:

                continue
        
        return filtered_bets

    def bet_feed(self, date_str=None):
        self.total_bets = 0
        self.total_knockbacks = 0
        self.total_sms_wagers = 0
        self.m_clients = set()
        self.w_clients = set()
        self.norisk_clients = set()

        # Fetch the actual database data for the given date or today if not specified
        self.data = get_database(date_str)

        # Retrieve current filter values
        username = self.current_filters['username']
        unit_stake = self.current_filters['unit_stake']
        risk_category = self.current_filters['risk_category']
        sport = self.current_filters['sport']

        # Filter bets based on current filter settings
        filtered_bets = self.filter_bets(self.data, username, unit_stake, risk_category, sport)
        # Initialize text tags for different categories
        self.initialize_text_tags()

        # Enable text widget for updates
        self.feed_text.config(state="normal")
        self.feed_text.delete('1.0', tk.END)  # Clear existing text

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


                # 'total_deposits': self.data.get('deposits_summary', {}).get('total_deposits', 0),
                # 'total_sum': self.data.get('deposits_summary', {}).get('total_sum', 0),
        # Format reporting data
        daily_turnover = reporting_data.get('daily_turnover', 'N/A')
        daily_profit = reporting_data.get('daily_profit', 'N/A')
        daily_profit_percentage = reporting_data.get('daily_profit_percentage', 'N/A')
        last_updated_time = reporting_data.get('last_updated_time', 'N/A')
        total_deposits = reporting_data.get('total_deposits', 'N/A')
        total_sum_deposits = reporting_data.get('total_sum', 'N/A')
        horse_bets = sport_count.get(0, 0)
        dog_bets = sport_count.get(1, 0)
        other_bets = sport_count.get(2, 0)


        avg_deposit = total_sum_deposits / total_deposits if total_deposits else 0

        status_text = (
            f"Bets: {self.total_bets} | Knockbacks: {self.total_knockbacks} ({knockback_percentage:.2f}%)\n"
            f"Turnover: {daily_turnover} | Profit: {daily_profit} ({daily_profit_percentage})\n"
            f"Deposits: {total_deposits} | Total: £{total_sum_deposits:,.2f} (~£{avg_deposit:,.2f})\n"
            f"Clients: {total_unique_clients} | M: {unique_m_clients} | W: {unique_w_clients} | --: {unique_norisk_clients}\n"
            f"Horses: {horse_bets} | Dogs: {dog_bets} | Other: {other_bets}\n"

            # f"Last Updated: {last_updated_time}"
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
        self.runs_frame.place(x=560, y=160, width=335, height=445)
        self.runs_frame.grid_columnconfigure(0, weight=1)
        self.runs_frame.grid_rowconfigure(0, weight=1)
        self.runs_frame.grid_columnconfigure(1, weight=0)

        self.runs_text = tk.Text(self.runs_frame, font=("Arial", 10), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
        self.runs_text.config(state='disabled') 
        self.runs_text.grid(row=0, column=0, sticky='nsew')

        self.spinbox_frame = ttk.Frame(self.runs_frame)
        self.spinbox_frame.grid(row=1, column=0, sticky='ew')
        self.spinbox_label = ttk.Label(self.spinbox_frame, text='Run: ')
        self.spinbox = ttk.Spinbox(self.spinbox_frame, from_=2, to=10, textvariable=self.num_run_bets_var, width=2)
        self.spinbox_frame.grid(row=1, column=0, sticky='ew')
        self.spinbox_frame.grid_columnconfigure(0, weight=1)
        self.spinbox_frame.grid_columnconfigure(1, weight=1)
        self.spinbox_frame.grid_columnconfigure(2, weight=1)
        self.spinbox_frame.grid_columnconfigure(3, weight=1)

        self.spinbox_label.grid(row=0, column=0, sticky='ew', padx=6)  # Adjusted sticky to 'ew'
        self.spinbox.grid(row=0, column=1, pady=(0, 3), sticky='ew') 
        self.num_run_bets_var.set("2")
        self.spinbox.grid(row=0, column=1, pady=(0, 3), sticky='w')
        self.num_run_bets_var.trace("w", self.set_num_run_bets)

        self.combobox_label = ttk.Label(self.spinbox_frame, text=' Num bets: ')
        self.combobox_label.grid(row=0, column=2, sticky='ew', padx=6)  # Adjusted sticky to 'ew'

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
        selection_bets = get_database()[:num_bets] 
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












class BetViewerApp:
    def __init__(self, root):
        self.root = root
        self.initialize_ui()
        self.bet_feed = BetFeed(root)  # Integrate BetFeed into BetViewerApp
        self.bet_runs = BetRuns(root)  # Integrate BetRuns into BetViewerApp

    def initialize_ui(self):
        self.root.title("Bet Viewer v8.5")
        self.root.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
        ttk.Style().theme_use('forest-light')
        style = ttk.Style(self.root)
        width = 900
        height = 1000

        
        screenwidth = self.root.winfo_screenwidth()
        screenheight = self.root.winfo_screenheight()
        # self.root.configure(bg='#ffffff')
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width - 10), 0)
        self.root.geometry(alignstr)
        #self.root.resizable(False, False)

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
        options_menu.add_command(label="Refresh", command=self.refresh_display, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Settings", command=self.open_settings, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Set User Initials", command=self.user_login, foreground="#000000", background="#ffffff")
        options_menu.add_separator(background="#ffffff")
        options_menu.add_command(label="Exit", command=self.root.quit, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Options", menu=options_menu)
        menu_bar.add_command(label="Report Freebet", command=self.report_freebet, foreground="#000000", background="#ffffff")
        menu_bar.add_command(label="Add notification", command=self.user_notification, foreground="#000000", background="#ffffff")
        menu_bar.add_command(label="Add Factoring", command=self.open_factoring_wizard, foreground="#000000", background="#ffffff")
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
        pass

    def open_factoring_wizard(self):
        pass

    def howTo(self):
        pass

    def about(self):
        pass


if __name__ == "__main__":
    root = tk.Tk()
    app = BetViewerApp(root)
    root.mainloop()