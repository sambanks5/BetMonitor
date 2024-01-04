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
from datetime import date, datetime, timedelta
from PIL import Image, ImageTk

#Default Values for settings
DEFAULT_NUM_RECENT_FILES = 50
DEFAULT_NUM_BETS_TO_RUN = 3

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

# Path to BWW Export folder containing raw bet texts
BET_FOLDER_PATH = "c:\TESTING"
#BET_FOLDER_PATH = "F:\BWW\Export"
#BET_FOLDER_PATH = "/Users/sambanks/Documents/testing"

credentials_file = 'src/creds.json'
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(credentials_file, scope)
gc = gspread.authorize(credentials)

### REFRESH/UPDATE DISPLAY AND DICTIONARY
def refresh_display():
    global selection_bets, bet_info

    # Get the number of recent files to check from the user input
    num_recent_files = DEFAULT_NUM_RECENT_FILES
    # Clear the dictionaries
    selection_bets = {}
    bet_info = {}

    # Refresh the display
    start_bet_check_thread(num_recent_files)
    display_courses()
    run_factoring_sheet()
    print("Refreshed Bets")

### FUNCTION TO HANDLE REFRESHING DISPLAY EVERY 30 SECONDS
def refresh_display_periodic():
    # Check if auto refresh is enabled
    if auto_refresh_state.get():
        # Refresh the display
        refresh_display()

    # Schedule the next refresh check
    root.after(30000, refresh_display_periodic)

### RETURN 'DATE OF CREATION' FOR TEXT FILES
def get_creation_date(file_path):
    return os.path.getctime(file_path)

### GET FILES FROM FOLDER
def get_files():
    try:
        files = [f for f in os.listdir(BET_FOLDER_PATH) if f.endswith('.bww')]
        # Sort files by creation date in descending order
        files.sort(key=lambda x: get_creation_date(os.path.join(BET_FOLDER_PATH, x)), reverse=True)

        return files
    except FileNotFoundError:
        error_message = f"Error: Could not find files in folder: {BET_FOLDER_PATH}. Please check the folder path in settings."
        print(error_message)
        messagebox.showerror("Error", error_message)
        return []
    except Exception as e:
        error_message = f"An error occurred: {e}"
        print(error_message)
        messagebox.showerror("Error", error_message)
        return []

### BET CHECK THREAD FUNCTIONS
def start_bet_check_thread(num_recent_files):
    bet_thread = threading.Thread(target=bet_check_thread, args=(num_recent_files,))
    bet_thread.daemon = True
    bet_thread.start()

### MAIN FUNCTION TO GET FILES
def bet_check_thread(num_recent_files):
    global BET_FOLDER_PATH

    # Get a list of all text files in the folder
    files = get_files()
    recent_files = files[:num_recent_files]

    feed_content = ""
    separator = '\n\n------------------------------------------------------------------------------------\n\n'

    # Get the feed options
    risk_only, show_wageralert, show_sms = get_feed_options()

    # Process the selected recent files
    for filename in recent_files:
        file_path = os.path.join(BET_FOLDER_PATH, filename)

        with open(file_path, 'r') as file:
            bet_text = file.read()

            # Check the type of the bet
            bet_text_lower = bet_text.lower()
            is_sms = 'sms' in bet_text_lower
            is_bet = 'website' in bet_text_lower
            is_wageralert = 'knockback' in bet_text_lower

            if is_wageralert and show_wageralert:
                customer_ref, knockback_id, knockback_details, time = parse_wageralert_details(bet_text)
                formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items()])
                feed_content += f"{time} - {knockback_id} - {customer_ref} - WAGER KNOCKBACK:\n   {formatted_knockback_details}" + separator

                # Create a dictionary with the bet information
                bet_info = {
                    'id': knockback_id,
                    'type': 'WAGER KNOCKBACK',
                    'customer_ref': customer_ref,
                    'details': knockback_details,
                    'time': time
                }

                # Call the create_database function
                #create_database(bet_info)

            elif is_sms and show_sms:
                wager_number, customer_reference, _, sms_wager_text = parse_sms_details(bet_text)
                feed_content += f"{customer_reference}-{wager_number} SMS WAGER:\n{sms_wager_text}" + separator

                # Create a dictionary with the bet information
                bet_info = {
                    'id': wager_number,
                    'type': 'SMS WAGER',
                    'customer_ref': customer_reference,
                    'details': sms_wager_text
                }

                # Call the create_database function
                #create_database(bet_info)

            elif is_bet:
                bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type = parse_bet_details(bet_text)
                if risk_only and customer_risk_category and customer_risk_category != '-':
                    selection = "\n".join([f"   - {sel} at {odds}" for sel, odds in parsed_selections])
                    feed_content += f"{timestamp}-{bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator
                elif not risk_only:
                    selection = "\n".join([f"   - {sel} at {odds}" for sel, odds in parsed_selections])
                    feed_content += f"{timestamp}-{bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator

                # Create a dictionary with the bet information
                bet_info = {
                    'id': bet_no,
                    'type': 'BET',
                    'customer_ref': customer_reference,
                    'details': {
                        'selections': parsed_selections,
                        'timestamp': timestamp,
                        'risk_category': customer_risk_category,
                        'bet_details': bet_details,
                        'unit_stake': unit_stake,
                        'payment': payment,
                        'bet_type': bet_type
                    }
                }

                # Call the create_database function
                #create_database(bet_info)
                update_selection_bets(bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type)
    
    # Update the feed label with the latest bet or wageralert information
    feed_text.config(state="normal")
    feed_text.delete('1.0', tk.END)
    feed_text.insert('1.0', feed_content)
    feed_text.config(state="disabled")

    # Update the display
    check_bet_runs()
    get_bets_with_risk_category()

