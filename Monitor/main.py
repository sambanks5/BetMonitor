import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from PIL import Image, ImageTk
from ui import BetFeed, RaceUpdaton, Next3Panel, BetRuns, Notebook, Settings, ClientWizard
from utils import schedule_data_updates, notification, user_notification, import_reporting, user, login, resource_path
from config import NETWORK_PATH_PREFIX
from utils.db_manager import DatabaseManager


class BetViewerApp:
    def __init__(self, root, database_manager):
        self.database_manager = database_manager
        self.root = root
        self.initialize_ui()
        login.user_login()
        self.start_background_tasks()
        self.initialize_modules()

    def initialize_ui(self):
        self.import_logo()
        self.root.title("Bet Viewer")
        self.root.tk.call('source', resource_path.get_resource_path('Forest-ttk-theme-master/forest-light.tcl'))
        ttk.Style().theme_use('forest-light')
        width = 900
        height = 1007
        screenwidth = self.root.winfo_screenwidth()
        screenheight = self.root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (screenwidth - width - 10), 0)
        self.root.geometry(alignstr)
        self.root.resizable(False, False)
        self.setup_menu_bar()

    def import_logo(self):
        logo_image = Image.open(resource_path.get_resource_path('splash.ico'))
        logo_image.thumbnail((70, 70))
        self.company_logo = ImageTk.PhotoImage(logo_image)
        self.root.iconbitmap(resource_path.get_resource_path('splash.ico'))
        return self.company_logo

    def setup_menu_bar(self):
        menu_bar = tk.Menu(self.root)
        options_menu = tk.Menu(menu_bar, tearoff=0)
        options_menu.add_command(label="Change User", command=self.user_login, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Report Monitor Issue", command=self.report_monitor_issue, foreground="#000000", background="#ffffff")
        options_menu.add_command(label="Apply Bonus Points", command=self.apply_bonus_points, foreground="#000000", background="#ffffff")
        options_menu.add_separator(background="#ffffff")
        options_menu.add_command(label="Exit", command=self.root.quit, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Options", menu=options_menu)
        
        utils_menu = tk.Menu(menu_bar, tearoff=0)
        utils_menu.add_command(label="Import Reporting Data", command=self.import_reporting_data, foreground="#000000", background="#ffffff")
        menu_bar.add_cascade(label="Utilities", menu=utils_menu)

        menu_bar.add_command(label="Client", command=lambda: self.open_client_wizard("Factoring"), foreground="#000000", background="#ffffff")
        menu_bar.add_command(label="About", command=self.about, foreground="#000000", background="#ffffff")

        self.root.config(menu=menu_bar)

    def start_background_tasks(self):
        threading.Thread(target=schedule_data_updates, daemon=True).start()
        threading.Thread(target=self.database_manager.periodic_cache_update, daemon=True).start()

    def initialize_modules(self):
        self.bet_feed = BetFeed(self.root, self.database_manager)
        self.race_updation = RaceUpdaton(self.root)
        self.next3_panel = Next3Panel(self.root)
        self.bet_runs = BetRuns(self.root, self.database_manager)
        self.notebook = Notebook(self.root, self.database_manager)
        self.settings = Settings(self.root)

    def open_client_wizard(self, default_tab="Factoring"):
        ClientWizard(self.root, default_tab)

    def user_login(self):
        login.user_login()

    def import_reporting_data(self):
        import_reporting_window = tk.Toplevel(self.root)
        import_reporting_window.geometry("290x310")
        import_reporting_window.title("Import Reporting")
        import_reporting_window.iconbitmap(resource_path.get_resource_path('splash.ico'))
        screen_width = import_reporting_window.winfo_screenwidth()
        import_reporting_window.geometry(f"+{screen_width - 350}+50")
    
        import_reporting_frame = ttk.Frame(import_reporting_window, style='Card')
        import_reporting_frame.place(x=5, y=5, width=280, height=300)
    
        import_reporting_label = ttk.Label(import_reporting_frame, text="Import Reporting Data", font=("Helvetica", 12, "bold"))
        import_reporting_label.pack(pady=20)

        import_reporting_description = ttk.Label(import_reporting_frame, text="Import tomorrows Horse & Greyhound racing into reporting sheet.\nIf you want to import today's racing, check the box.", wraplength=240, justify='center')
        import_reporting_description.pack(pady=10)

        checkbox_frame = ttk.Frame(import_reporting_frame)
        checkbox_frame.pack(pady=10)
    
        day_label = ttk.Label(checkbox_frame, text="Import today's races:")
        day_label.grid(row=0, column=0)
    
        import_todays_var = tk.BooleanVar()
        import_todays_checkbox = ttk.Checkbutton(checkbox_frame, variable=import_todays_var)
        import_todays_checkbox.grid(row=0, column=1)
    
        progress_note = ttk.Label(import_reporting_frame, text="---", wraplength=250, anchor='center', justify='center')
        progress_note.pack(pady=10)
    
        import_reporting_button = ttk.Button(
            import_reporting_frame, 
            text="Import", 
            command=lambda: self.start_import_reporting(import_todays_var.get(), progress_note)
        )
        import_reporting_button.pack(pady=10)

    def start_import_reporting(self, current_day, progress_note):
        progress_note.config(text="Importing data...")
        self.root.update_idletasks()
        import_reporting(current_day, progress_note)

    def report_monitor_issue(self):
        if not user.get_user():
            login.user_login()

        def submit_issue():
            issue = issue_textbox.get("1.0", tk.END).strip()
            if issue:
                issues_file_path = os.path.join(NETWORK_PATH_PREFIX, 'issues.txt')
                try:
                    with open(issues_file_path, 'a') as f:
                        f.write(f"{user.get_user()} - {issue}\n\n")
                    messagebox.showinfo("Submitted", "Your issue/suggestion has been submitted.")
                    issue_window.destroy()
                except FileNotFoundError:
                    messagebox.showerror("File Not Found", f"Could not find the file: {issues_file_path}")
            else:
                messagebox.showwarning("Empty Issue", "Please describe the issue or suggestion before submitting.")

        issue_window = tk.Toplevel(self.root)
        issue_window.title("Report Monitor Issue")
        issue_window.geometry("400x300")

        issue_label = ttk.Label(issue_window, text="Describe issue/suggestion:")
        issue_label.pack(pady=10)

        issue_textbox = tk.Text(issue_window, wrap='word', height=10)
        issue_textbox.pack(padx=10, pady=10, fill='both', expand=True)

        submit_button = ttk.Button(issue_window, text="Submit", command=submit_issue)
        submit_button.pack(pady=10)

    def open_settings(self):
        settings_window = tk.Toplevel(self.root)
        settings_window.geometry("270x370")
        settings_window.title("Settings")
        settings_window.iconbitmap(resource_path.get_resource_path('splash.ico'))
        screen_width = settings_window.winfo_screenwidth()
        settings_window.geometry(f"+{screen_width - 350}+50")
        
        settings_frame = ttk.Frame(settings_window, style='Card')
        settings_frame.place(x=5, y=5, width=260, height=360)
        
    def apply_bonus_points(self):
        if user.get_user() not in ['SB', 'DF']:
            messagebox.showerror("Error", "You do not have permission to apply bonus points.")
            return
    
        def submit_bonus():
            selected_full_name = users_combobox.get()
            points = points_entry.get()
            if not selected_full_name or not points:
                messagebox.showerror("Error", "Please select a user and enter the points.")
                return
    
            try:
                points = float(points)
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number for points.")
                return
    
            selected_user = None
            for key, value in user.USER_NAMES.items():
                if value == selected_full_name:
                    selected_user = key
                    break
    
            if not selected_user:
                messagebox.showerror("Error", "Selected user not found.")
                return
    
            now = datetime.now()
            date_string = now.strftime('%d-%m-%Y')
            time_string = now.strftime('%H:%M')
            log_file = os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', f'update_log_{date_string}.txt')
    
            update = f"{time_string} - {selected_user} - {points:.2f}\n"
            notification.log_notification(f"{selected_user} received a bonus of {points:.2f} points from {user.get_user()}", True)
    
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        data = f.readlines()
                except IOError as e:
                    print(f"Error reading log file: {e}")
                    data = []
            else:
                data = []
    
            bonus_index = None
            for i, line in enumerate(data):
                if line.strip() == "Bonus:":
                    bonus_index = i
                    break
    
            if bonus_index is not None:
                # Insert the update under the existing "Bonus:" header
                data.insert(bonus_index + 1, update)
            else:
                # Add a new "Bonus:" header and the update
                data.append(f"\nBonus:\n")
                data.append(update)
    
            try:
                with open(log_file, 'w') as f:
                    f.writelines(data)
                print(f"Bonus points logged for {selected_user}")
                messagebox.showinfo("Success", f"Bonus points logged for {selected_user}")
                bonus_window.destroy()
            except IOError as e:
                print(f"Error writing to log file: {e}")
                messagebox.showerror("Error", "Failed to log bonus points.")
    
        bonus_window = tk.Toplevel(self.root)
        bonus_window.geometry("270x270")
        bonus_window.title("Apply Bonus")
        bonus_window.iconbitmap(resource_path.get_resource_path('splash.ico'))
        screen_width = bonus_window.winfo_screenwidth()
        bonus_window.geometry(f"+{screen_width - 350}+50")
        bonus_frame = ttk.Frame(bonus_window, style='Card')
        bonus_frame.place(x=5, y=5, width=260, height=260)
    
        user_label = ttk.Label(bonus_frame, text="Select User:")
        user_label.pack(pady=5)
        users_combobox = ttk.Combobox(bonus_frame, values=list(user.USER_NAMES.values()), state="readonly")
        users_combobox.pack(pady=10)
    
        points_label = ttk.Label(bonus_frame, text="Enter Points:")
        points_label.pack(pady=5)
        points_entry = ttk.Entry(bonus_frame)
        points_entry.pack(pady=5)
    
        submit_button = ttk.Button(bonus_frame, text="Submit", command=submit_bonus)
        submit_button.pack(pady=20)

    def user_notification(self):
        user_notification(self.root)

    def about(self):
        messagebox.showinfo("About", "Geoff Banks Bet Monitoring\n     Sam Banks 2024")

if __name__ == "__main__":
    database_manager = DatabaseManager() 
    root = tk.Tk()
    app = BetViewerApp(root, database_manager)
    root.mainloop()