import os
import re
import threading
import pyperclip
import random
import tkinter as tk
import cProfile
import concurrent.futures
from collections import defaultdict, Counter
from tkinter import messagebox, filedialog, simpledialog
from tkinter import ttk
from tkinter.ttk import *
from datetime import date, datetime, timedelta
from PIL import Image, ImageTk

#Default Values for settings
DEFAULT_NUM_RECENT_FILES = 50
DEFAULT_NUM_BETS_TO_RUN = 3

# Main dictionary containing Selections
selection_bets = {}

# Nested dictionary containing bet information per Selection
bet_info = {}  

# List to hold current displayed bets
displayed_bets = []

# List to hold users displayed in custom feed
custom_feed_users = []

# Variable to hold generated temporary password 
password_result_label = None

wageralerts_active = True

# Path to BWW Export folder containing raw bet texts
#BET_FOLDER_PATH = "c:\TESTING"
BET_FOLDER_PATH = "F:\BWW\Export"



### REFRESH/UPDATE DISPLAY AND DICTIONARY
def refresh_display():
    global selection_bets, bet_info, displayed_bets

    # Get the number of recent files to check from the user input
    num_recent_files = DEFAULT_NUM_RECENT_FILES
    # Clear the dictionaries
    selection_bets = {}
    bet_info = {}
    displayed_bets = []

    # Refresh the display
    start_bet_check_thread(num_recent_files)

    print("Refreshed Bets")



### FUNCTION TO HANDLE REFRESHING DISPLAY EVERY 30 SECONDS
def refresh_display_periodic():
    # Refresh the display
    refresh_display()
    # Schedule this function to be called again after 30000 milliseconds (30 seconds)
    root.after(30000, refresh_display_periodic)



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



### RETURN 'DATE OF CREATION' FOR TEXT FILES
def get_creation_date(file_path):
    return os.path.getctime(file_path)



### BET CHECK THREAD FUNCTIONS
def start_bet_check_thread(num_recent_files):
    bet_thread = threading.Thread(target=bet_check_thread, args=(num_recent_files,))
    bet_thread.daemon = True
    bet_thread.start()



### MAIN FUNCTION TO GET FILES
def bet_check_thread(num_recent_files):
    global BET_FOLDER_PATH
    global wageralerts_active

    # Get a list of all text files in the folder
    files = [f for f in os.listdir(BET_FOLDER_PATH) if f.endswith('.bww')]
    
    # Sort files by creation date in descending order
    files.sort(key=lambda x: get_creation_date(os.path.join(BET_FOLDER_PATH, x)), reverse=True)


    recent_files = files[:num_recent_files]

    feed_content = ""

    # Process the selected recent files
    for filename in recent_files:
        file_path = os.path.join(BET_FOLDER_PATH, filename)

        risk_only, show_wageralert, show_sms = get_feed_options()

        separator = '\n\n---------------------------------------------------------------------------------------\n\n'

        with open(file_path, 'r') as file:
            bet_text = file.read()

            is_sms =  'sms' in bet_text.lower()

            is_bet = 'website' in bet_text.lower()

            is_wageralert = 'knockback' in bet_text.lower()



            if is_wageralert:
                if show_wageralert:
                    customer_ref, knockback_details, time = parse_wageralert_details(bet_text)
                    formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items()])
                    feed_content += f"{time} - {customer_ref} - WAGER KNOCKBACK:\n   {formatted_knockback_details}" + separator
                else:
                    print("Wageralert ", filename, " not being displayed")


            elif is_sms:
                if show_sms:
                    wager_number, customer_reference, mobile_number, sms_wager_text = parse_sms_details(bet_text)
                    feed_content += f"{customer_reference}-{wager_number} SMS WAGER:\n{sms_wager_text}" + separator
                else:
                    print("SMS ", filename, " not being displayed")


            elif is_bet:                    
                bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type = parse_bet_details(bet_text)
                if risk_only:
                    if customer_risk_category and customer_risk_category != '-':
                        selection = "\n".join([f"   - {sel} at {odds}" for sel, odds in parsed_selections])
                        feed_content += f"{timestamp}-{bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator
                else:        
                    selection = "\n".join([f"   - {sel} at {odds}" for sel, odds in parsed_selections])
                    feed_content += f"{timestamp}-{bet_no} | {customer_reference} ({customer_risk_category}) | {unit_stake} {bet_details}, {bet_type}:\n{selection}" + separator
                
                update_selection_bets(bet_no, parsed_selections, timestamp, customer_reference, customer_risk_category, bet_details, unit_stake, payment, bet_type)

    # Update the feed label with the latest bet or wageralert information
    feed_text.config(state="normal")
    feed_text.delete('1.0', tk.END)
    feed_text.insert('1.0', feed_content)
    feed_text.config(state="disabled")

    # Update the display
    custom_search(custom_feed_users)
    check_bet_runs()
    get_bets_with_risk_category()