### CREATE DATABASE JSON FROM BET FILES (BETA)
def create_database(bet_info, json_file='bet_database.json'):
    # Load the existing database
    try:
        with open(json_file, 'r') as file:
            database = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        database = []

    # Check if the bet ID already exists in the database
    if not any(bet['id'] == bet_info['id'] for bet in database):
        # If not, append the new bet information
        database.append(bet_info)

        # Write the updated database back to the JSON file
        with open(json_file, 'w') as file:
            json.dump(database, file, indent=4)

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
    # Get today's date
    today = date.today()

    print("Displaying courses for", today.strftime('%Y-%m-%d'))

    # Load the existing data from the file
    with open('update_times.json', 'r') as f:
        data = json.load(f)

    #print("Data:", data)

    # Get the courses from the data
    courses = list(data['courses'].keys())

    #print("Courses:", courses)
    add_button = ttk.Button(race_updation_frame, text="+", command=add_course, width=2)
    add_button.grid(row=len(courses), column=1, padx=2, pady=2)  # Add padding
    # ...
    # Display the courses
    for i, course in enumerate(courses):
        # Create a label for the course
        course_label = ttk.Label(race_updation_frame, text=course)
        course_label.grid(row=i, column=0, padx=5, pady=2, sticky="w")  # Add padding

        # Create a button to remove the course
        remove_button = ttk.Button(race_updation_frame, text="X", command=lambda course=course: remove_course(course), width=2)
        remove_button.grid(row=i, column=1, padx=3, pady=2)  # Add padding

        # Create a button for the course
        course_button = ttk.Button(race_updation_frame, text="✔", command=lambda course=course: update_course(course), width=2)
        course_button.grid(row=i, column=2, padx=3, pady=2)  # Add padding

        # Create a label for the last updated time
        if course in data['courses'] and data['courses'][course]:
            last_updated_time = data['courses'][course].split(' ')[0]
            last_updated = datetime.strptime(last_updated_time, '%H:%M').time()
        else:
            # Handle the case where 'data['courses'][course]' is an empty string
            last_updated = datetime.now().time()

        # Get the current time
        now = datetime.now().time()

        # Calculate the time difference in minutes
        time_diff = (datetime.combine(date.today(), now) - datetime.combine(date.today(), last_updated)).total_seconds() / 60

        # Set the color based on the time difference
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

        # Set the text of the label based on the last updated time
        if course in data['courses'] and data['courses'][course]:
            time_text = data['courses'][course]
        else:
            time_text = "Not updated"

        time_label = ttk.Label(race_updation_frame, text=time_text, foreground=color)
        time_label.grid(row=i, column=3, padx=5, pady=2, sticky="w")  # Add padding

# Handle adding a course
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

