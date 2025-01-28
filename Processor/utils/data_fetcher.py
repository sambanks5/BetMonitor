import os
import json
import time
import threading
import concurrent.futures
import base64
import google.auth
import requests
import re
from datetime import date
from utils import notification, flashscore_scraper, google_auth
from config import executor
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from bs4 import BeautifulSoup

class DataUpdater:
    def __init__(self, app):
        self.app = app
        self.file_lock = threading.Lock()
        self.data_file_path = 'data.json'
        self.executor = executor

        # Load environment variables
        self.pipedrive_api_token = os.getenv('PIPEDRIVE_API_KEY')
        self.pipedrive_api_url = os.getenv('PIPEDRIVE_API_URL')

        # Ensure the API URL is loaded correctly
        if not self.pipedrive_api_url:
            raise ValueError("PIPEDRIVE_API_URL environment variable is not set")

        self.pipedrive_api_url = f'{self.pipedrive_api_url}?api_token={self.pipedrive_api_token}'
        self.gc = google_auth.get_google_auth()
        self.creds = self.get_google_api_tokens()

        self.run_get_data()
        self.start_periodic_update()

    def get_google_api_tokens(self):
        creds = None
        token_path = 'token.json'
        SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets.readonly']
        try:
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    notification.log_notification("Google API Token Expired. Please check BetProcessor PC for Google login.", True)
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'gmailcreds.json', SCOPES)
                    notification.log_notification("Google API Token Expired. Please check BetProcessor PC for Google login.", True)
                    creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        except google.auth.exceptions.RefreshError:
            print("Token has been expired or revoked. Deleting the token file and re-authenticating.")
            notification.log_notification("Google API Token Expired. Please check BetProcessor PC for Google login.", True)
            if os.path.exists(token_path):
                os.remove(token_path)
                flow = InstalledAppFlow.from_client_secrets_file(
                        'gmailcreds.json', SCOPES)            
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            notification.log_notification(f"Error obtaining Google API tokens: {e}", True)

        return creds

    def start_periodic_update(self):
        self.update_thread = threading.Thread(target=self.periodic_update)
        self.update_thread.daemon = True
        self.update_thread.start()

    def periodic_update(self):
        while True:
            time.sleep(120) 
            self.run_get_data()

    def run_get_data(self):
        self.executor.submit(self.update_data_file)

    def log_message(self, message):
        self.app.log_message(message)

    def load_data(self):
        with open(self.data_file_path, 'r') as f:
            return json.load(f)

    def save_data(self, data):
        with open(self.data_file_path, 'w') as f:
            json.dump(data, f, indent=4)
    
    def update_data_file(self):
        with self.file_lock:
            try:
                self.log_message(" --- Updating data file --- ")
                data = self.load_data()

                self.app.start_progress()
    
                timeout = 50 
    
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = {
                        executor.submit(self.get_vip_clients): 'vip_clients',
                        executor.submit(self.get_new_registrations): 'new_registrations',
                        executor.submit(self.get_reporting_data): 'reporting_data',
                        executor.submit(self.update_todays_oddsmonkey_selections, data.get('todays_oddsmonkey_selections', {})): 'todays_oddsmonkey_selections',
                        executor.submit(self.get_closures): 'closures',
                        executor.submit(flashscore_scraper.get_data): 'flashscore_data'
                    }
    
                    for future in concurrent.futures.as_completed(futures, timeout=timeout):
                        func_name = futures[future]
                        try:
                            result = future.result()
                            if func_name == 'vip_clients':
                                data['vip_clients'] = result
                            elif func_name == 'new_registrations':
                                data['new_registrations'] = result
                            elif func_name == 'reporting_data':
                                data['daily_turnover'], data['daily_profit'], data['daily_profit_percentage'], data['last_updated_time'], data['enhanced_places'] = result
                            elif func_name == 'todays_oddsmonkey_selections':
                                data['todays_oddsmonkey_selections'] = result
                            elif func_name == 'closures':
                                data['closures'] = result
                            elif func_name == 'flashscore_data':
                                data['flashscore_data'] = self.merge_flashscore_data(data.get('flashscore_data', []), result)
                        except concurrent.futures.TimeoutError:
                            self.log_message(f"Timeout occurred while executing {func_name}")
                            print(f"Timeout occurred while executing {func_name}")
                        except Exception as e:
                            self.log_message(f"An error occurred while executing {func_name}: {e}")
                            print(f"An error occurred while executing {func_name}: {e}")
    
                self.log_finished_games(data['flashscore_data'])
    
                self.save_data(data)
                
                self.app.stop_progress()

                self.log_message(" --- Data file updated --- ")
    
            except Exception as e:
                self.log_message(f"An error occurred while updating the data file: {e}")
                notification.log_notification(f"Processor Could not update data file.", True)
    
    def merge_flashscore_data(self, old_data, new_data):
        old_data_dict = {f"{game['home_team']} vs {game['away_team']}": game for game in old_data}
        for game in new_data:
            key = f"{game['home_team']} vs {game['away_team']}"
            if key in old_data_dict:
                game['logged'] = old_data_dict[key].get('logged', False)
        return new_data
    
    def log_finished_games(self, game_info_list):
        if not game_info_list:
            return
        
        print("Logging finished games...")
        for game_info in game_info_list:
            if game_info['status'] == 'Finished' and not game_info.get('logged', False):
                print(f"{game_info['home_team']} v {game_info['away_team']} Finished {game_info['home_score']} - {game_info['away_score']}")
                notification.log_notification(f"{game_info['home_team']} v {game_info['away_team']} Finished {game_info['home_score']} - {game_info['away_score']}", important=True)
                game_info['logged'] = True

    def get_closures(self):
        closures = []
        label_ids = {}
    
        with open(self.data_file_path, 'r') as f:
            existing_closures = json.load(f).get('closures', [])
    
        completed_status = {closure['email_id']: closure.get('completed', False) for closure in existing_closures}
    
        service = build('gmail', 'v1', credentials=self.creds)
    
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
    
        for label_name in ['REPORTING/ACCOUNT DEACTIVATION', 'REPORTING/SELF EXCLUSION', 'REPORTING/TAKE A BREAK']:
            for label in labels:
                if label['name'] == label_name:
                    label_ids[label_name] = label['id']
                    break
            else:
                label_ids[label_name] = None
        
        for label_name, label_id in label_ids.items():
            if label_id is None:
                print(f"Label '{label_name}' not found")
                continue
    
            results = service.users().messages().list(userId='me', labelIds=[label_id]).execute()
            messages = results.get('messages', [])
    
            for message in messages:
                try:
                    msg = service.users().messages().get(userId='me', id=message['id']).execute()
    
                    timestamp = int(msg['internalDate']) // 1000  
                    date_time = datetime.fromtimestamp(timestamp)
                    date_time_str = date_time.strftime('%Y-%m-%d %H:%M:%S')
    
                    payload = msg['payload']
                    email_id = message['id']
    
                    parts = payload.get('parts')
                    if parts is not None:
                        part = parts[0]
                        data = part['body']['data']
                    else:
                        data = payload['body']['data']
    
                    data = data.replace("-", "+").replace("_", "/")
                    decoded_data = base64.b64decode(data)
    
                    soup = BeautifulSoup(decoded_data, "lxml")
    
                    name = soup.find('td', string='Name').find_next_sibling('td').text.strip()
                    username = soup.find('td', string='UserName').find_next_sibling('td').text.strip()
                    type_ = soup.find('td', string='Type').find_next_sibling('td').text.strip()
                    period = soup.find('td', string='Period').find_next_sibling('td').text.strip()
    
                    closure = {
                        'email_id': email_id,
                        'timestamp': date_time_str,
                        'name': name,
                        'username': username,
                        'type': type_,
                        'period': period,
                        'completed': completed_status.get(email_id, False)
                    }
                    closures.append(closure)
                except Exception as e:
                    print(f"Error processing message {message['id']}: {e}")
        
        return closures
    
    def get_vip_clients(self):
        spreadsheet = self.gc.open('Management Tool')
        worksheet = spreadsheet.get_worksheet(33)
        data = worksheet.get_all_values()

        vip_clients = [row[0] for row in data if row[0]]
        
        return vip_clients
    
    def get_new_registrations(self):
        pipedrive_persons_api_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')
        if not pipedrive_persons_api_url:
            raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

        response = requests.get(f'{pipedrive_persons_api_url}?api_token={self.pipedrive_api_token}&filter_id=60')

        if response.status_code == 200:
            data = response.json()

            persons = data.get('data', [])
            newreg_clients = [person.get('c1f84d7067cae06931128f22af744701a07b29c6', '') for person in persons]
        
        return newreg_clients

    def get_reporting_data(self):
        current_month = datetime.now().strftime('%B')
        spreadsheet_name = 'Reporting ' + current_month
        spreadsheet = self.gc.open(spreadsheet_name)

        worksheet = spreadsheet.get_worksheet(3)
        daily_turnover = worksheet.acell('E1').value
        daily_profit = worksheet.acell('F1').value
        daily_profit_percentage = worksheet.acell('G1').value

        drive_service = build('drive', 'v3', credentials=self.creds)
        file_id = spreadsheet.id
        request = drive_service.files().get(fileId=file_id, fields='modifiedTime')
        response = request.execute()
        last_updated_time = datetime.strptime(response['modifiedTime'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%H:%M:%S")

        enhanced_place = spreadsheet.get_worksheet(7)
        values = enhanced_place.get_all_values()
        today = datetime.now().strftime('%d/%m/%Y')

        enhanced_places = [f'{row[3].title()}, {row[2]}' for row in values if row[1] == today]

        return daily_turnover, daily_profit, daily_profit_percentage, last_updated_time, enhanced_places

    def get_oddsmonkey_selections(self, num_messages=None, query=''):
        service = build('gmail', 'v1', credentials=self.creds)

        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        oddsmonkey_label_id = None
        for label in labels:
            if label['name'] == 'ODDSMONKEY':
                oddsmonkey_label_id = label['id']
                break

        if oddsmonkey_label_id is None:
            print("Label 'Oddsmonkey' not found")
            return {}
        results = service.users().messages().list(userId='me', labelIds=[oddsmonkey_label_id], q=query).execute()

        messages = results.get('messages', [])
        length = len(messages)

        all_selections = {}

        for message in messages if num_messages is None else messages[:num_messages]:
            try:
                msg = service.users().messages().get(userId='me', id=message['id']).execute()

                payload = msg['payload']
                headers = payload['headers']

                for d in headers:
                    if d['name'] == 'Subject':
                        subject = d['value']
                    if d['name'] == 'From':
                        sender = d['value']

                parts = payload.get('parts')
                if parts is not None:
                    part = parts[0]
                    data = part['body']['data']
                else:
                    data = payload['body']['data']

                data = data.replace("-","+").replace("_","/")
                decoded_data = base64.b64decode(data)

                soup = BeautifulSoup(decoded_data , "lxml")
                
                td_tags = soup.find_all('td', style="padding-left: 7px;padding-right: 7px;")

                try:
                    selections = self.extract_oddsmonkey_selections(td_tags)
                    all_selections.update(selections)
                except Exception as e:
                    self.log_message(f"An error occurred while extracting oddsmonkey data {e}")
                    print(f"An error occurred while extracting selections: {e}")

            except Exception as e:
                self.log_message(f"An error occurred while processing oddsmonkey data {e}")
                print(e)

        return all_selections

    def update_todays_oddsmonkey_selections(self, existing_selections):
        try:
            today = date.today().strftime('%Y/%m/%d')
            new_selections = self.get_oddsmonkey_selections(query=f'after:{today}')
    
            # Update existing selections with new selections and latest lay odds
            for event, selections in new_selections.items():
                if event in existing_selections:
                    existing_event_selections = {sel[0]: sel[1] for sel in existing_selections[event]}
                    for sel, odds in selections:
                        existing_event_selections[sel] = odds
                    existing_selections[event] = [[sel, odds] for sel, odds in existing_event_selections.items()]
                else:
                    existing_selections[event] = selections
    
            return existing_selections
    
        except Exception as e:
            self.log_message(f"An error occurred while updating today's Oddsmonkey selections: {str(e)}")
            print(f"An error occurred while updating today's Oddsmonkey selections: {str(e)}")
            return existing_selections
        
    def extract_oddsmonkey_selections(self, td_tags):
        selections = {}
    
        # Convert BeautifulSoup elements to strings and strip whitespace
        td_tags = [str(td.text).strip() for td in td_tags]
    
        # Check if the length of td_tags is a multiple of 11 (since each selection has 11 lines)
        if len(td_tags) % 11 != 0:
            print("Unexpected number of lines in td_tags")
            return selections
    
        # Iterate over td_tags in steps of 11
        for i in range(0, len(td_tags), 11):
            event = td_tags[i+2]  # Line 3
            selection = td_tags[i+3]  # Line 4
            lay_odds = td_tags[i+10]  # Line 11
    
            # Check if the event name contains a time (e.g., "13:45")
            if re.search(r'\d{2}:\d{2}', event):
                # This is a horse racing or dog racing event
                formatted_event = event
                # Add the selection to the selections dictionary
                if formatted_event not in selections:
                    selections[formatted_event] = {}
                selections[formatted_event][selection] = lay_odds
            else:
                # Skip non-racing events
                # print(f"Skipping non-racing event: {event}")
                pass
    
        # Convert the dictionary to the desired format
        formatted_selections = {event: [[sel, odds] for sel, odds in sel_dict.items()] for event, sel_dict in selections.items()}
        return formatted_selections

    def calculate_deposit_summary(self):
        # Implement the logic to calculate deposit summary
        pass