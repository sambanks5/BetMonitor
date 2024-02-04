import os
import re
import threading
import pyperclip
import json
import requests
import random
import gspread
import datetime
import tkinter as tk
from collections import defaultdict, Counter
from oauth2client.service_account import ServiceAccountCredentials
from tkinter import messagebox, filedialog, simpledialog
from tkinter import ttk
from tkinter.ttk import *
from datetime import date, datetime, timedelta, time
from PIL import Image, ImageTk

#Default Values for settings
DEFAULT_NUM_RECENT_FILES = 50
DEFAULT_NUM_BETS_TO_RUN = 3

current_file = None

# STAFF
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

# Main dictionary containing Selections
selection_bets = {}

# Nested dictionary containing bet information per Selection
bet_info = {}  

# Load the credentials from the JSON file
with open('src/creds.json') as f:
    data = json.load(f)

# Get the Pipedrive API token
pipedrive_api_token = data['pipedrive_api_key']

# Now you can use the token in your API URL
pipedrive_api_url = f'https://api.pipedrive.com/v1/itemSearch?api_token={pipedrive_api_token}'

# Get the Google API credentials and authorize
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(data, scope)
gc = gspread.authorize(credentials)


### REFRESH/UPDATE DISPLAY AND DICTIONARY
def refresh_display():
    # Get the number of recent files to check from the user input
    global current_file
    # Refresh the display
    start_bet_feed(current_file)
    display_courses()
    #run_factoring_sheet()
    print("Refreshed Bets")

### FUNCTION TO HANDLE REFRESHING DISPLAY EVERY 30 SECONDS
def refresh_display_periodic():
    # Check if auto refresh is enabled
    if auto_refresh_state.get():
        # Refresh the display
        refresh_display()

    # Schedule the next refresh check
    root.after(30000, refresh_display_periodic)

def get_database(date_str=None):
    # Generate the JSON file path based on the current date if no date_str is provided
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    if not date_str.endswith('-wager_database.json'):
        date_str += '-wager_database.json'
    json_file_path = f"database/{date_str}"

    max_retries = 5  # Maximum number of retries
    for attempt in range(max_retries):
        try:
            with open(json_file_path, 'r') as json_file:
                data = json.load(json_file)
            
            # Reverse the order of the list
            data.reverse()
            
            return data
        except FileNotFoundError:
            error_message = f"Error: Could not find file: {json_file_path}. Click 'Reprocess' on Bet Processor"
            print(error_message)
            messagebox.showerror("Error", error_message)
            return []
        except json.JSONDecodeError:
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                time.sleep(1)  # Wait for 1 second before retrying
            else:
                error_message = f"Error: Could not decode JSON from file: {json_file_path}. "
                print(error_message)
                messagebox.showerror("Error", error_message)
                return []  # Return an empty list after max_retries
        except Exception as e:
            error_message = f"An error occurred: {e}"
            print(error_message)
            messagebox.showerror("Error", error_message)
            return []

### BET CHECK THREAD FUNCTIONS
def start_bet_feed(current_file=None):
    # Load the data from the file
    data = get_database(current_file) if current_file else None
    bet_thread = threading.Thread(target=bet_feed, args=(data,))
    bet_thread.daemon = True
    bet_thread.start()

def bet_feed(data=None):
    if data is None:
        data = get_database()

    feed_content = ""
    risk_bets = ""
    separator = '\n\n----------------------------------------------------------------------------------\n\n'

    for bet in data:
        wager_type = bet.get('type', '').lower()
        if wager_type == 'wager knockback':
            customer_ref = bet.get('customer_ref', '')
            knockback_id = bet.get('id', '')
            # Remove the time from the knockback_id
            knockback_id = knockback_id.rsplit('-', 1)[0]
            knockback_details = bet.get('details', {})
            time = bet.get('time', '') 
            formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items()])
            feed_content += f"{time} - {knockback_id} - {customer_ref} - WAGER KNOCKBACK:\n   {formatted_knockback_details}" + separator
        
        elif wager_type == 'sms wager':
            wager_number = bet.get('id', '')
            customer_reference = bet.get('customer_ref', '')
            sms_wager_text = bet.get('details', '')
            feed_content += f"{customer_reference}-{wager_number} SMS WAGER:\n{sms_wager_text}" + separator

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
                feed_content += f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator
                risk_bets += f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator
            else:
                selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
                feed_content += f"{timestamp} - {bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator

    feed_text.config(state="normal")
    feed_text.delete('1.0', tk.END)
    feed_text.insert('1.0', feed_content)
    feed_text.config(state="disabled")

    bets_with_risk_text.config(state="normal")
    bets_with_risk_text.delete('1.0', tk.END)
    bets_with_risk_text.insert('1.0', risk_bets)
    bets_with_risk_text.config(state="disabled")

    bet_runs(data)

