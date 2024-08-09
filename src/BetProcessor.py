####################################################################################
##                                BETPROCESSOR.PY                                    


## PROCESS INCOMING & PREVIOUS BET, KNOCKBACK AND SMS REQUESTS, ADD TO DATABASE
## GET VIP CLIENTS, DAILY REPORTING, NEW REGISTRATIONS, RACECARDS, ODDSMONKEY
## GET ACCOUNT CLOSURE REQUESTS, WRITE API DATA TO DATA.JSON
####################################################################################



import os
import re
import json
import schedule
import fasteners
import time
import threading
import gspread
import requests
import base64
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, Label
from PIL import ImageTk, Image
from datetime import datetime, timedelta, date
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pytz import timezone
from collections import defaultdict, Counter
from bs4 import BeautifulSoup
from tkinter import scrolledtext



####################################################################################
## INITIALIZE GLOBAL VARIABLES & API CREDENTIALS
####################################################################################
USER_NAMES = {
    'GB': 'George',
    'JP': 'Jon',
    'DF': 'Dave',
    'SB': 'Sam',
    'JJ': 'Joji',
    'AE': 'Arch',
    'EK': 'Ed',
}

with open('src/creds.json') as f:
    creds = json.load(f)
pipedrive_api_token = creds['pipedrive_api_key']
scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)
gc = gspread.authorize(credentials)
last_processed_time = datetime.now()
last_run_time = None
file_lock = threading.Lock()
path = 'F:\BWW\Export'
processed_races = set()
processed_closures = set()
previously_seen_events = set()
notified_users = set()
bet_count_500 = False
bet_count_750 = False
bet_count_1000 = False
knockback_count_250 = False


####################################################################################
## SET FOLDER PATH FOR RAW BET FILES
####################################################################################
def set_bet_folder_path():
    global path
    new_folder_path = filedialog.askdirectory()
    if new_folder_path:
        path = new_folder_path



####################################################################################
## SET BET DATABASE OR GENERATE A NEW BET DATABASE FOR THE DAY
####################################################################################
def load_database(app):
    print("\nLoading database")
    date = datetime.now().strftime('%Y-%m-%d')
    filename = f'database/{date}-wager_database.json'

    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        app.log_message('No database found. Creating a new one for ' + date)
        return []



####################################################################################
## IDENTIFY BET TYPE AND PARSE TEXT ACCORDINGLY
####################################################################################
def identify_sport(selection):
    print(f"Type of selection: {type(selection)}, Content: {selection}")

    # Adjusted to handle both lists/tuples of selections and single selections within a tuple
    if isinstance(selection, (list, tuple)):
        print("Handling list or tuple format")
        # Check if the first element is a list or tuple, indicating a list of selections
        if all(isinstance(sel, (list, tuple)) for sel in selection):
            for sel in selection:
                if len(sel) > 0:
                    selection_str = sel[0]  # Extract the selection name from the first element
                    print(f"Processing selection: {selection_str}")
                    if 'trap' in selection_str.lower():
                        return 1  # Greyhound
                    elif re.search(r'\d{2}:\d{2}', selection_str):
                        return 0  # Horse
                    else:
                        return 2  # Other
                else:
                    print("Inner element is empty or not a list/tuple")
                    return 3  # Default for unrecognized format within list/tuple
        # New case: Handle single selection within a tuple
        else:
            selection_str = selection[0]  # Assuming the first element is the selection name
            print(f"Processing single selection: {selection_str}")
            if 'trap' in selection_str.lower():
                return 1  # Greyhound
            elif re.search(r'\d{2}:\d{2}', selection_str):
                return 0  # Horse
            else:
                return 2  # Other
            
    elif isinstance(selection, dict):
        print("Handling dictionary format")
        if selection is None or '- Meeting Name' not in selection or selection['- Meeting Name'] is None:
            print("Dictionary format not as expected")
            return 3  # Default identifier for null values
        if 'trap' in selection['- Selection Name'].lower():
            return 1  # Greyhound
        elif re.search(r'\d{2}:\d{2}', selection['- Meeting Name']):
            return 0  # Horse
        else:
            return 2  # Other
    else:
        print("Selection format unrecognized")
        return 3  # Default for unrecognized format

def add_sport_to_selections(selections):
    sports = set()
    for selection in selections:
        # Directly pass the selection to identify_sport without checking its type here
        sport = identify_sport(selection)
        sports.add(sport)
    return list(sports)

def parse_file(file_path, app):
    with open(file_path, 'r') as file:
        bet_text = file.read()
        bet_text_lower = bet_text.lower()
        is_sms = 'sms' in bet_text_lower
        is_bet = 'website' in bet_text_lower
        is_wageralert = 'knockback' in bet_text_lower

        if is_wageralert:
            details = parse_wageralert_details(bet_text)
            unique_knockback_id = f"{details['Knockback ID']}-{details['Time']}"
            sports = add_sport_to_selections(details['Selections'])
            bet_info = {
                'time': details['Time'],
                'id': unique_knockback_id,
                'type': 'WAGER KNOCKBACK',
                'customer_ref': details['Customer Ref'],
                'details': details,
                'Sport': sports,
            }
            print('Knockback Processed ' + unique_knockback_id)
            app.log_message(f"Knockback Processed {unique_knockback_id}, {details['Customer Ref']}, {details['Time']}")
            return bet_info

        elif is_sms:
            creation_time = os.path.getctime(file_path)
            creation_time_str = datetime.fromtimestamp(creation_time).strftime('%H:%M:%S')
            wager_number, customer_reference, _, sms_wager_text = parse_sms_details(bet_text)
            
            bet_info = {
                'time': creation_time_str,
                'id': wager_number,
                'type': 'SMS WAGER',
                'customer_ref': customer_reference,
                'details': sms_wager_text
            }
            print('SMS Processed ' + wager_number)
            app.log_message(f'SMS Processed {wager_number}, {customer_reference}')
            return bet_info

        elif is_bet:
            bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type = parse_bet_details(bet_text)
            sports = add_sport_to_selections(parsed_selections)
            bet_info = {
                'time': timestamp,
                'id': bet_no,
                'type': 'BET',
                'customer_ref': customer_reference,
                'details': {
                    'selections': parsed_selections,
                    'risk_category': customer_risk_category,
                    'bet_details': bet_details,
                    'unit_stake': unit_stake,
                    'payment': payment,
                    'bet_type': bet_type
                },
                'Sport': sports,
            }
            print('Bet Processed ' + bet_no)
            app.log_message(f'Bet Processed {bet_no}, {customer_reference}, {timestamp}')
            return bet_info
        
    print('File not processed ' + file_path + 'IF YOU SEE THIS TELL SAM - CODE 4')
    return {}

