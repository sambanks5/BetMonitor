from tkinter import ttk
import os
import threading
import requests
from utils.access_data import access_data

class Next3Panel:
    def __init__(self, root):
        self.root = root
        self.last_click_time = 0 
        _, _, _, reporting_data = access_data()
        self.enhanced_places = reporting_data.get('enhanced_places', [])

        # Load API URLs from environment variables
        self.horse_url = os.getenv('NEXT_3_HORSE_API_URL')
        self.dogs_url = os.getenv('NEXT_3_DOGS_API_URL')

        # Ensure the API URLs are loaded correctly
        if not self.horse_url:
            raise ValueError("NEXT_3_HORSE_API_URL environment variable is not set")
        if not self.dogs_url:
            raise ValueError("NEXT_3_DOGS_API_URL environment variable is not set")

        self.initialize_ui()
        self.run_display_next_3()
    
    def run_display_next_3(self):
        threading.Thread(target=self.display_next_3, daemon=True).start()
        self.root.after(10000, self.run_display_next_3)
    
    def initialize_ui(self):
        next_races_frame = ttk.Frame(self.root)
        next_races_frame.place(x=5, y=925, width=890, height=55)

        horses_frame = ttk.Frame(next_races_frame, style='Card')
        horses_frame.place(relx=0, rely=0.05, relwidth=0.50, relheight=0.9)

        self.horse_labels = [ttk.Label(horses_frame, justify='center', font=("Helvetica", 8, "bold")) for _ in range(3)]
        for i, label in enumerate(self.horse_labels):
            label.grid(row=0, column=i, padx=0, pady=5)
            horses_frame.columnconfigure(i, weight=1)

        greyhounds_frame = ttk.Frame(next_races_frame, style='Card')
        greyhounds_frame.place(relx=0.51, rely=0.05, relwidth=0.49, relheight=0.9)

        self.greyhound_labels = [ttk.Label(greyhounds_frame, justify='center', font=("Helvetica", 8, "bold")) for _ in range(3)]
        for i, label in enumerate(self.greyhound_labels):
            label.grid(row=0, column=i, padx=0, pady=5)
            greyhounds_frame.columnconfigure(i, weight=1)
    
    def process_data(self, data, labels_type):
        labels = self.horse_labels if labels_type == 'horse' else self.greyhound_labels
        for i, event in enumerate(data[:3]):
            meeting_name = event.get('meetingName', '')
            status = event.get('status', '')
            hour = str(event.get('hour', ''))
            ptype = event.get('pType', '')
            minute = str(event.get('minute', '')).zfill(2) 
            time = f"{hour}:{minute}"
            
            if len(meeting_name) > 14:
                meeting_name = meeting_name[:14] + "'"

            if not status:
                status = '-'
            if ptype == 'Board Price':
                ptype = 'BP'
            elif ptype == 'Early Price':
                ptype = 'EP'
            elif ptype == 'S.P. Only':
                ptype = 'SP'
            else:
                ptype = '-'

            race = f"{meeting_name}, {time}"

            if race in self.enhanced_places:
                labels[i].config(foreground='#ff00e6')
            else:
                labels[i].config(foreground='black')

            labels[i].config(text=f"{race} ({ptype})\n{status}")

    def display_next_3(self):
        headers = {"User-Agent": "Mozilla/5.0 ..."}
        horse_response = requests.get(self.horse_url, headers=headers)
        greyhound_response = requests.get(self.dogs_url, headers=headers)

        if horse_response.status_code == 200 and greyhound_response.status_code == 200:
            horse_data = horse_response.json()
            greyhound_data = greyhound_response.json()

            self.root.after(0, self.process_data, horse_data, 'horse')
            self.root.after(0, self.process_data, greyhound_data, 'greyhound')
        else:
            print("Error: The response from the API is not OK.")
