####################################################################################
##                                BETVIEWER.PY                                    


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



####################################################################################
## DEFAULT VALUES & GLOBAL VARIABLES BECAUSE LAZINESS
####################################################################################
DEFAULT_NUM_RECENT_FILES = 50
DEFAULT_NUM_BETS_TO_RUN = 3
current_file = None
selection_bets = {}
oddsmonkey_selections = {}
todays_oddsmonkey_selections = {}
enhanced_places = []
bet_info = {}  
bet_feed_lock = threading.Lock()
vip_clients = []
newreg_clients = []
courses_page = []
current_page = 0
courses_per_page = 6
blacklist = set()
closures_current_page = 0
requests_per_page = 8
last_notification = None

####################################################################################
## INITIALISE STAFF NAMES AND CREDENTIALS
####################################################################################
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



####################################################################################
## INITIALISE API CREDENTIALS
####################################################################################
with open('src/creds.json') as f:
    data = json.load(f)
pipedrive_api_token = data['pipedrive_api_key']
pipedrive_api_url = f'https://api.pipedrive.com/v1/itemSearch?api_token={pipedrive_api_token}'
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(data, scope)
gc = gspread.authorize(credentials)



####################################################################################
## GET DATA FROM DATA.JSON
####################################################################################

def get_newreg_clients():
    # Get New Registrations from pipedrive API
    global newreg_clients
    
    with open('src/data.json', 'r') as f:
        data = json.load(f)
        newreg_clients = data.get('new_registrations', [])

def get_vip_clients():
    global vip_clients

    with open('src/data.json', 'r') as f:
        data = json.load(f)
        vip_clients = data.get('vip_clients', [])

def get_reporting_data():
    global daily_turnover, daily_profit, daily_profit_percentage, last_updated_time, enhanced_places

    with open('src/data.json', 'r') as f:
        data = json.load(f)
        daily_turnover = data.get('daily_turnover', 0)
        daily_profit = data.get('daily_profit', 0)
        daily_profit_percentage = data.get('daily_profit_percentage', 0)
        last_updated_time = data.get('last_updated_time', '')
        total_deposits = data.get('deposits_summary', {}).get('total_deposits', 0)
        total_sum = data.get('deposits_summary', {}).get('total_sum', 0)
        enhanced_places = data.get('enhanced_places', [])

    avg_deposit = total_sum / total_deposits if total_deposits else 0
    total_sum = f"£{total_sum:,.2f}"
    avg_deposit = f"£{avg_deposit:,.2f}"

    return daily_turnover, daily_profit, daily_profit_percentage, last_updated_time, total_deposits, total_sum, avg_deposit, enhanced_places

def get_oddsmonkey_selections():
    global oddsmonkey_selections
    with open('src/data.json') as f:
        data = json.load(f)
        oddsmonkey_selections = data.get('oddsmonkey_selections', [])

    return oddsmonkey_selections

def get_todays_oddsmonkey_selections():
    global todays_oddsmonkey_selections
    with open('src/data.json') as f:
        data = json.load(f)
        todays_oddsmonkey_selections = data.get('todays_oddsmonkey_selections', [])

    return todays_oddsmonkey_selections



####################################################################################
## UPDATE/REFRESH DISPLAY
####################################################################################
def refresh_display():
    global current_file
    try:
        current_file = datetime.now().strftime('%Y-%m-%d') + '-wager_database.json'
        start_bet_feed(current_file)
        display_courses()
    except Exception as e:
        print(f"Error during refresh_display: {e}")
    else:
        print("Refreshed Bets")



####################################################################################
## GET JSON DATABASE
####################################################################################
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
            error_message = f"No bet data available for {date_str}. \nIf this is wrong, click 'Reprocess' on Bet Processor\n\n"
            # feed_text.after(0, update_feed_text, error_message)
            return []
        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                time.sleep(1)  
            else:
                error_message = f"Error: Could not decode JSON from file: {json_file_path}. "
                print(error_message)
                messagebox.showerror("Error", error_message)
                return []  
        except Exception as e:
            error_message = f"An error occurred: {e}"
            print(error_message)
            messagebox.showerror("Error", error_message)
            return []



####################################################################################
## FORMAT AND DISPLAY BETS, DISPLAY 'RISK' BETS
####################################################################################
def start_bet_feed(current_file=None):
    # logo_label.unbind("<Button-1>")

    data = get_database(current_file) if current_file else None
    bet_thread = threading.Thread(target=bet_feed, args=(data,))
    bet_thread.daemon = True
    bet_thread.start()

def bet_feed(data=None):
    global vip_clients, newreg_clients
    with bet_feed_lock:
        if data is None:
            data = get_database()

    bet_runs_thread = threading.Thread(target=bet_runs, args=(data,))
    bet_runs_thread.start()
    display_activity_data_thread = threading.Thread(target=display_activity_data, args=(data,))
    display_activity_data_thread.start()

    risk_bets = ""
    separator = '\n-------------------------------------------------------------------------------------\n'

    if feed_colours.get():
        feed_text.tag_configure("risk", foreground="#8f0000")
        feed_text.tag_configure("newreg", foreground="purple")
        feed_text.tag_configure("vip", foreground="#009685")
        feed_text.tag_configure("sms", foreground="orange")
        feed_text.tag_configure("Oddsmonkey", foreground="#ff00e6")
        feed_text.tag_configure("notices", font=("Helvetica", 11, "bold"))
    else:
        feed_text.tag_configure("risk", foreground="black")
        feed_text.tag_configure("newreg", foreground="black")
        feed_text.tag_configure("vip", foreground="black")
        feed_text.tag_configure("sms", foreground="black")

    feed_text.config(state="normal")
    feed_text.delete('1.0', tk.END)

    for bet in data:
        wager_type = bet.get('type', '').lower()
        if wager_type == 'wager knockback':
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
            if tag:
                feed_text.insert('end', f"{time} - {knockback_id} - {customer_ref} - WAGER KNOCKBACK:\n   {formatted_knockback_details}", tag)
            else:
                feed_text.insert('end', f"{time} - {knockback_id} - {customer_ref} - WAGER KNOCKBACK:\n   {formatted_knockback_details}")

        elif wager_type == 'sms wager':
            wager_number = bet.get('id', '')
            customer_reference = bet.get('customer_ref', '')
            sms_wager_text = bet.get('details', '')
            feed_text.insert('end', f"{customer_reference} - {wager_number} SMS WAGER:\n{sms_wager_text}", "sms")

        elif wager_type == 'bet':
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
                selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
                feed_text.insert('end', f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}", "risk")
                risk_bets += f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator
                if any(' - ' in sel[0] and sel[0].split(' - ')[1].strip() == om_sel[1][0].strip() and (sel[1] == 'SP' or (sel[1] == 'evs' and float(om_sel[1][1]) < 2.0) or (sel[1] != 'evs' and float(sel[1]) > float(om_sel[1][1]))) for sel in parsed_selections for om_sel in oddsmonkey_selections.items()):                    
                    feed_text.insert('end', f"\n ^ Oddsmonkey Selection Detected ^ ", "Oddsmonkey")
            elif customer_reference in vip_clients:
                selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
                feed_text.insert('end', f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}", "vip")
                if any(' - ' in sel[0] and sel[0].split(' - ')[1].strip() == om_sel[1][0].strip() and (sel[1] == 'SP' or (sel[1] == 'evs' and float(om_sel[1][1]) < 2.0) or (sel[1] != 'evs' and float(sel[1]) > float(om_sel[1][1]))) for sel in parsed_selections for om_sel in oddsmonkey_selections.items()):                    
                    feed_text.insert('end', f"\n ^ Oddsmonkey Selection Detected ^ ", "Oddsmonkey")
            elif customer_reference in newreg_clients:
                selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
                feed_text.insert('end', f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}", "newreg")
                if any(' - ' in sel[0] and sel[0].split(' - ')[1].strip() == om_sel[1][0].strip() and (sel[1] == 'SP' or (sel[1] == 'evs' and float(om_sel[1][1]) < 2.0) or (sel[1] != 'evs' and float(sel[1]) > float(om_sel[1][1]))) for sel in parsed_selections for om_sel in oddsmonkey_selections.items()):                    
                    feed_text.insert('end', f"\n ^ Oddsmonkey Selection Detected ^ ", "Oddsmonkey")
            else:
                selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
                feed_text.insert('end', f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}")
                if any(' - ' in sel[0] and sel[0].split(' - ')[1].strip() == om_sel[1][0].strip() and (sel[1] == 'SP' or (sel[1] == 'evs' and float(om_sel[1][1]) < 2.0) or (sel[1] != 'evs' and float(sel[1]) > float(om_sel[1][1]))) for sel in parsed_selections for om_sel in oddsmonkey_selections.items()):                    
                    feed_text.insert('end', f"\n ^ Oddsmonkey Selection Detected ^ ", "Oddsmonkey")
                     
        feed_text.insert('end', separator)

    feed_text.config(state="disabled")

    bets_with_risk_text.config(state="normal")
    bets_with_risk_text.delete('1.0', tk.END)
    bets_with_risk_text.insert('1.0', risk_bets)
    bets_with_risk_text.config(state="disabled")
    
