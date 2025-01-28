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