def process_file(file_path):
    database = load_database(app)

    bet_data = parse_file(file_path, app)

    add_bet(database, bet_data, app)

    save_database(database)



####################################################################################
## LOG NOTIFICATION FOR RG OR STAFF 
####################################################################################
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
    except json.JSONDecodeError:
        notifications = []
        
    notifications.insert(0, {'time': time, 'message': message, 'important': important})

    with file_lock:
        with open('notifications.json', 'w') as f:
            json.dump(notifications, f, indent=4)

def rg_report_notification():
    data = load_database(app)
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

    high_risk_users = []

    for user, scores in user_scores.items():
        scores['score'] = sum(scores['scores'].values())
        if scores['score'] >= 6:
            high_risk_users.append(user)

    if high_risk_users:
        log_notification(f">5 RG score: {', '.join(high_risk_users)}", True)

def staff_report_notification():
    global USER_NAMES
    global notified_users 
    staff_updates_today = Counter()
    today = datetime.now().date()

    log_files = os.listdir('logs/updatelogs')
    log_files.sort(key=lambda file: os.path.getmtime('logs/updatelogs/' + file))

    # Read the log file for today
    for log_file in log_files:
        file_date = datetime.fromtimestamp(os.path.getmtime('logs/updatelogs/' + log_file)).date()
        if file_date == today:
            with open('logs/updatelogs/' + log_file, 'r') as file:
                lines = file.readlines()

            for line in lines:
                if line.strip() == '':
                    continue

                parts = line.strip().split(' - ')

                if len(parts) == 2:
                    time, staff_initials = parts
                    staff_name = USER_NAMES.get(staff_initials, staff_initials)
                    staff_updates_today[staff_name] += 1

    for user, count in staff_updates_today.items():
        if count >= 50 and user not in notified_users:
            log_notification(f"{user} has {count} updates!", True)
            notified_users.add(user)

def activity_report_notification():
    data = load_database(app)
    bet_count = len([bet for bet in data if bet['type'] == 'BET'])
    knockback_count = len([bet for bet in data if bet['type'] == 'WAGER KNOCKBACK'])

    thresholds = {
        250: {'count': bet_count, 'flag': 'bet_count_250', 'message': 'bets taken'},
        500: {'count': bet_count, 'flag': 'bet_count_500', 'message': 'bets taken'},
        750: {'count': bet_count, 'flag': 'bet_count_750', 'message': 'bets taken'},
        1000: {'count': bet_count, 'flag': 'bet_count_1000', 'message': 'bets taken'},
        250: {'count': knockback_count, 'flag': 'knockback_count_250', 'message': 'knockbacks'}
    }

    for threshold, data in thresholds.items():
        if data['count'] == threshold and not globals()[data['flag']]:
            log_notification(f"{data['count']} {data['message']}", True)
            globals()[data['flag']] = True


####################################################################################
## EXTRACT DATA POINTS FROM BET TEXT
####################################################################################
def parse_bet_details(bet_text):
    bet_number_pattern = r"Wager Number - (\d+)"
    customer_ref_pattern = r"Customer Reference - (\w+)"
    customer_risk_pattern = r"Customer Risk Category - (\w+)?"
    time_pattern = r"Bet placed on \d{2}/\d{2}/\d{4} (\d{2}:\d{2}:\d{2})"
    selection_pattern = r"(.+?, .+?, .+?) (?:at|on) (\d+\.\d+|SP)?"
    bet_details_pattern = r"Bets (Win Only|Each Way|Forecast): (\d+ .+?)\. Unit Stake: (£[\d,]+\.\d+), Payment: (£[\d,]+\.\d+)\."
    bet_type_pattern = r"Wagers\s*:\s*([^\n@]+)"    
    odds_pattern = r"(?:at|on)\s+(\d+\.\d+|SP)"

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
        for selection, odds in selections:
            if '-' in selection and ',' in selection.split('-')[1]:
                unwanted_part = selection.split('-')[1].split(',')[0].strip()
                selection = selection.replace(unwanted_part, '').replace('-', '').strip()
                
            selection = selection.replace('  , ', ' - ').strip()

            if odds:
                if odds != 'SP':
                    odds = float(odds)
            else:
                odds = 'evs'
            parsed_selections.append((selection.strip(), odds))

        customer_risk_category = customer_risk_match.group(1).strip() if customer_risk_match and customer_risk_match.group(1) else "-"        
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
            bet_type_parts = bet_type_match.group(1).split(':')
            if len(bet_type_parts) > 1:
                bet_type = bet_type_parts[-1].strip()

        return bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type
    else:
        return None, None, None, None, None, None, None, None, None