def bet_runs(data):
    global DEFAULT_NUM_BETS_TO_RUN
    num_bets = DEFAULT_NUM_BETS_TO_RUN

    # Load the bets from the JSON database
    selection_bets = data

    selection_bets = selection_bets[:DEFAULT_NUM_RECENT_FILES]

    # Dictionary to store selections and their corresponding bet numbers
    selection_to_bets = defaultdict(list)

    # Iterate through the bets and update the dictionary
    for bet in selection_bets:
        if isinstance(bet['details'], dict):
            selections = [selection[0] for selection in bet['details'].get('selections', [])]
            for selection in selections:
                selection_to_bets[selection].append(bet['id'])

    # Sort selections by the number of bets in descending order
    sorted_selections = sorted(selection_to_bets.items(), key=lambda item: len(item[1]), reverse=True)

    # Clear the text widget
    runs_text.config(state="normal")
    runs_text.delete('1.0', tk.END)

    for selection, bet_numbers in sorted_selections:
        skip_selection = False
        # Check if the selection is a race that has already run
        if runs_remove_off_races.get():  # Replace with actual condition to check if checkbox is selected
            race_time_str = selection.split(", ")[1] if ", " in selection else None
            if race_time_str:
                try:
                    race_time_str = race_time_str.split(" - ")[0]
                    race_time = datetime.strptime(race_time_str, "%H:%M")
                    if race_time < datetime.now():
                        skip_selection = True
                except ValueError:
                    # If the time string is not in the expected format, ignore the time check
                    pass

        if skip_selection:
            continue

        if len(bet_numbers) > num_bets:
            runs_text.insert(tk.END, f"{selection}\n")
            for bet_number in bet_numbers:
                bet_info = next((bet for bet in selection_bets if bet['id'] == bet_number), None)
                if bet_info:
                    for sel in bet_info['details']['selections']:
                        if selection == sel[0]:
                            runs_text.insert(tk.END, f" - {bet_info['time']} - {bet_number} | {bet_info['customer_ref']} ({bet_info['details']['risk_category']}) at {sel[1]}\n")
            runs_text.insert(tk.END, f"\n")

    runs_text.config(state=tk.DISABLED)

### GET COURSES FROM API
def get_courses():
    # Load the credentials from the JSON file
    with open('src/creds.json') as f:
        creds = json.load(f)
    # Get today's date
    today = date.today()
    url = "https://horse-racing.p.rapidapi.com/racecards"
    querystring = {"date": today.strftime('%Y-%m-%d')}
    headers = {
        "X-RapidAPI-Key": creds['rapidapi_key'],
        "X-RapidAPI-Host": "horse-racing.p.rapidapi.com"
    }
    response = requests.get(url, headers=headers, params=querystring)
    data = response.json()

    # Check if the response is a list
    if not isinstance(data, list):
        print("Error: The response from the API is not a list.", data)
        return

    # Get a list of unique courses
    courses = set()
    for race in data:
        try:
            courses.add(race['course'])
        except TypeError:
            print("Error: The 'race' object is not a dictionary.")
            return []

    courses.add("SIS Greyhounds")
    courses.add("TRP Greyhounds")

    # Convert the set to a list
    courses = list(courses)
    print("Courses:", courses)
    # Try to load the existing data from the file
    try:
        with open('update_times.json', 'r') as f:
            update_data = json.load(f)
    except FileNotFoundError:
        # If the file doesn't exist, create it with the initial data
        update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {}}
        with open('update_times.json', 'w') as f:
            json.dump(update_data, f)

    # Check if the date in the file matches today's date
    if update_data['date'] != today.strftime('%Y-%m-%d'):
        # If not, update the file with the new date and courses
        update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {course: "" for course in courses}}
        with open('update_times.json', 'w') as f:
            json.dump(update_data, f)

    display_courses()

    return courses

def reset_update_times():
    # Delete the file if it exists
    if os.path.exists('update_times.json'):
        os.remove('update_times.json')

    # Create the file with the initial data
    update_data = {'date': '', 'courses': {}}
    with open('update_times.json', 'w') as f:
        json.dump(update_data, f)
    
    display_courses()

### DISPLAY THE COURSES
def display_courses():
    for widget in race_updation_frame.winfo_children():
        widget.destroy()
    today = date.today()

    with open('update_times.json', 'r') as f:
        data = json.load(f)


    courses = list(data['courses'].keys())

    add_button = ttk.Button(race_updation_frame, text="+", command=add_course, width=2)
    add_button.grid(row=len(courses), column=1, padx=2, pady=2) 

    for i, course in enumerate(courses):
        course_label = ttk.Label(race_updation_frame, text=course)
        course_label.grid(row=i, column=0, padx=5, pady=2, sticky="w")

        remove_button = ttk.Button(race_updation_frame, text="X", command=lambda course=course: remove_course(course), width=2)
        remove_button.grid(row=i, column=1, padx=3, pady=2)

        course_button = ttk.Button(race_updation_frame, text="✔", command=lambda course=course: update_course(course), width=2)
        course_button.grid(row=i, column=2, padx=3, pady=2)

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
            if 20 <= time_diff < 30:
                color = 'Orange'
            elif time_diff >= 30:
                color = 'red'
            else:
                color = 'black'

        if course in data['courses'] and data['courses'][course]:
            time_text = data['courses'][course]
        else:
            time_text = "Not updated"

        time_label = ttk.Label(race_updation_frame, text=time_text, foreground=color)
        time_label.grid(row=i, column=3, padx=5, pady=2, sticky="w")