### PARSE BET INFORMATION FROM RAW BET TEXT
def parse_bet_details(bet_text):
    bet_number_pattern = r"Wager Number - (\d+)"
    customer_ref_pattern = r"Customer Reference - (\w+)"
    customer_risk_pattern = r"Customer Risk Category - (\w+)"
    time_pattern = r"Bet placed on (\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})"
    selection_pattern = r"(.*?) at (\d+\.\d+)?"
    bet_details_pattern = r"Bets (Win Only|Each Way|Forecast): (\d+ .+?)\. Unit Stake: (£[\d,]+\.\d+), Payment: (£[\d,]+\.\d+)\."
    bet_type_pattern = r"Wagers\s*:\s*([^\n@]+)"    
    odds_pattern = r"(?:at|on)\s+(\d+\.\d+)"

    customer_reference_match = re.search(customer_ref_pattern, bet_text)
    customer_risk_match = re.search(customer_risk_pattern, bet_text)
    timestamp_match = re.search(time_pattern, bet_text)
    bet_number = re.search(bet_number_pattern, bet_text)
    bet_details_match = re.search(bet_details_pattern, bet_text)
    odds_match = re.search(odds_pattern, bet_text)
    bet_type_match = re.search(bet_type_pattern, bet_text)
    odds = odds_match.group(1) if odds_match else "evs"

    if all(match is not None for match in [customer_reference_match, timestamp_match, bet_number, bet_details_match]):
        selections = re.findall(selection_pattern, bet_text)
        bet_type = None
        parsed_selections = []
        # Extract selections and odds
        for selection, odds in selections:
            # Check if unwanted data exists and remove it
            if '-' in selection and ',' in selection.split('-')[1]:
                unwanted_part = selection.split('-')[1].split(',')[0].strip()
                selection = selection.replace(unwanted_part, '').replace('-', '').strip()
                
            # Remove any remaining commas
            selection = selection.replace('  , ', ' - ').strip()

            if odds:
                odds = float(odds)
            else:
                odds = 'evs'
            parsed_selections.append((selection.strip(), odds))

        customer_risk_category = customer_risk_match.group(1).strip() if customer_risk_match else "-"
        bet_no = bet_number.group(1).strip()
        customer_reference = customer_reference_match.group(1).strip()
        timestamp = re.search(r"(\d{2}:\d{2}:\d{2})", timestamp_match.group(1)).group(1)

        if bet_details_match and bet_details_match.group(1):
            bet_details = bet_details_match.group(1).strip()
            if bet_details == 'Win Only':
                bet_details = 'Win'
            elif bet_details == 'Each Way':
                bet_details = 'ew'        
        unit_stake = bet_details_match.group(3).strip()
        payment = bet_details_match.group(4).strip()
        if bet_type_match:
            # Split by ':' and take the last part
            bet_type_parts = bet_type_match.group(1).split(':')
            if len(bet_type_parts) > 1:
                bet_type = bet_type_parts[-1].strip()

        return bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type
    else:
        return None, None, None, None, None, None, None, None, None

### PARSE KNOCKBACK INFORMATION FROM WAGERALERT
def parse_wageralert_details(content):
    # Initialize variables to store extracted information
    customer_ref = None
    knockback_id = None
    knockback_details = {}
    time = None

    # Regular expressions to extract relevant information
    customer_ref_pattern = r'Customer Ref: (\w+)'
    details_pattern = r'Knockback Details: (\d+)([\s\S]*?)\n\nCustomer services reference no:'
    time_pattern = r'- Date: \d+ [A-Za-z]+ \d+\n - Time: (\d+:\d+:\d+)'

    # Extract Customer Ref
    customer_ref_match = re.search(customer_ref_pattern, content)
    if customer_ref_match:
        customer_ref = customer_ref_match.group(1)

    # Extract Knockback Details
    details_match = re.search(details_pattern, content)
    if details_match:
        knockback_id = details_match.group(1)
        details_content = details_match.group(2).strip()
        # Split details content by lines
        details_lines = details_content.split('\n')
        for line in details_lines:
            parts = line.split(':')
            if len(parts) == 2:
                knockback_details[parts[0].strip()] = parts[1].strip()

    # Extract Time
    time_match = re.search(time_pattern, content)
    if time_match:
        time = time_match.group(1)

    return customer_ref, knockback_id, knockback_details, time

###  PARSE SMS BETS
def parse_sms_details(bet_text):
    wager_number_pattern = r"Wager Number = (\d+)"
    customer_reference_pattern = r"Customer Reference: (\w+)"
    mobile_number_pattern = r"Mobile Number: (\d+)"
    sms_wager_text_pattern = r"SMS Wager Text:((?:.*\n?)+)"

    wager_number_match = re.search(wager_number_pattern, bet_text)
    customer_reference_match = re.search(customer_reference_pattern, bet_text)
    mobile_number_match = re.search(mobile_number_pattern, bet_text)
    sms_wager_text_match = re.search(sms_wager_text_pattern, bet_text)

    wager_number = wager_number_match.group(1) if wager_number_match else None
    customer_reference = customer_reference_match.group(1) if customer_reference_match else None
    mobile_number = mobile_number_match.group(1) if mobile_number_match else None
    sms_wager_text = sms_wager_text_match.group(1).strip() if sms_wager_text_match else None

    return wager_number, customer_reference, mobile_number, sms_wager_text

