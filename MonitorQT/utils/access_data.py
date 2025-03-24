import threading
import json
import time
from config import NETWORK_PATH_PREFIX
import os

class BetDataFetcher:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BetDataFetcher, cls).__new__(cls)
            cls._instance.data = {}
            cls._instance.lock = threading.Lock()
        return cls._instance

    def update_data(self):
        with self.lock:
            try:
                data_path = os.path.join(NETWORK_PATH_PREFIX, 'data.json')
                print(f"Loading data from: {data_path}")
                
                if not os.path.exists(data_path):
                    print(f"ERROR: Data file not found at {data_path}")
                    return
                    
                with open(os.path.join(NETWORK_PATH_PREFIX, 'data.json'), 'r') as file:
                    self.data = json.load(file)
                    print("Data loaded successfully")
            except json.JSONDecodeError as e:
                print(f"ERROR: Invalid JSON in data file: {e}")
            except Exception as e:
                print(f"ERROR: Failed to load data: {e}")

    def get_data(self):
        with self.lock:
            return self.data

    def get_newreg_clients(self):
        with self.lock:
            return self.data.get('new_registrations', [])

    def get_vip_clients(self):
        with self.lock:
            return self.data.get('vip_clients', [])

    def get_reporting_data(self):
        with self.lock:
            return {
                'daily_turnover': self.data.get('daily_turnover', 0),
                'daily_profit': self.data.get('daily_profit', 0),
                'daily_profit_percentage': self.data.get('daily_profit_percentage', 0),
                'last_updated_time': self.data.get('last_updated_time', ''),
                # 'total_deposits': self.data.get('deposits_summary', {}).get('total_deposits', 0),
                # 'total_sum': self.data.get('deposits_summary', {}).get('total_sum', 0),
                'enhanced_places': self.data.get('enhanced_places', [])
            }

    def get_todays_oddsmonkey_selections(self):
        with self.lock:
            return self.data.get('todays_oddsmonkey_selections', {})

def schedule_data_updates():
    fetcher = BetDataFetcher()
    print("Starting data updates...")   
    while True:
        fetcher.update_data()
        time.sleep(60)

def access_data():
    fetcher = BetDataFetcher()
    
    # Check if data loaded yet
    if not fetcher.data:
        print("Initial data load...")
        try:
            fetcher.update_data()
        except Exception as e:
            print(f"Error loading data: {e}")
    
    vip_clients = fetcher.get_vip_clients()
    newreg_clients = fetcher.get_newreg_clients()
    today_oddsmonkey_selections = fetcher.get_todays_oddsmonkey_selections()
    reporting_data = fetcher.get_reporting_data()
    print(f"Data sizes: VIP clients: {len(vip_clients)}, New reg: {len(newreg_clients)}, OM selections: {len(today_oddsmonkey_selections)}")
    return vip_clients, newreg_clients, today_oddsmonkey_selections, reporting_data