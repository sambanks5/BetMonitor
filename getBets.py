import os
import re
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tkinter import scrolledtext

path = 'F:\BWW\Export'

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Database Updater')
        
        self.iconbitmap('src/splash.ico')
        self.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
        ttk.Style().theme_use('forest-light')
        style = ttk.Style(self)
        style.configure('TButton', padding=(5, 5))


        # Create a ScrolledText widget
        self.text_area = scrolledtext.ScrolledText(self, undo=True)
        self.text_area['font'] = ('helvetica', '12')
        self.text_area.grid(row=0, column=0, columnspan=3, sticky='nsew')

        self.process_button = ttk.Button(self, text="Process Existing", command=self.process_bets, style='TButton', width=15)
        self.process_button.grid(row=1, column=0, padx=5, pady=5)

        self.set_path_button = ttk.Button(self, text="Set Bet Path", command=self.set_bet_path, style='TButton', width=15)
        self.set_path_button.grid(row=1, column=1, padx=5, pady=5)

        self.stop_button = ttk.Button(self, text="Reprocess", command=self.reprocess, style='TButton', width=15)
        self.stop_button.grid(row=1, column=2, padx=5, pady=5)

        # Bind the <Destroy> event
        self.bind('<Destroy>', self.on_destroy)
    
    def set_bet_path(self):
        global path
        new_folder_path = filedialog.askdirectory()
        if new_folder_path:
            path = new_folder_path

    def process_bets(self):
        # Call the process_existing_bets function
        process_existing_bets(path, self)

    def reprocess(self):
        app.log_message('Reprocessing bet database...')
        reprocess_file(self)

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

def set_bet_folder_path():
    global path
    new_folder_path = filedialog.askdirectory()
    if new_folder_path:
        path = new_folder_path

def process_file(file_path):
    # Load the existing database
    database = load_database(app)

    # Process the file and extract bet data
    bet_data = parse_file(file_path, app)

    # Add the bet data to the database
    add_bet(database, bet_data, app)

    # Save the updated database
    save_database(database)

def load_database(app):
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'

    try:
        with open(filename, 'r') as f:
            # app.log_message('Loading database for ' + date) 
            return json.load(f)
    except FileNotFoundError:
        app.log_message('No database found. Creating a new one for ' + date)
        return {}

def add_bet(database, bet, app):
    # Check if the bet is already in the database
    if bet['id'] not in database:
        database[bet['id']] = bet
    else:
        print('Bet already in database ' + bet['id'])
        app.log_message(f'Bet already in database {bet["id"]}, {bet["customer_ref"]}')

def save_database(database):
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'
    
    with open(filename, 'w') as f:
        json.dump(database, f, indent=4)

    # Sort the data in the file after it has been saved
    order_bets(filename)

def order_bets(filename):
    with open(filename, 'r') as f:
        data = json.load(f)  # parse the JSON string into a Python object

    # Convert the dictionary's values to a list and sort it
    data_list = sorted(list(data.values()), key=lambda x: x['time'])

    # Overwrite the original file with the sorted data
    with open(filename, 'w') as f:
        json.dump(data_list, f, indent=4)

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
            unique_knockback_id = f"{knockback_id}-{time}"
            bet_info = {
                'time': time,  # moved 'time' to the top
                'id': unique_knockback_id,
                'type': 'WAGER KNOCKBACK',
                'customer_ref': customer_ref,
                'details': knockback_details,
            }
            print('Knockback Processed ' + unique_knockback_id)
            app.log_message(f'Knockback Processed {unique_knockback_id}, {customer_ref}, {time}\n')
            return bet_info

        elif is_sms:
            creation_time = os.path.getctime(file_path)
            creation_time_str = datetime.fromtimestamp(creation_time).strftime('%H:%M:%S')
            wager_number, customer_reference, _, sms_wager_text = parse_sms_details(bet_text)
            
            bet_info = {
                'time': creation_time_str,  # add 'time' field
                'id': wager_number,
                'type': 'SMS WAGER',
                'customer_ref': customer_reference,
                'details': sms_wager_text
            }
            print('SMS Processed ' + wager_number)
            app.log_message(f'SMS Processed {wager_number}, {customer_reference}\n')
            return bet_info

        elif is_bet:
            bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type = parse_bet_details(bet_text)
            bet_info = {
                'time': timestamp,  # use 'timestamp' as 'time'
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
            app.log_message(f'Bet Processed {bet_no}, {customer_reference}, {timestamp}\n')
            return bet_info

    return {}

def process_existing_bets(directory, app):
    # Load the existing database
    database = load_database(app)

    # Get a list of all files in the directory
    files = os.listdir(directory)

    # Filter the list to include only .txt files
    bet_files = [f for f in files if f.endswith('.bww')]
    app.log_message(f'Found {len(bet_files)} files. Will begin processing...\n')
    
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

def reprocess_file(app):
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'

    # Delete the existing file if it exists
    if os.path.exists(filename):
        os.remove(filename)
        app.log_message('Existing database deleted.')

def main(app):
    global path
    while not app.stop_main_loop:
        # Set up the file watcher
        event_handler = FileHandler()
        observer = Observer()
        if not os.path.exists(path):
            print(f"Error: The path {path} does not exist.")
            set_bet_folder_path()  # Ask the user to select a directory
            if not os.path.exists(path):
                continue  # If the user didn't select a directory, skip this iteration
        observer.schedule(event_handler, path, recursive=True)
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