####################################################################################
## EXTRACT DATA POINTS FROM KNOCKBACK TEXT
####################################################################################
def parse_wageralert_details(content):
    customer_ref_pattern = r'Customer Ref: (\w+)'
    knockback_id_pattern = r'Knockback Details: (\d+)'
    error_message_pattern = r'- Error Message: (.*)'
    liability_exceeded_pattern = r'- Liability Exceeded: (True|False)'
    max_stake_pattern = r'- Maximum stake available: (.*)'
    time_pattern = r'- Date: \d+ [A-Za-z]+ \d+\n - Time: (\d+:\d+:\d+)'
    bets_details_pattern = r"Customer's Bets Details:([\s\S]*?)\n\nCustomer's Wagers Details:"
    wagers_details_pattern = r"Customer's Wagers Details:([\s\S]*?)\n\nCustomer's services reference no:"

    customer_ref_match = re.search(customer_ref_pattern, content)
    customer_ref = customer_ref_match.group(1) if customer_ref_match else None

    knockback_id_match = re.search(knockback_id_pattern, content)
    knockback_id = knockback_id_match.group(1) if knockback_id_match else None

    error_message_match = re.search(error_message_pattern, content)
    error_message = error_message_match.group(1) if error_message_match else None

    liability_exceeded_match = re.search(liability_exceeded_pattern, content)
    liability_exceeded = liability_exceeded_match.group(1) if liability_exceeded_match else None

    max_stake_match = re.search(max_stake_pattern, content)
    max_stake = max_stake_match.group(1) if max_stake_match else None

    if not error_message:
        if liability_exceeded == 'True':
            error_message = f'Liability Exceeded: {liability_exceeded}, Maximum stake available: {max_stake}'
        else:
            error_message = 'No error message provided'

    time_match = re.search(time_pattern, content)
    time = time_match.group(1) if time_match else None

    bets_details = extract_details(content, bets_details_pattern)

    wagers_details_match = re.search(wagers_details_pattern, content)
    wagers_details = wagers_details_match.group(1).strip().split('\n') if wagers_details_match else None
    wager_name = wagers_details[0].split(': ')[1] if wagers_details else None
    total_stake = wagers_details[2].split(': ')[1] if wagers_details else None

    return {
        'Customer Ref': customer_ref,
        'Knockback ID': knockback_id,
        'Error Message': error_message,
        'Time': time,
        'Selections': bets_details,
        'Wager Name': wager_name,
        'Total Stake': total_stake
    }

def extract_details(content, pattern):
    match = re.search(pattern, content)
    selections = []
    if match:
        content = match.group(1).strip().split('\n\n')
        for selection_content in content:
            lines = selection_content.split('\n')
            selection = {}
            for key in ['- Meeting Name', '- Selection Name', '- Bet Price']:
                selection[key] = None  # Initialize keys with None
            for line in lines:
                key, value = line.split(': ')
                if key in ['- Meeting Name', '- Selection Name', '- Bet Price']:
                    selection[key] = value
            selections.append(selection)
    return selections



####################################################################################
## EXTRACT DATA POINTS FROM SMS REQUEST TEXT 
####################################################################################
def parse_sms_details(bet_text):
    bet_text = bet_text.encode("ascii", "ignore").decode()

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



####################################################################################
## ADD BET TO DATABASE, SAVE DATABASE, ORDER DATABASE
####################################################################################
def add_bet(database, bet, app):
    print("Adding a bet to the database")
    if not any(bet['id'] == existing_bet['id'] for existing_bet in database):
        database.append(bet)
    else:
        app.log_message(f'Bet already in database {bet["id"]}, {bet["customer_ref"]}! Skipping...\n')

def save_database(database):
    print("Saving database")
    date = datetime.now().strftime('%Y-%m-%d')

    filename = f'database/{date}-wager_database.json'
    
    with open(filename, 'w') as f:
        json.dump(database, f, indent=4)
    
    order_bets(filename)

def order_bets(filename):
    print("Ordering bets")
    with open(filename, 'r') as f:
        data = json.load(f)

    data_sorted = sorted(data, key=lambda x: x['time'])

    with open(filename, 'w') as f:
        json.dump(data_sorted, f, indent=4)



####################################################################################
## REPROCESS ALL RAW BET TEXTS IN FOLDER
####################################################################################
def reprocess_file(app):
    print("Reprocessing file")
    date = datetime.now().strftime('%Y-%m-%d')

    filename = f'database/{date}-wager_database.json'

    if os.path.exists(filename):
        os.remove(filename)
        app.log_message('Existing database deleted. Will begin to process todays bets....\n\n')
    else:
        app.log_message('No existing database found. Will begin processing todays bets...\n\n')

def process_existing_bets(directory, app):
    log_notification(f'Reprocessing bets', True)
    database = load_database(app)

    files = os.listdir(directory)

    bet_files = [f for f in files if f.endswith('.bww')]
    app.log_message(f'Found {len(bet_files)} files. Beginning process, please wait...\n')
    time.sleep(3)
    
    for bet_file in bet_files:
        bet = parse_file(os.path.join(directory, bet_file), app)
        print("Parsed a file")
        add_bet(database, bet, app)
        print("Added a bet to JSON")

    save_database(database)
    app.log_message('Bet processing complete. Waiting for new files...\n')
    log_notification(f'Finished reprocessing', True)



####################################################################################
## GET VIP CLIENTS & DAILY REPORTING FROM GOOGLE SHEETS API
####################################################################################
def get_vip_clients(app):
    spreadsheet = gc.open('Management Tool')
    worksheet = spreadsheet.get_worksheet(4)
    data = worksheet.get_all_values()

    vip_clients = [row[0] for row in data if row[0]]
    
    return vip_clients

