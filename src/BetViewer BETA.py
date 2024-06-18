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
        self.initialize_ui()
        self.start_feed_update()

    def initialize_ui(self):
        # BET FEED UI Setup
        self.feed_frame = ttk.LabelFrame(self.root, style='Card', text="Bet Feed")
        self.feed_frame.place(x=5, y=5, width=550, height=600)
        self.feed_frame.grid_columnconfigure(0, weight=1)
        self.feed_frame.grid_rowconfigure(0, weight=1)
        self.feed_frame.grid_columnconfigure(1, weight=0)
        
        self.feed_text = tk.Text(self.feed_frame, font=("Helvetica", 11, "bold"), wrap='word', padx=10, pady=10, bd=0, fg="#000000")
        self.feed_text.config(state='disabled')
        self.feed_text.grid(row=0, column=0, sticky='nsew')
        
        self.feed_scroll = ttk.Scrollbar(self.feed_frame, orient='vertical', command=self.feed_text.yview, cursor="hand2")
        self.feed_scroll.grid(row=0, column=1, sticky='ns')
        self.feed_text.configure(yscrollcommand=self.feed_scroll.set)

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
        # Call the bet_feed method to update the feed
        self.bet_feed()
        
        # Schedule start_feed_update to be called again after 30 seconds
        self.feed_frame.after(5000, self.start_feed_update)

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
        self.feed_text.tag_configure("notices", font=("Helvetica", 11, "bold"))

    def display_bet(self, bet, vip_clients, newreg_clients, oddsmonkey_selections):
        wager_type = bet.get('type', '').lower()
        if wager_type == 'wager knockback':
            self.display_wager_knockback(bet, vip_clients, newreg_clients, oddsmonkey_selections)
        elif wager_type == 'sms wager':
            self.display_sms_wager(bet, vip_clients, newreg_clients, oddsmonkey_selections)
        elif wager_type == 'bet':
            self.display_regular_bet(bet, vip_clients, newreg_clients, oddsmonkey_selections)

    def display_wager_knockback(self, bet, vip_clients, newreg_clients, oddsmonkey_selections):
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
        if customer_ref in vip_clients:
            tag = "vip"
        elif customer_ref in newreg_clients:
            tag = "newreg"
        else:
            tag = None
        
        self.insert_feed_text(f"{time} - {knockback_id} - {customer_ref} - WAGER KNOCKBACK:\n   {formatted_knockback_details}", tag)
        self.total_knockbacks += 1

    def display_sms_wager(self, bet, vip_clients, newreg_clients, oddsmonkey_selections):
        wager_number = bet.get('id', '')
        customer_reference = bet.get('customer_ref', '')
        sms_wager_text = bet.get('details', '')
        self.insert_feed_text(f"{customer_reference} - {wager_number} SMS WAGER:\n{sms_wager_text}", "sms")
        self.total_sms_wagers += 1

    def display_regular_bet(self, bet, vip_clients, newreg_clients, oddsmonkey_selections):
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

        if customer_reference in vip_clients:
            tag = "vip"
        elif customer_reference in newreg_clients:
            tag = "newreg"
        else:
            tag = None

        # Prepare the selection text
        selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])

        # Use insert_feed_text for inserting the text with the appropriate tag
        self.insert_feed_text(f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}", tag)

        # Check for Oddsmonkey selections and insert them with the "Oddsmonkey" tag
        if any(' - ' in sel[0] and sel[0].split(' - ')[1].strip() == om_sel[1][0].strip() for sel in parsed_selections for om_sel in oddsmonkey_selections.items()):
            self.insert_feed_text(f"\n ^ Oddsmonkey Selection Detected ^ ", "Oddsmonkey")
        
        self.total_bets += 1
 
    def update_activity_frame(self, reporting_data):
        unique_m_clients = len(self.m_clients)
        unique_w_clients = len(self.w_clients)
        unique_norisk_clients = len(self.norisk_clients)
        total_unique_clients = len(self.m_clients.union(self.w_clients, self.norisk_clients))
        knockback_percentage = (self.total_knockbacks / self.total_bets * 100) if self.total_bets > 0 else 0

        # Format reporting data
        daily_turnover = reporting_data.get('daily_turnover', 'N/A')
        daily_profit = reporting_data.get('daily_profit', 'N/A')
        daily_profit_percentage = reporting_data.get('daily_profit_percentage', 'N/A')
        last_updated_time = reporting_data.get('last_updated_time', 'N/A')

        status_text = (
            f"Bets: {self.total_bets} | Knockbacks: {self.total_knockbacks} | SMS: {self.total_sms_wagers}\n"
            f"Knockback Percentage: {knockback_percentage:.2f}%\n"
            f"Clients: {total_unique_clients} | M: {unique_m_clients} | W: {unique_w_clients} | NoRisk: {unique_norisk_clients}\n"
            f"Turnover: {daily_turnover} | Profit: {daily_profit}\n"
            f"Profit Percentage: {daily_profit_percentage}\n"
            f"Last Updated: {last_updated_time}"
        )

        self.activity_text.config(state='normal')  # Enable the widget for editing
        self.activity_text.delete('1.0', tk.END)  # Clear existing text
        
        self.activity_text.tag_configure('center', justify='center')
        self.activity_text.insert(tk.END, status_text, 'center')  # Insert the updated status text and apply the 'center' tag
        
        self.activity_text.config(state='disabled')  # Disable editing

    def bet_feed(self, date_str=None):
        self.total_bets = 0
        self.total_knockbacks = 0
        self.total_sms_wagers = 0
        self.m_clients = set()
        self.w_clients = set()
        self.norisk_clients = set()

        # Fetch the actual database data for the given date or today if not specified
        data = get_database(date_str)
        
        # Initialize text tags for different categories
        self.initialize_text_tags()

        # Enable text widget for updates
        self.feed_text.config(state="normal")
        self.feed_text.delete('1.0', tk.END)  # Clear existing text

        separator = '\n-------------------------------------------------------------------------------------------------------\n'

        # Access additional data needed for display
        vip_clients, newreg_clients, oddsmonkey_selections, _, reporting_data = access_data()

        for bet in data:  # Iterate through each bet in the fetched data
            self.display_bet(bet, vip_clients, newreg_clients, oddsmonkey_selections)
            self.feed_text.insert('end', separator)
        
        self.update_activity_frame(reporting_data)
        # Disable the text widget to prevent user edits
        self.feed_text.config(state="disabled")

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
        self.runs_text = tk.Text(self.runs_frame, font=("Arial", 11), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
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