def display_activity_data(data):
    turnover, profit, profit_percentage, last_updated_time, total_deposits, total_sum, avg_deposit, _ = get_reporting_data()

    total_bets = sum(1 for bet in data if bet.get('type', '').lower() == 'bet')
    total_knockbacks = sum(1 for bet in data if bet.get('type', '').lower() == 'wager knockback')
    percentage = total_knockbacks / total_bets * 100 if total_bets else 0

    activity_summary_text.tag_configure("activity", font=("Helvetica", 10, "bold"), justify="center")
    activity_summary_text.config(state="normal")
    activity_summary_text.delete('1.0', tk.END)
    activity_summary_text.insert('1.0', f"Bets: {total_bets} | Knockbacks: {total_knockbacks}  -  {percentage:.2f}%\nTurnover: {turnover} | Profit: {profit}  -  {profit_percentage}\nDeposits: {total_deposits} | Amount: {total_sum} | Average: {avg_deposit}", "activity")
    activity_summary_text.config(state="disabled")



####################################################################################
## DISPLAY 'RUNS ON SELECTIONS' PANEL
####################################################################################
def set_recent_bets(*args):
    global DEFAULT_NUM_RECENT_FILES
    DEFAULT_NUM_RECENT_FILES = combobox_var.get()
    refresh_display()

def set_num_run_bets(*args):
    global DEFAULT_NUM_BETS_TO_RUN
    new_value = int(num_run_bets_var.get())
    if new_value is not None:
        DEFAULT_NUM_BETS_TO_RUN = new_value
    refresh_display()

def bet_runs(data):
    global DEFAULT_NUM_BETS_TO_RUN, DEFAULT_NUM_RECENT_FILES, enhanced_places, todays_oddsmonkey_selections
    num_bets = DEFAULT_NUM_BETS_TO_RUN

    selection_bets = data

    selection_bets = selection_bets[:DEFAULT_NUM_RECENT_FILES]

    selection_to_bets = defaultdict(list)

    for bet in selection_bets:
        if isinstance(bet['details'], dict):
            selections = [selection[0] for selection in bet['details'].get('selections', [])]
            for selection in selections:
                selection_to_bets[selection].append(bet['id'])

    sorted_selections = sorted(selection_to_bets.items(), key=lambda item: len(item[1]), reverse=True)

    runs_text.tag_configure("risk", foreground="#8f0000")
    runs_text.tag_configure("vip", foreground="#009685")
    runs_text.tag_configure("newreg", foreground="purple")
    runs_text.tag_configure("oddsmonkey", foreground="#ff00e6")
    runs_text.config(state="normal")
    runs_text.delete('1.0', tk.END)

    for selection, bet_numbers in sorted_selections:
        skip_selection = False
        if runs_remove_off_races.get(): 
            race_time_str = selection.split(", ")[1] if ", " in selection else None
            if race_time_str:
                try:
                    race_time_str = race_time_str.split(" - ")[0]
                    race_time = datetime.strptime(race_time_str, "%H:%M")
                    if race_time < datetime.now():
                        skip_selection = True
                except ValueError:
                    pass

        if skip_selection:
            continue

        if len(bet_numbers) > num_bets:
            selection_name = selection.split(' - ')[1] if ' - ' in selection else selection

            matched_odds = None
            for om_sel in todays_oddsmonkey_selections.values():
                if selection_name == om_sel[0]:
                    matched_odds = float(om_sel[1])
                    break

            if matched_odds is not None:
                runs_text.insert(tk.END, f"{selection} | OM Lay: {matched_odds}\n", "oddsmonkey")
            else:
                runs_text.insert(tk.END, f"{selection}\n")

            for bet_number in bet_numbers:
                bet_info = next((bet for bet in selection_bets if bet['id'] == bet_number), None)
                if bet_info:
                    for sel in bet_info['details']['selections']:
                        if selection == sel[0]:
                            if 'risk_category' in bet_info['details'] and bet_info['details']['risk_category'] != '-':
                                runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n", "risk")
                            elif bet_info['customer_ref'] in vip_clients:
                                runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n", "vip")
                            elif bet_info['customer_ref'] in newreg_clients:
                                runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n", "newreg")
                            else:
                                runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n")

            # Extract the meeting name and time from the selection
            meeting_time = ' '.join(selection.split(' ')[:2])

            # Check if the meeting name and time is in the enhanced_places list
            if meeting_time in enhanced_places:
                runs_text.insert(tk.END, 'Enhanced Place Race\n', "oddsmonkey")
            
            runs_text.insert(tk.END, f"\n")

    runs_text.config(state=tk.DISABLED)



####################################################################################
## DISPLAY NEXT 3 HORSE & GREYHOUND RACES
####################################################################################
def run_display_next_3():
    threading.Thread(target=display_next_3).start()
    root.after(10000, run_display_next_3)

def process_data(data, labels_type):
    global enhanced_places
    global horse_labels
    global greyhound_labels
    
    labels = horse_labels if labels_type == 'horse' else greyhound_labels

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

        if race in enhanced_places:
            labels[i].config(foreground='#ff00e6')
        else:
            labels[i].config(foreground='black')

        # Create a label for each meeting and place it in the grid
        labels[i].config(text=f"{race} ({ptype})\n{status}")

def display_next_3():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }

    horse_response = requests.get('https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=H,h,o', headers=headers)
    greyhound_response = requests.get('https://globalapi.geoffbanks.bet/api/Geoff/NewLive?sportcode=g', headers=headers)

    # Check if the responses are not empty and have a status code of 200 (OK)
    if horse_response.status_code == 200 and greyhound_response.status_code == 200:

        horse_data = horse_response.json()
        greyhound_data = greyhound_response.json()

        # Process the horse and greyhound data
        process_data(horse_data, 'horse')
        process_data(greyhound_data, 'greyhound')    

    else:
        print("Error: The response from the API is not OK.")
        return



####################################################################################
## RACE UPDATION TRACKER
####################################################################################
def get_courses():
    with open('src/creds.json') as f:
        creds = json.load(f)
    today = date.today()
    url = "https://horse-racing.p.rapidapi.com/racecards"
    querystring = {"date": today.strftime('%Y-%m-%d')}
    headers = {
        "X-RapidAPI-Key": creds['rapidapi_key'],
        "X-RapidAPI-Host": "horse-racing.p.rapidapi.com"
    }
    response = requests.get(url, headers=headers, params=querystring)
    data = response.json()

    if not isinstance(data, list):
        print("Error: The response from the API is not a list.", data)
        return

    courses = set()
    for race in data:
        try:
            courses.add(race['course'])
        except TypeError:
            print("Error: The 'race' object is not a dictionary.")
            return []

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

    display_courses()

    return courses

def reset_update_times():
    if os.path.exists('update_times.json'):
        os.remove('update_times.json')

    update_data = {'date': '', 'courses': {}}
    with open('update_times.json', 'w') as f:
        json.dump(update_data, f)
    
    display_courses()

def course_needs_update(course, data):
    if course in data['courses'] and data['courses'][course]:
        last_updated_time = data['courses'][course].split(' ')[0]
        last_updated = datetime.strptime(last_updated_time, '%H:%M').time()
    else:
        last_updated = datetime.now().time()

    now = datetime.now().time()

    time_diff = (datetime.combine(date.today(), now) - datetime.combine(date.today(), last_updated)).total_seconds() / 60

    if course in ["SIS Greyhounds", "TRP Greyhounds"]:
        return time_diff >= 60
    else:
        return time_diff >= 25

