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
from collections import defaultdict
from itertools import groupby
from operator import itemgetter
from bs4 import BeautifulSoup
from tkinter import scrolledtext



####################################################################################
## INITIALIZE GLOBAL VARIABLES & API CREDENTIALS
####################################################################################
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
def parse_file(file_path, app):
    with open(file_path, 'r') as file:
        bet_text = file.read()
        bet_text_lower = bet_text.lower()
        is_sms = 'sms' in bet_text_lower
        is_bet = 'website' in bet_text_lower
        is_wageralert = 'knockback' in bet_text_lower

        if is_wageralert:
            customer_ref, knockback_id, time, details = parse_wageralert_details(bet_text)
            unique_knockback_id = f"{knockback_id}-{time}"
            bet_info = {
                'time': time,
                'id': unique_knockback_id,
                'type': 'WAGER KNOCKBACK',
                'customer_ref': customer_ref,
                'details': details,
            }
            print('Knockback Processed ' + unique_knockback_id)
            app.log_message(f'Knockback Processed {unique_knockback_id}, {customer_ref}, {time}')
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
                }
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
    details_pattern = r"Knockback Details:([\s\S]*?)\n\nCustomer's Bets Details:"
    time_pattern = r'- Date: \d+ [A-Za-z]+ \d+\n - Time: (\d+:\d+:\d+)'
    bets_details_pattern = r"Customer's Bets Details:([\s\S]*?)\n\nCustomer's Wagers Details:"
    wagers_details_pattern = r"Customer's Wagers Details:([\s\S]*?)\n\nCustomer's services reference no:"

    customer_ref_match = re.search(customer_ref_pattern, content)
    customer_ref = customer_ref_match.group(1) if customer_ref_match else None

    knockback_excluded_keys = ['- Wager Type', '- Liability Failure Code', '- Wager Number (if available)', '- Error Code']
    knockback_id, knockback_details = extract_details(content, details_pattern, knockback_excluded_keys)

    time_match = re.search(time_pattern, content)
    time = time_match.group(1) if time_match else None

    bets_excluded_keys = ['- Event File', '- Event Group', '- Event Index', '- Selection Index']
    _, bets_details = extract_details(content, bets_details_pattern, bets_excluded_keys)

    wagers_excluded_keys = []
    _, wagers_details = extract_details(content, wagers_details_pattern, wagers_excluded_keys)

    details = {**knockback_details, **bets_details, **wagers_details}
    details = {key.replace('-', '').strip(): value for key, value in details.items()}

    return customer_ref, knockback_id, time, details