def add_course():
    # Prompt the user for a course name
    course_name = simpledialog.askstring("Add Course", "Enter the course name:")
    if course_name:
        # Load the existing data from the file
        with open('update_times.json', 'r') as f:
            data = json.load(f)

        # Add the course to the data
        data['courses'][course_name] = ""

        # Write the updated data back to the file
        with open('update_times.json', 'w') as f:
            json.dump(data, f)

        # Refresh the display
        display_courses()

### REMOVE COURSE FROM COURSES LIST
def remove_course(course):
    # Load the existing data from the file
    with open('update_times.json', 'r') as f:
        data = json.load(f)

    # Remove the course from the data
    if course in data['courses']:
        del data['courses'][course]

    # Write the updated data back to the file
    with open('update_times.json', 'w') as f:
        json.dump(data, f)

    # Refresh the display
    display_courses()

### HANDLE UPDATE OF COURSE
def update_course(course):
    global user
    # Check if user is empty
    if not user:
        user_login()

    now = datetime.now()
    time_string = now.strftime('%H:%M')

    # Load the existing data from the file
    with open('update_times.json', 'r') as f:
        data = json.load(f)

    # Update the course in the data
    data['courses'][course] = f"{time_string} by {user}"


    # Write the updated data back to the file
    with open('update_times.json', 'w') as f:
        json.dump(data, f)

    log_update(course, time_string, user)

    #print(f"Button clicked for course: {course}. Updated at {time_string} - {user}.")

    # Refresh the display
    display_courses()

### LOG ALL COURSE UPDATES TO FILE
def log_update(course, time, user):
    now = datetime.now()
    date_string = now.strftime('%d-%m-%Y')
    log_file = f'logs/update_log_{date_string}.txt'

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

    with open(log_file, 'w') as f:
        f.writelines(data)