def display_courses():
    global courses_page, current_page
    for widget in race_updation_frame.winfo_children():
        widget.destroy()
    today = date.today()

    with open('update_times.json', 'r') as f:
        data = json.load(f)

    courses = list(data['courses'].keys())
    courses.sort(key=lambda x: (x=="SIS Greyhounds", x=="TRP Greyhounds"))
    start = current_page * courses_per_page
    end = start + courses_per_page
    courses_page = courses[start:end]

    button_frame = ttk.Frame(race_updation_frame)
    button_frame.grid(row=len(courses_page), column=0, padx=2, sticky='ew')

    # Create the add button and align it to the left of the Frame
    add_button = ttk.Button(button_frame, text="+", command=add_course, width=2, cursor="hand2")
    add_button.pack(side='left')

    # Add an indicator in the middle
    update_indicator = ttk.Label(button_frame, text="\u2022", foreground='red', font=("Helvetica", 24))
    update_indicator.pack(side='left', padx=2, pady=2, expand=True)

    # Create the remove button and align it to the right of the Frame
    remove_button = ttk.Button(button_frame, text="-", command=remove_course, width=2, cursor="hand2")
    remove_button.pack(side='right')

    for i, course in enumerate(courses_page):
        # Replace the course label with a button
        course_button = ttk.Button(race_updation_frame, text=course, command=lambda course=course: update_course(course), width=15, cursor="hand2")
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

        time_label = ttk.Label(race_updation_frame, text=time_text, foreground=color)
        time_label.grid(row=i, column=1, padx=5, pady=2, sticky="w")

    navigation_frame = ttk.Frame(race_updation_frame)
    navigation_frame.grid(row=len(courses_page), column=1, padx=2, pady=2, sticky='ew')

    back_button = ttk.Button(navigation_frame, text="<", command=back, width=2, cursor="hand2")
    back_button.grid(row=0, column=0, padx=2, pady=2)

    forward_button = ttk.Button(navigation_frame, text=">", command=forward, width=2, cursor="hand2")
    forward_button.grid(row=0, column=1, padx=2, pady=2)

    # Check if any course on other pages needs updating
    other_courses = [course for i, course in enumerate(courses) if i < start or i >= end]
    if any(course_needs_update(course, data) for course in other_courses):
        update_indicator.pack()
    else:
        update_indicator.pack_forget()

    if current_page == 0:
        back_button.config(state='disabled')
    else:
        back_button.config(state='normal')

    if current_page == len(courses) // courses_per_page:
        forward_button.config(state='disabled')
    else:
        forward_button.config(state='normal')

def remove_course():
    # Open a dialog box to get the course name
    course = simpledialog.askstring("Remove Course", "Enter the course name:")
    
    with open('update_times.json', 'r') as f:
        data = json.load(f)
    if course in data['courses']:
        del data['courses'][course]

    with open('update_times.json', 'w') as f:
        json.dump(data, f)

    log_notification(f"'{course}' removed by {user}")

    display_courses()

def add_course():
    course_name = simpledialog.askstring("Add Course", "Enter the course name:")
    if course_name:
        with open('update_times.json', 'r') as f:
            data = json.load(f)

        data['courses'][course_name] = ""

        with open('update_times.json', 'w') as f:
            json.dump(data, f)

        log_notification(f"'{course_name}' added by {user}")

        display_courses()

def back():
    global current_page
    if current_page > 0:
        current_page -= 1
        display_courses()

def forward():
    global current_page
    with open('update_times.json', 'r') as f:
        data = json.load(f)
    total_courses = len(data['courses'].keys())
    if (current_page + 1) * courses_per_page < total_courses:
        current_page += 1
        display_courses()

def update_course(course):
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

    log_update(course, time_string, user)
    display_courses()

def log_update(course, time, user):
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



####################################################################################
## CREATE DAILY, CLIENT, STAFF REPORTS & SCREEN FOR RISK CLIENTS
####################################################################################
def create_daily_report(current_file=None):
    data = get_database(current_file)
    report_output = ""
    
    if current_file and '-wager_database.json' in current_file:
        date_string = current_file.split('-wager_database.json')[0]
        current_date = datetime.strptime(date_string, '%Y-%m-%d').date()
    else:
        current_date = date.today()
        date_string = current_date.strftime("%d-%m-%y")


    # Get the current time
    time = datetime.now()
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
    progress["maximum"] = len(data)
    progress["value"] = 0
    root.update_idletasks()

    for i, bet in enumerate(data):
        progress["value"] = i + 1
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

    separator = "\n---------------------------------------------------------------------------------\n"

    report_output += f"---------------------------------------------------------------------------------\n"
    report_output += f"\tDAILY REPORT TICKET {date_string}\n\t        Generated at {formatted_time}"
    report_output += f"{separator}"

    report_output += f"\nStakes: £{total_stakes:,.2f}  |  "
    report_output += f"Bets: {total_bets}  |  "
    report_output += f"Knockbacks: {total_wageralerts}"
    report_output += f"\n\tKnockback Percentage: {total_wageralerts / total_bets * 100:.2f}%"
    report_output += f"\n\tAverage Stake: £{total_stakes / total_bets:,.2f}\n"

    # Add the sport bet percentages to the report
    report_output += f"\nSport Type Percentages:\n"
    report_output += f"\tHorse Racing: {percentage_horse_racing:.2f}%\n"
    report_output += f"\tGreyhounds: {percentage_greyhound:.2f}%\n"
    report_output += f"\tOther: {percentage_other:.2f}%"

    report_output += f"\n\nClients: {total_clients}  |  "
    report_output += f"No Risk: {total_norisk_clients}  |  "
    report_output += f"M: {total_m_clients}  |  "
    report_output += f"W: {total_w_clients}"
    report_output += f"\n\tRisk Cat. Percentage: {total_m_clients / total_clients * 100:.2f}%"

    report_output += "\n\nHighest Spend:\n"
    for rank, (customer, spend) in enumerate(top_spenders, start=1):
        report_output += f"\t{rank}. {customer} - Stakes: £{spend:,.2f}\n"

    report_output += "\nMost Bets:\n"
    for rank, (client, count) in enumerate(top_client_bets, start=1):
        report_output += f"\t{rank}. {client} - Bets: {count}\n"

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

    report_output += f"\nMost Knockbacks:\n"
    for rank, (client, count) in enumerate(top_wageralert_clients, start=1):
        report_output += f"\t{rank}. {client} - Knockbacks: {count}\n"

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

    report_output += f"\n{separator}"
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


    report_ticket.config(state="normal")
    report_ticket.delete('1.0', tk.END)
    report_ticket.insert('1.0', report_output)
    report_ticket.config(state="disabled")

def create_client_report(customer_ref, current_file=None):
    data = get_database(current_file)

    if current_file and '-wager_database.json' in current_file:
        date_string = current_file.split('-wager_database.json')[0]
        current_date = datetime.strptime(date_string, '%Y-%m-%d').date()
    else:
        current_date = date.today()
        date_string = current_date.strftime("%d-%m-%y")

    report_output = ""
    client_report_feed = ""
    separator = "\n\n---------------------------------------------------------------------------------\n\n"

    time = datetime.now()
    formatted_time = time.strftime("%H:%M:%S")

    total_bets = 0
    total_stakes = 0.0

    total_wageralerts = 0
    liability_exceeded = 0
    price_change = 0
    event_ended = 0
    other_alert = 0
    user_restriction = 0
    price_type_disallowed = 0
    sport_disallowed = 0
    max_stake_exceeded = 0
    total_sms = 0

    timestamps = []
    hour_ranges = {}

    for i, bet in enumerate(data):
        bet_type = bet['type'].lower()
        is_sms = bet_type == 'sms wager'
        is_bet = bet_type == 'bet'
        is_wageralert = bet_type == 'wager knockback'
        
        if is_bet and bet['customer_ref'] == customer_ref:
            selection = "\n".join([f"   - {sel} at {odds}" for sel, odds in bet['details']['selections']])
            client_report_feed += f"{bet['time']}-{bet['id']} | {bet['customer_ref']} ({bet['details']['risk_category']}) | {bet['details']['unit_stake']} {bet['details']['bet_details']}, {bet['details']['bet_type']}:\n{selection}" + separator
            timestamps.append(bet['time'])
            total_stakes += float(bet['details']['payment'][1:].replace(',', ''))
            total_bets += 1

        if is_wageralert and bet['customer_ref'] == customer_ref:
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
            total_wageralerts += 1

            formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items() if key not in ['Selections', 'Knockback ID', 'Time', 'Customer Ref', 'Error Message']])
            formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' for i, selection in enumerate(knockback_details.get('Selections', []))])
            formatted_knockback_details += '\n   ' + formatted_selections

            error_message = knockback_details.get('Error Message', '')
            if 'Maximum stake available' in error_message:
                error_message = error_message.replace(', Maximum stake available', '\n   Maximum stake available')
            formatted_knockback_details = f"Error Message: {error_message}\n   {formatted_knockback_details}"
            client_report_feed += f"{bet['time']} - {bet['customer_ref']} - WAGER KNOCKBACK:\n   {formatted_knockback_details}" + separator
      
        if is_sms and bet['customer_ref'] == customer_ref:
            client_report_feed += f"{bet['time']}-{bet['id']} | {bet['customer_ref']} SMS WAGER:\n{bet['details']}" + separator
            total_sms += 1

    timestamp_hours = [timestamp.split(':')[0] + ":00" for timestamp in timestamps]
    hour_counts = Counter(timestamp_hours)

    report_output += f"---------------------------------------------------------------------------------\n"
    report_output += f"        CLIENT REPORT FOR {customer_ref} {date_string}\n\t        Generated at {formatted_time}"
    report_output += f"\n---------------------------------------------------------------------------------\n"

    report_output += f"TOTALS - Stakes: £{total_stakes:.2f} | Bets: {total_bets}\n\n"

    report_output += f"BETS PER HOUR:\n"
    for hour, count in hour_counts.items():
        start_hour = hour
        end_hour = f"{int(start_hour.split(':')[0]) + 1:02d}:00"
        hour_range = f"{start_hour} - {end_hour}"
        if hour_range in hour_ranges:
            hour_ranges[hour_range] += count
        else:
            hour_ranges[hour_range] = count

    for hour_range, count in hour_ranges.items():
        report_output += f"{hour_range} - Bets {count}\n"

    report_output += f"\nKNOCKBACKS: {total_wageralerts}\n\n"
    report_output += f"Liability Exceeded: {liability_exceeded}\n"
    report_output += f"Price Changes: {price_change}\n"
    report_output += f"Event Ended: {event_ended}\n\n"
    report_output += f"User Restrictions: {user_restriction}\n"
    report_output += f"Price Type Disallowed: {price_type_disallowed}\n"
    report_output += f"Sport Disallowed: {sport_disallowed}\n"
    report_output += f"Max Stake Exceeded: {max_stake_exceeded}\n"
    report_output += f"Other: {other_alert}\n"

    report_output += f"\nTEXTBETS: {total_sms}\n"

    report_output += f"\n\nFULL FEED FOR {customer_ref}:{separator}"

    report_ticket.config(state="normal")
    report_ticket.delete('1.0', tk.END)
    report_ticket.insert('1.0', client_report_feed)
    report_ticket.insert('1.0', report_output)
    report_ticket.config(state="disabled")    

