import os
import re
import json
import schedule
import time
import threading
import gspread
import requests
import base64
import email
import tkinter as tk
from tkinter import ttk, filedialog, Label
from PIL import ImageTk, Image
from datetime import datetime, timedelta, date
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
from tkinter import scrolledtext

last_processed_time = datetime.now()

with open('src/creds.json') as f:
    creds = json.load(f)

pipedrive_api_token = creds['pipedrive_api_key']

scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds, scope)
gc = gspread.authorize(credentials)

path = 'F:\BWW\Export'
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

def set_bet_folder_path():
    global path
    new_folder_path = filedialog.askdirectory()
    if new_folder_path:
        path = new_folder_path

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
    app.log_message('\nBet processing complete.\nWaiting for new files...\n')

def reprocess_file(app):
    print("Reprocessing file")
    date = datetime.now().strftime('%Y-%m-%d')

    filename = f'database/{date}-wager_database.json'

    if os.path.exists(filename):
        os.remove(filename)
        app.log_message('Existing database deleted. Will begin to process todays bets....\n\n')
    else:
        app.log_message('No existing database found. Will begin processing todays bets...\n\n')

def get_vip_clients(app):
    spreadsheet = gc.open('Management Tool')
    worksheet = spreadsheet.get_worksheet(4)
    data = worksheet.get_all_values()

    vip_clients = [row[0] for row in data if row[0]]
    
    app.log_message("VIP Clients List Updated\n")

    return vip_clients

def get_new_registrations(app):
    response = requests.get(f'https://api.pipedrive.com/v1/persons?api_token={pipedrive_api_token}&filter_id=55')

    if response.status_code == 200:
        data = response.json()

        persons = data.get('data', [])
        newreg_clients = [person.get('c1f84d7067cae06931128f22af744701a07b29c6', '') for person in persons]
    
    app.log_message("New Registrations List Updated\n")

    return newreg_clients

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
    
    app.log_message("Reporting data retrieved from reporting " + current_month + "\n")

    return daily_turnover, daily_profit, daily_profit_percentage, last_updated_time

def get_racecards(app):
    current_date = datetime.now().strftime('%Y-%m-%d')
    app.log_message("Getting Racecards from Racing Post")

    headers = {
        "X-RapidAPI-Key": "22f72e5c1amsha91beaa0531671ep173453jsnad4cb1bce081",
    }

    # Greyhound data
    url = "https://greyhound-racing-uk.p.rapidapi.com/racecards"
    headers["X-RapidAPI-Host"] = "greyhound-racing-uk.p.rapidapi.com"
    response = requests.get(url, headers=headers, params={"date": current_date})
    greyhound_data = response.json()

    greyhound_races = []
    for race in greyhound_data:
        time_only = race['date'].split(' ')[1] 
        greyhound_races.append({
            'track': race['dogTrack'],
            'time': time_only,
        })

    # Horse racing data
    url = "https://horse-racing.p.rapidapi.com/racecards"
    headers["X-RapidAPI-Host"] = "horse-racing.p.rapidapi.com"
    response = requests.get(url, headers=headers, params={"date": current_date})
    horse_racing_data = response.json()

    horse_races = []
    for race in horse_racing_data:
        time_with_seconds = race['date'].split(' ')[1] 
        time_only = ':'.join(time_with_seconds.split(':')[:2])  
        horse_races.append({
            'course': race['course'],
            'time': time_only,
        })

    app.log_message("Todays Racecards retrieved\n")

    return greyhound_races, horse_races

def update_racecards():
    greyhound_races, horse_races = get_racecards(app)

    with open('src/data.json', 'r+') as f:
        data = json.load(f)
        data['greyhound_racecards'] = greyhound_races
        data['horse_racecards'] = horse_races
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()

def get_oddsmonkey_selections(app):
    creds = None

    app.log_message("Getting Recent Oddsmonkey Selections")

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
    # Rest of your code
        # Get the messages in the 'Oddsmonkey' label
    # Get the list of all labels
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

    # Get the messages in the 'Oddsmonkey' label
    try:
        results = service.users().messages().list(userId='me', labelIds=[oddsmonkey_label_id]).execute()
        messages = results.get('messages', [])
    except BaseException as e:  # Catch all exceptions
        print("Error retrieving messages:", e)
        return

    # Initialize an empty dictionary to store all selections
    all_selections = {}

    # Get the first three messages
    for message in messages[:6]:
        try:
            # Get the message details
            msg = service.users().messages().get(userId='me', id=message['id']).execute()

            # Get the message data
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
            body = soup.body()

            # Extract selections from this message and add them to the all_selections dictionary
            selections = extract_oddsmonkey_selections(str(body))
            all_selections.update(selections)
        except Exception as e:
            print("Error processing message:", e)
            continue

    app.log_message("Recent Oddsmonkey Selections Updated\n")
    return all_selections
    