### CREATE REPORT ON DAILY ACTIVITY
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
    course_updates = {}
    staff_updates = {}
    # Wageralert Report
    total_wageralerts = 0
    price_change = 0
    event_ended = 0
    other_alert = 0
    liability_exceeded = 0
    wageralert_clients = []
    # SMS Report
    total_sms = 0
    sms_clients = set()
    progress["maximum"] = len(data)
    progress["value"] = 0
    root.update_idletasks()

    for i, bet in enumerate(data):
        progress["value"] = i + 1
        root.update_idletasks()

        bet_type = bet['type'].lower()
        is_sms = bet_type == 'sms wager'
        is_bet = bet_type == 'bet'
        is_wageralert = bet_type == 'wager knockback'  # Adjust this as per your data

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
            # Update the total payment for this customer
            if bet_customer_reference in customer_payments:
                customer_payments[bet_customer_reference] += payment_value
            else:
                customer_payments[bet_customer_reference] = payment_value
            active_clients_set.add(bet_customer_reference)
            total_clients = len(active_clients_set)
            active_clients.append(bet_customer_reference)
            total_bets += 1

        if is_wageralert:
            wageralert_customer_reference = bet['customer_ref']
            knockback_details = bet['details']
            is_alert = False
            for key, value in knockback_details.items():
                if 'Price Has Changed' in key or 'Price Has Changed' in value:
                    price_change += 1
                    is_alert = True
                elif 'Liability Exceeded' in key and 'True' in value:
                    liability_exceeded += 1
                    is_alert = True
                elif 'Event Has Ended' in key or 'Event Has Ended' in value:
                    event_ended += 1
                    is_alert = True
            if not is_alert:
                other_alert += 1
            wageralert_clients.append(wageralert_customer_reference)
            total_wageralerts += 1

        if is_sms:
            sms_customer_reference = bet['customer_ref']
            sms_clients.add(sms_customer_reference)
            total_sms += 1

    # Get the list of all files in the 'logs' directory
    log_files = os.listdir('logs')
    # Sort the files by modification time
    log_files.sort(key=lambda file: os.path.getmtime('logs/' + file))
    # Get the latest file
    latest_file = log_files[-1]
    # Open and read the latest log file
    with open('logs/' + latest_file, 'r') as file:
        lines = file.readlines()
    # Process each line
    for line in lines:
        # Skip empty lines
        if line.strip() == '':
            continue

        # Split line by '-'
        parts = line.strip().split(' - ')

        # Handle lines with a course name followed by a colon
        if len(parts) == 1 and parts[0].endswith(':'):
            course = parts[0].replace(':', '')
            continue

        # Handle lines with time, course, and staff
        if len(parts) == 2:
            time, staff = parts

            # Increment course count
            if course in course_updates:
                course_updates[course] += 1
            else:
                course_updates[course] = 1

            # Increment staff count
            if staff in staff_updates:
                staff_updates[staff] += 1
            else:
                staff_updates[staff] = 1

    top_spenders = Counter(customer_payments).most_common(5)
    client_bet_counter = Counter(active_clients)
    top_client_bets = client_bet_counter.most_common(5)
    timestamp_hours = [timestamp.split(':')[0] + ":00" for timestamp in timestamps]
    hour_counts = Counter(timestamp_hours)
    wageralert_counter = Counter(wageralert_clients)
    top_wageralert_clients = wageralert_counter.most_common(3)
    sms_counter = Counter(sms_clients)
    top_sms_clients = sms_counter.most_common(3)

    separator = "\n---------------------------------------------------------------------------------\n"

    report_output += f"---------------------------------------------------------------------------------\n"
    report_output += f"\tDAILY REPORT TICKET {date_string}\n\t        Generated at {formatted_time}"
    report_output += f"{separator}"

    report_output += f"TOTALS - Stakes: £{total_stakes:.2f} | "
    report_output += f"Bets: {total_bets} | "
    report_output += f"Clients: {total_clients}\n\n"


    report_output += f"CLIENTS BY RISK - No Risk: {total_norisk_clients} | "
    report_output += f"M: {total_m_clients} | "
    report_output += f"W: {total_w_clients}"

    report_output += "\n\nMOST SPEND:\n"
    for rank, (customer, spend) in enumerate(top_spenders, start=1):
        report_output += f"{rank}. {customer} - Stakes: £{spend:.2f}\n"

    report_output += "\nMOST BETS:\n"
    for rank, (client, count) in enumerate(top_client_bets, start=1):
        report_output += f"{rank}. {client} - Bets: {count}\n"

    # Add counts to report_output
    report_output += "\nCOURSE UPDATES:\n"
    for course, count in course_updates.items():
        report_output += f"{course}: {count} updates\n"

    report_output += "\nSTAFF UPDATES:\n"
    for staff, count in staff_updates.items():
        report_output += f"{staff}: {count} updates\n"

    report_output += f"\nBETS PER HOUR:\n"

    for hour, count in hour_counts.items():
        start_hour = hour
        end_hour = f"{int(start_hour.split(':')[0])+1:02d}:00"
        hour_range = f"{start_hour} - {end_hour}"
        if hour_range in hour_ranges:
            hour_ranges[hour_range] += count
        else:
            hour_ranges[hour_range] = count

    for hour_range, count in hour_ranges.items():
        report_output += f"{hour_range} - Bets {count}\n"

    report_output += f"\nKNOCKBACKS: {total_wageralerts}\n"
    report_output += f"\nMOST KNOCKBACKS:\n"
    for rank, (client, count) in enumerate(top_wageralert_clients, start=1):
        report_output += f"{rank}. {client} - Knockbacks: {count}\n"

    report_output += f"\nLiability Exceeded: {liability_exceeded}\n"
    report_output += f"Price Changes: {price_change}\n"
    report_output += f"Event Ended: {event_ended}\n"
    report_output += f"Other: {other_alert}\n"

    report_output += f"\nTEXTBETS: {total_sms}"

    report_output += f"\n\nMOST TEXTBETS: \n"
    for rank, (client, count) in enumerate(top_sms_clients, start=1):
        report_output += f"{rank}. {client} - TEXTS: {count}\n"

    report_output += f"\n{separator}"
    report_output += f"\nALL ACTIVE CLIENTS BY RISK\n\n"


    report_output += f"M Clients: \n"
    for client in m_clients:
        report_output += f"{client}, "
    report_output += f"\n\nW Clients: \n"
    for client in w_clients:
        report_output += f"{client}, "
    report_output += f"\n\nNo Risk Clients: \n"
    for client in norisk_clients:
        report_output += f"{client}, "
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
            is_alert = False
            for key, value in bet['details'].items():
                if 'Price Has Changed' in key or 'Price Has Changed' in value:
                    price_change += 1
                    is_alert = True
                elif 'Liability Exceeded' in key and 'True' in value:
                    liability_exceeded += 1
                    is_alert = True
                elif 'Event Has Ended' in key or 'Event Has Ended' in value:
                    event_ended += 1
                    is_alert = True
            if not is_alert:
                other_alert += 1
            total_wageralerts += 1
            formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in bet['details'].items()])
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
    report_output += f"Event Ended: {event_ended}\n"
    report_output += f"Other: {other_alert}\n"

    report_output += f"\nTEXTBETS: {total_sms}\n"

    report_output += f"\n\nFULL FEED FOR {customer_ref}:{separator}"


    report_ticket.config(state="normal")
    report_ticket.delete('1.0', tk.END)
    report_ticket.insert('1.0', client_report_feed)
    report_ticket.insert('1.0', report_output)
    report_ticket.config(state="disabled")    

