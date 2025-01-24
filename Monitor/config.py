import os
from dotenv import load_dotenv

load_dotenv()
LOCAL_DATABASE_PATH = os.getenv('LOCAL_DATABASE_PATH')
LOCK_FILE_PATH = os.getenv('LOCK_FILE_PATH')
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
PIPEDRIVE_API_KEY = os.getenv('PIPEDRIVE_API_KEY')
X_RAPIDAPI_KEY = os.getenv('X_RAPIDAPI_KEY')

# DATABASE_PATH = 'F:\\GB Bet Monitor\\wager_database.sqlite'
# NETWORK_PATH_PREFIX = 'F:\\GB Bet Monitor\\'

DATABASE_PATH = './wager_database.sqlite'
NETWORK_PATH_PREFIX = ''

CACHE_UPDATE_INTERVAL = 80 * 1

_user = ""

USER_NAMES = {
    'GB': 'George B',
    'GM': 'George M',
    'JP': 'Jon',
    'DF': 'Dave',
    'SB': 'Sam',
    'JJ': 'Joji',
    'AE': 'Arch',
    'EK': 'Ed',
    'VO': 'Victor',
    'MF': 'Mark'
}

def get_user():
    global _user
    return _user

def set_user(value):
    global _user
    _user = value