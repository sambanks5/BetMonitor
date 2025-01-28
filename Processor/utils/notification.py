import json
import fasteners
import os
import requests
from utils import get_db_connection
from config import (
    USER_NAMES,
    executor,
    get_processed_races,
    add_processed_race,
    clear_processed_races,
    get_processed_closures,
    add_processed_closure,
    clear_processed_closures,
    get_previously_seen_events,
    add_previously_seen_event,
    clear_previously_seen_events,
    get_bet_count_500,
    set_bet_count_500,
    get_bet_count_750,
    set_bet_count_750,
    get_bet_count_1000,
    set_bet_count_1000,
    get_knockback_count_250,
    set_knockback_count_250
)
from collections import Counter
from datetime import date, datetime

def log_notification(message, important=False):
    # Get the current time
    time = datetime.now().strftime('%H:%M:%S')

    file_lock = fasteners.InterProcessLock('notifications.lock')

    try:
        with file_lock:
            with open('notifications.json', 'r') as f:
                notifications = json.load(f)
    except FileNotFoundError:
        notifications = []
    except json.JSONDecodeError:
        notifications = []
        
    notifications.insert(0, {'time': time, 'message': message, 'important': important})

    with file_lock:
        with open('notifications.json', 'w') as f:
            json.dump(notifications, f, indent=4)

def staff_report_notification():
    staff_scores_today = Counter()
    today = datetime.now().date()
    
    try:
        log_files = os.listdir('logs/updatelogs')
        log_files.sort(key=lambda file: os.path.getmtime('logs/updatelogs/' + file))
    except Exception as e:
        print(f"Error reading log files: {e}")
        return

    # Read the log file for today
    for log_file in log_files:
        try:
            file_date = datetime.fromtimestamp(os.path.getmtime('logs/updatelogs/' + log_file)).date()
            if file_date == today:
                with open('logs/updatelogs/' + log_file, 'r') as file:
                    lines = file.readlines()

                for line in lines:
                    if line.strip() == '':
                        continue

                    parts = line.strip().split(' - ')

                    if len(parts) == 3:
                        time, staff_initials, score = parts
                        score = float(score)
                        staff_name = USER_NAMES.get(staff_initials, staff_initials)
                        staff_scores_today[staff_name] += score
        except Exception as e:
            print(f"Error processing log file {log_file}: {e}")
            continue

    # Load personalized messages from user_messages.json
    try:
        with open('user_messages.json', 'r') as f:
            user_messages = json.load(f)
    except Exception as e:
        print(f"Error loading user messages: {e}")
        user_messages = {}

    # Find the user with the highest score
    if staff_scores_today:
        highest_scorer = max(staff_scores_today, key=staff_scores_today.get)
        highest_score = staff_scores_today[highest_scorer]
        message = user_messages.get(highest_scorer, "What a legend!")
        try:
            log_notification(f"{message} {highest_scorer} leading with {highest_score:.2f} score.", True)
        except Exception as e:
            print(f"Error sending notification for {highest_scorer}: {e}")

def activity_report_notification():
    conn = get_db_connection.load_database()
    cursor = conn.cursor()
    today = date.today().strftime("%d/%m/%Y")
    
    cursor.execute("SELECT * FROM database WHERE date = ?", (today,))
    todays_records = cursor.fetchall()
    
    bet_count = len([bet for bet in todays_records if bet[5] == 'BET'])
    knockback_count = len([bet for bet in todays_records if bet[5] == 'WAGER KNOCKBACK'])

    thresholds = {
        250: {'count': bet_count, 'flag': 'bet_count_250', 'message': 'bets taken'},
        500: {'count': bet_count, 'flag': 'bet_count_500', 'message': 'bets taken'},
        750: {'count': bet_count, 'flag': 'bet_count_750', 'message': 'bets taken'},
        1000: {'count': bet_count, 'flag': 'bet_count_1000', 'message': 'bets taken'},
        250: {'count': knockback_count, 'flag': 'knockback_count_250', 'message': 'knockbacks'}
    }

    for threshold, data in thresholds.items():
        if data['count'] == threshold and not globals().get(data['flag'], False):
            log_notification(f"{data['count']} {data['message']}", True)
            globals()[data['flag']] = True

    conn.close()