### GET FACTORING DATA FROM GOOGLE SHEETS USING API
def factoring_sheet():
    tree.delete(*tree.get_children())
    spreadsheet = gc.open('Factoring Diary')
    print("Getting Factoring Sheet")
    worksheet = spreadsheet.get_worksheet(4)
    data = worksheet.get_all_values()
    print("Retrieving factoring data")

    for row in data[2:]:
        tree.insert("", "end", values=[row[0], row[1], row[2], row[3], row[4]])

### WIZARD TO ADD FACTORING TO FACTORING DIARY
def open_wizard():
    global user
    if not user:
        user_login()

    def handle_submit():

        params = {
            'term': entry1.get(),
            'item_types': 'person',
            'fields': 'custom_fields',
            'exact_match': 'true',
        }

        response = requests.get(pipedrive_api_url, params=params)

        if response.status_code == 200:
            persons = response.json()['data']['items']
            print(persons)
            if not persons:
                messagebox.showerror("Error", f"No persons found for username: {entry1.get()}. Please make sure the username is correct, or enter the risk category in pipedrive manually.")
                return

            for person in persons:
                person_id = person['item']['id']

                # Update the 'Risk Category' field for this person
                update_url = f'https://api.pipedrive.com/v1/persons/{person_id}?api_token={pipedrive_api_token}'
                update_data = {
                    'ab6b3b25303ffd7c12940b72125487171b555223': entry2.get()  # get the new value from the entry2 field
                }
                update_response = requests.put(update_url, json=update_data)

                if update_response.status_code == 200:
                    print(f'Successfully updated person {person_id}')
                else:
                    print(f'Error updating person {person_id}: {update_response.status_code}')
        else:
            print(f'Error: {response.status_code}')

        spreadsheet = gc.open('Factoring Diary')
        worksheet = spreadsheet.get_worksheet(4)

        next_row = len(worksheet.col_values(1)) + 1

        current_time = datetime.now().strftime("%H:%M:%S")

        worksheet.update_cell(next_row, 1, current_time)
        worksheet.update_cell(next_row, 2, entry1.get().capitalize())
        worksheet.update_cell(next_row, 3, entry2.get())
        worksheet.update_cell(next_row, 4, entry3.get())
        worksheet.update_cell(next_row, 5, user) 

        tree.insert("", "end", values=[current_time, entry1.get().capitalize(), entry2.get(), entry3.get(), user])

        wizard_window.destroy()

    wizard_window = tk.Toplevel(root)
    wizard_window.geometry("250x300")  # Width x Height
    wizard_window.title("Add Factoring")
    wizard_window.iconbitmap('src/splash.ico')

    username = ttk.Label(wizard_window, text="Username")
    username.pack(padx=5, pady=5)
    entry1 = ttk.Entry(wizard_window)
    entry1.pack(padx=5, pady=5)

    riskcat = ttk.Label(wizard_window, text="Risk Category")
    riskcat.pack(padx=5, pady=5)

    options = ["W - WATCHLIST", "M - BP ONLY NO OFFERS", "X - SP ONLY NO OFFERS", "S - SP ONLY", "D - BP ONLY", "O - NO OFFERS"]
    entry2 = ttk.Combobox(wizard_window, values=options, state="readonly")
    entry2.pack(padx=5, pady=5)
    entry2.set(options[0])
     
    assrating = ttk.Label(wizard_window, text="Assessment Rating")
    assrating.pack(padx=5, pady=5)
    entry3 = ttk.Entry(wizard_window)
    entry3.pack(padx=5, pady=5)

    factoringnote = ttk.Label(wizard_window, text="Risk Category will be updated in Pipedrive.")
    factoringnote.pack(padx=5, pady=5)

    wizard_window.bind('<Return>', lambda event=None: handle_submit())

    submit_button = ttk.Button(wizard_window, text="Submit", command=handle_submit)
    submit_button.pack(padx=5, pady=5)

### OPTIONS SETTINGS
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

### STAFF LOGIN FOR REPORTING AND FACTORING
def user_login():
    global user
    global full_name
    while True:
        user = simpledialog.askstring("Input", "Please enter your initials:")
        if user and len(user) <= 2:
            user = user.upper()
            if user in USER_NAMES:
                full_name = USER_NAMES[user]
                break
            else:
                messagebox.showerror("Error", "Could not find staff member! Please try again.")
        else:
            messagebox.showerror("Error", "Maximum of 2 characters.")

    # Update the UI to display the logged in user's full name
    login_label.config(text=f'Logged in as {full_name}')