### ADD PARSED DATA TO SELECTION_BETS DICTIONARY
def update_selection_bets(bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type):
    # Check if any essential information is missing
    if parsed_selections is None or customer_reference is None or bet_no is None or timestamp is None:
        print("Skipping bet due to missing information")
        return

    # If bet_number not in selection_bets, create a new entry
    if bet_no not in selection_bets:
        selection_bets[bet_no] = []

    # Append the bet details to the selections for the given bet_number
    selection_bets[bet_no].append((
        parsed_selections,
        timestamp,
        customer_reference,
        customer_risk_category,
        bet_details,
        unit_stake,
        payment,
        bet_type
    ))

### CREATE REPORT ON DAILY ACTIVITY
def create_daily_report():
    # Get a list of all text files in the folder
    files = get_files()
    
    report_output = ""

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
    m_clients = set()
    norisk_clients = set()

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

    progress["maximum"] = len(files)
    progress["value"] = 0
    root.update_idletasks()

    for i, bet in enumerate(files):
        file_path = os.path.join(BET_FOLDER_PATH, bet)

        progress["value"] = i + 1
        root.update_idletasks()

        with open(file_path, 'r') as file:
            bet_text = file.read()

            is_sms =  'sms' in bet_text.lower()

            is_bet = 'website' in bet_text.lower()

            is_wageralert = 'knockback' in bet_text.lower()

            if is_bet:
                
                _, _, timestamp, bet_customer_reference, customer_risk_category, _, _, payment, _ = parse_bet_details(bet_text)


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
                wageralert_customer_reference, knockback_id, knockback_details, time = parse_wageralert_details(bet_text)

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
                _, sms_customer_reference, _, _ = parse_sms_details(bet_text)
                sms_clients.add(sms_customer_reference)
                total_sms += 1

    # Get the list of all files in the 'logs' directory
    log_files = os.listdir('logs')

    # Sort the files by modification time
    log_files.sort(key=lambda file: os.path.getmtime('logs/' + file))

    # Get the latest file
    latest_file = log_files[-1]
    print("Latest file:", latest_file)

    # Open and read the latest log file
    with open('logs/' + latest_file, 'r') as file:
        lines = file.readlines()
    print(lines)
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

    print("Course updates:", course_updates)
    print("Staff updates:", staff_updates)

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

### CREATE CLIENT REPORT ON DAILY ACTIVITY
def create_client_report(customer_ref):
    # Get a list of all text files in the folder
    files = get_files()
    
    report_output = ""
    client_report_feed = ""
    separator = "\n\n---------------------------------------------------------------------------------\n\n"


    current_date = date.today()
    date_string = current_date.strftime("%d-%m-%y")

    # Get the current time
    time = datetime.now()
    formatted_time = time.strftime("%H:%M:%S")

    # Bets Report for the specific client
    total_bets = 0
    total_stakes = 0.0

    # Wageralert Report for the specific client
    total_wageralerts = 0
    liability_exceeded = 0
    price_change = 0
    event_ended = 0
    other_alert = 0

    # SMS Report for the specific client
    total_sms = 0

    
    # List of timestamps for the client
    timestamps = []
    hour_ranges = {}

    progress["maximum"] = len(files)
    progress["value"] = 0
    root.update_idletasks()

    for i, bet in enumerate(files):
        file_path = os.path.join(BET_FOLDER_PATH, bet)

        progress["value"] = i + 1
        root.update_idletasks()

        with open(file_path, 'r') as file:
            bet_text = file.read()

            is_bet = 'website' in bet_text.lower()
            is_wageralert = 'knockback' in bet_text.lower()
            is_sms = 'sms' in bet_text.lower()


            if is_bet:
                bet_no, parsed_selections, timestamp, bet_customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type = parse_bet_details(bet_text)

                if bet_customer_reference == customer_ref:
                    selection = "\n".join([f"   - {sel} at {odds}" for sel, odds in parsed_selections])
                    client_report_feed += f"{timestamp}-{bet_no} | {bet_customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator
                    
                    timestamps.append(timestamp)
                    payment_value = float(payment[1:].replace(',', ''))
                    total_stakes += payment_value
                    total_bets += 1
            if is_wageralert:
                wageralert_customer_reference, knockback_id, knockback_details, time = parse_wageralert_details(bet_text)

                if wageralert_customer_reference == customer_ref:
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
                    total_wageralerts += 1
                    formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items()])
                    client_report_feed += f"{time} - {wageralert_customer_reference} - WAGER KNOCKBACK:\n   {formatted_knockback_details}" + separator 

            if is_sms:
                wager_number, sms_customer_reference, _, sms_wager_text = parse_sms_details(bet_text)

                if sms_customer_reference == customer_ref:
                    client_report_feed += f"{sms_customer_reference}-{wager_number} SMS WAGER:\n{sms_wager_text}" + separator
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