def create_staff_report():
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
    progress["maximum"] = len(log_files)
    progress["value"] = 0
    # Read all the log files from the past month
    for i, log_file in enumerate(log_files):

        progress["value"] = i + 1
        root.update_idletasks()

        file_date = datetime.fromtimestamp(os.path.getmtime('logs/updatelogs/' + log_file)).date()
        if month_ago <= file_date <= current_date:
            with open('logs/updatelogs/' + log_file, 'r') as file:
                lines = file.readlines()

            last_update = {}
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


    report_output += f"---------------------------------------------------------------------------------\n"
    report_output += f"\t    STAFF REPORT {current_date.strftime('%d-%m-%y')}\n"
    report_output += f"---------------------------------------------------------------------------------\n"

    employee_of_the_month, _ = staff_updates.most_common(1)[0]
    report_output += f"\nEmployee Of The Month: {employee_of_the_month}\n"

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

    report_ticket.config(state="normal")
    report_ticket.delete('1.0', tk.END)
    report_ticket.insert('1.0', report_output)
    report_ticket.config(state="disabled")

def find_traders():
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

    for bet in data:
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
                if race_meeting in enhanced_places:
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

def find_rg_issues():
    
    data = get_database()
    user_scores = {}
    virtual_events = ['Portman Park', 'Sprintvalley', 'Steepledowns', 'Millersfield', 'Brushwood']

    for bet in data:
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

def update_rg_report():
    user_scores = find_rg_issues()
    # Sort the user_scores dictionary by total score
    user_scores = dict(sorted(user_scores.items(), key=lambda item: item[1]['score'], reverse=True))
    # Create a dictionary to map the keys to more descriptive sentences
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
    report_output += f"          RESPONSIBLE GAMBLING SCREENER\n\n"

    for user, scores in user_scores.items():
        if scores['score'] > 1:
            report_output += f"-----------------------------------------------------------------\n"
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

    traders_report_ticket.config(state='normal')
    traders_report_ticket.delete('1.0', tk.END)
    traders_report_ticket.insert(tk.END, report_output)
    traders_report_ticket.config(state='disabled')

def update_traders_report():
    users_without_risk_category, oddsmonkey_traders, enhanced_bets_counter = find_traders()

    username_counts = Counter(trader['username'] for trader in oddsmonkey_traders)
    top_users = username_counts.most_common(6)
    top_enhanced_users = {user for user, count in enhanced_bets_counter.items() if count > 3}


    users_without_risk_category_str = '  |  '.join(user[0] for user in users_without_risk_category)

    traders_report_ticket.config(state='normal')
    traders_report_ticket.delete('1.0', tk.END)
    traders_report_ticket.insert(tk.END, "                      TRADERS SCREENER\n\n")
    traders_report_ticket.insert(tk.END, "-----------------------------------------------------------------\n") 

    traders_report_ticket.insert(tk.END, "Clients backing selections shown on OddsMonkey above the lay price:\n")
    for user, count in top_users:
        traders_report_ticket.insert(tk.END, f"\t{user}, Count: {count}\n")

    traders_report_ticket.insert(tk.END, "\nClients wagering frequently on Extra Place Races:\n\n")
    for user in sorted(top_enhanced_users, key=enhanced_bets_counter.get, reverse=True):  # Sort by count
        traders_report_ticket.insert(tk.END, f"\t{user}, Count: {enhanced_bets_counter[user]}\n")

    traders_report_ticket.insert(tk.END, "\nClients wagering on selections containing multiple risk users:\n\n")
    traders_report_ticket.insert(tk.END, users_without_risk_category_str)

    #traders_report_ticket.insert(tk.END, "\n\nList of users taking higher odds than Oddsmonkey:\n")
    #for trader in oddsmonkey_traders:
    #    traders_report_ticket.insert(tk.END, f"{trader['username']}, Selection: {trader['selection_name']}\nOdds Taken: {trader['user_odds']}, Lay Odds: {trader['oddsmonkey_odds']}\n\n")

    traders_report_ticket.config(state='disabled')



####################################################################################
## GET & DISPLAY 'FACTORING' SHEET, HANDLE NEW FACTORING ENTRIES
####################################################################################
def factoring_sheet():
    tree.delete(*tree.get_children())
    spreadsheet = gc.open('Factoring Diary')
    print("Getting Factoring Sheet")
    worksheet = spreadsheet.get_worksheet(4)
    data = worksheet.get_all_values()
    print("Retrieving factoring data")

    for row in data[2:]:
        tree.insert("", "end", values=[row[0], row[1], row[2], row[3], row[4]])

