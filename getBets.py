import os
import re
import json
import time
import threading
import tkinter as tk
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tkinter import scrolledtext

class Application(tk.Tk):
    def __init__(self):
        super().__init__()

        # Set the window icon
        self.iconbitmap('src/splash.ico')

        # Create a ScrolledText widget
        self.text_area = scrolledtext.ScrolledText(self, undo=True)
        self.text_area['font'] = ('consolas', '12')
        self.text_area.pack(expand=True, fill='both')

        # Create a button to process existing bets
        self.process_button = tk.Button(self, text="Process Existing Bets", command=self.process_bets, padx=10, pady=5)
        self.process_button.pack()

        # Create a button to stop the main loop
        self.stop_button = tk.Button(self, text="Stop", command=self.stop, padx=10, pady=5)
        self.stop_button.pack()

        # Bind the <Destroy> event
        self.bind('<Destroy>', self.on_destroy)

    def process_bets(self):
        # Call the process_existing_bets function
        process_existing_bets('c:\TESTING', self)

    def stop(self):
        # Signal the main loop to stop
        self.stop_main_loop = True
        app.log_message('Stopping checking process. Please close the window.')

    def log_message(self, message):
        # Append the message to the text area
        self.text_area.insert(tk.END, message + '\n')

        # Auto-scroll to the end
        self.text_area.see(tk.END)

    def on_destroy(self, event):
        # Signal the main loop to stop
        self.stop_main_loop = True

class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Check if it's a file, not a directory
        if not os.path.isdir(event.src_path):
            process_file(event.src_path)

def process_file(file_path):
    # Load the existing database
    database = load_database()

    # Process the file and extract bet data
    bet_data = parse_file(file_path, app)

    # Add the bet data to the database
    add_bet(database, bet_data, app)

    # Save the updated database
    save_database(database)

def load_database():
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'

    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_database(database):
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'

    with open(filename, 'w') as f:
        json.dump(database, f, indent=4)

def add_bet(database, bet, app):
    # Check if the bet is already in the database
    if bet['id'] not in database:
        database[bet['id']] = bet
    else:
        print('Bet already in database ' + bet['id'])
        app.log_message(f'Bet already in database {bet["id"]}')

def parse_file(file_path, app):
    with open(file_path, 'r') as file:
        bet_text = file.read()

        # Check the type of the bet
        bet_text_lower = bet_text.lower()
        is_sms = 'sms' in bet_text_lower
        is_bet = 'website' in bet_text_lower
        is_wageralert = 'knockback' in bet_text_lower

        if is_wageralert:
            customer_ref, knockback_id, knockback_details, time = parse_wageralert_details(bet_text)
            bet_info = {
                'id': knockback_id,
                'type': 'WAGER KNOCKBACK',
                'customer_ref': customer_ref,
                'details': knockback_details,
                'time': time
            }
            print('Bet Processed ' + knockback_id)
            app.log_message(f'Knockback Processed {knockback_id}, {customer_ref}, {time}')
            return bet_info

        elif is_sms:
            wager_number, customer_reference, _, sms_wager_text = parse_sms_details(bet_text)
            bet_info = {
                'id': wager_number,
                'type': 'SMS WAGER',
                'customer_ref': customer_reference,
                'details': sms_wager_text
            }
            print('Bet Processed ' + wager_number)
            app.log_message(f'SMS Processed {wager_number}, {customer_reference}')
            return bet_info

        elif is_bet:
            bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type = parse_bet_details(bet_text)
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
            print('Bet Processed ' + bet_no)
            app.log_message(f'Bet Processed {bet_no}, {customer_reference}, {timestamp}')
            return bet_info

    return {}

def process_existing_bets(directory, app):
    # Load the existing database
    database = load_database()

    # Get a list of all files in the directory
    files = os.listdir(directory)

    # Filter the list to include only .txt files
    bet_files = [f for f in files if f.endswith('.bww')]
    app.log_message(f'Found {len(bet_files)} files')
    
    # Parse each bet file and add it to the database
    for bet_file in bet_files:
        bet = parse_file(os.path.join(directory, bet_file), app)
        add_bet(database, bet, app)

    # Save the updated database
    save_database(database)

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

def main(app):
    while not app.stop_main_loop:
        process_existing_bets('c:\TESTING', app)
        # Set up the file watcher
        event_handler = FileHandler()
        observer = Observer()
        observer.schedule(event_handler, path='c:\TESTING', recursive=False)
        observer.start()
        app.log_message('Watching for new files...')
        try:
            while not app.stop_main_loop:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            observer.stop()
        observer.join()

if __name__ == "__main__":
    # Create the application
    app = Application()

    # Start the main function in a separate thread
    app.stop_main_loop = False
    app.main_loop = threading.Thread(target=main, args=(app,))
    app.main_loop.start()

    # Start the application
    app.mainloop()