### SETTINGS WINDOW
def open_settings():
    def load_database(event):
        global current_file
        # Get the selected file
        selected_file = databases_combobox.get()
        current_file = selected_file

        # Use a regular expression to extract the date string from the selected file
        match = re.search(r'\d{4}-\d{2}-\d{2}', selected_file)
        if match:
            date_str = match.group()
        else:
            print(f"Error: Could not extract date from file name: {selected_file}")
            return

        # Load the data from the selected file
        data = get_database(date_str)

        bet_feed(data)

    settings_window = tk.Toplevel(root)
    settings_window.title("Options")
    settings_window.iconbitmap('src/splash.ico')

    # Set window size to match frame size
    settings_window.geometry("310x300")  # Width x Height

    # Disable window resizing
    settings_window.resizable(False, False)

    # Position window on the right side of the screen
    screen_width = settings_window.winfo_screenwidth()
    settings_window.geometry(f"+{screen_width - 350}+50")  # "+X+Y"

    # OPTIONS FRAME
    options_frame = ttk.LabelFrame(settings_window, style='Card', text="Options", width=120, height=205)
    options_frame.place(x=5, y=5, width=300, height=420)

    toggle_button = ttk.Checkbutton(options_frame, text='Auto Refresh', variable=auto_refresh_state, onvalue=True, offvalue=False)
    toggle_button.place(x=60, y=5) 

    remove_off_races = ttk.Checkbutton(options_frame, text='Hide Off Races from Runs', variable=runs_remove_off_races, onvalue=True, offvalue=False)
    remove_off_races.place(x=60, y=30)

    get_courses_button = ttk.Button(options_frame, text="Get Courses", command=get_courses)
    get_courses_button.place(x=30, y=70, width=110)

    reset_courses_button = ttk.Button(options_frame, text="Reset Courses", command=reset_update_times)
    reset_courses_button.place(x=160, y=70, width=110)

    separator = ttk.Separator(options_frame, orient='horizontal')
    separator.place(x=10, y=130, width=270)

    # Get a list of all JSON files in the 'databases' directory
    json_files = [f for f in os.listdir('database') if f.endswith('.json')]

    databases_combobox = ttk.Combobox(options_frame, values=json_files, width=4)
    databases_combobox.place(x=20, y=160, width=250)

    if current_file is not None:
        databases_combobox.set(current_file)
    else:
        databases_combobox.set("Select previous database...")

    databases_combobox.bind('<<ComboboxSelected>>', load_database)

### PASSWORD GENERATOR FUNCTIONS
def generate_random_string():
    # Generate 6 random digits
    random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    # Combine 'GB' with the random numbers
    generated_string = 'GB' + random_numbers
    
    return generated_string

### COPY PASSWORD TO CLIPBOARD
def copy_to_clipboard():
    global result_label  # Access the global result_label variable
    # Generate the string
    generated_string = generate_random_string()
    
    # Copy the generated string to the clipboard
    pyperclip.copy(generated_string)
    
    password_result_label.config(text=f"{generated_string}")
    copy_button.config(state=tk.NORMAL)

def staff_bulletin():
    with open('staff_bulletin.txt', 'r') as file:
        bulletin = file.read()

    staff_bulletin_text.config(state="normal")
    staff_bulletin_text.delete('1.0', tk.END)
    staff_bulletin_text.insert('1.0', bulletin)

### MENU BAR * OPTIONS ITEMS
def about():
    messagebox.showinfo("About", "Geoff Banks Bet Monitoring v7.1")

def howTo():
    messagebox.showinfo("How to use", "General\nProgram checks bww\export folder on 30s interval.\nOnly set amount of recent bets are checked. This amount can be defined in options.\nBet files are parsed then displayed in feed and any bets from risk clients show in 'Risk Bets'.\n\nRuns on Selections\nDisplays selections with more than 'X' number of bets.\nX can be defined in options.\n\nReports\nDaily Report - Generates a report of the days activity.\nClient Report - Generates a report of a specific clients activity.\n\nFactoring\nLinks to Google Sheets factoring diary.\nAny change made to customer account reported here by clicking 'Add'.\n\nRace Updation\nList of courses for updating throughout the day.\nWhen course updated, click ✔.\nTo remove course, click X.\nTo add a course or event for update logging, click +\nHorse meetings will turn red after 30 minutes. Greyhounds 1 hour.\nAll updates are logged under F:\GB Bet Monitor\logs.\n\nPlease report any errors to Sam.")

def factoring_sheet_periodic():
    # Call factoring_sheet
    run_factoring_sheet()

    # Schedule the next call to factoring_sheet
    root.after(300000, factoring_sheet_periodic)

def run_factoring_sheet():
    threading.Thread(target=factoring_sheet).start()

def run_create_daily_report():
    global current_file
    threading.Thread(target=create_daily_report, args=(current_file,)).start()

def get_client_report_ref():
    global client_report_user, current_file
    client_report_user = simpledialog.askstring("Client Reporting", "Enter Client Username: ")
    if client_report_user:
        client_report_user = client_report_user.upper()
        threading.Thread(target=create_client_report, args=(client_report_user, current_file)).start()

