import os
import json
import requests
import threading
import tkinter as tk
import random
from tkinter import ttk, messagebox
from datetime import datetime
from PIL import Image, ImageTk
import pyperclip
from config import NETWORK_PATH_PREFIX
from utils import notification, user


class Settings:
    def __init__(self, root):
        self.root = root
        self.initialize_ui()
    
    def initialize_ui(self):        
        self.settings_frame = ttk.Frame(self.root, style='Card')
        self.settings_frame.place(x=714, y=655, width=180, height=265)

        logo_image = Image.open('Monitor/splash.ico')
        logo_image = logo_image.resize((60, 60))
        self.company_logo = ImageTk.PhotoImage(logo_image)
        self.logo_label = ttk.Label(self.settings_frame, image=self.company_logo)
        self.logo_label.pack(pady=(10, 2))

        self.version_label = ttk.Label(self.settings_frame, text="v12.0", font=("Helvetica", 10))
        self.version_label.pack(pady=(0, 7))
        
        self.separator = ttk.Separator(self.settings_frame, orient='horizontal')
        self.separator.pack(fill='x', pady=5)

        self.current_user_label = ttk.Label(self.settings_frame, text="", font=("Helvetica", 10))
        self.current_user_label.pack()

        if user.get_user():
            self.current_user_label.config(text=f"Logged in as: {user.get_user()}")

        self.separator = ttk.Separator(self.settings_frame, orient='horizontal')
        self.separator.pack(fill='x', pady=5)

        self.view_events_button = ttk.Button(self.settings_frame, text="Live Events", command=self.show_live_events, cursor="hand2", width=13)
        self.view_events_button.pack(pady=(20, 0))

        self.copy_frame = ttk.Frame(self.settings_frame)
        self.copy_frame.pack(pady=(15, 0))
        self.copy_button = ttk.Button(self.copy_frame, text="⟳", command=self.copy_to_clipboard, cursor="hand2", width=2, style='Large.TButton')
        self.copy_button.grid(row=0, column=0)
        self.password_result_label = ttk.Label(self.copy_frame, text="GB000000", font=("Helvetica", 10), wraplength=200)
        self.password_result_label.grid(row=0, column=1, padx=(5, 5))

    def fetch_and_save_events(self):
        url = os.getenv('ALL_EVENTS_API_URL')

        if not url:
            raise ValueError("ALL_EVENTS_API_URL environment variable is not set")

        try:
            response = requests.get(url)
            response.raise_for_status() 
            data = response.json()
        except requests.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch events: {e}")
            return None

        if not data:
            messagebox.showerror("Error", "Couldn't get any events from API")
            return None

        filename = os.path.join(NETWORK_PATH_PREFIX, 'events.json')

        if os.path.exists(filename):
            with open(filename, 'r') as f:
                existing_data = json.load(f)
        else:
            messagebox.showerror("Error", "Events file not found.")
            return None

        existing_data_map = {event['EventName']: event for event in existing_data}

        for event in data:
            existing_event = existing_data_map.get(event['EventName'])
            if existing_event:
                event['lastUpdate'] = existing_event.get('lastUpdate', '-')
                event['user'] = existing_event.get('user', '-')
            else:
                event['lastUpdate'] = '-'
                event['user'] = '-'

        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)

        return data

    def show_live_events(self):
        data = self.fetch_and_save_events()
        filename = os.path.join(NETWORK_PATH_PREFIX, 'events.json')
        if data:
            sorted_data = self.sort_events(data)
            live_events_window = tk.Toplevel(self.root)
            live_events_window.geometry("650x700")
            live_events_window.title("Live Events")
            live_events_window.iconbitmap('Monitor/splash.ico')
            screen_width = live_events_window.winfo_screenwidth()
            live_events_window.geometry(f"+{screen_width - 800}+50")
            live_events_window.resizable(False, False)
            live_events_frame = ttk.Frame(live_events_window)
            live_events_frame.pack(fill=tk.BOTH, expand=True)
            live_events_title = ttk.Label(live_events_frame, text="Live Events", font=("Helvetica", 12, "bold"))
            live_events_title.pack(pady=5)
            total_events_label = ttk.Label(live_events_frame, text=f"Total Events: {len(data)}")
            total_events_label.pack(pady=5)
            tree_frame = ttk.Frame(live_events_frame)
            tree_frame.pack(fill=tk.BOTH, expand=True)
            tree_scroll = ttk.Scrollbar(tree_frame)
            tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set, selectmode="extended")
            tree.pack(fill=tk.BOTH, expand=True)
            tree_scroll.config(command=tree.yview)
    
            tree["columns"] = ("EventCode", "numChildren", "EventDate", "lastUpdate", "user")
            tree.column("#0", width=200, minwidth=200)
            tree.column("EventCode", width=50, minwidth=50)
            tree.column("numChildren", width=50, minwidth=50)
            tree.column("EventDate", width=50, minwidth=50)
            tree.column("lastUpdate", width=120, minwidth=120)
            tree.column("user", width=10, minwidth=10)
            tree.heading("#0", text="Event Name", anchor=tk.W)
            tree.heading("EventCode", text="Event File", anchor=tk.W)
            tree.heading("numChildren", text="Markets", anchor=tk.W)
            tree.heading("EventDate", text="Event Date", anchor=tk.W)
            tree.heading("lastUpdate", text="Last Update", anchor=tk.W)
            tree.heading("user", text="User", anchor=tk.W)
    
            self.populate_tree(tree, sorted_data)
    
            def on_button_click():
                selected_items = tree.selection()
                for item_id in selected_items:
                    item = tree.item(item_id)
                    event_name = item['text']
                    for event in data:
                        if event['EventName'] == event_name:
                            markets = len(event["Meetings"])
                            original_last_update = event.get('lastUpdate', None)
                            if original_last_update and original_last_update != '-':
                                try:
                                    original_last_update = datetime.strptime(original_last_update, '%d-%m-%Y %H:%M:%S')
                                except ValueError:
                                    original_last_update = None
                            else:
                                original_last_update = None
                            event['lastUpdate'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
                            event['user'] = user.get_user()
                            if event['Meetings'][0]['EventCode'][3:5].lower() == 'ap':
                                antepost = True
                            else:
                                antepost = False
                            threading.Thread(target=self.log_update, args=(event_name, markets, antepost, original_last_update, user.get_user()), daemon=True).start()
                            break
            
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=4)
            
                self.populate_tree(tree, data)
    
            action_button = ttk.Button(live_events_frame, text="Update Event", command=on_button_click)
            action_button.pack(pady=10)
            update_events_label = ttk.Label(live_events_frame, text="Select an event (or multiple) and click 'Update Event' to log latest refresh.", wraplength=600)
            update_events_label.pack(pady=5)

        else:
            messagebox.showerror("Error", "Failed to fetch events. Please tell Sam.")

    def log_update(self, event_name, markets, antepost, last_update_time, user):

        if last_update_time:
            log_time = last_update_time.strftime('%H:%M')
        else:
            log_time = datetime.now().strftime('%H:%M')
        event_name = event_name.replace("-", "")
        now = datetime.now()
        date_string = now.strftime('%d-%m-%Y')
        
        big_events = [
            'Flat Racing Futures', 
            'National Hunt Futures', 
            'Cheltenham Festival Futures', 
            'International Racing Futures', 
            'Greyhound Futures', 
            'Football Futures', 
            'Tennis Futures', 
            'Golf Futures'
        ]
    
        log_file = os.path.join(NETWORK_PATH_PREFIX, f'logs/updatelogs/update_log_{date_string}.txt')
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    data = f.readlines()
            except IOError as e:
                print(f"Error reading log file: {e}")
                data = []
        else:
            data = []
    
        if last_update_time:
            time_diff = now - last_update_time
            hours_diff = time_diff.total_seconds() / 3600
        else:
            hours_diff = float('inf') 
    
        if antepost:
            score = round(0.3 * markets, 2)
            if event_name in big_events:
                score += 3
            elif event_name.lower() == 'mma Futures' or event_name == 'boxing Futures':
                score = round(0.08 * markets, 2)
            else:
                score += 1
        else:
            score = round(0.2 * markets, 2)
    
        if hours_diff < 4:
            score *= 0.4
    
        update = f"{log_time} - {user} - {score}\n"
    
        notification.log_notification(f"{user} updated {event_name} ({score:.2f})")
    
        course_index = None
        for i, line in enumerate(data):
            if line.strip() == event_name + ":":
                course_index = i
                break
    
        if course_index is not None:
            data.insert(course_index + 1, update)
        else:
            data.append(f"\n{event_name}:\n")
            data.append(update)
    
        try:
            with open(log_file, 'w') as f:
                f.writelines(data)
        except IOError as e:
            print(f"Error writing to log file: {e}")

    def populate_tree(self, tree, data):
        # Clear existing tree items
        for item in tree.get_children():
            tree.delete(item)
    
        sorted_data = self.sort_events(data)
    
        # Define tags for outdated events and separators
        tree.tag_configure('outdated', background='lightcoral')
        tree.tag_configure('separator', background='lightblue')
    
        ignored_events = ['TRP', 'SIS', 'Racing.', 'AUS']
        
        # Separate antepost and non-antepost events
        antepost_events = [event for event in sorted_data if len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() == 'ap']
        non_antepost_events = [event for event in sorted_data if len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() != 'ap' and not any(ignored in event["EventName"] for ignored in ignored_events)]
    
        # Insert separator for antepost events
        tree.insert("", "end", text="-- Antepost --", values=("", "", "", "", ""), tags=('separator',))
    
        # Insert antepost events
        for event in antepost_events:
            event_name = event["EventName"]
            event_file = event["Meetings"][0]["EventCode"] if event["Meetings"] else ""
            num_children = len(event["Meetings"])
            last_update = event.get("lastUpdate", "-")
            user = event.get("user", "-")
    
            # Check if the last update is more than two days old for antepost events
            if last_update != "-" and (datetime.now() - datetime.strptime(last_update, '%d-%m-%Y %H:%M:%S')).days > 2:
                tag = 'outdated'
            else:
                tag = ''
    
            parent_id = tree.insert("", "end", text=event_name, values=(event_file, num_children, "", last_update, user), tags=(tag,))
            for meeting in event["Meetings"]:
                meeting_name = meeting["EventName"]
                event_date = meeting["EventDate"]
                tree.insert(parent_id, "end", text=meeting_name, values=("", "", event_date, "", ""))
    
        # Insert separator for non-antepost events
        tree.insert("", "end", text="-- Non-Antepost --", values=("", "", "", "", ""), tags=('separator',))
    
        # Insert non-antepost events
        for event in non_antepost_events:
            event_name = event["EventName"]
            event_file = event["Meetings"][0]["EventCode"] if event["Meetings"] else ""
            num_children = len(event["Meetings"])
            last_update = event.get("lastUpdate", "-")
            user = event.get("user", "-")
    
            # Check if the last update is more than one day old for non-antepost events
            if last_update != "-" and (datetime.now() - datetime.strptime(last_update, '%d-%m-%Y %H:%M:%S')).days > 1:
                tag = 'outdated'
            else:
                tag = ''
    
            parent_id = tree.insert("", "end", text=event_name, values=(event_file, num_children, "", last_update, user), tags=(tag,))
            for meeting in event["Meetings"]:
                meeting_name = meeting["EventName"]
                event_date = meeting["EventDate"]
                tree.insert(parent_id, "end", text=meeting_name, values=("", "", event_date, "", ""))

    def sort_events(self, data):
        antepost_events = [event for event in data if len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() == 'ap']
        non_antepost_events = [event for event in data if not (len(event["Meetings"]) > 0 and event["Meetings"][0]["EventCode"][3:5].lower() == 'ap')]
        return antepost_events + non_antepost_events
    
    def generate_random_string(self):
        random_numbers = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        generated_string = 'GB' + random_numbers
        
        return generated_string

    def copy_to_clipboard(self):
        self.generated_string = self.generate_random_string()
        
        pyperclip.copy(self.generated_string)
        
        self.password_result_label.config(text=f"{self.generated_string}")
        self.copy_button.config(state=tk.NORMAL)
