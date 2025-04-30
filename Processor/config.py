import os
from collections import Counter
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

USER_NAMES = {
    'G': 'Geoff',
    'GM': 'George M',
    'JP': 'Jon',
    'DF': 'Dave',
    'SB': 'Sam',
    'JJ': 'Joji',
    'AE': 'Arch',
    'EK': 'Ed',
    'VO': 'Victor',
    'MF': 'Mark',
    'GB': 'George B',
    'RE': 'Rodney',
}

ARCHIVE_DATABASE_PATH = 'archive_database.sqlite'
LOCK_FILE_PATH = 'database.lock'
last_processed_time = datetime.now()
executor = ThreadPoolExecutor(max_workers=5)
path = 'F:\\BWW\\Export'

# Shared state
_processed_races = set()
_processed_closures = set()
_previously_seen_events = set()
_bet_count_500 = False
_bet_count_750 = False
_bet_count_1000 = False
_knockback_count_250 = False

## Getter and Setter functinons for last_processed_time
def get_last_processed_time():
    global last_processed_time
    return last_processed_time

def set_last_processed_time(value):
    global last_processed_time
    last_processed_time = value

## Getter and Setter functinons for path
def get_path():
    global path
    return path

def set_path(value):
    global path
    path = value

# Getter and Setter functions for processed_races
def get_processed_races():
    global _processed_races
    return _processed_races

def add_processed_race(race):
    global _processed_races
    _processed_races.add(race)

def clear_processed_races():
    global _processed_races
    _processed_races.clear()

# Getter and Setter functions for processed_closures
def get_processed_closures():
    global _processed_closures
    return _processed_closures

def add_processed_closure(closure):
    global _processed_closures
    _processed_closures.add(closure)

def clear_processed_closures():
    global _processed_closures
    _processed_closures.clear()

# Getter and Setter functions for previously_seen_events
def get_previously_seen_events():
    global _previously_seen_events
    return _previously_seen_events

def add_previously_seen_event(event):
    global _previously_seen_events
    _previously_seen_events.add(event)

def clear_previously_seen_events():
    global _previously_seen_events
    _previously_seen_events.clear()

# Getter and Setter functions for bet_count flags
def get_bet_count_500():
    global _bet_count_500
    return _bet_count_500

def set_bet_count_500(value):
    global _bet_count_500
    _bet_count_500 = value

def get_bet_count_750():
    global _bet_count_750
    return _bet_count_750

def set_bet_count_750(value):
    global _bet_count_750
    _bet_count_750 = value

def get_bet_count_1000():
    global _bet_count_1000
    return _bet_count_1000

def set_bet_count_1000(value):
    global _bet_count_1000
    _bet_count_1000 = value

def get_knockback_count_250():
    global _knockback_count_250
    return _knockback_count_250

def set_knockback_count_250(value):
    global _knockback_count_250
    _knockback_count_250 = value