### FUNCTION TO EXTRACT BETS PLACED BY RISK CLIENTS FROM DICTIONARY
def get_bets_with_risk_category():
    risk_users_betting = set()
    bets_with_risk = []
    for bet_number, bet_details_list in selection_bets.items():
        for bet_details in bet_details_list:
            parsed_selections, timestamp, customer_reference, customer_risk_category, unit_stake, payment, bet_details, bet_Type = bet_details
            selection = "\n - ".join([f"{sel} at {odds}" for sel, odds in parsed_selections])

            if customer_risk_category and customer_risk_category != '-':
                if (selection, bet_number, customer_reference, customer_risk_category, timestamp, unit_stake, bet_details, payment) not in bets_with_risk:
                    bets_with_risk.append((selection, bet_number, customer_reference, customer_risk_category, timestamp, unit_stake, bet_details, payment))
                risk_users_betting.add((customer_reference, customer_risk_category))

    sorted_risk_users = sorted(risk_users_betting, key=lambda x: x[1])  # Sort by customer reference

    bets_with_risk.sort(key=lambda bet: int(bet[1]), reverse=True)
    formatted_risk_users_list = ''.join([f"{customer_reference} ({customer_risk_category})\n" for customer_reference, customer_risk_category in sorted_risk_users])


    formatted_message = '\n'.join([f"{timestamp} - {bet_no} | {customer_reference} ({risk_category}) | {payment} {bet_details}:\n - {selection} \n" for selection, bet_no, customer_reference, risk_category, timestamp, bet_details, unit_stake, payment in bets_with_risk])
    bets_with_risk_text.config(state="normal")
    bets_with_risk_text.delete('1.0', tk.END)
    bets_with_risk_text.insert('1.0', formatted_message)
    bets_with_risk_text.config(state="disabled")

### GET EP BETS, NOT BEING USED BUT MAY BE IN FUTURE
def get_ep_bets():
    # Regular expression pattern to extract the time in the format "hh:mm"
    time_pattern = r"(\d{2}:\d{2})"
    ep_bets_to_display = []

    for selection, bets in selection_bets.items():
        match = re.search(time_pattern, selection)

        if match:
            selection_time = datetime.strptime(match.group(1), '%H:%M')
            for bet_number, bet_info_list in bets.items():
                for bet in bet_info_list:
                    bet_time = datetime.strptime(bet[2], '%H:%M:%S')
                    time_difference = selection_time - bet_time

                    if time_difference > timedelta(minutes=11):
                        # Append a tuple with selection, bet_number, and bet_info to ep_bets_to_display
                        ep_bets_to_display.append((selection, bet_number, bet))

    ep_bets_to_display.sort(key=lambda bet: int(bet[1]), reverse=True)

    formatted_message = '\n'.join([f"{bet[2]} | {bet[0]} ({bet[1]}) | {bet[4]} {bet[3]} @ {bet[6]}\n{bet_number} | {selection}\n" for selection, bet_number, bet in ep_bets_to_display])

    # ep_bets_text.config(state="normal")
    # ep_bets_text.delete('1.0', tk.END)
    # ep_bets_text.insert('1.0', formatted_message)
    # ep_bets_text.config(state="disabled")

### FUNCTION TO DISPLAY RUNS ON SELECTIONS
def check_bet_runs():
    global DEFAULT_NUM_BETS_TO_RUN
    num_bets = DEFAULT_NUM_BETS_TO_RUN

    # Dictionary to store selections and their corresponding bet numbers
    selection_to_bets = defaultdict(list)

    # Iterate through the bets and update the dictionary
    for bet_no, bet_details in selection_bets.items():
        selections = [selection for selection, _ in bet_details[0][0]]
        for selection in selections:
            selection_to_bets[selection].append(bet_no)

    # Sort selections by the number of bets in descending order
    sorted_selections = sorted(selection_to_bets.items(), key=lambda item: len(item[1]), reverse=True)

    # Clear the text widget
    runs_text.config(state="normal")
    runs_text.delete('1.0', tk.END)

    for selection, bet_numbers in sorted_selections:
        if len(bet_numbers) > num_bets:
            runs_text.insert(tk.END, f"{selection}\n")
            for bet_number in bet_numbers:
                bet_info = selection_bets[bet_number][0]
                for sel, odds in bet_info[0]:
                    if selection == sel:
                        runs_text.insert(tk.END, f" - {bet_info[1]} - {bet_number} | {bet_info[2]} ({bet_info[3]}) at {odds}\n")
            runs_text.insert(tk.END, f"\n")



    runs_text.config(state=tk.DISABLED)