### CREATE REPORT ON DAILY ACTIVITY
def create_daily_report():
    # Get a list of all text files in the folder
    files = [f for f in os.listdir(BET_FOLDER_PATH) if f.endswith('.bww')]
    
    # Sort files by creation date in descending order
    files.sort(key=lambda x: get_creation_date(os.path.join(BET_FOLDER_PATH, x)), reverse=True)
    
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

    # Wageralert Report
    total_wageralerts = 0
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
                wageralert_customer_reference, _, time = parse_wageralert_details(bet_text)
                wageralert_clients.append(wageralert_customer_reference)
                total_wageralerts += 1

            if is_sms:
                _, sms_customer_reference, _, _ = parse_sms_details(bet_text)
                sms_clients.add(sms_customer_reference)
                total_sms += 1

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
    knockback_details = {}
    time = None

    # Regular expressions to extract relevant information
    customer_ref_pattern = r'Customer Ref: (\w+)'
    details_pattern = r'Knockback Details:([\s\S]*?)\n\nCustomer services reference no:'
    time_pattern = r'- Date: \d+ [A-Za-z]+ \d+\n - Time: (\d+:\d+:\d+)'

    # Extract Customer Ref
    customer_ref_match = re.search(customer_ref_pattern, content)
    if customer_ref_match:
        customer_ref = customer_ref_match.group(1)

    # Extract Knockback Details
    details_match = re.search(details_pattern, content)
    if details_match:
        details_content = details_match.group(1).strip()
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

    return customer_ref, knockback_details, time



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



### CUSTOM SEARCH FUNCTION, USER ENTERS USERNAMES (CUSTOMER_REFS) AND IT OUTPUTS FEED OF THOSE USERS' BETS
def custom_search(custom_feed_users):
    # Get the list of usernames from the UI
    # Initialize a string to hold the feed
    feed_content = ""

    # Iterate over your bets and check if the username matches any of the custom_feed_users
    for bet_number, bet_info in selection_bets.items():
        for selections, timestamp, customer_reference, _, bet_details, unit_stake, payment, bet_type in bet_info:
            if customer_reference in custom_feed_users:
                selection_info = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in selections])
                feed_content += f"{bet_number} - {timestamp} | {customer_reference} | {unit_stake} {bet_details}:\n{selection_info}\n\n"

    # Display the feed in your UI
    # Assuming you have a widget named feed_text to display the feed
    custom_feed_text.config(state="normal")
    custom_feed_text.delete('1.0', tk.END)
    custom_feed_text.insert('1.0', feed_content)
    custom_feed_text.config(state="disabled")



### GET THE LIST OF USERS TO SEARCH
def get_custom_feed_users():
    global custom_feed_users
    custom_feed_users = simpledialog.askstring("Custom Search", "Enter usernames (comma-separated):")
    if custom_feed_users:
        custom_feed_users = custom_feed_users.split(',')
        custom_feed_users = [user.strip() for user in custom_feed_users if user.strip()]
        custom_search(custom_feed_users)