def run_activity_report_notification():
    executor.submit(activity_report_notification)

def run_staff_report_notification():
    executor.submit(staff_report_notification)

def check_closures_and_race_times():
    current_time = datetime.now().strftime('%H:%M')

    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
            enhanced_places = data['enhanced_places']
            closures = data['closures']
    except FileNotFoundError:
        print("File 'data.json' not found.")
        return
    except json.JSONDecodeError:
        print("Error decoding JSON.")
        return

    for closure in closures:
        if closure['email_id'] in get_processed_closures():
            continue
        if not closure.get('completed', False):
            log_notification(f"{closure['type']} request from {closure['username'].strip()}", important=True)
            add_processed_closure(closure['email_id'])

    try:
        url = os.getenv('GET_COURSES_HORSES_API_URL')
        if not url:
            raise ValueError("GET_COURSES_HORSES_API_URL environment variable is not set")

        response = requests.get(url)
        response.raise_for_status()
        api_data = response.json()
    except requests.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return
    except json.JSONDecodeError:
        print("Error decoding JSON from API response.")
        return

    races_today = []
    races_tomorrow = []
    current_weekday_name = datetime.now().strftime('%A')

    for event in api_data:
        event_weekday_name = event['eventName'].split("'s")[0]
        if event_weekday_name == current_weekday_name:
            for meeting in event['meetings']:
                meeting_name = meeting['meetinName']
                for race in meeting['events']:
                    time = race['time']
                    races_today.append(f'{meeting_name}, {time}')
        else:
            for meeting in event['meetings']:
                meeting_name = meeting['meetinName']
                for race in meeting['events']:
                    time = race['time']
                    races_tomorrow.append(f'{meeting_name}, {time}')

    races_today.sort(key=lambda race: datetime.strptime(race.split(', ')[1], '%H:%M'))
    total_races_today = len(races_today)
    for index, race in enumerate(races_today, start=1):
        race_time = race.split(', ')[1]
        if current_time == race_time and race not in get_processed_races():
            if race in enhanced_places:
                add_processed_race(race)
                log_notification(f"{race} (enhanced) is past off time - {index}/{total_races_today}", important=True)
            else:
                add_processed_race(race)
                log_notification(f"{race} is past off time - {index}/{total_races_today}")

def fetch_and_print_new_events():
    url = os.getenv('ALL_EVENTS_API_URL')

    # Ensure the API URL is loaded correctly
    if not url:
        raise ValueError("ALL_EVENTS_API_URL environment variable is not set")

    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

    # Extract event names from the response
    current_events = set(event['EventName'] for event in data)

    if not get_previously_seen_events():
        for event in current_events:
            add_previously_seen_event(event)
    else:
        new_events = current_events - get_previously_seen_events()
        for event in new_events:
            log_notification(f"New event live: {event}", True)

        for event in new_events:
            add_previously_seen_event(event)

def clear_processed():
    clear_processed_races()
    clear_processed_closures()
    clear_previously_seen_events()
    set_bet_count_500(False)
    set_bet_count_750(False)
    set_bet_count_1000(False)
    set_knockback_count_250(False)

    file_lock = fasteners.InterProcessLock('notifications.lock')
    with file_lock:
        try:
            with open('notifications.json', 'w') as f:
                json.dump([], f)
        except IOError as e:
            print(f"Error writing to notifications.json: {e}")

    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
        data['todays_oddsmonkey_selections'] = {}
        data['flashscore_data'] = []
        with open('data.json', 'w') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Error reading or writing to data.json: {e}")