### GET THE LIST OF USERS TO SEARCH
def get_client_report_ref():
    global client_report_user
    client_report_user = simpledialog.askstring("Client Reporting", "Enter Client Username: ")
    if client_report_user:
        client_report_user = client_report_user.upper()
        threading.Thread(target=create_client_report, args=(client_report_user,)).start()

### GET FACTORING DATA FROM GOOGLE SHEETS USING API
def factoring_sheet():
    tree.delete(*tree.get_children())
    spreadsheet = gc.open('Factoring Diary')
    print("Getting Factoring Sheet")
    worksheet = spreadsheet.get_worksheet(4)  # 0 represents the first worksheet
    data = worksheet.get_all_values()
    print("Retrieving factoring data")
    # Insert data into the Treeview for the specified columns
    for row in data[2:]:  # Start from the 4th row (index 3) in your spreadsheet
        tree.insert("", "end", values=[row[0], row[1], row[2], row[3], row[4]])

### WIZARD TO ADD FACTORING TO FACTORING DIARY
def open_wizard():
    global user
    # Check if user is empty
    if not user:
        user_login()

    def handle_submit():
        # Insert the values into the corresponding columns in your Google Sheet
        spreadsheet = gc.open('Factoring Diary')
        worksheet = spreadsheet.get_worksheet(4)  # Adjust the worksheet index as needed

        # Get the next available row
        next_row = len(worksheet.col_values(1)) + 1

        current_time = datetime.now().strftime("%H:%M:%S")

        # Insert the values into the sheet
        worksheet.update_cell(next_row, 1, current_time)
        worksheet.update_cell(next_row, 2, entry1.get())
        worksheet.update_cell(next_row, 3, entry2.get())
        worksheet.update_cell(next_row, 4, entry3.get())
        worksheet.update_cell(next_row, 5, user)  # Use user initials instead of entry4.get()

        # Insert the new row into the Treeview
        tree.insert("", "end", values=[current_time, entry1.get(), entry2.get(), entry3.get(), user])

        # Close the wizard window
        wizard_window.destroy()

    # Create a new Toplevel window for the wizard
    wizard_window = tk.Toplevel(root)

    # Create and pack three Entry widgets for user input
    username = ttk.Label(wizard_window, text="Username")
    username.pack(padx=5, pady=5)
    entry1 = ttk.Entry(wizard_window)
    entry1.pack(padx=5, pady=5)

    riskcat = ttk.Label(wizard_window, text="Risk Category")
    riskcat.pack(padx=5, pady=5)
    # Options for the risk category
    options = ["W", "M", "X", "S"]
    entry2 = ttk.Combobox(wizard_window, values=options)
    entry2.pack(padx=5, pady=5)
    entry2.set(options[0])
     
    assrating = ttk.Label(wizard_window, text="Assessment Rating")
    assrating.pack(padx=5, pady=5)
    entry3 = ttk.Entry(wizard_window)
    entry3.pack(padx=5, pady=5)

    # Bind the "Enter" key to the submit function
    wizard_window.bind('<Return>', lambda event=None: handle_submit())

    # Create a submit button that handles the submitted values
    submit_button = ttk.Button(wizard_window, text="Submit", command=handle_submit)
    submit_button.pack(padx=5, pady=5)

### OPTIONS SETTINGS
def set_recent_bets():
    global DEFAULT_NUM_RECENT_FILES
    DEFAULT_NUM_RECENT_FILES = recent_bets_var.get()
#
def set_bet_folder_path():
    global BET_FOLDER_PATH
    new_folder_path = tk.filedialog.askdirectory()
    if new_folder_path is not None:
        BET_FOLDER_PATH = new_folder_path
    refresh_display()
#
def set_num_run_bets(*args):
    global DEFAULT_NUM_BETS_TO_RUN
    new_value = int(num_run_bets_var.get())
    if new_value is not None:
        DEFAULT_NUM_BETS_TO_RUN = new_value

