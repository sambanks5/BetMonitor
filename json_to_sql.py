import sqlite3
import json
import os
from datetime import datetime
import re

# Drop the existing table if it exists
def drop_table(conn):
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS entries')
    cursor.execute('DROP TABLE IF EXISTS database')

    conn.commit()

# Define the database schema
def create_table(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS database (
            id TEXT PRIMARY KEY,
            date TEXT,
            time TEXT,
            customer_ref TEXT,
            risk_category TEXT,
            type TEXT,
            unit_stake REAL,
            bet_details TEXT,
            bet_type TEXT,
            total_stake REAL,
            selections TEXT,
            sports TEXT,  -- New column to store sports information
            requested_stake REAL,
            error_message TEXT,
            text_request TEXT,
            requested_type TEXT
        )
    ''')
    conn.commit()

# Insert data into the database
def insert_data(conn, data, date):
    cursor = conn.cursor()
    for item in data:
        try:
            sports = []
            if item['type'] == 'SMS WAGER':
                sports = add_sport_to_selections(item['details'])
                cursor.execute('''
                    INSERT OR REPLACE INTO database (id, time, type, customer_ref, text_request, date, sports)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (item['id'], item['time'], item['type'], item['customer_ref'], json.dumps(item['details']), date, json.dumps(sports)))
            elif item['type'] == 'WAGER KNOCKBACK':
                details = item['details']
                selections = json.dumps(details.get('Selections', []))
                sports = add_sport_to_selections(details.get('Selections', []))
                requested_stake = float(details['Total Stake'].replace('£', '').replace(',', ''))
                cursor.execute('''
                    INSERT OR REPLACE INTO database (id, time, type, customer_ref, error_message, requested_type, requested_stake, selections, date, sports)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item['id'], item['time'], item['type'], details['Customer Ref'], details['Error Message'], details['Wager Name'], requested_stake, selections, date, json.dumps(sports)))
            elif item['type'] == 'BET':
                details = item['details']
                selections = json.dumps(details['selections'])
                sports = add_sport_to_selections(details['selections'])
                unit_stake = float(details['unit_stake'].replace('£', '').replace(',', ''))
                total_stake = float(details['payment'].replace('£', '').replace(',', ''))
                cursor.execute('''
                    INSERT OR REPLACE INTO database (id, time, type, customer_ref, selections, risk_category, bet_details, unit_stake, total_stake, bet_type, date, sports)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item['id'], item['time'], item['type'], item['customer_ref'], selections, details['risk_category'], details['bet_details'], unit_stake, total_stake, details['bet_type'], date, json.dumps(sports)))
        except KeyError as e:
            print(f"KeyError: {e} in file with date {date} and bet number {item['id']}")
        except Exception as e:
            print(f"Error: {e} in file with date {date} and bet number {item['id']}")
    conn.commit()

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

# Convert JSON files to SQLite database
def convert_json_to_sqlite(json_folder, db_path):
    conn = sqlite3.connect(db_path)
    drop_table(conn)
    create_table(conn)
    
    for json_file in os.listdir(json_folder):
        if json_file.endswith('.json'):
            filename = os.path.basename(json_file)
            date_str = '-'.join(filename.split('-')[:3])
            date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
            
            with open(os.path.join(json_folder, json_file), 'r') as f:
                data = json.load(f)
                insert_data(conn, data, date)
    
    conn.close()

# Example usage
json_folder = 'database'
db_path = 'wager_database.sqlite'
convert_json_to_sqlite(json_folder, db_path)