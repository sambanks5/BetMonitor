import os
import time
import sqlite3
import json
import re
import requests
from utils import get_db_connection
from config import LOCK_FILE_PATH, get_last_processed_time, set_last_processed_time, get_path, set_path 
from datetime import datetime, timedelta
from watchdog.events import FileSystemEventHandler
from tkinter import filedialog

from dotenv import load_dotenv
load_dotenv()

class FileHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def on_created(self, event):
        file_path = os.path.normpath(event.src_path)
        
        if not os.path.isdir(file_path):
            max_retries = 6  
            for attempt in range(max_retries):
                print("Loading database")
                if os.access(file_path, os.R_OK):
                    send_to_api(file_path, datetime.fromtimestamp(os.path.getctime(file_path)))

                    process_file(file_path, self.app)
                    set_last_processed_time(datetime.now())
                    break
                else:
                    raise PermissionError(f"Permission denied: '{file_path}'")
            else:
                print(f"Failed to process the file {file_path} after {max_retries} attempts.")
        else:
            print(f"Directory created: {file_path}, skipping processing.")

def send_to_api(file_path, file_creation_time):
    with open(file_path, 'r', encoding='latin-1') as file:
        bet_text = file.read()
    headers = {
        'Authorization': f'Token {os.getenv("API_TOKEN")}',
        'Content-Type': 'application/json'
    }
    data = {
        'wager_text': bet_text,
        'file_timestamp': file_creation_time.isoformat()
    }
    
    response = requests.post(os.getenv("API_URL"), json=data, headers=headers)
    
    if response.status_code in (200, 201):
        print(f"Successfully sent bet to API: {os.path.basename(file_path)}")
        file.close()
    else:
        error_msg = response.text
        raise Exception(f"API returned error {response.status_code}: {error_msg}")

def parse_file(file_path, app):
    try:
        creation_time = os.path.getctime(file_path)
        creation_date_str = datetime.fromtimestamp(creation_time).strftime('%d/%m/%Y')
    except Exception as e:
        print(f"Error getting file creation date: {e}")
        creation_date_str = datetime.today().strftime('%d/%m/%Y')

    with open(file_path, 'r', encoding='latin-1') as file:
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
                'date': creation_date_str
            }
            print('Knockback Processed ' + unique_knockback_id)
            app.log_message(f"Knockback Processed {unique_knockback_id}, {details['Customer Ref']}, {details['Time']}")
            return bet_info

        elif is_sms:
            creation_time_str = datetime.fromtimestamp(creation_time).strftime('%H:%M:%S')
            wager_number, customer_reference, _, sms_wager_text = parse_sms_details(bet_text)
            
            bet_info = {
                'time': creation_time_str,
                'id': wager_number,
                'type': 'SMS WAGER',
                'customer_ref': customer_reference,
                'details': sms_wager_text,
                'date': creation_date_str
            }
            print('SMS Processed ' + wager_number)
            app.log_message(f'SMS Processed {wager_number}, {customer_reference}')
            return bet_info

        elif is_bet:
            bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type = parse_bet_details(bet_text)
            print(bet_no, customer_reference)
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
                'date': creation_date_str
            }
            print('Bet Processed ' + bet_no)
            app.log_message(f'Bet Processed {bet_no}, {customer_reference}, {timestamp}')
            return bet_info
        
    print('File not processed ' + file_path)
    return {}

def calculate_date_range(days_back):
    end_date = datetime.now()
    if days_back == 1:
        start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = end_date - timedelta(days=days_back - 1) 
    
    return start_date, end_date