### GET CURRENT OPTIONS SETUP FOR FEED
def get_feed_options():
    risk_value = default_state_risk.get()
    wageralert_value = default_state_wageralert.get()
    textbets_value = default_state_textbets.get()
    return risk_value, wageralert_value, textbets_value

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

    settings_window = tk.Toplevel(root)
    settings_window.title("Options")
    settings_window.iconbitmap('src/splash.ico')


    # Set window size to match frame size
    settings_window.geometry("310x430")  # Width x Height

    # Disable window resizing
    settings_window.resizable(False, False)

    # Position window on the right side of the screen
    screen_width = settings_window.winfo_screenwidth()
    settings_window.geometry(f"+{screen_width - 350}+50")  # "+X+Y"

    # OPTIONS FRAME
    options_frame = ttk.LabelFrame(settings_window, style='Card', text="Options", width=120, height=205)
    options_frame.place(x=5, y=5, width=300, height=420)
    
    set_recent_bets_label=tk.Label(options_frame, font=("Helvetica", 10), text="Bets to Check", fg="#000000", bg="#ffffff")
    set_recent_bets_label.place(x=100,y=10)

    radiobutton_values = [20, 50, 100, 300, 1000]
    for i, value in enumerate(radiobutton_values):
        ttk.Radiobutton(options_frame, text=str(value), variable=recent_bets_var, value=value, command=set_recent_bets).place(x=5 + i*55, y=30, width=65)
    
    set_recent_runs_label=tk.Label(options_frame, font=("Helvetica", 10), text="Bets to a Run", fg="#000000", bg="#ffffff")
    set_recent_runs_label.place(x=100,y=70)

    spinbox = ttk.Spinbox(options_frame, from_=2, to=10, textvariable=num_run_bets_var)
    spinbox.place(x=50, y=95, width=200)

    separator = ttk.Separator(options_frame, orient='horizontal')
    separator.place(x=10, y=140, width=270)

    set_recent_bets_label=tk.Label(options_frame, font=("Helvetica", 10), text="Feed Options", fg="#000000", bg="#ffffff")
    set_recent_bets_label.place(x=100,y=150)

    show_risk_bets = ttk.Checkbutton(options_frame, text='Risk Only',style="Switch", variable=default_state_risk)
    show_risk_bets.place(x=20, y=175)

    show_wageralert = ttk.Checkbutton(options_frame, text='Knockbacks',style="Switch", variable=default_state_wageralert)
    show_wageralert.place(x=140, y=205)

    show_textbets = ttk.Checkbutton(options_frame, text='Text Bets',style="Switch", variable=default_state_textbets)
    show_textbets.place(x=20, y=205)

    separator = ttk.Separator(options_frame, orient='horizontal')
    separator.place(x=10, y=240, width=270)

    toggle_button = ttk.Checkbutton(options_frame, text='Auto Refresh', variable=auto_refresh_state, onvalue=True, offvalue=False)
    toggle_button.place(x=90, y=260) 

    separator = ttk.Separator(options_frame, orient='horizontal')
    separator.place(x=10, y=300, width=270)

    ### SET EXPORT PATH BUTTON
    set_bet_folder_path_button = ttk.Button(options_frame, command=set_bet_folder_path, text="BWW Folder")
    set_bet_folder_path_button.place(x=20, y=320, width=110)

    get_courses_button = ttk.Button(options_frame, text="Get Courses", command=get_courses)
    get_courses_button.place(x=150, y=320, width=110)

    reset_courses_button = ttk.Button(options_frame, text="Reset Courses", command=reset_update_times)
    reset_courses_button.place(x=150, y=360, width=110)

    def save_and_close():
        refresh_display()
        settings_window.destroy()

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
    messagebox.showinfo("About", "Geoff Banks Bet Monitoring v6.0")

def howTo():
    messagebox.showinfo("How to use", "General\nProgram checks bww\export folder on 30s interval.\nOnly set amount of recent bets are checked. This amount can be defined in options.\nBet files are parsed then displayed in feed and any bets from risk clients show in 'Risk Bets'.\n\nRuns on Selections\nDisplays selections with more than 'X' number of bets.\nX can be defined in options.\n\nReports\nDaily Report - Generates a report of the days activity.\nClient Report - Generates a report of a specific clients activity.\n\nFactoring\nLinks to Google Sheets factoring diary.\nAny change made to customer account reported here by clicking 'Add'.\n\nRace Updation\nList of courses for updating throughout the day.\nWhen course updated, click ✔.\nTo remove course, click X.\nTo add a course or event for update logging, click +\nHorse meetings will turn red after 30 minutes. Greyhounds 1 hour.\nAll updates are logged under F:\GB Bet Monitor\logs.\n\nPlease report any errors to Sam.")

def run_factoring_sheet():
    threading.Thread(target=factoring_sheet).start()

def run_create_daily_report():
    threading.Thread(target=create_daily_report).start()