def get_feed_options():
    risk_value = default_state_risk.get()
    wageralert_value = default_state_wageralert.get()
    textbets_value = default_state_textbets.get()
    return risk_value, wageralert_value, textbets_value



### MENU BAR * OPTIONS ITEMS
def about():
    messagebox.showinfo("About", "Geoff Banks Bet Monitoring V4.4")



def howTo():
    messagebox.showinfo("How to use", "Runs on Selections - Recent selections with >3 bets\nRisk Client Bets - Feed of bets from clients of risk\nBet Feed - Feed of all bets placed online\nRisk Clients Active Today - All clients of risk active today\n\nUse above info to monitor bets and cut prices when needed.")



def set_num_run_bets(value):
    global DEFAULT_NUM_BETS_TO_RUN, run_bets_label
    DEFAULT_NUM_BETS_TO_RUN = int(float(value))
    #refresh_display()
    run_bets_label.config(text=f"{DEFAULT_NUM_BETS_TO_RUN+1}")



def set_recent_bets(value):
    global DEFAULT_NUM_RECENT_FILES
    new_recent_value = int(float(value))
    #refresh_display()
    if new_recent_value is not None:
        DEFAULT_NUM_RECENT_FILES = new_recent_value
        recent_bets_label.config(text=f"{DEFAULT_NUM_RECENT_FILES}")

    #recent_bets_label.config(text=f"{DEFAULT_NUM_RECENT_FILES}")



def set_bet_folder_path():
    global BET_FOLDER_PATH
    new_folder_path = tk.filedialog.askdirectory()
    if new_folder_path is not None:
        BET_FOLDER_PATH = new_folder_path
        #folder_path_label.config(text=f"{BET_FOLDER_PATH}")
    refresh_display()



