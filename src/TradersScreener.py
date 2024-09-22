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
    # Get the results from the API
    url = "https://globalapi.geoffbanks.bet/api/geoff/GetCachedRaceResults?sportcode=H,h,g,o"
    response = requests.get(url)
    data = response.json()
    return data

def load_database():
    conn = sqlite3.connect('wager_database.sqlite')
    conn.execute('PRAGMA journal_mode=WAL;')  # Enable WAL mode
    return conn

def get_client_wagers(conn, customer_ref):
    time = datetime.now()
    current_date_str = time.strftime("%d/%m/%Y")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM database WHERE customer_ref = ? AND date = ?", (customer_ref, current_date_str,))
    wagers = cursor.fetchall()

    client_wagers = []
    for bet in wagers:
        if bet[5] == 'BET':
            betID = bet[0]
            selections = json.loads(bet[10])  # Assuming selections are stored as JSON string
            client_wagers.append((betID, selections))

    return client_wagers

def fractional_to_decimal(fractional_odds):
    # Handle special case for 'Evens'
    if fractional_odds.lower() == 'evens':
        return 2.0
    numerator, denominator = map(int, fractional_odds.split('-'))
    return (numerator / denominator) + 1

def compare_odds(client_wagers, race_results):
    total_bets = 0  # Initialize counter for total bets
    bets_beaten = 0  # Initialize counter for bets where the user beat the SP
    
    for betID, selections in client_wagers:
        # print(f"\nBet ID: {betID}")
        for selection in selections:
            if len(selection) >= 2:
                race_name = selection[0]  # Extract race name and time
                placed_odds = selection[1]  # Extract placed odds
                
                # Check if the selection follows the expected format (contains " - ")
                if " - " not in race_name:
                    #print(f"Skipping non-horse race selection: {race_name}")
                    continue
                
                total_bets += 1  # Increment total bets counter
                
                # Extract race time and selection name from race_name
                race_name_parts = race_name.split(" - ")
                race_time = race_name_parts[0].split(", ")[1]
                selection_name = race_name_parts[1]
                
                for event in race_results:
                    for meeting in event['meetings']:
                        for race in meeting['events']:
                            if race['status'] == 'Result':  # Check if the race has results
                                race_start_time = race['startDateTime'].split('T')[1][:5]
                                race_full_name = f"{meeting['meetinName']}, {race_start_time}"

                                # Compare race name and time
                                if race_full_name.lower() == race_name_parts[0].lower():
                                    for race_selection in race['selections']:

                                        # Handle greyhound racing
                                        if meeting['sportCode'] == 'g':
                                            trap_number = 'Trap ' + race_selection['runnerNumber']
                                            
                                            # Compare trap number with selection name
                                            if trap_number.lower() == selection_name.lower():
                                                last_price_fractional = race_selection['lastPrice']
                                                last_price_decimal = fractional_to_decimal(last_price_fractional)
                                                #print(f"{race_full_name}, {race_selection['name']}, Placed Odds: {placed_odds}, SP: {last_price_decimal:.1f}")
                                                
                                                # Handle special cases for placed odds
                                                if placed_odds == 'SP':
                                                    placed_odds = last_price_decimal
                                                if placed_odds == 'evs':
                                                    placed_odds = 2.0

                                                # Compare placed odds with SP odds
                                                if placed_odds > last_price_decimal:
                                                    print("Beat - Dog")
                                                    bets_beaten += 1  # Increment bets beaten counter
                                                else:
                                                    print("Lost - Dog")
                                        else:
                                            # Compare selection names for horse racing
                                            if race_selection['name'].lower() == selection_name.lower():
                                                last_price_fractional = race_selection['lastPrice']
                                                last_price_decimal = fractional_to_decimal(last_price_fractional)
                                                #print(f"{race_full_name}, {race_selection['name']}, Placed Odds: {placed_odds}, SP: {last_price_decimal:.1f}")
                                                
                                                # Handle special cases for placed odds
                                                if placed_odds == 'SP':
                                                    placed_odds = last_price_decimal
                                                if placed_odds == 'evs':
                                                    placed_odds = 2.0

                                                # Compare placed odds with SP odds
                                                if placed_odds > last_price_decimal:
                                                    print("Beat - hoorse")
                                                    bets_beaten += 1  # Increment bets beaten counter
                                                else:
                                                    print("Lost - hoorse")
    
    if total_bets > 0:
        percentage_beaten = (bets_beaten / total_bets) * 100  # Calculate percentage of bets beaten
        print(f"\nPercentage of selections today the user beat the SP: {percentage_beaten:.2f}%")
    else:
        print("\nNo bets found.")


conn = load_database()
client_wagers = get_client_wagers(conn, 'MA29R')
data = get_results_json()

compare_odds(client_wagers, data)