def extract_details(content, pattern, excluded_keys):
    match = re.search(pattern, content)
    details = {}
    knockback_id = None
    if match:
        content = match.group(1).strip().replace('\n', ' ')
        lines = content.split('- ')
        knockback_id = lines.pop(0)
        for line in lines:
            parts = line.split(':')
            if len(parts) >= 2:
                key = '- ' + parts[0].strip()
                value = ':'.join(parts[1:]).strip()
                if key not in excluded_keys:
                    details[key] = value
    return knockback_id, details



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
    last_updated_time = response['modifiedTime']
    last_updated_datetime = datetime.strptime(last_updated_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    last_updated_time = last_updated_datetime.strftime("%H:%M:%S")
    
    return daily_turnover, daily_profit, daily_profit_percentage, last_updated_time



####################################################################################
## GET NEW REGISTRATIONS FROM PIPEDRIVE API
####################################################################################
def get_new_registrations(app):
    response = requests.get(f'https://api.pipedrive.com/v1/persons?api_token={pipedrive_api_token}&filter_id=55')

    if response.status_code == 200:
        data = response.json()

        persons = data.get('data', [])
        newreg_clients = [person.get('c1f84d7067cae06931128f22af744701a07b29c6', '') for person in persons]
    
    return newreg_clients



####################################################################################
## GET DAILY RACECARDS FOR HORSES & GREYHOUNDS FROM RAPIDAPI
####################################################################################
def get_racecards(app):
    current_date = datetime.now().strftime('%Y-%m-%d')

    with open('src/creds.json') as f:
        creds = json.load(f)

    # Retrieve the RapidAPI key
    rapidapi_key = creds['X-RapidAPI-Key']

    headers = {
        "X-RapidAPI-Key": rapidapi_key,
    }

    # Greyhound data
    url = "https://greyhound-racing-uk.p.rapidapi.com/racecards"
    headers["X-RapidAPI-Host"] = "greyhound-racing-uk.p.rapidapi.com"
    try:
        response = requests.get(url, headers=headers, params={"date": current_date})
        response.raise_for_status()
        greyhound_data = response.json()

        greyhound_races = []
        for race in greyhound_data:
            time_only = race['date'].split(' ')[1] 
            greyhound_races.append({
                'track': race['dogTrack'],
                'time': time_only,
            })

    except requests.exceptions.RequestException as e:
        app.log_message(f"Error retrieving greyhound racecards: {e}")
        greyhound_races = []

    # Horse racing data
    url = "https://horse-racing.p.rapidapi.com/racecards"
    headers["X-RapidAPI-Host"] = "horse-racing.p.rapidapi.com"
    try:
        response = requests.get(url, headers=headers, params={"date": current_date})
        response.raise_for_status()
        horse_racing_data = response.json()

        horse_races = []
        for race in horse_racing_data:
            time_with_seconds = race['date'].split(' ')[1] 
            time_only = ':'.join(time_with_seconds.split(':')[:2])  
            horse_races.append({
                'course': race['course'],
                'time': time_only,
            })

    except requests.exceptions.RequestException as e:
        app.log_message(f"Error retrieving horse racing racecards: {e}")
        horse_races = []
    print(len(greyhound_races), len(horse_races))
    return greyhound_races, horse_races

def update_racecards():
    with file_lock:
        greyhound_races, horse_races = get_racecards(app)

        with open('src/data.json', 'r+') as f:
            data = json.load(f)
            data['greyhound_racecards'] = greyhound_races
            data['horse_racecards'] = horse_races
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()



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
    # Find the ID of the 'Oddsmonkey' label
    oddsmonkey_label_id = None
    for label in labels:
        if label['name'] == 'ODDSMONKEY':
            oddsmonkey_label_id = label['id']
            break

    if oddsmonkey_label_id is None:
        print("Label 'Oddsmonkey' not found")
        return

    # Get the messages in the 'Oddsmonkey' label from today
    results = service.users().messages().list(userId='me', labelIds=[oddsmonkey_label_id], q=query).execute()

    messages = results.get('messages', [])
    length = len(messages)

    # Initialize an empty dictionary to store all selections
    all_selections = {}

    for message in messages if num_messages is None else messages[:num_messages]:
        try:
            # Get the message details
            msg = service.users().messages().get(userId='me', id=message['id']).execute()

            payload = msg['payload']
            headers = payload['headers']

            for d in headers:
                if d['name'] == 'Subject':
                    subject = d['value']
                if d['name'] == 'From':
                    sender = d['value']

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
            
            # Find all 'td' tags with the specific style attribute
            td_tags = soup.find_all('td', style="padding-left: 7px;padding-right: 7px;")

            # Extract selections from this message and add them to the all_selections dictionary
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
            print("user", username)

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
    today_filename = f'depositlogs/deposits_{now_local.strftime("%Y-%m-%d")}.json'

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
                    else:
                        print(f"Skipping message: {msg['id']}")

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
        filename = f'depositlogs/deposits_{date}.json'

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
    today_filename = f'depositlogs/deposits_{now_local.strftime("%Y-%m-%d")}.json'

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
        day_filename = f'depositlogs/deposits_{day_to_process.strftime("%Y-%m-%d")}.json'

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
            filename = f'depositlogs/deposits_{date}.json'

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
            print("vip clients")
            data['new_registrations'] = get_new_registrations(app)
            print("new registrations")
            data['daily_turnover'], data['daily_profit'], data['daily_profit_percentage'], data['last_updated_time'] = get_reporting_data(app)
            print("reporting data")
            data['oddsmonkey_selections'] = get_oddsmonkey_selections(app, 5)
            print("oddsmonkey selections")
            data['closures'] = get_closures(app)
            print("closures")
            data['deposits_summary'] = calculate_deposit_summary()
            print("deposits summary")

            # Write updated data back to file
            with open('src/data.json', 'w') as f:
                json.dump(data, f, indent=4)
            
            app.log_message(" --- Data file updated --- ")

        except Exception as e:
            app.log_message(f"An error occurred while updating the data file: {e}")



####################################################################################
## THREADING FUNCTIONS
####################################################################################
def run_get_data(app):
    get_data_thread = threading.Thread(target=update_data_file, args=(app,))
    get_data_thread.start()

def run_update_todays_oddsmonkey_selections():
    update_todays_oddsmonkey_selections_thread = threading.Thread(target=update_todays_oddsmonkey_selections)
    update_todays_oddsmonkey_selections_thread.start()

def run_update_racecards():
    update_racecards_thread = threading.Thread(target=update_racecards)
    update_racecards_thread.start()

def run_get_deposit_data(app):
    global last_run_time
    current_time = datetime.now()
    if last_run_time is not None and (current_time - last_run_time).total_seconds() < 120:
        print("Function just ran")
        return
    
    last_run_time = current_time
    get_deposit_data_thread = threading.Thread(target=get_deposits, args=(app,))
    get_deposit_data_thread.start()



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

def remove_duplicates_and_misplaced():
    filenames = ['depositlogs/deposits_2024-04-23.json', 'depositlogs/deposits_2024-04-24.json']
    all_deposits = []
    unique_ids = set()

    for filename in filenames:
        with open(filename, 'r') as f:
            deposits = json.load(f)
            for deposit in deposits:
                deposit_date = datetime.strptime(deposit['Time'], '%Y-%m-%d %H:%M:%S').date()
                file_date = datetime.strptime(filename.split('_')[-1].split('.')[0], '%Y-%m-%d').date()
                if deposit['ID'] not in unique_ids and deposit_date == file_date:
                    unique_ids.add(deposit['ID'])
                    all_deposits.append(deposit)

    for filename in filenames:
        with open(filename, 'w') as f:
            file_date = datetime.strptime(filename.split('_')[-1].split('.')[0], '%Y-%m-%d').date()
            json.dump([deposit for deposit in all_deposits if datetime.strptime(deposit['Time'], '%Y-%m-%d %H:%M:%S').date() == file_date], f, indent=4)


####################################################################################
## MAIN FUNCTIONS CONTAINING MAIN LOOP
####################################################################################
def main(app):
    global path, last_processed_time
    event_handler = FileHandler()
    observer = None
    observer_started = False
    
    app.log_message('Bet Processor - import, parse and store daily bet data.\n')
    #remove_duplicates_and_misplaced()
    #reprocess_deposits(app)
    run_get_data(app)
    run_update_racecards()
    run_update_todays_oddsmonkey_selections()
    run_get_deposit_data(app)

    schedule.every(2).minutes.do(run_get_data, app)
    schedule.every(10).minutes.do(run_get_deposit_data, app)
    schedule.every(6).hours.do(run_update_racecards)
    schedule.every(15).minutes.do(run_update_todays_oddsmonkey_selections)
    schedule.every().day.at("11:57").do(run_get_deposit_data, app)

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
        print("OBSERVER STOPPED!")  
        observer.join()

if __name__ == "__main__":
    app = Application()
    app.stop_main_loop = False
    app.main_loop = threading.Thread(target=main, args=(app,))
    app.main_loop.start()
    app.mainloop()