def get_reporting_data(app):
    current_month = datetime.now().strftime('%B')

    spreadsheet_name = 'Reporting ' + current_month
    spreadsheet = gc.open(spreadsheet_name)

    worksheet = spreadsheet.get_worksheet(3)
    daily_turnover = worksheet.acell('E1').value
    daily_profit = worksheet.acell('F1').value
    daily_profit_percentage = worksheet.acell('G1').value

    drive_service = build('drive', 'v3', credentials=credentials)
    file_id = spreadsheet.id
    request = drive_service.files().get(fileId=file_id, fields='modifiedTime')
    response = request.execute()
    last_updated_time = datetime.strptime(response['modifiedTime'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%H:%M:%S")

    enhanced_place = spreadsheet.get_worksheet(7)
    values = enhanced_place.get_all_values()
    today = datetime.now().strftime('%d/%m/%Y')  # adjust the date format as needed

    enhanced_places = [f'{row[3].title()}, {row[2]}' for row in values if row[1] == today]

    return daily_turnover, daily_profit, daily_profit_percentage, last_updated_time, enhanced_places



####################################################################################
## GET NEW REGISTRATIONS FROM PIPEDRIVE API
####################################################################################
def get_new_registrations(app):
    response = requests.get(f'https://api.pipedrive.com/v1/persons?api_token={pipedrive_api_token}&filter_id=60')

    if response.status_code == 200:
        data = response.json()

        persons = data.get('data', [])
        newreg_clients = [person.get('c1f84d7067cae06931128f22af744701a07b29c6', '') for person in persons]
    
    return newreg_clients



####################################################################################
## LOG NOTIFICATIONS
####################################################################################
def check_closures_and_race_times():
    global processed_races, processed_closures
    current_time = datetime.now().strftime('%H:%M')
    current_date = datetime.now().date()

    try:
        with open('src/data.json', 'r') as f:
            data = json.load(f)
            enhanced_places = data['enhanced_places']
            closures = data['closures']
    except FileNotFoundError:
        print("File 'src/data.json' not found.")
        return
    except json.JSONDecodeError:
        print("Error decoding JSON.")
        return

    for closure in closures:
        if closure['email_id'] in processed_closures:
            continue
        if not closure.get('completed', False):
            log_notification(f"{closure['Restriction']} request from {closure['Username'].strip()}")
            processed_closures.add(closure['email_id'])

    try:
        response = requests.get('https://globalapi.geoffbanks.bet/api/Geoff/GetSportApiData?sportcode=H,h')
        response.raise_for_status()
        api_data = response.json()
    except requests.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return
    except json.JSONDecodeError:
        print("Error decoding JSON from API response.")
        return

    races_today = []
    races_tomorrow = []
    current_weekday_name = datetime.now().strftime('%A')

    for event in api_data:
        event_weekday_name = event['eventName'].split("'s")[0]
        if event_weekday_name == current_weekday_name:
            for meeting in event['meetings']:
                for race in meeting['events']:
                    meeting_name = race['meetingName']
                    time = race['time']
                    races_today.append(f'{meeting_name}, {time}')
        else:  # This condition now correctly assumes the event is for tomorrow
            for meeting in event['meetings']:
                for race in meeting['events']:
                    meeting_name = race['meetingName']
                    time = race['time']
                    races_tomorrow.append(f'{meeting_name}, {time}')

    races_today.sort(key=lambda race: datetime.strptime(race.split(', ')[1], '%H:%M'))
    total_races_today = len(races_today)
    for index, race in enumerate(races_today, start=1):
        race_time = race.split(', ')[1]
        if current_time == race_time and race not in processed_races:
            if race in enhanced_places:
                processed_races.add(race)
                log_notification(f"{race} (enhanced) is past off time - {index}/{total_races_today}", important=True)
            else:
                processed_races.add(race)
                log_notification(f"{race} is past off time - {index}/{total_races_today}")
    
def fetch_and_print_new_events():
    global previously_seen_events
    print("Fetching new events...")
    url = 'https://globalapi.geoffbanks.bet/api/Geoff/GetSportApiData?sportcode=f,s,N,t,m,G,C,K,v,R,r,l,I,D,j,S,q,a,p,T,e,k,E,b,A,Y,n,c,y,M'
    response = requests.get(url)
    data = response.json() 

    # Extract event names from the response
    current_events = set(event['eventName'] for event in data)

    if not previously_seen_events:
        print("yep")
        previously_seen_events = current_events
    else:
        new_events = current_events - previously_seen_events
        print(len(new_events))

        for event in new_events:
            log_notification(f"New event live: {event}", True)

        previously_seen_events.update(new_events)

    print(len(current_events))

def find_stale_antepost_events():
    with open('events.json', 'r') as f:
        data = json.load(f)

    current_date = datetime.now()
    stale_antepost_events = []
    stale_events = []

    for event in data:
        event_file = event["meetings"][0]["eventFile"] if event["meetings"] else ""
        last_update_str = event.get("lastUpdate", "-")
        
        if len(event_file) > 5 and event_file[3:5].lower() == 'ap':
            try:
                last_update_date = datetime.strptime(last_update_str, '%d-%m-%Y %H:%M:%S')
            except ValueError:
                continue
            
            if current_date - last_update_date > timedelta(weeks=1):
                stale_antepost_events.append(event["eventName"])
                
        elif len(event_file) > 5:
            try:
                last_update_date = datetime.strptime(last_update_str, '%d-%m-%Y %H:%M:%S')
            except ValueError:
                continue
            
            if current_date - last_update_date > timedelta(days=1):
                stale_events.append(event["eventName"])

    if stale_antepost_events:
        log_notification(f"{stale_antepost_events} may need updating", True)
    if stale_events:
        log_notification(f"{stale_events} may need updating", True)


####################################################################################
## GET ODDSMONKEY EMAILS FROM GMAIL API, EXTRACT SELECTIONS
####################################################################################
def get_oddsmonkey_selections(app, num_messages=None, query=''):
    creds = None

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.readonly'])
                creds = flow.run_local_server(port=0)
        except RefreshError:
            print("The access token has expired or been revoked. Please re-authorize the app.")
            flow = InstalledAppFlow.from_client_secrets_file(
                'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    oddsmonkey_label_id = None
    for label in labels:
        if label['name'] == 'ODDSMONKEY':
            oddsmonkey_label_id = label['id']
            break

    if oddsmonkey_label_id is None:
        print("Label 'Oddsmonkey' not found")
        return
    results = service.users().messages().list(userId='me', labelIds=[oddsmonkey_label_id], q=query).execute()

    messages = results.get('messages', [])
    length = len(messages)

    all_selections = {}

    for message in messages if num_messages is None else messages[:num_messages]:
        try:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()

            payload = msg['payload']
            headers = payload['headers']

            for d in headers:
                if d['name'] == 'Subject':
                    subject = d['value']
                if d['name'] == 'From':
                    sender = d['value']

            parts = payload.get('parts')
            if parts is not None:
                part = parts[0]
                data = part['body']['data']
            else:
                data = payload['body']['data']

            data = data.replace("-","+").replace("_","/")
            decoded_data = base64.b64decode(data)

            soup = BeautifulSoup(decoded_data , "lxml")
            
            td_tags = soup.find_all('td', style="padding-left: 7px;padding-right: 7px;")

            try:
                selections = extract_oddsmonkey_selections(td_tags)
                all_selections.update(selections)
            except Exception as e:
                app.log_message(f"An error occurred while extracting oddsmonkey data {e}")
                print(f"An error occurred while extracting selections: {e}")

        except Exception as e:
            app.log_message(f"An error occurred while processing oddsmonkey data {e}")
            print(e)

    return all_selections

def update_todays_oddsmonkey_selections():
    with file_lock:
        try:
            today = date.today().strftime('%Y/%m/%d')
            todays_selections = get_oddsmonkey_selections(app, query=f'after:{today}')

            with open('src/data.json', 'r+') as f:
                data = json.load(f)
                data['todays_oddsmonkey_selections'] = todays_selections
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()

        except Exception as e:
            print(f"An error occurred while updating today's Oddsmonkey selections: {str(e)}")

def extract_oddsmonkey_selections(td_tags):
    selections = {}

    # Convert BeautifulSoup elements to strings and strip whitespace
    td_tags = [str(td.text).strip() for td in td_tags]
    #print(td_tags)

    # Check if the length of td_tags is a multiple of 11 (since each selection has 11 lines)
    if len(td_tags) % 11 != 0:
        print("Unexpected number of lines in td_tags")
        return selections

    # Iterate over td_tags in steps of 11
    for i in range(0, len(td_tags), 11):
        event = td_tags[i+2]  # Line 3
        selection = td_tags[i+3]  # Line 4
        lay_odds = td_tags[i+10]  # Line 11

        # Add the selection to the selections dictionary
        selections[event] = selection, lay_odds

    return selections



####################################################################################
## GET ACCOUNT CLOSURE REQUESTS & DEPOSITS FROM GMAIL API
####################################################################################
def get_closures(app):
    creds = None
    closures = []
    label_ids = {}

    # Load the existing closures from the JSON file
    with open('src/data.json', 'r') as f:
        existing_closures = json.load(f).get('closures', [])

    # Create a dictionary mapping email IDs to 'completed' status
    completed_status = {closure['email_id']: closure.get('completed', False) for closure in existing_closures}

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    # Find the IDs of the labels
    for label_name in ['REPORTING/ACCOUNT DEACTIVATION', 'REPORTING/SELF EXCLUSION', 'REPORTING/TAKE A BREAK']:
        for label in labels:
            if label['name'] == label_name:
                label_ids[label_name] = label['id']
                break

    for label_name, label_id in label_ids.items():
        if label_id is None:
            print(f"Label '{label_name}' not found")
            continue

        # Get the messages in the label
        results = service.users().messages().list(userId='me', labelIds=[label_id]).execute()
        messages = results.get('messages', [])

        for message in messages:
            # Get the message details
            msg = service.users().messages().get(userId='me', id=message['id']).execute()

            timestamp = int(msg['internalDate']) // 1000  # Convert to seconds
            date_time = datetime.fromtimestamp(timestamp)
            date_time_str = date_time.strftime('%Y-%m-%d %H:%M:%S')

            payload = msg['payload']
            email_id = message['id']


            # Get the message body
            parts = payload.get('parts')
            if parts is not None:
                part = parts[0]
                data = part['body']['data']
            else:
                # If there are no parts, get the body from the 'body' field
                data = payload['body']['data']

            data = data.replace("-","+").replace("_","/")
            decoded_data = base64.b64decode(data)

            soup = BeautifulSoup(decoded_data , "lxml")

            # Extract the data from the specified tags
            first_name_tag = soup.find('span', {'class': 'given-name'})
            last_name_tag = soup.find('span', {'class': 'family-name'})
            username_tag = soup.find('td', {'id': 'roField4'}).find('div')

            # Find all 'tr' elements with class 'radio'
            tr_tags = soup.find_all('tr', {'class': 'radio'})

            # Initialize restriction and length
            restriction = None
            length = None

            # Iterate over the 'tr' elements
            for tr_tag in tr_tags:
                # Find the 'th' and 'div' elements within the 'tr' element
                th_tag = tr_tag.find('th')
                div_tag = tr_tag.find('div')

                # If both 'th' and 'div' elements are found
                if th_tag and div_tag:
                    # Get the text content of the 'th' and 'div' elements
                    # Get the text content of the 'th' and 'div' elements
                    th_text = th_tag.get_text().strip().replace('\n', '').replace('*', '').strip()
                    div_text = div_tag.get_text().strip()

                    # Check if the 'th' text is 'Restriction Required' or 'Further Options', and if so, set the restriction
                    if th_text in ['Restriction Required', 'Further Options']:
                        restriction = div_text

                    # Check if the 'th' text is 'Take-A-Break Length' or 'Self-Exclusion Length', and if so, set the length
                    elif th_text in ['Take-A-Break Length', 'Self-Exclusion Length']:
                        length = div_text

            # Get the text content of the tags
            first_name = first_name_tag.get_text() if first_name_tag else None
            last_name = last_name_tag.get_text() if last_name_tag else None
            username = username_tag.get_text().upper() if username_tag else None

            closure_data = {
                'email_id': email_id,
                'timestamp': date_time_str,
                'Label': label_name,
                'First name': first_name,
                'Last name': last_name,
                'Username': username,
                'Restriction': restriction,
                'Length': length,
                'completed': completed_status.get(email_id, False),  # Preserve the 'completed' status
            }
            closures.append(closure_data)
    return closures

def get_deposits(app):
    creds = None
    messages_data = []
    label_ids = {}

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    # Find the IDs of the labels
    for label_name in ['DEPOSIT', 'DEPOSIT/PAYPAL']:
        for label in labels:
            if label['name'] == label_name:
                label_ids[label_name] = label['id']
                break
    # Get the current date in your local time zone
    now_local = datetime.now(timezone('Europe/London'))
    # Format the current date and the next date as strings
    date_str = now_local.strftime('%Y/%m/%d')
    next_date_str = (now_local + timedelta(days=1)).strftime('%Y/%m/%d')
    # Define the filename for today's deposits
    today_filename = f'logs/depositlogs/deposits_{now_local.strftime("%Y-%m-%d")}.json'
    # Load the existing messages from the JSON file for today's date
    if os.path.exists(today_filename):
        with open(today_filename, 'r') as f:
            existing_messages = json.load(f)
    else:
        existing_messages = []

    existing_ids = {message['ID'] for message in existing_messages}

    for label_name, label_id in label_ids.items():
        if label_id is None:
            print(f"Label '{label_name}' not found")
            continue

        page_token = None
        try:
            while True:
                results = service.users().messages().list(userId='me', labelIds=[label_id], pageToken=page_token, q=f'after:{date_str} before:{next_date_str}').execute()
                messages = results.get('messages', [])
                page_token = results.get('nextPageToken')

                if messages:
                    last_message = service.users().messages().get(userId='me', id=messages[-1]['id']).execute()
                    last_message_time = datetime.fromtimestamp(int(last_message['internalDate']) // 1000)

                for message in messages:
                    # Get the message details
                    msg = service.users().messages().get(userId='me', id=message['id']).execute()
                    payload = msg['payload']
                    # Get the message body
                    parts = payload.get('parts')
                    if parts is not None:
                        part = parts[0]
                        data = part['body']['data']
                    else:
                        # If there are no parts, get the body from the 'body' field
                        data = payload['body']['data']

                    data = data.replace("-","+").replace("_","/")
                    decoded_data = base64.b64decode(data)

                    soup = BeautifulSoup(decoded_data , "lxml")

                    # Get the email time from the Gmail API
                    email_time = datetime.fromtimestamp(int(msg['internalDate']) // 1000, tz=timezone('UTC'))

                    email_time_str = email_time.strftime('%Y-%m-%d %H:%M:%S')

                    # Parse the email based on its label and add the type, time, and ID
                    if label_name == 'DEPOSIT':
                        parsed_data = parse_card_email(soup.prettify())
                        parsed_data['Type'] = 'Card'
                    elif label_name == 'DEPOSIT/PAYPAL':
                        parsed_data = parse_paypal_email(soup.prettify())
                        parsed_data['Type'] = 'PayPal'

                    email_time_str = email_time.strftime('%Y-%m-%d %H:%M:%S')
                    parsed_data['Time'] = email_time_str
                    parsed_data['ID'] = msg['id']

                    # Only add the message to the list if its ID is not already in the JSON file
                    if msg['id'] not in existing_ids:
                        messages_data.append(parsed_data)

                if not page_token:
                    break
        except Exception as e:
            print(f"An error occurred while processing deposits: {e}")
            
    # Sort the messages by time
    messages_data.sort(key=lambda x: datetime.strptime(x['Time'], '%Y-%m-%d %H:%M:%S'))

    # Group the messages by day
    messages_by_day = defaultdict(list)
    for message in messages_data:
        date = message['Time'][:10]
        messages_by_day[date].append(message)

    # Write the messages for each day to a separate JSON file
    for date, messages in messages_by_day.items():
        filename = f'logs/depositlogs/deposits_{date}.json'

        # Read the existing messages for the day from the file, if it exists
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing_messages = json.load(f)
        else:
            existing_messages = []

        # Append the new messages to the list
        existing_messages.extend(messages)

        # Write the updated list back to the file
        with open(filename, 'w') as f:
            json.dump(existing_messages, f, indent=4)

    return messages_data

def calculate_deposit_summary():
    now_local = datetime.now(timezone('Europe/London'))
    today_filename = f'logs/depositlogs/deposits_{now_local.strftime("%Y-%m-%d")}.json'

    # Load the existing messages from the JSON file for today's date
    if os.path.exists(today_filename):
        with open(today_filename, 'r') as f:
            messages_data = json.load(f)
    else:
        messages_data = []

    total_deposits = 0
    total_sum = 0
    deposits_by_user = defaultdict(int)
    sum_by_user = defaultdict(int)

    for message in messages_data:
        user = message['Username']
        amount = float(message['Amount'].replace(',', ''))
        total_deposits += 1
        total_sum += amount
        deposits_by_user[user] += 1
        sum_by_user[user] += amount

    most_deposits_user = max(deposits_by_user, key=deposits_by_user.get) if deposits_by_user else None
    most_sum_user = max(sum_by_user, key=sum_by_user.get) if sum_by_user else None

    return {
        'total_deposits': total_deposits,
        'total_sum': total_sum,
        'most_deposits_user': most_deposits_user,
        'most_sum_user': most_sum_user,
    }

def log_deposit_summary():
    deposit_summary = calculate_deposit_summary()
    log_notification(f"Most Deposits: {deposit_summary['most_deposits_user']} Highest Total: {deposit_summary['most_sum_user']}", True)

def reprocess_deposits(app):
    creds = None
    messages_data = []
    label_ids = {}

    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Call the Gmail API
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    # Find the IDs of the labels
    for label_name in ['DEPOSIT', 'DEPOSIT/PAYPAL']:
        for label in labels:
            if label['name'] == label_name:
                print(label['name'])
                label_ids[label_name] = label['id']
                break

    # Get the current date in your local time zone
    now_local = datetime.now(timezone('Europe/London'))

    for i in range(7):
        # Calculate the date for the day to process
        day_to_process = now_local - timedelta(days=i)

        # Format the date and the next date as strings
        date_str = day_to_process.strftime('%Y/%m/%d')
        next_date_str = (day_to_process + timedelta(days=1)).strftime('%Y/%m/%d')

        # Define the filename for the day's deposits
        day_filename = f'logs/depositlogs/deposits_{day_to_process.strftime("%Y-%m-%d")}.json'

        # Reset the list of existing messages and IDs for the day
        existing_messages = []
        existing_ids = set()
        messages_data = []  # Reset the list of messages for the day

        # Load the existing messages from the JSON file for today's date
        if os.path.exists(day_filename):
            with open(day_filename, 'r') as f:
                existing_messages = json.load(f)
        else:
            existing_messages = []

        existing_ids = {message['ID'] for message in existing_messages}

        for label_name, label_id in label_ids.items():
            if label_id is None:
                print(f"Label '{label_name}' not found")
                continue

            page_token = None
            try:
                while True:
                    print(f'Label ID: {label_id}, Page token: {page_token}')
                    results = service.users().messages().list(userId='me', labelIds=[label_id], pageToken=page_token, q=f'after:{date_str} before:{next_date_str}').execute()
                    messages = results.get('messages', [])
                    page_token = results.get('nextPageToken')
                    print(f'Next page token: {page_token}')

                    if messages:
                        print(messages[-1]['id'])
                        last_message = service.users().messages().get(userId='me', id=messages[-1]['id']).execute()
                        last_message_time = datetime.fromtimestamp(int(last_message['internalDate']) // 1000)
                        print(f'Number of messages: {len(messages)}')

                    for message in messages:
                        print(f"Processing message: {message['id']}")
                        # Get the message details
                        msg = service.users().messages().get(userId='me', id=message['id']).execute()
                        payload = msg['payload']
                        # Get the message body
                        parts = payload.get('parts')
                        if parts is not None:
                            part = parts[0]
                            data = part['body']['data']
                        else:
                            # If there are no parts, get the body from the 'body' field
                            data = payload['body']['data']

                        data = data.replace("-","+").replace("_","/")
                        decoded_data = base64.b64decode(data)

                        soup = BeautifulSoup(decoded_data , "lxml")

                        # Get the email time from the Gmail API
                        email_time = datetime.fromtimestamp(int(msg['internalDate']) // 1000, tz=timezone('UTC'))
                        print(email_time)

                        email_time_str = email_time.strftime('%Y-%m-%d %H:%M:%S')

                        # Parse the email based on its label and add the type, time, and ID
                        if label_name == 'DEPOSIT':
                            parsed_data = parse_card_email(soup.prettify())
                            parsed_data['Type'] = 'Card'
                        elif label_name == 'DEPOSIT/PAYPAL':
                            parsed_data = parse_paypal_email(soup.prettify())
                            parsed_data['Type'] = 'PayPal'

                        email_time_str = email_time.strftime('%Y-%m-%d %H:%M:%S')
                        parsed_data['Time'] = email_time_str
                        parsed_data['ID'] = msg['id']

                        # Only add the message to the list if its ID is not already in the JSON file
                        if msg['id'] not in existing_ids:
                            print(f"Adding message: {msg['id']}")
                            messages_data.append(parsed_data)
                        else:
                            print(f"Skipping message: {msg['id']}")

                    if not page_token:
                        break
            except Exception as e:
                print(f"An error occurred while processing deposits: {e}")
                
        # Sort the messages by time
        messages_data.sort(key=lambda x: datetime.strptime(x['Time'], '%Y-%m-%d %H:%M:%S'))

        print(messages_data)

        # Group the messages by day
        messages_by_day = defaultdict(list)
        for message in messages_data:
            date = message['Time'][:10]
            messages_by_day[date].append(message)

        # Write the messages for each day to a separate JSON file
        for date, messages in messages_by_day.items():
            filename = f'logs/depositlogs/deposits_{date}.json'

            # Read the existing messages for the day from the file, if it exists
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    existing_messages = json.load(f)
            else:
                existing_messages = []

            # Append the new messages to the list
            existing_messages.extend(messages)

            # Write the updated list back to the file
            with open(filename, 'w') as f:  # Use 'filename' instead of 'day_filename'
                json.dump(existing_messages, f, indent=4)

    return messages_data

def parse_card_email(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    # Extract the customer ID, amount and date & time
    customer_id = re.search(r"Customer ID - {'merchantCustomerId': '(.*?)'", text).group(1)
    amount = re.search(r"Amount - (\d+\.\d+)", text).group(1)
    date_time = re.search(r"Date & Time - (.*?)\+0000", text).group(1)
    return {'Username': customer_id, 'Amount': amount, 'Time': date_time}

def parse_paypal_email(html):
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ')
    # Extract the username and amount
    username = re.search(r"Username: (.*?)\n", text).group(1)
    amount = re.search(r"Amount: (\d+\.\d+)\n", text).group(1)
    return {'Username': username, 'Amount': amount}



####################################################################################
## WRITE API DATA TO DATA.JSON
####################################################################################
def update_data_file(app):
    with file_lock:
        try:
            app.log_message(" --- Updating data file --- ")
            # Load existing data
            with open('src/data.json', 'r') as f:
                data = json.load(f)

            # Update data
            data['vip_clients'] = get_vip_clients(app)
            data['new_registrations'] = get_new_registrations(app)
            data['daily_turnover'], data['daily_profit'], data['daily_profit_percentage'], data['last_updated_time'], data['enhanced_places'] = get_reporting_data(app)
            data['oddsmonkey_selections'] = get_oddsmonkey_selections(app, 5)
            data['closures'] = get_closures(app)
            data['deposits_summary'] = calculate_deposit_summary()

            with open('src/data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            app.log_message(" --- Data file updated --- ")

        except Exception as e:
            app.log_message(f"An error occurred while updating the data file: {e}")
            log_notification(f"Processor Could not update data file.", True)



####################################################################################
## THREADING FUNCTIONS
####################################################################################
def run_get_data(app):
    get_data_thread = threading.Thread(target=update_data_file, args=(app,))
    get_data_thread.start()

def run_update_todays_oddsmonkey_selections():
    update_todays_oddsmonkey_selections_thread = threading.Thread(target=update_todays_oddsmonkey_selections)
    update_todays_oddsmonkey_selections_thread.start()

def run_get_deposit_data(app):
    global last_run_time
    current_time = datetime.now()
    if last_run_time is not None and (current_time - last_run_time).total_seconds() < 120:
        print("Function just ran")
        return
    
    last_run_time = current_time
    get_deposit_data_thread = threading.Thread(target=get_deposits, args=(app,))
    get_deposit_data_thread.start()

def run_find_rg_issues():
    find_rg_issues_thread = threading.Thread(target=rg_report_notification)
    find_rg_issues_thread.start()

def run_staff_report_notification():
    staff_report_thread = threading.Thread(target=staff_report_notification)
    staff_report_thread.start()

def run_activity_report_notification():
    activity_report_thread = threading.Thread(target=activity_report_notification)
    activity_report_thread.start()


def clear_processed():
    global processed_races, processed_closures, bet_count_1000, bet_count_500, knockback_count_250, notified_users
    notified_users.clear()
    bet_count_500 = False
    bet_count_1000 = False
    knockback_count_250 = False
    processed_races.clear()
    processed_closures.clear()

    # Clear the notifications.json file
    file_lock = fasteners.InterProcessLock('notifications.lock')
    with file_lock:
        with open('notifications.json', 'w') as f:
            json.dump([], f)



####################################################################################
## GENERATE TKINTER UI
####################################################################################
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Bet Processor v4.0')
        self.geometry('820x300')
        
        self.iconbitmap('src/splash.ico')
        self.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
        ttk.Style().theme_use('forest-light')
        style = ttk.Style(self)

        style.configure('TButton', padding=(5, 5))

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=2)  
        self.grid_rowconfigure(1, weight=1) 
        self.grid_rowconfigure(2, weight=1)  
        self.grid_rowconfigure(3, weight=1)  
        self.grid_rowconfigure(4, weight=1)  
        self.grid_rowconfigure(5, weight=1)  

        self.text_area = scrolledtext.ScrolledText(self, undo=True)
        self.text_area['font'] = ('helvetica', '12')
        self.text_area.grid(row=0, column=0, rowspan=5, sticky='nsew')

        image = Image.open('src/splash.ico')
        image = image.resize((100, 100)) 
        self.logo = ImageTk.PhotoImage(image)

        self.logo_label = Label(self, image=self.logo)
        self.logo_label.grid(row=0, column=1) 

        self.reprocess_button = ttk.Button(self, text="Reprocess Bets", command=self.reprocess, style='TButton', width=20)
        self.reprocess_button.grid(row=2, column=1, padx=5, pady=5, sticky='nsew')  # sticky='nsew' to fill the cell
        
        self.reprocess_deposits_button = ttk.Button(self, text="Reprocess Deposits", command=self.reprocess_deposits, style='TButton', width=15)
        self.reprocess_deposits_button.grid(row=3, column=1, padx=5, pady=5, sticky='nsew')  # sticky='nsew' to fill the cell

        self.set_path_button = ttk.Button(self, text="BWW Folder", command=self.set_bet_path, style='TButton', width=20)
        self.set_path_button.grid(row=4, column=1, padx=5, pady=5, sticky='nsew')  # sticky='nsew' to fill the cell

        self.bind('<Destroy>', self.on_destroy)
    
    def set_bet_path(self):
        global path
        new_folder_path = filedialog.askdirectory()
        if new_folder_path:
            path = new_folder_path

    def reprocess(self):
        reprocess_file(self)
        process_thread = threading.Thread(target=process_existing_bets, args=(path, self))
        process_thread.start()

    def reprocess_deposits(self):
        reprocess_deposits(self)
        process_deposits_thread = threading.Thread(target=reprocess_deposits, args=(path, self))
        process_deposits_thread.start()

    def log_message(self, message):
        current_time = datetime.now().strftime('%H:%M:%S')  # Get the current time
        self.text_area.insert(tk.END, f'{current_time}: {message}\n')  # Add the time to the message

        self.text_area.see(tk.END)

        max_lines = 1500
        lines = self.text_area.get('1.0', tk.END).splitlines()
        if len(lines) > max_lines:
            self.text_area.delete('1.0', f'{len(lines) - max_lines + 1}.0')

    def on_destroy(self, event):
        self.stop_main_loop = True



####################################################################################
## FILE HANDLER FOR INCOMING BETS USING WATCHDOG OBSERVER
####################################################################################
class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        global last_processed_time
        if not os.path.isdir(event.src_path):
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    process_file(event.src_path)
                    last_processed_time = datetime.now()  
                    break 
                except Exception as e:
                    print(f"An error occurred while processing the file {event.src_path}: {e}")
        else: 
            print(f"Failed to process the file {event.src_path} after {max_retries} attempts.")



####################################################################################
## MAIN FUNCTIONS CONTAINING MAIN LOOP
####################################################################################
def main(app):
    global path, last_processed_time
    event_handler = FileHandler()
    observer = None
    observer_started = False
    
    app.log_message('Bet Processor - import, parse and store daily bet data.\n')
    log_notification("Processor Started")
    run_get_data(app)
    run_get_deposit_data(app)
    run_update_todays_oddsmonkey_selections()
    check_closures_and_race_times()
    fetch_and_print_new_events()
    find_stale_antepost_events()

    schedule.every(2).minutes.do(run_get_data, app)

    schedule.every(10).minutes.do(run_get_deposit_data, app)
    schedule.every(15).minutes.do(run_update_todays_oddsmonkey_selections)

    schedule.every(50).seconds.do(check_closures_and_race_times)
    schedule.every(10).minutes.do(fetch_and_print_new_events)
    schedule.every(3).hours.do(run_find_rg_issues)
    schedule.every(1).minute.do(run_staff_report_notification)
    schedule.every(1).minute.do(run_activity_report_notification)

    schedule.every().day.at("23:57").do(run_get_deposit_data, app)
    schedule.every().day.at("17:00").do(log_deposit_summary)
    schedule.every().day.at("13:00").do(find_stale_antepost_events)
    schedule.every().day.at("00:05").do(clear_processed)

    while not app.stop_main_loop:
        # Run pending tasks
        schedule.run_pending()

        if not os.path.exists(path):
            print(f"Error: The path {path} does not exist.")
            set_bet_folder_path() 
            if not os.path.exists(path):
                continue  
        if not observer_started or datetime.now() - last_processed_time > timedelta(minutes=3):
            if observer_started:
                observer.stop()
                observer.join()
            observer = Observer()
            observer.schedule(event_handler, path, recursive=False)
            observer.start()
            observer_started = True
            app.log_message('Watchdog observer watching folder ' + path + '\n' )
            last_processed_time = datetime.now()

        try:
            time.sleep(1) 
        except Exception as e:
            app.log_message(f"An error occurred: {e}")
            app.reprocess() 
            time.sleep(10)
        except KeyboardInterrupt:
            pass
    if observer is not None:
        observer.stop()
        log_notification("Processor Stopped")
        print("OBSERVER STOPPED!")  
        observer.join()

if __name__ == "__main__":
    app = Application()
    app.stop_main_loop = False
    app.main_loop = threading.Thread(target=main, args=(app,))
    app.main_loop.start()
    app.mainloop()