if __name__ == "__main__":

    ### ROOT WINDOW
    root = tk.Tk()
    root.title("GB Bet Monitor v6.0")
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

    recent_bets_var = tk.IntVar()
    recent_bets_var.set(DEFAULT_NUM_RECENT_FILES)

    auto_refresh_state = tk.BooleanVar()
    auto_refresh_state.set(True)



    ### BET FEED
    feed_frame = ttk.LabelFrame(root, style='Card', text="Bet Feed")
    feed_frame.place(relx=0.44, rely=0.01, relwidth=0.55, relheight=0.64)
    feed_text = tk.Text(feed_frame, font=("Helvetica", 11, "bold"),wrap='word',padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    feed_text.config(state='disabled')
    feed_text.pack(fill='both', expand=True)
    feed_scroll = ttk.Scrollbar(feed_text, orient='vertical', command=feed_text.yview)
    feed_scroll.pack(side="right", fill="y")
    feed_text.configure(yscrollcommand=feed_scroll.set)



    ### RUNS ON SELECTIONS
    runs_frame = ttk.LabelFrame(root, style='Card', text="Runs on Selections")
    runs_frame.place(relx=0.01, rely=0.01, relwidth=0.41, relheight=0.52)
    runs_text=tk.Text(runs_frame, font=("Helvetica", 11), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    runs_text.config(state='disabled') 
    runs_text.pack(fill='both', expand=True)

    runs_scroll = ttk.Scrollbar(runs_text, orient='vertical', command=runs_text.yview)
    runs_scroll.pack(side="right", fill="y")

    runs_text.configure(yscrollcommand=runs_scroll.set)



    ### NOTEBOOK FRAME
    notebook_frame = ttk.Frame(root)
    notebook_frame.place(relx=0.01, rely=0.54, relwidth=0.42, relheight=0.43)
    notebook = ttk.Notebook(notebook_frame)

    ### STAFF BULLETIN TAB
    tab_1 = ttk.Frame(notebook)
    notebook.add(tab_1, text="Staff Bulletin")
    staff_bulletin_text=tk.Text(tab_1, font=("Helvetica", 10), bd=0, wrap='word',padx=10, pady=10, fg="#000000", bg="#ffffff")
    staff_bulletin_text.pack(fill='both', expand=True)

    ### RISK BETS TAB
    tab_2 = ttk.Frame(notebook)
    notebook.add(tab_2, text="Risk Bets")
    bets_with_risk_text=tk.Text(tab_2, font=("Helvetica", 10), bd=0, wrap='word',padx=10, pady=10, fg="#000000", bg="#ffffff")
    bets_with_risk_text.grid(row=0, column=0, sticky="nsew")
    bets_with_risk_text.pack(fill='both', expand=True)

    ### REPORT TAB
    tab_3 = ttk.Frame(notebook)
    notebook.add(tab_3, text="Report")
    tab_3.grid_rowconfigure(0, weight=1)
    tab_3.grid_rowconfigure(1, weight=1)
    tab_3.grid_columnconfigure(0, weight=1)
    report_ticket = tk.Text(tab_3, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
    report_ticket.config(state='disabled')
    report_ticket.grid(row=0, column=0, sticky="nsew")

    # PROGRESS BAR FOR REPORT
    progress = ttk.Progressbar(tab_3, mode="determinate", length=250)
    progress.grid(row=2, column=0, pady=(0, 0), sticky="nsew")

    # GENERATE REPORT BUTTONS: CLIENT REPORT AND DAILY REPORT
    client_refresh_button = ttk.Button(tab_3, text="User Report", command=get_client_report_ref)
    client_refresh_button.grid(row=3, column=0, pady=(0, 0), sticky="w")
    daily_refresh_button = ttk.Button(tab_3, text="Daily Report", command=run_create_daily_report)
    daily_refresh_button.grid(row=3, column=0, pady=(0, 0), sticky="e")

    ### CLIENT FACTORING TAB
    tab_4 = ttk.Frame(notebook)
    notebook.add(tab_4, text="Factoring")

    # CONFIGURING THE TREEVIEW
    tree = ttk.Treeview(tab_4)
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
    tab_4.grid_columnconfigure(0, weight=1)

    # BUTTONS AND TOOLTIP LABEL FOR FACTORING TAB
    add_restriction_button = ttk.Button(tab_4, text="Add", command=open_wizard)
    add_restriction_button.grid(row=1, column=0, pady=(5, 10), sticky="e")
    refresh_factoring_button = ttk.Button(tab_4, text="Refresh", command=factoring_sheet)
    refresh_factoring_button.grid(row=1, column=0, pady=(5, 10), sticky="w")
    factoring_label = ttk.Label(tab_4, text="Click 'Add' to report a new customer restriction.")
    factoring_label.grid(row=1, column=0, pady=(80, 0), sticky="s")

    notebook.pack(expand=True, fill="both", padx=5, pady=5)



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
    settings_button = ttk.Button(settings_frame, text="⚙", command=open_settings, width=3)
    settings_button.place(relx=0.6, rely=0.1)

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
    staff_bulletin()

    ### GUI LOOP
    threading.Thread(target=refresh_display_periodic, daemon=True).start()
    root.mainloop()