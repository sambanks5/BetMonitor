import sqlite3
import json
import os
from datetime import datetime

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
            time TEXT,
            type TEXT,
            customer_ref TEXT,
            text_request TEXT,
            error_message TEXT,
            requested_type TEXT,
            requested_stake REAL,
            selections TEXT,
            risk_category TEXT,
            bet_details TEXT,
            unit_stake REAL,
            total_stake REAL,
            bet_type TEXT,
            date TEXT
        )
    ''')
    conn.commit()

# Insert data into the database
def insert_data(conn, data, date):
    cursor = conn.cursor()
    for item in data:
        try:
            if item['type'] == 'SMS WAGER':
                cursor.execute('''
                    INSERT OR REPLACE INTO database (id, time, type, customer_ref, text_request, date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (item['id'], item['time'], item['type'], item['customer_ref'], json.dumps(item['details']), date))
            elif item['type'] == 'WAGER KNOCKBACK':
                details = item['details']
                selections = json.dumps(details.get('Selections', []))
                requested_stake = float(details['Total Stake'].replace('£', '').replace(',', ''))
                cursor.execute('''
                    INSERT OR REPLACE INTO database (id, time, type, customer_ref, error_message, requested_type, requested_stake, selections, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item['id'], item['time'], item['type'], details['Customer Ref'], details['Error Message'], details['Wager Name'], requested_stake, selections, date))
            elif item['type'] == 'BET':
                details = item['details']
                selections = json.dumps(details['selections'])
                unit_stake = float(details['unit_stake'].replace('£', '').replace(',', ''))
                total_stake = float(details['payment'].replace('£', '').replace(',', ''))
                cursor.execute('''
                    INSERT OR REPLACE INTO database (id, time, type, customer_ref, selections, risk_category, bet_details, unit_stake, total_stake, bet_type, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (item['id'], item['time'], item['type'], item['customer_ref'], selections, details['risk_category'], details['bet_details'], unit_stake, total_stake, details['bet_type'], date))
        except KeyError as e:
            print(f"KeyError: {e} in file with date {date} and bet number {item['id']}")
        except Exception as e:
            print(f"Error: {e} in file with date {date} and bet number {item['id']}")
    conn.commit()

# Convert JSON files to SQLite database
def convert_json_to_sqlite(json_folder, db_path):
    conn = sqlite3.connect(db_path)
    drop_table(conn)  # Drop the existing table
    create_table(conn)  # Create the new table with updated schema
    
    for json_file in os.listdir(json_folder):
        if json_file.endswith('.json'):
            # Extract date from file name and convert to DD/MM/YYYY format
            filename = os.path.basename(json_file)
            date_str = '-'.join(filename.split('-')[:3])
            date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y')
            
            with open(os.path.join(json_folder, json_file), 'r') as f:
                data = json.load(f)
                insert_data(conn, data, date)
    
    conn.close()

# Example usage
json_folder = 'database'  # Folder containing JSON files
db_path = 'wager_database.sqlite'
convert_json_to_sqlite(json_folder, db_path)