if __name__ == "__main__":
    
    ### WINDOW SETTINGS
    root = tk.Tk()
    root.title("GB Bet Monitor v4.4")
    root.tk.call('source', 'src\\Forest-ttk-theme-master\\forest-light.tcl')
    ttk.Style().theme_use('forest-light')
    style = ttk.Style(root)
    width=900
    height=975
    root.configure(bg='#ffffff')
    screenwidth = root.winfo_screenwidth()
    screenheight = root.winfo_screenheight()
    alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2)
    root.geometry(alignstr)
    root.resizable(width=False, height=False)
    root.iconbitmap('src\\splash.ico')

    ### MENU BAR SETTINGS
    menu_bar = tk.Menu(root)
    options_menu = tk.Menu(menu_bar, tearoff=0)
    options_menu.add_command(label="Set Recent Bets", command=set_recent_bets, foreground="#000000", background="#ffffff")
    options_menu.add_command(label="Set Num of Bets to a Run", command=set_num_run_bets, foreground="#000000", background="#ffffff")
    options_menu.add_command(label="Set BWW Export Folder", command=set_bet_folder_path, foreground="#000000", background="#ffffff")
    options_menu.add_separator(background="#ffffff")
    options_menu.add_command(label="Exit", command=root.quit, foreground="#000000", background="#ffffff")
    menu_bar.add_cascade(label="Options", menu=options_menu)
    help_menu = tk.Menu(menu_bar, tearoff=0)
    help_menu.add_command(label="How to use", command=howTo, foreground="#000000", background="#ffffff")
    help_menu.add_command(label="About", command=about, foreground="#000000", background="#ffffff")
    help_menu.add_separator(background="#ffffff")
    menu_bar.add_cascade(label="Help", menu=help_menu, foreground="#000000", background="#ffffff")
    refresh_menu = tk.Menu(menu_bar, tearoff=0)
    refresh_menu.add_command(label="Refresh Dictionary", command=refresh_display, foreground="#000000", background="#ffffff")
    #refresh_menu.add_command(label="Stop Automatic Refresh", command=refresh_display, foreground="#000000", background="#ffffff")
    menu_bar.add_cascade(label="Refresh", menu=refresh_menu)
    root.config(menu=menu_bar)

    ### IMPORT LOGO
    logo_image = Image.open('src\\splash.ico')
    logo_image.thumbnail((80, 80))
    company_logo = ImageTk.PhotoImage(logo_image)    

    ### BET FEED
    feed_frame = ttk.LabelFrame(root, style='Card', text="Bet Feed")
    feed_frame.place(x=395, y=10, width=495, height=630)

    feed_text = tk.Text(feed_frame, font=("Helvetica", 11, "bold"),wrap='word',padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    feed_text.config(state='disabled')
    feed_text.pack(fill='both', expand=True)

    feed_scroll = ttk.Scrollbar(feed_text, orient='vertical', command=feed_text.yview)
    feed_scroll.pack(side="right", fill="y")

    feed_text.configure(yscrollcommand=feed_scroll.set)

    ### RUNS ON SELECTIONS
    runs_frame = ttk.LabelFrame(root, style='Card', text="Runs on Selections")
    runs_frame.place(x=10, y=10, width=370, height=510)
    runs_text=tk.Text(runs_frame, font=("Helvetica", 11), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
    runs_text.config(state='disabled') 
    runs_text.pack(fill='both', expand=True)

    runs_scroll = ttk.Scrollbar(runs_text, orient='vertical', command=runs_text.yview)
    runs_scroll.pack(side="right", fill="y")

    runs_text.configure(yscrollcommand=runs_scroll.set)

    notebook_frame = ttk.Frame(root)
    notebook_frame.place(x=5, y=530, width=380, height=420)

    notebook = ttk.Notebook(notebook_frame)

    tab_1 = ttk.Frame(notebook)
    notebook.add(tab_1, text="Risk Bets")

    bets_with_risk_text=tk.Text(tab_1, font=("Helvetica", 10), bd=0, wrap='word',padx=10, pady=10, fg="#000000", bg="#ffffff")
    bets_with_risk_text.grid(row=0, column=0, sticky="nsew")
    bets_with_risk_text.pack(fill='both', expand=True)

    tab_2 = ttk.Frame(notebook)
    notebook.add(tab_2, text="Search")

    tab_2.grid_rowconfigure(0, weight=1)
    tab_2.grid_columnconfigure(0, weight=1)

    custom_feed_text = tk.Text(tab_2, font=("Helvetica", 10), bd=0, wrap='word', padx=10, pady=10, fg="#000000", bg="#ffffff")
    custom_feed_text.insert('1.0', "No users set for custom feed.\n\n- Filter bets for certain users by clicking the button below.\n- A new search will reset the current set.\n- Enter usernames in Uppercase.")
    custom_feed_text.config(state='disabled')
    custom_feed_text.grid(row=0, column=0, sticky="nsew")

    add_users_button = ttk.Button(tab_2, text="Set users to track", command=get_custom_feed_users)
    add_users_button.grid(row=1, column=0, padx=10, pady=(10, 0), sticky="ew")

    tab_4 = ttk.Frame(notebook)
    notebook.add(tab_4, text="Report")

    report_ticket = tk.Text(tab_4, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
    report_ticket.config(state='disabled')
    report_ticket.grid(row=0, column=0, sticky="nsew")

    progress = ttk.Progressbar(tab_4, mode="determinate", length=250)
    progress.grid(row=1, column=0, pady=(10, 20), sticky="w")

    refresh_button = ttk.Button(tab_4, text="Generate", command=create_daily_report)
    refresh_button.grid(row=1, column=0, pady=(0, 10), sticky="e")


    # Configure the row and column weights for the frame
    tab_4.grid_rowconfigure(0, weight=1)
    tab_4.grid_columnconfigure(0, weight=1)

    notebook.pack(expand=True, fill="both", padx=5, pady=5)


    ### OPTIONS FRAME
    options_frame = ttk.LabelFrame(root, style='Card', text="Options", width=120, height=205)
    options_frame.place(x=395, y=650, width=495, height=290)

    options_label=tk.Label(options_frame, font=("Helvetica", 11), wraplength=140, text="Click logo to refresh", fg="#000000", bg="#ffffff")
    options_label.place(x=60,y=10)



    ### CHECK BOX OPTIONS
    # default_show_bets = tk.IntVar(value=1)
    default_state_risk = tk.IntVar(value=0)
    default_state_wageralert = tk.IntVar(value=1)
    default_state_textbets = tk.IntVar(value=1)  # Default to checked

    # show_bets = ttk.Checkbutton(options_frame, text='Bets',style="Switch", variable=default_show_bets)
    # show_bets.place(x=140, y=40)

    show_risk_bets = ttk.Checkbutton(options_frame, text='Risk Bets Only',style="Switch", variable=default_state_risk)
    show_risk_bets.place(x=60, y=50)

    show_wageralert = ttk.Checkbutton(options_frame, text='Knockbacks',style="Switch", variable=default_state_wageralert)
    show_wageralert.place(x=140, y=90)

    show_textbets = ttk.Checkbutton(options_frame, text='Text Bets',style="Switch", variable=default_state_textbets)
    show_textbets.place(x=20, y=90)



    ### SLIDER OPTIONS
    recent_bets_label = ttk.Label(options_frame, text=f"{DEFAULT_NUM_RECENT_FILES}")
    recent_bets_label.place(x=240, y=150)

    set_recent_bets_label=tk.Label(options_frame, font=("Helvetica", 10), text="Bets to Check", fg="#000000", bg="#ffffff")
    set_recent_bets_label.place(x=85,y=130)

    set_recent_bets = ttk.Scale(options_frame, from_=20, to=350,cursor="hand2", command=set_recent_bets)
    set_recent_bets.set(DEFAULT_NUM_RECENT_FILES)
    set_recent_bets.pack()
    set_recent_bets.place(x=30, y=150, width=200)

    run_bets_label = ttk.Label(options_frame, text=f"{DEFAULT_NUM_BETS_TO_RUN}")
    run_bets_label.place(x=240, y=200)

    set_recent_runs_label=tk.Label(options_frame, font=("Helvetica", 10), text="Bets to a Run", fg="#000000", bg="#ffffff")
    set_recent_runs_label.place(x=85,y=175)

    set_num_run_bets = ttk.Scale(options_frame, from_=2, to=7, cursor="hand2",command=set_num_run_bets)
    set_num_run_bets.set(DEFAULT_NUM_BETS_TO_RUN)
    set_num_run_bets.pack()
    set_num_run_bets.place(x=30, y=195, width=200)



    ### SET EXPORT PATH BUTTON
    set_bet_folder_path_button = ttk.Button(options_frame, command=set_bet_folder_path, text="Set BWW Folder")
    set_bet_folder_path_button.place(x=30, y=230, width=200)



    ### OPTIONS SEPARATOR
    separator = ttk.Separator(options_frame, orient='vertical')
    separator.place(x=270, y=5, height=255)



    ### LOGO DISPLAY
    logo_label = tk.Label(options_frame, image=company_logo, bd=0, cursor="hand2")
    logo_label.place(x=343, y=10)
    logo_label.bind("<Button-1>", lambda e: refresh_display())

    ### TITLE TEXT
    title_label=tk.Label(options_frame, font=("Helvetica", 14), wraplength=140, text="Geoff Banks Bet Monitoring", fg="#000000", bg="#ffffff")
    title_label.place(x=320,y=100)



    ### PASSWORD GENERATOR
    copy_button = ttk.Button(options_frame, command=copy_to_clipboard, text="Generate & Copy Password")
    copy_button.place(x=290, y=200)

    password_result_label = tk.Label(options_frame, wraplength=200, font=("Helvetica", 12), justify="center", text="GB000000", fg="#000000", bg="#ffffff")
    password_result_label.place(x=340, y=240)


    ### GUI LOOP
    threading.Thread(target=refresh_display_periodic, daemon=True).start()
    root.mainloop()