if __name__ == "__main__":

    ### ROOT WINDOW
    root = tk.Tk()
    root.title("Bet Viewer v7.1")
    root.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
    ttk.Style().theme_use('forest-light')
    style = ttk.Style(root)
    width=900
    height=970
    screenwidth = root.winfo_screenwidth()
    screenheight = root.winfo_screenheight()
    root.configure(bg='#ffffff')
    alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2)
    root.geometry(alignstr)
    root.minsize(width//2, height//2)  # Minimum size to half of the initial size
    root.maxsize(screenwidth, screenheight)  # Maximum size to the screen size
    root.resizable(True, True)  # Allow resizing in both directions


    ### IMPORT LOGO
    logo_image = Image.open('src/splash.ico')
    logo_image.thumbnail((70, 70))
    company_logo = ImageTk.PhotoImage(logo_image)  
    root.iconbitmap('src/splash.ico')

    ### MENU BAR SETTINGS
    menu_bar = tk.Menu(root)
    options_menu = tk.Menu(menu_bar, tearoff=0)
    options_menu.add_command(label="Set User Initials", command=user_login, foreground="#000000", background="#ffffff")
    options_menu.add_command(label="Set Num of Bets to a Run", command=set_num_run_bets, foreground="#000000", background="#ffffff")
    options_menu.add_separator(background="#ffffff")
    options_menu.add_command(label="Exit", command=root.quit, foreground="#000000", background="#ffffff")
    menu_bar.add_cascade(label="Options", menu=options_menu)
    help_menu = tk.Menu(menu_bar, tearoff=0)
    help_menu.add_command(label="How to use", command=howTo, foreground="#000000", background="#ffffff")
    help_menu.add_command(label="About", command=about, foreground="#000000", background="#ffffff")
    help_menu.add_separator(background="#ffffff")
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

    runs_remove_off_races = tk.BooleanVar()
    runs_remove_off_races.set(False)

    ### BET FEED
    feed_frame = ttk.LabelFrame(root, style='Card', text="Bet Feed")
    feed_frame.place(relx=0.44, rely=0.01, relwidth=0.55, relheight=0.64)
    feed_text = tk.Text(feed_frame, font=("Helvetica", 11, "bold"),wrap='word',padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    feed_text.config(state='disabled')
    feed_text.pack(fill='both', expand=True)
    feed_scroll = ttk.Scrollbar(feed_text, orient='vertical', command=feed_text.yview, cursor="hand2")
    feed_scroll.pack(side="right", fill="y")
    feed_text.configure(yscrollcommand=feed_scroll.set)



    ### RUNS ON SELECTIONS
    runs_frame = ttk.LabelFrame(root, style='Card', text="Runs on Selections")
    runs_frame.place(relx=0.01, rely=0.01, relwidth=0.41, relheight=0.52)
    runs_text=tk.Text(runs_frame, font=("Helvetica", 11), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    runs_text.config(state='disabled') 
    runs_text.pack(fill='both', expand=True)

    # Create a new frame for the label and spinbox
    spinbox_frame = ttk.Frame(runs_frame)
    spinbox_frame.pack(side='bottom')

    # Create the label
    spinbox_label = ttk.Label(spinbox_frame, text='Bets to a run: ')
    spinbox_label.grid(row=0, column=0, sticky='e')

    # Create the Spinbox
    spinbox = ttk.Spinbox(spinbox_frame, from_=2, to=10, textvariable=num_run_bets_var, width=2)
    spinbox.grid(row=0, column=1, pady=(0, 3), sticky='w')

    combobox_label = ttk.Label(spinbox_frame, text=' Number of bets: ')
    combobox_label.grid(row=0, column=2, sticky='w')

    # Create the Combobox
    combobox_values = [20, 50, 100, 300, 1000, 2000]
    combobox_var = tk.IntVar(value=50)   
    combobox = ttk.Combobox(spinbox_frame, textvariable=combobox_var, values=combobox_values, width=4)
    combobox.grid(row=0, column=3, pady=(0, 3), sticky='w')
    combobox_var.trace("w", set_recent_bets)

    runs_scroll = ttk.Scrollbar(runs_text, orient='vertical', command=runs_text.yview, cursor="hand2")
    runs_scroll.pack(side="right", fill="y")

    runs_text.configure(yscrollcommand=runs_scroll.set)


    ### NOTEBOOK FRAME
    notebook_frame = ttk.Frame(root)
    notebook_frame.place(relx=0.01, rely=0.54, relwidth=0.42, relheight=0.43)
    notebook = ttk.Notebook(notebook_frame)

    ### RISK BETS TAB
    tab_4 = ttk.Frame(notebook)
    notebook.add(tab_4, text="Risk Bets")
    bets_with_risk_text=tk.Text(tab_4, font=("Helvetica", 10), bd=0, wrap='word',padx=10, pady=10, fg="#000000", bg="#ffffff")
    bets_with_risk_text.grid(row=0, column=0, sticky="nsew")
    bets_with_risk_text.pack(fill='both', expand=True)

    ### REPORT TAB
    tab_2 = ttk.Frame(notebook)
    notebook.add(tab_2, text="Report")
    tab_2.grid_rowconfigure(0, weight=1)
    tab_2.grid_rowconfigure(1, weight=1)
    tab_2.grid_columnconfigure(0, weight=1)
    report_ticket = tk.Text(tab_2, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
    report_ticket.config(state='disabled')
    report_ticket.grid(row=0, column=0, sticky="nsew")

    # PROGRESS BAR FOR REPORT
    progress = ttk.Progressbar(tab_2, mode="determinate", length=250)
    progress.grid(row=2, column=0, pady=(0, 0), sticky="nsew")

    # GENERATE REPORT BUTTONS: CLIENT REPORT AND DAILY REPORT
    client_refresh_button = ttk.Button(tab_2, text="User Report", command=get_client_report_ref)
    client_refresh_button.grid(row=3, column=0, pady=(0, 0), sticky="w")
    daily_refresh_button = ttk.Button(tab_2, text="Daily Report", command=run_create_daily_report)
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

    # BUTTONS AND TOOLTIP LABEL FOR FACTORING TAB
    add_restriction_button = ttk.Button(tab_3, text="Add", command=open_wizard)
    add_restriction_button.grid(row=1, column=0, pady=(5, 10), sticky="e")
    refresh_factoring_button = ttk.Button(tab_3, text="Refresh", command=run_factoring_sheet)
    refresh_factoring_button.grid(row=1, column=0, pady=(5, 10), sticky="w")
    factoring_label = ttk.Label(tab_3, text="Click 'Add' to report a new customer restriction.")
    factoring_label.grid(row=1, column=0, pady=(80, 0), sticky="s")

    notebook.pack(expand=True, fill="both", padx=5, pady=5)

    ### STAFF BULLETIN TAB
    tab_4 = ttk.Frame(notebook)
    notebook.add(tab_4, text="Staff Bulletin")
    staff_bulletin_text=tk.Text(tab_4, font=("Helvetica", 10), bd=0, wrap='word',padx=10, pady=10, fg="#000000", bg="#ffffff")
    staff_bulletin_text.pack(fill='both', expand=True)

    ### RACE UPDATION CANVAS (MUST BE CANVAS OR SCROLLBAR WILL NOT WORK)
    canvas = tk.Canvas(root)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    # LABELFRAME INSIDE CANVAS
    race_updation_frame = ttk.LabelFrame(canvas, style='Card', text="Race Updation")
    canvas.create_window((0, 0), window=race_updation_frame, anchor="nw")
    race_updation_frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

    canvas.place(relx=0.44, rely=0.67, relwidth=0.33, relheight=0.3)
    scrollbar.place(relx=0.76, rely=0.67, relwidth=0.02, relheight=0.3)



    ### SETTINGS FRAME
    settings_frame = ttk.LabelFrame(root, style='Card', text="Settings")
    settings_frame.place(relx=0.785, rely=0.67, relwidth=0.2, relheight=0.3)

    # LOGO, SETTINGS BUTTON AND SEPARATOR
    logo_label = tk.Label(settings_frame, image=company_logo, bd=0, cursor="hand2")
    logo_label.place(relx=0.09, rely=0.02)
    logo_label.bind("<Button-1>", lambda e: refresh_display())
    separator = ttk.Separator(settings_frame, orient='horizontal')
    separator.place(relx=0.02, rely=0.35, relwidth=0.95)
    settings_button = ttk.Button(settings_frame, text="Options", command=open_settings, width=7)
    settings_button.place(relx=0.53, rely=0.1)

    # PASSWORD GENERATOR AND SEPARATOR
    copy_button = ttk.Button(settings_frame, command=copy_to_clipboard, text="Generate PW", state=tk.NORMAL)
    copy_button.place(relx=0.2, rely=0.4)
    password_result_label = tk.Label(settings_frame, wraplength=200, font=("Helvetica", 12), justify="center", text="GB000000", fg="#000000", bg="#ffffff")
    password_result_label.place(relx=0.26, rely=0.55)
    separator = ttk.Separator(settings_frame, orient='horizontal')
    separator.place(relx=0.02, rely=0.7, relwidth=0.95)

    # USER LABEL DISPLAY
    login_label = ttk.Label(settings_frame, text='')
    login_label.place(relx=0.2, rely=0.8)

    ### STARTUP FUNCTIONS (COMMENT OUT FOR TESTING AS TO NOT MAKE UNNECESSARY REQUESTS)
    #get_courses()
    #user_login()
    factoring_sheet_periodic()
    staff_bulletin()

    ### GUI LOOP
    threading.Thread(target=refresh_display_periodic, daemon=True).start()
    root.mainloop()