def get_todays_oddsmonkey_selections(app):
    creds = None

    app.log_message("Getting Todays Oddsmonkey Selections")
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'src/gmailcreds.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

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

    today = date.today().strftime('%Y/%m/%d')

    results = service.users().messages().list(userId='me', labelIds=[oddsmonkey_label_id], q=f'after:{today}').execute()

    messages = results.get('messages', [])
    length = len(messages)
    print(length)

    all_selections = {}

    for message in messages[:length]:
        try:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            print(f"Processing message with ID {message['id']}")

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
            #body = soup.body()
            table = soup.table

            #td_tags = soup.find_all('td', style="padding-left: 7px;padding-right: 7px;")

            #for td in td_tags:
                #print(td.text)  # This will print the text within each 'td' tag


            #print(f"Body for message {message['id']}: {table}")
            #print(f"Body for message {message['id']}: {body}")



            try:
                selections = extract_oddsmonkey_selections(str(table))
                all_selections.update(selections)
            except Exception as e:
                print(f"An error occurred while extracting selections: {e}")

        except Exception as e:
            print(e)

    app.log_message("Todays Oddsmonkey Selections Updated\n")
    return all_selections

def extract_oddsmonkey_selections(body):
    selections = {}
    pattern = r'<img src="https://azcdn.oddsmonkey.com/om3/images/sports/24x24/.*?.png" style="border-width:0px;"/></td><td style="padding-left: 7px;padding-right: 7px;">(.*?)</td>\s*<td style="padding-left: 7px;padding-right: 7px;">(.*?)</td>.*?<td style="padding-left: 7px;padding-right: 7px;">(\d+\.\d+)</td></tr>'

    try:
        matches = re.findall(pattern, body, re.DOTALL)

        if not matches:
            return selections

        for match in matches:
            event = re.sub(r'</td><td\s*style="padding-left: 7px;padding-right: 7px;">', '', match[0]).strip()
            selection = match[1].strip()
            lay_odds = match[2].strip()
            selections[event] = selection, lay_odds

    except Exception as e:
        print(f"An error occurred in extract_oddsmonkey_selections: {e}")

    return selections

def update_todays_oddsmonkey_selections():
    todays_oddsmonkey_selections = get_todays_oddsmonkey_selections(app)

    with open('src/data.json', 'r+') as f:
        data = json.load(f)
        data['todays_oddsmonkey_selections'] = todays_oddsmonkey_selections
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()

def run_update_todays_oddsmonkey_selections():
    update_todays_oddsmonkey_selections_thread = threading.Thread(target=update_todays_oddsmonkey_selections)
    update_todays_oddsmonkey_selections_thread.start()

def update_data_file(app):
    vip_clients = get_vip_clients(app)
    newreg_clients = get_new_registrations(app)
    daily_turnover, daily_profit, daily_profit_percentage, last_updated_time = get_reporting_data(app)
    oddsmonkey_selections = get_oddsmonkey_selections(app)

    with open('src/data.json', 'r+') as f:
        data = json.load(f)
        data.update({
            'vip_clients': vip_clients,
            'new_registrations': newreg_clients,
            'daily_turnover': daily_turnover,
            'daily_profit': daily_profit,
            'daily_profit_percentage': daily_profit_percentage,
            'last_updated_time': last_updated_time,
            'oddsmonkey_selections': oddsmonkey_selections,
        })
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()
    
    app.log_message("Data file updated")

def run_get_data(app):
    get_data_thread = threading.Thread(target=update_data_file, args=(app,))
    get_data_thread.start()

def run_get_oddsmonkey_selections(app):
    thread = threading.Thread(target=get_oddsmonkey_selections, args=(app,))
    thread.start()

def run_update_todays_oddsmonkey_selections():
    update_todays_oddsmonkey_selections_thread = threading.Thread(target=update_todays_oddsmonkey_selections)
    update_todays_oddsmonkey_selections_thread.start()

def run_update_racecards():
    update_racecards_thread = threading.Thread(target=update_racecards)
    update_racecards_thread.start()
        
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Bet Processor v4.0')
        self.geometry('750x300')
        
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
        self.text_area.grid(row=0, column=0, rowspan=4, sticky='nsew')

        image = Image.open('src/splash.ico')
        image = image.resize((100, 100)) 
        self.logo = ImageTk.PhotoImage(image)

        self.logo_label = Label(self, image=self.logo)
        self.logo_label.grid(row=0, column=1) 

        self.reprocess_button = ttk.Button(self, text="Reprocess", command=self.reprocess, style='TButton', width=15)
        self.reprocess_button.grid(row=2, column=1, padx=5, pady=5, sticky='nsew')  # sticky='nsew' to fill the cell

        self.set_path_button = ttk.Button(self, text="Set Path", command=self.set_bet_path, style='TButton', width=15)
        self.set_path_button.grid(row=3, column=1, padx=5, pady=5, sticky='nsew')  # sticky='nsew' to fill the cell


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

    def log_message(self, message):
        self.text_area.insert(tk.END, message + '\n')

        self.text_area.see(tk.END)

        max_lines = 1500
        lines = self.text_area.get('1.0', tk.END).splitlines()
        if len(lines) > max_lines:
            self.text_area.delete('1.0', f'{len(lines) - max_lines + 1}.0')

    def on_destroy(self, event):
        self.stop_main_loop = True

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

def main(app):
    global path, last_processed_time
    event_handler = FileHandler()
    observer = None
    observer_started = False
    
    app.log_message('Bet Processor - import, parse and store daily bet data.\n')
    run_get_data(app)
    run_update_racecards()
    run_update_todays_oddsmonkey_selections()

    schedule.every(2).minutes.do(run_get_data, app)
    schedule.every(6).hours.do(run_update_racecards)
    schedule.every(1).hours.do(run_update_todays_oddsmonkey_selections)

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
            app.log_message('\nWatchdog observer watching folder ' + path + '\n' )
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