def open_factoring_wizard():
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
        response = requests.get(pipedrive_api_url, params=params)
        progress.set(20)
        if response.status_code == 200:
            persons = response.json()['data']['items']
            if not persons:
                messagebox.showerror("Error", f"No persons found for username: {entry1.get()}. Please make sure the username is correct, or enter the risk category in pipedrive manually.")
                return

            for person in persons:
                person_id = person['item']['id']

                update_url = f'https://api.pipedrive.com/v1/persons/{person_id}?api_token={pipedrive_api_token}'
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

        spreadsheet = gc.open('Factoring Diary')
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
        worksheet.update_cell(next_row, 6, current_date)  # Column F

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
        tree.insert("", "end", values=[current_time, entry1.get().upper(), entry2_value, entry3.get(), user])
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
     
    assrating = ttk.Label(wizard_window_frame, text="Assessment Rating")
    assrating.pack(padx=5, pady=5)
    entry3 = ttk.Entry(wizard_window_frame)
    entry3.pack(padx=5, pady=5)

    factoring_note = ttk.Label(wizard_window_frame, text="Risk Category will be updated in Pipedrive.\n\n", anchor='center', justify='center')
    factoring_note.pack(padx=5, pady=5)

    submit_button = ttk.Button(wizard_window_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2")
    submit_button.pack(padx=5, pady=5)

    progress_bar = ttk.Progressbar(wizard_window_frame, length=200, mode='determinate', variable=progress)
    progress_bar.pack(padx=5, pady=5)



####################################################################################
## DISPLAY CLOSURE (EXCLUSION) REQUESTS, SEND CONFIRMATION EMAILS & REPORT
####################################################################################
def display_closure_requests():
    global closures_current_page, requests_per_page, blacklist


    # Clear the old requests from the UI
    for widget in requests_frame.winfo_children():
        widget.destroy()


    def handle_request(request):
        log_notification(f"{user} Handling {request['Restriction']} request for {request['Username']} ")

        # Define the mapping for the 'restriction' field
        restriction_mapping = {
            'Further Options': 'Self Exclusion'
        }

        # Map the 'restriction' field
        request['Restriction'] = restriction_mapping.get(request['Restriction'], request['Restriction'])

        # Get the current date
        current_date = datetime.now()

        # Convert the 'Length' string to a number of years or days
        length_mapping = {
            'One Day': timedelta(days=1),
            'One Week': timedelta(weeks=1),
            'Two Weeks': timedelta(weeks=2),
            'Four Weeks': timedelta(weeks=4),
            'Six Weeks': timedelta(weeks=6),
            '6 Months': relativedelta(months=6),
            'One Year': relativedelta(years=1),
            'Two Years': relativedelta(years=2),
            'Three Years': relativedelta(years=3),
            'Four Years': relativedelta(years=4),
            'Five Years': relativedelta(years=5),
        }
        length_in_time = length_mapping.get(request['Length'], timedelta(days=0))

        # Calculate the reopen date
        reopen_date = current_date + length_in_time

        # Format the string to be copied to the clipboard
        copy_string = f"{request['Restriction']}"

        # Add the 'Length' to the string if it's not 'None' or 'Null'
        if request['Length'] not in [None, 'None', 'Null']:
            copy_string += f" {request['Length']}"

        copy_string += f" {current_date.strftime('%d/%m/%Y')}"
        copy_string = copy_string.upper()

        # If the restriction is 'Take-a-break' or 'Self Exclusion', add the reopen date to the string
        if request['Restriction'] in ['Take-A-Break', 'Self Exclusion']:
            copy_string += f" (CAN REOPEN {reopen_date.strftime('%d/%m/%Y')})"

        # Add the user to the string
        copy_string += f" {user}"

        # Copy the string to the clipboard
        pyperclip.copy(copy_string)

        def handle_submit():
            if confirm_betty_update_bool.get():
                try:
                    if send_confirmation_email_bool.get():
                        threading.Thread(target=send_email, args=(request['Username'], request['Restriction'], request['Length'])).start()
                except Exception as e:
                    print(f"Error sending email: {e}")

                try:
                    if archive_email_bool.get():
                        threading.Thread(target=archive_email, args=(request['email_id'],)).start()
                except Exception as e:
                    print(f"Error archiving email: {e}")

                try:
                    threading.Thread(target=report_closure_requests, args=(request['Restriction'], request['Username'], request['Length'])).start()
                except Exception as e:
                    print(f"Error reporting closure requests: {e}")

                # Mark the request as completed
                request['completed'] = True

                # Write the updated data back to 'data.json'
                with open('src/data.json', 'w') as f:
                    json.dump(data, f, indent=4)

                # Add the user to the blacklist
                blacklist.add(request['Username'])

                # Destroy the request window
                handle_closure_request.destroy()

                # Redisplay the closure requests
                if request['completed']:
                    display_closure_requests()

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

        confirm_betty_update = ttk.Checkbutton(handle_closure_request_frame, text='Confirm Closed on Betty', variable=confirm_betty_update_bool, onvalue=True, offvalue=False, cursor="hand2")
        confirm_betty_update.place(x=10, y=80)

        send_confirmation_email = ttk.Checkbutton(handle_closure_request_frame, text='Send Pipedrive Confirmation Email', variable=send_confirmation_email_bool, onvalue=True, offvalue=False, cursor="hand2")
        send_confirmation_email.place(x=10, y=110)

        if user == 'DF':
            archive_email_check = ttk.Checkbutton(handle_closure_request_frame, text='Archive Email Request', variable=archive_email_bool, onvalue=True, offvalue=False, cursor="hand2")
            archive_email_check.place(x=10, y=140)

        submit_button = ttk.Button(handle_closure_request_frame, text="Submit", command=handle_submit, cursor="hand2")
        submit_button.place(x=80, y=190)

        ## Labels
        closure_request_label = ttk.Label(handle_closure_request_frame, text=f"Close on Betty before anything else!\n\nPlease double check:\n- Request details above are correct\n- Confirmation email was sent to client.\n\nReport to Sam any errors.", anchor='center', justify='center')
        closure_request_label.place(x=10, y=240)

    # Read the data from data.json
    with open('src/data.json', 'r') as f:
        data = json.load(f)
        requests = [request for request in data.get('closures', []) if not request.get('completed', False)]

    # Check if the requests list is empty
    if not requests:
        # Create a text widget with a message
        notebook.tab(tab_5, text="Requests")
        no_requests_label = ttk.Label(requests_frame, text="No requests to display.", width=40, anchor='center', justify='center')
        no_requests_label.grid(row=0, column=0, padx=10, pady=2, sticky="w")
    else:
        notebook.tab(tab_5, text="Requests*")
        start = closures_current_page * requests_per_page
        end = start + requests_per_page
        requests_page = requests[start:end]

        # Define the mapping for the 'restriction' field
        restriction_mapping = {
            'Account Deactivation': 'Deactivation',
            'Further Options': 'Self Exclusion'
        }

        # Loop over the requests on the current page and create a label and a tick button for each one
        for i, request in enumerate(requests_page):
            # Map the 'restriction' field
            restriction = restriction_mapping.get(request['Restriction'], request['Restriction'])

            # Check if the 'length' field is None or Null
            length = request['Length'] if request['Length'] not in [None, 'Null'] else ''

            # Create a label with the request data
            request_label = ttk.Label(requests_frame, text=f"{restriction} | {request['Username']} | {length}", width=40)
            request_label.grid(row=i, column=1, padx=10, pady=2, sticky="w")

            # Create a tick button
            tick_button = ttk.Button(requests_frame, text="✔", command=lambda request=request: handle_request(request), width=2, cursor="hand2")
            tick_button.grid(row=i, column=0, padx=3, pady=2)

        # Create the back and forward buttons
        back_button = ttk.Button(requests_frame, text="<", command=closures_back, width=2, cursor="hand2")
        back_button.grid(row=requests_per_page, column=1, padx=2, pady=2)

        forward_button = ttk.Button(requests_frame, text=">", command=closures_forward, width=2, cursor="hand2")
        forward_button.grid(row=requests_per_page, column=1, padx=2, pady=2)

        # Remove the back button if we're on the first page
        if closures_current_page == 0:
            back_button.grid_remove()

        # Remove the forward button if we're on the last page
        if closures_current_page == len(requests) // requests_per_page:
            forward_button.grid_remove()

def closures_back():
    global closures_current_page
    if closures_current_page > 0:
        closures_current_page -= 1
        display_closure_requests()

def closures_forward():
    global closures_current_page, requests_per_page
    with open('src/data.json', 'r') as f:
        data = json.load(f)

    total_requests = len([request for request in data.get('closures', []) if request['Username'] not in blacklist])
    if (closures_current_page + 1) * requests_per_page < total_requests:
        closures_current_page += 1
        display_closure_requests()

def update_person(update_url, update_data, person_id):
    update_response = requests.put(update_url, json=update_data)
    print(update_url, update_data, person_id)

    if update_response.status_code == 200:
        print(f'Successfully updated person {person_id}')
    else:
        print(f'Error updating person {person_id}: {update_response.status_code}')
        print(f'Response: {update_response.json()}')

def send_email(username, restriction, length):
    print(username, restriction, length)

    params = {
        'term': username,
        'item_types': 'person',
        'fields': 'custom_fields',
        'exact_match': 'true',
    }

    try:
        response = requests.get(pipedrive_api_url, params=params)
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
        update_url = f'https://api.pipedrive.com/v1/persons/{person_id}?api_token={pipedrive_api_token}'

        if restriction == 'Account Deactivation':
            update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': "Deactivated"}
            update_person(update_url, update_data, person_id)

        elif restriction == 'Further Options':
            if length.split()[0] in number_mapping:
                digit_length = length.replace(length.split()[0], number_mapping[length.split()[0]])
                update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'SE {digit_length}'}
                update_person(update_url, update_data, person_id)
            else:
                print("Error: Invalid length")

        elif restriction == 'Take-A-Break':
            if length.split()[0] in number_mapping:
                digit_length = length.replace(length.split()[0], number_mapping[length.split()[0]])
                update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'TAB {digit_length}'}
                update_person(update_url, update_data, person_id)
            else:
                print("Error: Invalid length")
    
def archive_email(msg_id):
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

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=creds)

    # Get the current labels of the message
    message = service.users().messages().get(userId='me', id=msg_id).execute()
    current_labels = message['labelIds']

    # Remove all current labels from the message
    return service.users().messages().modify(
      userId='me',
      id=msg_id,
      body={
          'removeLabelIds': current_labels
      }
    ).execute()

def report_closure_requests(restriction, username, length):
    current_date = datetime.now().strftime("%d/%m/%Y")  


    try:
        spreadsheet = gc.open("Management Tool")
    except gspread.SpreadsheetNotFound:
        messagebox.showerror("Error", f"Spreadsheet 'Management Tool' not found. Please notify Sam, or enter the exclusion details manually.")
        return


    if restriction == 'Account Deactivation':
        worksheet = spreadsheet.get_worksheet(31)
        next_row = len(worksheet.col_values(1)) + 1
        worksheet.update_cell(next_row, 2, username.upper())
        worksheet.update_cell(next_row, 1, current_date)

    elif restriction == 'Further Options':
        worksheet = spreadsheet.get_worksheet(34)
        next_row = len(worksheet.col_values(1)) + 1
        worksheet.update_cell(next_row, 2, username.upper())
        worksheet.update_cell(next_row, 1, current_date)
        worksheet.update_cell(next_row, 3, length)

    elif restriction == 'Take-A-Break':
        worksheet = spreadsheet.get_worksheet(33)
        next_row = len(worksheet.col_values(1)) + 1
        worksheet.update_cell(next_row, 2, username.upper())
        worksheet.update_cell(next_row, 1, current_date)
        worksheet.update_cell(next_row, 3, length.upper())
    
    else:
        print("Error: Invalid restriction")