def remove_existing_records(database, start_date, end_date):
    cursor = database.cursor()
    # Convert date strings to dd/mm/yyyy format for the query
    start_date_str = start_date.strftime('%d/%m/%Y')
    end_date_str = end_date.strftime('%d/%m/%Y')
    
    print(f"Deleting records between {start_date_str} and {end_date_str}")
    
    cursor.execute("""
        DELETE FROM database 
        WHERE strftime('%Y-%m-%d', substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2))
        BETWEEN ? AND ?
    """, (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
    
    database.commit()
    print(f"Deleted {cursor.rowcount} records")

def reprocess_bets(days_back, bet_path, app):
    start_date, end_date = calculate_date_range(days_back)
    print(f"Processing bets from {start_date} to {end_date}")
    database = get_db_connection.load_database()

    remove_existing_records(database, start_date, end_date)

    # Reprocess files in the bet_path directory (current day files)
    failed_files = []
    for bet_file in os.listdir(bet_path):
        if bet_file.endswith('.bww'):
            file_path = os.path.join(bet_path, bet_file)
            try:
                creation_time = os.path.getctime(file_path)
                creation_date = datetime.fromtimestamp(creation_time)
                if start_date <= creation_date <= end_date:
                    bet = parse_file(file_path, app)
                    add_bet(database, bet, app)
                else:
                    print(f"Skipping file {file_path} as it is outside the date range.")
            except Exception as e:
                print(f"Failed to process file {file_path}: {e}")
                failed_files.append(file_path)

    # Only check the archive directory if the date range is more than 1 day
    if days_back > 1:
        archive_directory = os.path.join(bet_path, 'archive')
        if not os.path.exists(archive_directory):
            app.log_message(f"Archive directory not found: {archive_directory}")
            return

        # Get the list of folders and sort them by date (newest to oldest)
        folders = sorted(os.listdir(archive_directory), reverse=True)

        # Only check the latest two folders
        folders_to_check = folders[:2]

        for folder in folders_to_check:
            folder_path = os.path.join(archive_directory, folder)
            if os.path.isdir(folder_path):
                for bet_file in os.listdir(folder_path):
                    if bet_file.endswith('.bww'):
                        file_path = os.path.join(folder_path, bet_file)
                        try:
                            creation_time = os.path.getctime(file_path)
                            creation_date = datetime.fromtimestamp(creation_time)
                            if start_date <= creation_date <= end_date:
                                bet = parse_file(file_path, app)
                                add_bet(database, bet, app)
                            else:
                                print(f"Skipping file {file_path} as it is outside the date range.")
                                app.log_message(f"Skipping file {file_path} as it is outside the date range.")
                        except Exception as e:
                            print(f"Failed to process file {file_path}: {e}")
                            failed_files.append(file_path)

    if failed_files:
        app.log_message(f"Failed to process the following files: {', '.join(failed_files)}")

    app.log_message('Bet reprocessing complete.')
    database.close()

def process_file(file_path, app):
    conn = get_db_connection.load_database()
    bet_data = parse_file(file_path, app)
    add_bet(conn, bet_data, app)
    conn.close()

def add_bet(conn, bet, app, retries=5, delay=1):
    print("Adding a bet to the database")
    
    with open(LOCK_FILE_PATH, 'w') as lock_file:
        lock_file.write('locked')

    cursor = conn.cursor()
    
    for attempt in range(retries):
        try:
            if bet['type'] == 'SMS WAGER':
                cursor.execute('''
                    INSERT INTO database (id, time, type, customer_ref, text_request, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (bet['id'], bet['time'], bet['type'], bet['customer_ref'], json.dumps(bet['details']), bet['date']))
            elif bet['type'] == 'WAGER KNOCKBACK':
                details = bet['details']
                selections = json.dumps(details.get('Selections', []))
                requested_stake = float(details['Total Stake'].replace('£', '').replace('€', '').replace(',', ''))
                cursor.execute('''
                    INSERT INTO database (id, time, type, customer_ref, error_message, requested_type, requested_stake, selections, date, sports)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (bet['id'], bet['time'], bet['type'], details['Customer Ref'], details['Error Message'], details['Wager Name'], requested_stake, selections, bet['date'], json.dumps(bet['Sport'])))
            elif bet['type'] == 'BET':
                details = bet['details']
                selections = json.dumps(details['selections'])
                unit_stake = float(details['unit_stake'].replace('£', '').replace('€', '').replace(',', ''))
                total_stake = float(details['payment'].replace('£', '').replace('€', '').replace(',', ''))
                cursor.execute('''
                    INSERT INTO database (id, time, type, customer_ref, selections, risk_category, bet_details, unit_stake, total_stake, bet_type, date, sports)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (bet['id'], bet['time'], bet['type'], bet['customer_ref'], selections, details['risk_category'], details['bet_details'], unit_stake, total_stake, details['bet_type'], bet['date'], json.dumps(bet['Sport'])))
            conn.commit()
            break
        except sqlite3.IntegrityError:
            app.log_message(f'Bet already in database {bet["id"]}, {bet["customer_ref"]}! Skipping...\n')
            break 
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                print(f"Database is locked, retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"SQLite error: {e}")
                app.log_message(f"SQLite error: {e} while processing bet {bet['id']}, {bet['customer_ref']}!\n")
                break 
        except sqlite3.Error as e:
            print(f"SQLite error: {e}")
            app.log_message(f"SQLite error: {e} while processing bet {bet['id']}, {bet['customer_ref']}!\n")
            break 
        finally:
            if os.path.exists(LOCK_FILE_PATH):
                os.remove(LOCK_FILE_PATH)

def identify_sport(selection):
    if isinstance(selection, (list, tuple)):
        if all(isinstance(sel, (list, tuple)) for sel in selection):
            for sel in selection:
                if len(sel) > 0:
                    selection_str = sel[0]
                    if 'trap' in selection_str.lower():
                        return 1
                    elif re.search(r'\d{2}:\d{2}', selection_str):
                        return 0
                    else:
                        return 2
                else:
                    print("Inner element is empty or not a list/tuple")
                    return 3
        else:
            selection_str = selection[0]
            if 'trap' in selection_str.lower():
                return 1
            elif re.search(r'\d{2}:\d{2}', selection_str):
                return 0
            else:
                return 2
            
    elif isinstance(selection, dict):
        if selection is None or '- Meeting Name' not in selection or selection['- Meeting Name'] is None:
            return 3
        if 'trap' in selection['- Selection Name'].lower():
            return 1
        elif re.search(r'\d{2}:\d{2}', selection['- Meeting Name']):
            return 0
        else:
            return 2
    else:
        return 3

def add_sport_to_selections(selections):
    sports = set()
    for selection in selections:
        sport = identify_sport(selection)
        sports.add(sport)
    return list(sports)

def parse_bet_details(bet_text):
    bet_number_pattern = r"Wager Number - (\d+)"
    customer_ref_pattern = r"Customer Reference - (\w+)"
    customer_risk_pattern = r"Customer Risk Category - (\w+)?"
    time_pattern = r"Bet placed on \d{2}/\d{2}/\d{4} (\d{2}:\d{2}:\d{2})"
    selection_pattern = r"(.+?, .+?, .+?) (?:at|on) (\d+\.\d+|SP)?"
    bet_details_pattern = r"Bets (Win Only|Each Way|Forecast): (\d+ .+?)\. Unit Stake: ([£€][\d,]+\.\d+), Payment: ([£€][\d,]+\.\d+)\."    
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
