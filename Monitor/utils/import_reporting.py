import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from tkinter import messagebox
from utils.google_auth import get_google_auth
from config import NETWORK_PATH_PREFIX

load_dotenv()

API_URL = os.getenv('ALL_API_URL')

name_changes_file = os.path.join(NETWORK_PATH_PREFIX, 'name_changes.json')

try:
    with open(name_changes_file, 'r') as f:
        name_changes = json.load(f)
except FileNotFoundError:
    name_changes = {}

def get_next_weekday_name():

    """
    Get the name of the next weekday.
    """

    today = datetime.now()
    next_day = today + timedelta(days=1)
    return next_day.strftime("%A")

def get_today_weekday_name():

    """
    Get the name of the current weekday.
    """

    today = datetime.now()
    return today.strftime("%A")

def extract_data(data, target_day):

    """
    Extract the data from the API response for the target day.
    """

    extracted_data = {}
    for event in data:
        if target_day in event['eventName'] and '.' not in event['eventName']:
            for meeting in event['meetings']:
                meeting_name = meeting['meetinName']
                meeting_name = meeting_name.upper()
                # Apply name changes if needed
                if meeting_name in name_changes:
                    meeting_name = name_changes[meeting_name]
                if meeting_name.endswith('1'):
                    meeting_name = meeting_name[:-1]
                if meeting_name not in extracted_data:
                    extracted_data[meeting_name] = []
                for race in meeting['events']:
                    race_time = race['time']
                    extracted_data[meeting_name].append(race_time)
    return extracted_data

def append_to_spreadsheet(data, current_day=False):

    """
    Append the extracted data to the Google Sheet.
    """
    current_month = datetime.now().strftime('%B')

    gc = get_google_auth()

    spreadsheet_name = 'Reporting ' + current_month
    sh = gc.open(spreadsheet_name)
    worksheet = sh.get_worksheet(2)
    

    if current_day:
        date = datetime.now().strftime('%d %b %Y')
    else:
        date = (datetime.now() + timedelta(days=1)).strftime('%d %b %Y')


    title = worksheet.title
    if title != 'RACE BY RACE':
        print("Worksheet not found.")
        messagebox.showerror("Error", "Reporting RACE BY RACE sheet not found.")
        return False
        
    date_column = worksheet.col_values(12)
    if date in date_column:
        print("Data already exists for this date.")
        messagebox.showerror("Error", "Data already exists for date: " + date + ". If you want to update the racelist, please delete the existing data.")
        return False
    
    time_column = worksheet.col_values(11)
    last_row = len(time_column) + 1 

    # Show confirmation message
    confirm = messagebox.askyesno("Confirmation", "Data will be appended to the spreadsheet. Do you want to proceed?")
    if not confirm:
        messagebox.showinfo("Cancelled", "Data import cancelled.")
        return False
    
    rows_to_append = []
    for meeting in data:
        for race_time in data[meeting]:
            rows_to_append.append([meeting, race_time, date])

    # Update the worksheet with the new data
    cell_range = f'J{last_row}:L{last_row + len(rows_to_append) - 1}'
    worksheet.update(cell_range, rows_to_append)
    messagebox.showinfo("Success", "Data appended successfully. Some may still need manual correction.")
    return True

def import_reporting(current_day=False, progress_note=None):

    """
    Import racing data from the API.
    """

    try:
        url = API_URL
        if not url:
            raise ValueError("Environment variable is not set")
        response = requests.get(url)
        response.raise_for_status()
        api_data = response.json()
    except requests.RequestException as e:
        print("Error fetching data from GB API for Courses.")
        if progress_note:
            progress_note.config(text="Error fetching data.")
        return False
    except json.JSONDecodeError:
        print("Error decoding JSON from GB API response.")
        if progress_note:
            progress_note.config(text="Error decoding data.")
        return False
    
    next_weekday_name = get_next_weekday_name()
    current_weekday_name = get_today_weekday_name()
    target_day = current_weekday_name if current_day else next_weekday_name

    import_data = extract_data(api_data, target_day)

    if import_data:
        print("Data extracted successfully.")
        success = append_to_spreadsheet(import_data, current_day)
        if success:
            if progress_note:
                progress_note.config(text="Data imported successfully.")
            return True
        else:
            if progress_note:
                progress_note.config(text="Failed to append data to spreadsheet.")
            return False
    else:
        print(f"No data for {target_day}.")
        if progress_note:
            progress_note.config(text=f"No data for {target_day}.")
        return False

if __name__ == "__main__":
    import_reporting(True)