import os
import re
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, Label
from PIL import ImageTk, Image
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tkinter import scrolledtext

path = 'F:\BWW\Export'

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Bet Processor')
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


        # Bind the <Destroy> event
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
        # Check if it's a file, not a directory
        if not os.path.isdir(event.src_path):
            max_retries = 5  # Maximum number of retries
            for attempt in range(max_retries):
                try:
                    process_file(event.src_path)
                    break  # If the file was processed successfully, break out of the loop
                except Exception as e:
                    print(f"An error occurred while processing the file {event.src_path}: {e}")
        else:  # This block will be executed if the for loop completed, i.e., max retries reached
            print(f"Failed to process the file {event.src_path} after {max_retries} attempts.")
        

def parse_bet_details(bet_text):
    bet_number_pattern = r"Wager Number - (\d+)"
    customer_ref_pattern = r"Customer Reference - (\w+)"
    customer_risk_pattern = r"Customer Risk Category - (\w+)?"
    time_pattern = r"Bet placed on \d{2}/\d{2}/\d{4} (\d{2}:\d{2}:\d{2})"
    selection_pattern = r"(.+?, .+?, .+?) (?:at|on) (\d+\.\d+|SP)?"
    bet_details_pattern = r"Bets (Win Only|Each Way|Forecast): (\d+ .+?)\. Unit Stake: (£[\d,]+\.\d+), Payment: (£[\d,]+\.\d+)\."
    bet_type_pattern = r"Wagers\s*:\s*([^\n@]+)"    
    odds_pattern = r"(?:at|on)\s+(\d+\.\d+|SP)"  # Updated pattern to include 'SP'

    # Rest of the code remains the same
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
    print("\nLoading database")
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'

    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        app.log_message('No database found. Creating a new one for ' + date)
        # Create a new file and return an empty list
        # with open(filename, 'w') as f:
        #     json.dump([], f, indent=4)
        return []

def add_bet(database, bet, app):
    print("Adding a bet to the database")
    # Check if the bet is already in the database
    if not any(bet['id'] == existing_bet['id'] for existing_bet in database):
        database.append(bet)
    else:
        app.log_message(f'Bet already in database {bet["id"]}, {bet["customer_ref"]}! Skipping...\n')

def save_database(database):
    print("Saving database")
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'
    
    with open(filename, 'w') as f:
        json.dump(database, f, indent=4)  # dump the list directly
    
    order_bets(filename)

def order_bets(filename):
    print("Ordering bets")
    with open(filename, 'r') as f:
        data = json.load(f)  # load the list directly

    # Sort the list
    data_sorted = sorted(data, key=lambda x: x['time'])

    # Overwrite the original file with the sorted data
    with open(filename, 'w') as f:
        json.dump(data_sorted, f, indent=4)  # dump the sorted list

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
                'time': time,
                'id': unique_knockback_id,
                'type': 'WAGER KNOCKBACK',
                'customer_ref': customer_ref,
                'details': knockback_details,
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
    app.log_message('\nBet processing complete...\nWaiting for new files...\n')

def reprocess_file(app):
    print("Reprocessing file")
    # Get the current date
    date = datetime.now().strftime('%Y-%m-%d')

    # Use the date in the filename and specify the folder
    filename = f'database/{date}-wager_database.json'

    # Delete the existing file if it exists
    if os.path.exists(filename):
        os.remove(filename)
        app.log_message('Existing database deleted. Will begin processing existing bets...\n\n')
    else:
        app.log_message('No existing database found. Will begin processing existing bets...\n\n')

def main(app):
    global path
    event_handler = FileHandler()
    observer = Observer()
    observer_started = False
        
    app.log_message('Bet Processor - import, parse and store daily bet data.\n')
    app.log_message('Watching for new files...')

    while not app.stop_main_loop:
        if not os.path.exists(path):
            print(f"Error: The path {path} does not exist.")
            set_bet_folder_path() 
            if not os.path.exists(path):
                continue  
        if not observer_started:
            observer.schedule(event_handler, path, recursive=False)
            observer.start()
            observer_started = True


        try:
            time.sleep(1)  # Add a delay of 1 second
        except Exception as e:
            app.log_message(f"An error occurred: {e}")
            app.reprocess() 
            time.sleep(10)
        except KeyboardInterrupt:
            pass
    observer.stop()
    print("OBSERVER STOPPED!")  
    observer.join()
    print("MAIN LOOP STOPPED! If you see this please tell Sam.")

if __name__ == "__main__":
    # Create the application
    app = Application()

    # Start the main function in a separate thread
    app.stop_main_loop = False
    app.main_loop = threading.Thread(target=main, args=(app,))
    app.main_loop.start()

    # Start the application
    app.mainloop()