####################################################################################
## REPORT A CREDITED FREE BET
####################################################################################
def report_freebet():
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
            spreadsheet = gc.open(spreadsheet_name)
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



####################################################################################
## STAFF LOGIN TO TRACK UPDATES
####################################################################################
def user_login():
    global user
    global full_name
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

    # login_label.config(text=f'Logged in as {full_name}')



####################################################################################
## SETTINGS WINDOW
####################################################################################
def open_settings():
    def load_database(event):
        global current_file
        selected_file = databases_combobox.get()
        current_file = selected_file

        match = re.search(r'\d{4}-\d{2}-\d{2}', selected_file)
        if match:
            date_str = match.group()
        else:
            print(f"Error: Could not extract date from file name: {selected_file}")
            return

        data = get_database(date_str)

        bet_feed(data)

    settings_window = tk.Toplevel(root)
    settings_window.title("Settings")
    settings_window.iconbitmap('src/splash.ico')

    settings_window.geometry("310x430")

    settings_window.resizable(False, False)

    screen_width = settings_window.winfo_screenwidth()
    settings_window.geometry(f"+{screen_width - 350}+50")

    # OPTIONS FRAME
    options_frame = ttk.Frame(settings_window, style='Card', width=120, height=205)
    options_frame.place(x=5, y=5, width=300, height=420)

    toggle_button = ttk.Checkbutton(options_frame, text='Auto Refresh', variable=auto_refresh_state, onvalue=True, offvalue=False, cursor="hand2")
    toggle_button.place(x=60, y=5)

    enable_feed_colours = ttk.Checkbutton(options_frame, text='Feed Colours', variable=feed_colours, onvalue=True, offvalue=False, cursor="hand2")
    enable_feed_colours.place(x=60, y=30)

    courses_label = ttk.Label(options_frame, text="Get todays meetings or reset current list")
    courses_label.place(x=25, y=70)

    get_courses_button = ttk.Button(options_frame, text="Get Courses", command=get_courses, cursor="hand2")
    get_courses_button.place(x=30, y=100, width=110)

    reset_courses_button = ttk.Button(options_frame, text="Reset Courses", command=reset_update_times, cursor="hand2")
    reset_courses_button.place(x=160, y=100, width=110)

    separator = ttk.Separator(options_frame, orient='horizontal')
    separator.place(x=10, y=160, width=270)

    json_files = [f for f in os.listdir('database') if f.endswith('.json')]

    databases_combobox = ttk.Combobox(options_frame, values=json_files, width=4)
    databases_combobox.place(x=20, y=190, width=250)

    previous_database_label = ttk.Label(options_frame, text="Selecting old database disables auto refresh.\n   You will need to reload the application.")
    previous_database_label.place(x=10, y=230, width=280)

    separator = ttk.Separator(options_frame, orient='horizontal')
    separator.place(x=10, y=290, width=270)

    if current_file is not None:
        databases_combobox.set(current_file)
    else:
        databases_combobox.set("Select previous database...")

    databases_combobox.bind('<<ComboboxSelected>>', load_database)



####################################################################################
## GENERATE TEMPORARY PASSWORD
####################################################################################
def generate_random_string():
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    generated_string = 'GB' + random_numbers
    
    return generated_string

### COPY PASSWORD TO CLIPBOARD
def copy_to_clipboard():
    global result_label
    generated_string = generate_random_string()
    
    pyperclip.copy(generated_string)
    
    password_result_label.config(text=f"{generated_string}")
    copy_button.config(state=tk.NORMAL)



####################################################################################
## MENU BAR 'ABOUT' AND 'HOWTO' 
####################################################################################
def about():
    messagebox.showinfo("About", "Geoff Banks Bet Monitoring v8.5")

def howTo():
    messagebox.showinfo("How to use", "General\nProgram checks bww\export folder on 20s interval.\nOnly set amount of recent bets are checked. This amount can be defined in options.\nBet files are parsed then displayed in feed and any bets from risk clients show in 'Risk Bets'.\n\nRuns on Selections\nDisplays selections with more than 'X' number of bets.\nX can be defined in options.\n\nReports\nDaily Report - Generates a report of the days activity.\nClient Report - Generates a report of a specific clients activity.\n\nFactoring\nLinks to Google Sheets factoring diary.\nAny change made to customer account reported here by clicking 'Add'.\n\nRace Updation\nList of courses for updating throughout the day.\nWhen course updated, click ✔.\nTo remove course, click X.\nTo add a course or event for update logging, click +\nHorse meetings will turn red after 30 minutes. Greyhounds 1 hour.\nAll updates are logged under F:\GB Bet Monitor\logs.\n\nPlease report any errors to Sam.")



####################################################################################
## PERIODIC FUNCTIONS & THREADING 
####################################################################################
def refresh_display_periodic():
    if auto_refresh_state.get():
        refresh_display()

    root.after(30000, refresh_display_periodic)

def factoring_sheet_periodic():
    threading.Thread(target=factoring_sheet).start()
    root.after(600000, factoring_sheet_periodic) 

def get_data_periodic():
    global vip_clients, newreg_clients
    threading.Thread(target=display_closure_requests).start()
    threading.Thread(target=get_vip_clients).start()
    threading.Thread(target=get_newreg_clients).start()
    threading.Thread(target=get_reporting_data).start()
    threading.Thread(target=get_oddsmonkey_selections).start()
    threading.Thread(target=get_todays_oddsmonkey_selections).start()

    root.after(30000, get_data_periodic)

def run_create_daily_report():
    global current_file
    threading.Thread(target=create_daily_report, args=(current_file,)).start()

def get_client_report_ref():
    global client_report_user, current_file
    client_report_user = simpledialog.askstring("Client Reporting", "Enter Client Username: ")
    if client_report_user:
        client_report_user = client_report_user.upper()
        threading.Thread(target=create_client_report, args=(client_report_user, current_file)).start()

def run_rg_scan():
    threading.Thread(target=update_rg_report).start()

def run_traders_scan():
    threading.Thread(target=update_traders_report).start()

def user_notification():
    if not user:
        user_login()

    def submit():
        message = entry.get()
        message = (user + ": " + message)
        log_notification(message, important=True)
        window.destroy()

    window = tk.Toplevel(root)
    window.title("Enter Notification")
    window.iconbitmap('src/splash.ico')
    window.geometry("300x130")
    screen_width = window.winfo_screenwidth()
    window.geometry(f"+{screen_width - 350}+50")

    label = ttk.Label(window, text="Enter your message:")
    label.pack(padx=5, pady=5)

    entry = ttk.Entry(window, width=50)
    entry.pack(padx=5, pady=5)
    entry.focus_set()  # Set focus to the Entry widget
    entry.bind('<Return>', lambda event=None: submit())  # Bind the <Return> event to the submit function

    button = ttk.Button(window, text="Submit", command=submit)
    button.pack(padx=5, pady=10)

def log_notification(message, important=False):
    # Get the current time
    time = datetime.now().strftime('%H:%M:%S')

    file_lock = fasteners.InterProcessLock('notifications.lock')

    try:
        with file_lock:
            with open('notifications.json', 'r') as f:
                notifications = json.load(f)
    except FileNotFoundError:
        notifications = []

    notifications.insert(0, {'time': time, 'message': message, 'important': important})

    with file_lock:
        with open('notifications.json', 'w') as f:
            json.dump(notifications, f, indent=4)

# Initialize a variable to keep track of the most recent notification

def update_notifications():
    global last_notification  # Use the global variable

    notifications_text.tag_configure("important", font=("TkDefaultFont", 10, "bold"))
    file_lock = fasteners.InterProcessLock('notifications.lock')

    with file_lock:
        try:
            with open('notifications.json', 'r') as f:
                notifications = json.load(f)

            # If there's a new notification or notifications is empty, update the widget
            if not notifications or (last_notification is None or last_notification != notifications[0]):
                # Find the index of the last notification in the list
                last_index = next((index for index, notification in enumerate(notifications) if notification == last_notification), len(notifications))

                # Add the new notifications to the widget
                for notification in reversed(notifications[:last_index]):
                    time = notification['time']
                    message = notification['message']
                    important = notification['important']
                    if important:
                        message = f'{time}: {message}\n'
                        notifications_text.insert('1.0', message, "important")
                    else:
                        notifications_text.insert('1.0', f'{time}: {message}\n')

                # Update the most recent notification
                last_notification = notifications[0] if notifications else None

        except FileNotFoundError:
            pass

    # Schedule the next update
    notifications_text.after(1000, update_notifications)  # Update every 1000 milliseconds (1 second)


