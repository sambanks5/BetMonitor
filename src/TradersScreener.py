import os
import threading
import pyperclip
import fasteners
import json
import sqlite3
import requests
from datetime import date, datetime, timedelta
from fractions import Fraction

def get_results_json():
    url = "https://globalapi.geoffbanks.bet/api/geoff/GetCachedRaceResults?sportcode=H,h,g,o"
    response = requests.get(url)
    data = response.json()
    return data

def load_database():
    conn = sqlite3.connect('wager_database.sqlite')
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def get_client_wagers(conn, customer_refs):
    time = datetime.now()
    current_date_str = time.strftime("%d/%m/%Y")
    cursor = conn.cursor()
    
    client_wagers = {}
    for customer_ref in customer_refs:
        cursor.execute("SELECT * FROM database WHERE customer_ref = ? AND date = ?", (customer_ref, current_date_str,))
        wagers = cursor.fetchall()
        
        user_wagers = []
        for bet in wagers:
            if bet[5] == 'BET':
                betID = bet[0]
                selections = json.loads(bet[10])
                user_wagers.append((betID, selections))
        
        client_wagers[customer_ref] = user_wagers
    
    return client_wagers

def fractional_to_decimal(fractional_odds):
    if fractional_odds.lower() == 'evens':
        return 2.0
    numerator, denominator = map(int, fractional_odds.split('-'))
    return (numerator / denominator) + 1

def compare_odds(client_wagers, race_results):
    results = []
    
    for customer_ref, wagers in client_wagers.items():
        total_bets = 0
        bets_beaten = 0 
        
        for betID, selections in wagers:
            for selection in selections:
                if len(selection) >= 2:
                    race_name = selection[0]
                    placed_odds = selection[1]
                    
                    if " - " not in race_name:
                        continue
                    
                    total_bets += 1
                    
                    race_name_parts = race_name.split(" - ")
                    race_time = race_name_parts[0].split(", ")[1]
                    selection_name = race_name_parts[1]
                    
                    for event in race_results:
                        for meeting in event['meetings']:
                            for race in meeting['events']:
                                if race['status'] == 'Result':
                                    race_start_time = race['startDateTime'].split('T')[1][:5]
                                    race_full_name = f"{meeting['meetinName']}, {race_start_time}"
                                    
                                    if race_full_name.lower() == race_name_parts[0].lower():
                                        for race_selection in race['selections']:
                                            if meeting['sportCode'] == 'g':
                                                trap_number = 'Trap ' + race_selection['runnerNumber']
                                                
                                                if trap_number.lower() == selection_name.lower():
                                                    last_price_fractional = race_selection['lastPrice']
                                                    last_price_decimal = fractional_to_decimal(last_price_fractional)
                                                    
                                                    if placed_odds == 'SP':
                                                        placed_odds = last_price_decimal
                                                    if placed_odds == 'evs':
                                                        placed_odds = 2.0
                                                    
                                                    if placed_odds > last_price_decimal:
                                                        bets_beaten += 1
                                            else:
                                                if race_selection['name'].lower() == selection_name.lower():
                                                    last_price_fractional = race_selection['lastPrice']
                                                    last_price_decimal = fractional_to_decimal(last_price_fractional)
                                                    
                                                    if placed_odds == 'SP':
                                                        placed_odds = last_price_decimal
                                                    if placed_odds == 'evs':
                                                        placed_odds = 2.0
                                                    
                                                    if placed_odds > last_price_decimal:
                                                        bets_beaten += 1
        
        if total_bets > 0:
            percentage_beaten = (bets_beaten / total_bets) * 100
        else:
            percentage_beaten = 0.0
        
        results.append((customer_ref, percentage_beaten))
    
    return results

conn = load_database()
customer_refs = ['MA29R', 'USER2', 'USER3']  # Replace with actual user references
client_wagers = get_client_wagers(conn, customer_refs)
data = get_results_json()

results = compare_odds(client_wagers, data)
for customer_ref, percentage_beaten in results:
    print(f"User {customer_ref}: {percentage_beaten:.2f}% of selections beat the SP")