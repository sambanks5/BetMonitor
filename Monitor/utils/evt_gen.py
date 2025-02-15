import os
import requests
from tkinter import Toplevel, Label, ttk
from tkinter import StringVar, messagebox
import threading

class EventGenerator:
    def __init__(self, app):
        self.app = app
        self.sports_data = []
        self.leagues_data = []
        self.open_window(self.app)

    def open_window(self, app):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, 'splash.ico')
        archive_window = Toplevel(app)
        archive_window.title("Event Generator")
        archive_window.geometry("300x320")
        # archive_window.iconbitmap(icon_path)

        # Create a label
        label = Label(archive_window, text="Event Generator", justify='center', font=("Helvetica", 20))
        label.pack( pady=15)

        # Create sports selection combobox
        self.sports_selection = ttk.Combobox(archive_window, state="readonly", )
        self.sports_selection.pack(pady=5)
        self.sports_selection.bind("<<ComboboxSelected>>", self.on_sport_selected)

        # Create league selection combobox
        self.league_selection = ttk.Combobox(archive_window, state="readonly")
        self.league_selection.pack(pady=5)

        # Create a progress bar
        self.progress_var = StringVar()
        self.progress_label = Label(archive_window, textvariable=self.progress_var, justify='center')
        self.progress_label.pack()

        self.generate_button = ttk.Button(archive_window, text="Generate", command=self.generate_event)
        self.generate_button.pack(pady=5)

        self.run_start_bat_button = ttk.Button(archive_window, text="Reboot Service", command=self.run_start_bat)
        self.run_start_bat_button.pack(pady=10)

        # Fetch sports data
        self.fetch_sports_data()

    def fetch_sports_data(self):
        self.progress_var.set("Loading sports data...")
        threading.Thread(target=self._fetch_sports_data).start()

    def _fetch_sports_data(self):
        try:
            response = requests.get("https://be.geoff-banks.com/_/items/sports?access_token=RRjlZrh9k4rZVnC4ZkzguNFnjRvELg1M")
            if response.status_code == 200:
                self.sports_data = response.json().get('data', [])
                sports_names = [sport['name'] for sport in self.sports_data]
                self.sports_selection['values'] = sports_names
            else:
                self.sports_data = []
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch sports data: {e}")
        finally:
            self.progress_var.set("")

    def on_sport_selected(self, event):
        selected_sport_name = self.sports_selection.get()
        selected_sport = next((sport for sport in self.sports_data if sport['name'] == selected_sport_name), None)
        if selected_sport:
            sport_id = selected_sport['sport_id']
            self.league_selection.set('')  # Clear the league selection combobox
            self.league_selection['values'] = []  # Clear the values in the league selection combobox
            self.fetch_leagues_data(sport_id)

    def fetch_leagues_data(self, sport_id):
        self.progress_var.set("Loading leagues data...")
        threading.Thread(target=self._fetch_leagues_data, args=(sport_id,)).start()

    def _fetch_leagues_data(self, sport_id):
        try:
            response = requests.get(f"http://192.168.0.145:4000/GetUniqLeagueListFromEventList?SportId={sport_id}")
            if response.status_code == 200:
                self.leagues_data = response.json()
                league_names = [league['league']['name'] for league in self.leagues_data]
                self.league_selection['values'] = league_names
            else:
                self.leagues_data = []
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Connection Error", "Failed to connect to the server. Please click the 'Reboot Service' button.")
            print("Connection Error: ", e)
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch leagues data: {e}")
        finally:
            self.progress_var.set("")

    def generate_event(self):
        selected_sport_name = self.sports_selection.get()
        selected_league_name = self.league_selection.get()
        selected_sport = next((sport for sport in self.sports_data if sport['name'] == selected_sport_name), None)
        selected_league = next((league for league in self.leagues_data if league['league']['name'] == selected_league_name), None)
        
        if selected_sport and selected_league:
            sport_id = selected_sport['sport_id']
            league_id = selected_league['league']['id']
            try:
                response = requests.get(f"http://192.168.0.145:4000/GenerateFileByLeagueId?SportId={sport_id}&LeagueId={league_id}")
                if response.status_code == 200:
                    messagebox.showinfo("Success", "Event file generated successfully.")
                else:
                    messagebox.showerror("Error", "Failed to generate event file.")
            except requests.exceptions.RequestException as e:
                messagebox.showerror("Error", f"Failed to generate event file: {e}")
        else:
            messagebox.showerror("Error", "Please select both a sport and a league.")

    def run_start_bat(self):
        desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        bat_file_path = os.path.join(desktop_path, 'start.bat')
        os.system(f'start {bat_file_path}')