####################################################################################
## MAIN FUNCTION CONTAINING ROOT UI, MAIN LOOP & STARTUP FUNCTIONS
####################################################################################
if __name__ == "__main__":

    ### ROOT WINDOW
    root = tk.Tk()
    root.title(f"Bet Viewer v8.5")
    root.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
    ttk.Style().theme_use('forest-light')
    style = ttk.Style(root)
    width=900
    height=1000
    screenwidth = root.winfo_screenwidth()
    screenheight = root.winfo_screenheight()
    root.configure(bg='#ffffff')
    alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width-10), 0)    
    root.geometry(alignstr)
    # root.minsize(width//2, height//2)
    # root.maxsize(screenwidth, screenheight)
    root.resizable(False, False)

    ### IMPORT LOGO
    logo_image = Image.open('src/splash.ico')
    logo_image.thumbnail((70, 70))
    company_logo = ImageTk.PhotoImage(logo_image)  
    root.iconbitmap('src/splash.ico')

    ### MENU BAR SETTINGS
    menu_bar = tk.Menu(root)
    options_menu = tk.Menu(menu_bar, tearoff=0)
    options_menu.add_command(label="Refresh", command=refresh_display, foreground="#000000", background="#ffffff")
    options_menu.add_command(label="Settings", command=open_settings, foreground="#000000", background="#ffffff")
    options_menu.add_command(label="Set User Initials", command=user_login, foreground="#000000", background="#ffffff")
    options_menu.add_separator(background="#ffffff")
    options_menu.add_command(label="Exit", command=root.quit, foreground="#000000", background="#ffffff")
    menu_bar.add_cascade(label="Options", menu=options_menu)
    menu_bar.add_command(label="Report Freebet", command=report_freebet, foreground="#000000", background="#ffffff")
    menu_bar.add_command(label="Add notification", command=user_notification, foreground="#000000", background="#ffffff")
    menu_bar.add_command(label="Add Factoring", command=open_factoring_wizard, foreground="#000000", background="#ffffff")
    help_menu = tk.Menu(menu_bar, tearoff=0)
    help_menu.add_command(label="How to use", command=howTo, foreground="#000000", background="#ffffff")
    help_menu.add_command(label="About", command=about, foreground="#000000", background="#ffffff")
    menu_bar.add_cascade(label="Help", menu=help_menu, foreground="#000000", background="#ffffff")

    root.config(menu=menu_bar)

    ### CHECK BOX OPTIONS
    default_state_risk = tk.IntVar(value=0)
    default_state_wageralert = tk.IntVar(value=1)
    default_state_textbets = tk.IntVar(value=1)

    num_run_bets_var = tk.StringVar()
    num_run_bets_var.set(DEFAULT_NUM_BETS_TO_RUN)
    num_run_bets_var.trace("w", set_num_run_bets)

    auto_refresh_state = tk.BooleanVar()
    auto_refresh_state.set(True)

    feed_colours = tk.BooleanVar()
    feed_colours.set(True)

    runs_remove_off_races = tk.BooleanVar()
    runs_remove_off_races.set(False)

    confirm_betty_update_bool = tk.BooleanVar()
    confirm_betty_update_bool.set(False)  # Set the initial state to False

    send_confirmation_email_bool = tk.BooleanVar()
    send_confirmation_email_bool.set(True)  # Set the initial state to True

    archive_email_bool = tk.BooleanVar()
    archive_email_bool.set(False)  # Set the initial state to True

    all_var = tk.IntVar(value=1)
    uk_ir_var = tk.IntVar(value=0)


    ### BET FEED
    feed_frame = ttk.LabelFrame(root, style='Card', text="Bet Feed")
    feed_frame.place(relx=0.44, rely=0.01, relwidth=0.55, relheight=0.64)
    feed_frame.grid_columnconfigure(0, weight=1)
    feed_frame.grid_rowconfigure(0, weight=1)
    feed_frame.grid_columnconfigure(1, weight=0)
    feed_text = tk.Text(feed_frame, font=("Helvetica", 11, "bold"),wrap='word',padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")

    feed_text.config(state='disabled')
    feed_text.grid(row=0, column=0, sticky='nsew')

    feed_scroll = ttk.Scrollbar(feed_frame, orient='vertical', command=feed_text.yview, cursor="hand2")
    feed_scroll.grid(row=0, column=1, sticky='ns')
    feed_text.configure(yscrollcommand=feed_scroll.set)

    # filter_frame = ttk.Frame(feed_frame)
    # filter_frame.grid(row=1, column=0, sticky='ew')
    # unit_stake_label = ttk.Label(filter_frame, text='Unit Stk:')
    # unit_stake_label.grid(row=0, column=0, sticky='e', padx=6)
    # unit_stake = ttk.Entry(filter_frame, width=4)
    # unit_stake.grid(row=0, column=1, pady=(0, 3), sticky='w')

    # combobox_label = ttk.Label(filter_frame, text='Risk Cat:')
    # combobox_label.grid(row=0, column=2, sticky='w', padx=6)
    # riskcat_options = ["", "W", "M", "S", "X"]
    # combobox = ttk.Combobox(filter_frame, values=riskcat_options, width=4)
    # combobox.grid(row=0, column=3, pady=(0, 3), sticky='w')

    # sport_options = ["", "Horses", "Greyhounds", "Other"]
    # sport_label = ttk.Label(filter_frame, text='Sport:')
    # sport_label.grid(row=0, column=4, sticky='w', padx=6)
    # sport_combobox = ttk.Combobox(filter_frame, values=sport_options, state="readonly", width=10)
    # sport_combobox.grid(row=0, column=5, pady=(0, 3), sticky='w')
    # sport_combobox.set(sport_options[0])



    ### RUNS ON SELECTIONS
    runs_frame = ttk.LabelFrame(root, style='Card', text="Runs on Selections")
    runs_frame.place(relx=0.01, rely=0.01, relwidth=0.42, relheight=0.45)
    runs_frame.grid_columnconfigure(0, weight=1)
    runs_frame.grid_rowconfigure(0, weight=1)
    runs_frame.grid_columnconfigure(1, weight=0)
    runs_text = tk.Text(runs_frame, font=("Arial", 11), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    runs_text.config(state='disabled') 
    runs_text.grid(row=0, column=0, sticky='nsew')

    spinbox_frame = ttk.Frame(runs_frame)
    spinbox_frame.grid(row=1, column=0, sticky='ew')
    spinbox_label = ttk.Label(spinbox_frame, text='Bets to a run: ')
    spinbox_label.grid(row=0, column=0, sticky='e', padx=6)
    spinbox = ttk.Spinbox(spinbox_frame, from_=2, to=10, textvariable=num_run_bets_var, width=2)
    spinbox.grid(row=0, column=1, pady=(0, 3), sticky='w')
    combobox_label = ttk.Label(spinbox_frame, text=' Number of bets: ')
    combobox_label.grid(row=0, column=2, sticky='w', padx=6)
    combobox_values = [20, 50, 100, 300, 1000, 2000]
    combobox_var = tk.IntVar(value=50)   
    combobox = ttk.Combobox(spinbox_frame, textvariable=combobox_var, values=combobox_values, width=4)
    combobox.grid(row=0, column=3, pady=(0, 3), sticky='w')
    combobox_var.trace("w", set_recent_bets)

    runs_scroll = ttk.Scrollbar(runs_frame, orient='vertical', command=runs_text.yview, cursor="hand2")
    runs_scroll.grid(row=0, column=1, sticky='ns')

    runs_text.configure(yscrollcommand=runs_scroll.set)
    
    ### ACTIVITY SUMMARY FRAME
    activity_summary_frame = ttk.Frame(root, style='Card', padding=1)
    activity_summary_frame.place(relx=0.01, rely=0.466, relwidth=0.42, relheight=0.072)
    activity_summary_text=tk.Text(activity_summary_frame, font=("Arial", 11), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    activity_summary_text.config(state='disabled') 
    activity_summary_text.pack(fill='both', expand=True)
    
    ### NOTEBOOK FRAME
    notebook_frame = ttk.Frame(root)
    notebook_frame.place(relx=0.005, rely=0.54, relwidth=0.43, relheight=0.41)
    notebook = ttk.Notebook(notebook_frame)

    ### RISK BETS TAB
    tab_1 = ttk.Frame(notebook)
    notebook.add(tab_1, text="Risk")
    bets_with_risk_text=tk.Text(tab_1, font=("Helvetica", 10), bd=0, wrap='word',padx=10, pady=10, fg="#000000", bg="#ffffff")
    bets_with_risk_text.grid(row=0, column=0, sticky="nsew")
    bets_with_risk_text.pack(fill='both', expand=True)

    ### REPORT TAB
    tab_2 = ttk.Frame(notebook)
    notebook.add(tab_2, text="Reports")
    tab_2.grid_rowconfigure(0, weight=1)
    tab_2.grid_rowconfigure(1, weight=1)
    tab_2.grid_columnconfigure(0, weight=1)
    report_ticket = tk.Text(tab_2, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
    report_ticket.tag_configure("center", justify='center')
    report_ticket.insert('1.0', "User Report\nGenerate a report for a specific client, including their bet history.\n\nStaff Report\nGenerate a report on staff activity.\n\nDaily Report\nGenerate a report for the days betting activity.", "center")    
    report_ticket.config(state='disabled')
    report_ticket.grid(row=0, column=0, sticky="nsew")


    # PROGRESS BAR FOR REPORT
    progress = ttk.Progressbar(tab_2, mode="determinate", length=250)
    progress.grid(row=2, column=0, pady=(0, 0), sticky="nsew")

    # GENERATE REPORT BUTTONS: CLIENT REPORT AND DAILY REPORT
    client_refresh_button = ttk.Button(tab_2, text="User Report", command=get_client_report_ref, cursor="hand2")
    client_refresh_button.grid(row=3, column=0, pady=(0, 0), sticky="w")
    staff_refresh_button = ttk.Button(tab_2, text="Staff Report", command=create_staff_report, cursor="hand2")
    staff_refresh_button.grid(row=3, column=0, pady=(0, 0), sticky="n")
    daily_refresh_button = ttk.Button(tab_2, text="Daily Report", command=run_create_daily_report, cursor="hand2")
    daily_refresh_button.grid(row=3, column=0, pady=(0, 0), sticky="e")

    ### CLIENT FACTORING TAB
    tab_3 = ttk.Frame(notebook)
    notebook.add(tab_3, text="Factoring")

    # CONFIGURING THE TREEVIEW
    tree = ttk.Treeview(tab_3)
    columns = ["A", "B", "C", "D", "E"]
    headings = ["Time", "User", "Risk", "Rating", "Initials"]
    tree["columns"] = columns
    for col, heading in enumerate(headings):
        tree.heading(columns[col], text=heading)
        tree.column(columns[col], width=84, stretch=tk.NO)
    tree.column("A", width=70, stretch=tk.NO)
    tree.column("B", width=80, stretch=tk.NO)
    tree.column("C", width=50, stretch=tk.NO)
    tree.column("D", width=67, stretch=tk.NO)
    tree.column("E", width=70, stretch=tk.NO)
    tree.column("#0", width=10, stretch=tk.NO)
    tree.heading("#0", text="", anchor="w")
    tree.grid(row=0, column=0, sticky="nsew")
    tab_3.grid_columnconfigure(0, weight=1)
    tab_3.grid_rowconfigure(0, weight=1)

    # BUTTONS AND TOOLTIP LABEL FOR FACTORING TAB
    add_restriction_button = ttk.Button(tab_3, text="Add", command=open_factoring_wizard, cursor="hand2")
    add_restriction_button.grid(row=1, column=0, pady=(5, 10), sticky="e")
    refresh_factoring_button = ttk.Button(tab_3, text="Refresh", command=factoring_sheet, cursor="hand2")
    refresh_factoring_button.grid(row=1, column=0, pady=(5, 10), sticky="w")

    notebook.pack(expand=True, fill="both", padx=5, pady=5)

    ### FIND TRADERS TAB
    tab_4 = ttk.Frame(notebook)
    notebook.add(tab_4, text="Screener")
    tab_4.grid_rowconfigure(0, weight=1)
    tab_4.grid_rowconfigure(1, weight=1)
    tab_4.grid_columnconfigure(0, weight=1)
    traders_report_ticket = tk.Text(tab_4, font=("Helvetica", 11), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
    traders_report_ticket.tag_configure("center", justify='center')
    traders_report_ticket.insert('1.0', "Scan for Risk\nGenerate report on potential 'risk' clients\n\nScan for RG Issues\nScreen daily betting and deposits activity for users showing signs of irresponsible gambling", "center")    
    traders_report_ticket.config(state='disabled')
    traders_report_ticket.grid(row=0, column=0, sticky="nsew")

    find_traders_button = ttk.Button(tab_4, text="Scan for Potential Risk Users", command=run_traders_scan, cursor="hand2")
    find_traders_button.grid(row=2, column=0, pady=(0, 0), sticky="w")
    
    find_rg_risk_button = ttk.Button(tab_4, text="Scan for RG Issues", command=run_rg_scan, cursor="hand2")
    find_rg_risk_button.grid(row=2, column=0, pady=(0, 0), sticky="e")

    ### CLOSURE REQUESTS TAB
    tab_5 = ttk.Frame(notebook)
    notebook.add(tab_5, text="Requests")

    requests_frame = ttk.Frame(tab_5)
    requests_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")

    # RACE UPDATION
    race_updation_frame = ttk.LabelFrame(root, style='Card', text="Race Updation")
    race_updation_frame.place(relx=0.44, rely=0.66, relwidth=0.26, relheight=0.283)

    ### NOTIFICATIONS FRAME
    notifications_frame = ttk.LabelFrame(root, style='Card', text="Staff Feed")
    notifications_frame.place(relx=0.71, rely=0.66, relwidth=0.28, relheight=0.247)

    notifications_text = tk.Text(notifications_frame, font=("Helvetica", 10), wrap='word',padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    notifications_text.pack(expand=True, fill='both')

    # LOGO, SETTINGS BUTTON AND SEPARATOR
    # logo_label = tk.Label(settings_frame, image=company_logo, bd=0, cursor="hand2")
    # logo_label.place(relx=0.3, rely=0.02)
    # logo_label.bind("<Button-1>", lambda e: refresh_display())    
    # settings_button = ttk.Button(settings_frame, text="Settings", command=open_settings, width=7, cursor="hand2")
    # settings_button.place(relx=0.29, rely=0.32)
    # separator = ttk.Separator(settings_frame, orient='horizontal')
    # separator.place(relx=0.02, rely=0.48, relwidth=0.95)


    copy_frame = ttk.Frame(root, style='Card')
    copy_frame.place(relx=0.72, rely=0.91, relwidth=0.26, relheight=0.033)

    copy_button = ttk.Button(copy_frame, command=copy_to_clipboard, text="Generate", state=tk.NORMAL, cursor="hand2")
    copy_button.place(relx=0.1, rely=0.05, relwidth=0.4, relheight=0.9)
    password_result_label = tk.Label(copy_frame, wraplength=200, font=("Helvetica", 12), justify="center", text="GB000000", fg="#000000", bg="#ffffff")
    password_result_label.place(relx=0.5, rely=0.25, relwidth=0.4, relheight=0.4)

    # USER LABEL DISPLAY
    # login_label = ttk.Label(settings_frame, text='')
    # login_label.place(relx=0.18, rely=0.85)

    next_races_frame = ttk.Frame(root)
    next_races_frame.place(relx=0.012, rely=0.95, relwidth=0.975, relheight=0.047)

    horses_frame = ttk.Frame(next_races_frame, style='Card')
    horses_frame.place(relx=0, rely=0.05, relwidth=0.5, relheight=0.9)

    greyhounds_frame = ttk.Frame(next_races_frame, style='Card')
    greyhounds_frame.place(relx=0.51, rely=0.05, relwidth=0.49, relheight=0.9)

    # Create the labels for the horse data
    horse_labels = [ttk.Label(horses_frame, justify='center', font=("Helvetica", 9, "bold")) for _ in range(3)]
    for i, label in enumerate(horse_labels):
        label.grid(row=0, column=i, padx=0, pady=5)
        horses_frame.columnconfigure(i, weight=1)

    # Create the labels for the greyhound data
    greyhound_labels = [ttk.Label(greyhounds_frame, justify='center', font=("Helvetica", 9, "bold")) for _ in range(3)]
    for i, label in enumerate(greyhound_labels):
        label.grid(row=1, column=i, padx=0, pady=5)
        greyhounds_frame.columnconfigure(i, weight=1)

    ### STARTUP FUNCTIONS (COMMENT OUT FOR TESTING AS TO NOT MAKE UNNECESSARY REQUESTS)
    get_courses()
    user_login()
    factoring_sheet_periodic()
    get_data_periodic()
    run_display_next_3()
    update_notifications()

    ### GUI LOOP
    threading.Thread(target=refresh_display_periodic, daemon=True).start()
    root.mainloop()