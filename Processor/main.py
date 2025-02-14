import os
import sqlite3
import threading
import tkinter as tk
import time
import schedule
from watchdog.observers import Observer
from utils import notification, bet_import_handler, data_fetcher, evt_gen
from config import ARCHIVE_DATABASE_PATH, executor, get_path, set_path, get_last_processed_time, set_last_processed_time
from datetime import datetime, timedelta
from tkinter import Toplevel, filedialog, scrolledtext, ttk
from PIL import Image, ImageTk

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Bet Processor v4.0')
        self.geometry('800x300')

        # Get the absolute path of the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(current_dir, 'splash.ico')

        self.iconbitmap(icon_path)
        self.tk.call('source', os.path.join(current_dir, 'Forest-ttk-theme-master/forest-light.tcl'))
        ttk.Style().theme_use('forest-light')
        style = ttk.Style(self)

        style.configure('TButton', padding=(5, 5))

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=2)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(5, weight=1)

        self.text_area = scrolledtext.ScrolledText(self, undo=True)
        self.text_area['font'] = ('helvetica', '12')
        self.text_area.grid(row=0, column=0, rowspan=7, sticky='nsew')

        image = Image.open(icon_path)
        image = image.resize((70, 70)) 
        self.logo = ImageTk.PhotoImage(image)

        self.logo_label = ttk.Label(self, image=self.logo)
        self.logo_label.grid(row=0, column=1) 

        self.logo_label.bind('<Button-1>', self.run_staff_report_notification)

        self.reprocess_button = ttk.Button(self, text="Reprocess Bets", command=self.open_reprocess_window, style='TButton', width=20)
        self.reprocess_button.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

        self.archive_button = ttk.Button(self, text="Archive", command=self.open_archive_window, style='TButton', width=20)
        self.archive_button.grid(row=3, column=1, padx=5, pady=5, sticky='ew')

        self.set_path_button = ttk.Button(self, text="BWW Folder", command=self.set_bet_path, style='TButton', width=20)
        self.set_path_button.grid(row=4, column=1, padx=5, pady=5, sticky='ew')

        self.evt_gen_button = ttk.Button(self, text="Event Generator", command=lambda: evt_gen.EventGenerator(self), style='TButton', width=20)
        self.evt_gen_button.grid(row=5, column=1, padx=5, pady=5, sticky='ew')

        self.progress_bar = ttk.Progressbar(self, mode='indeterminate')
        self.progress_bar.grid(row=6, column=1, padx=5, pady=5)

        self.bind('<Destroy>', self.on_destroy)

    def start_progress(self):
        self.progress_bar.start()
        self.progress_bar.grid()

    def stop_progress(self):
        self.progress_bar.stop()
        self.progress_bar.grid_remove()

    def run_staff_report_notification(self, event):
        executor.submit(notification.staff_report_notification)
    
    def set_bet_path(self):
        new_folder_path = filedialog.askdirectory()
        if new_folder_path:
            set_path(new_folder_path)

    def open_archive_window(self):
        self.archive_window = Toplevel(self)
        self.archive_window.title("Archive")
        self.archive_window.geometry("300x150")

        ttk.Label(self.archive_window, text="Archive anything over 2 months old.").pack(pady=10)
        
        reprocess_button = ttk.Button(self.archive_window, text="Archive", command=self.archive_old_data)
        reprocess_button.pack(pady=10)

    def create_archive_database(self):
        if not os.path.exists(ARCHIVE_DATABASE_PATH):
            conn = sqlite3.connect(ARCHIVE_DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS database (
                    id TEXT PRIMARY KEY,
                    time TEXT,
                    type TEXT,
                    customer_ref TEXT,
                    text_request TEXT,
                    error_message TEXT,
                    requested_type TEXT,
                    requested_stake REAL,
                    selections TEXT,
                    risk_category TEXT,
                    bet_details TEXT,
                    unit_stake REAL,
                    total_stake REAL,
                    bet_type TEXT,
                    date TEXT,
                    sports TEXT
                )
            """)
            conn.commit()
            conn.close()
            print(f"Archive database created at {ARCHIVE_DATABASE_PATH}")

    def archive_old_data(self):
        try:
            # Create the archive database if it does not exist
            self.create_archive_database()

            # Connect to the main and archive databases
            main_conn = sqlite3.connect('wager_database.sqlite')
            archive_conn = sqlite3.connect(ARCHIVE_DATABASE_PATH)
            main_cursor = main_conn.cursor()
            archive_cursor = archive_conn.cursor()

            # Calculate the cutoff date (2 months ago)
            cutoff_date = datetime.now() - timedelta(days=60)
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')

            # Select data older than the cutoff date from the main database
            main_cursor.execute("""
                SELECT id, time, type, customer_ref, text_request, error_message, requested_type, requested_stake, selections, risk_category, bet_details, unit_stake, total_stake, bet_type, date, sports
                FROM database
                WHERE DATE(substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)) < ?
            """, (cutoff_date_str,))
            old_data = main_cursor.fetchall()

            # Insert the old data into the archive database
            archive_cursor.executemany("""
                INSERT INTO database (id, time, type, customer_ref, text_request, error_message, requested_type, requested_stake, selections, risk_category, bet_details, unit_stake, total_stake, bet_type, date, sports)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, old_data)
            archive_conn.commit()

            # Delete the old data from the main database
            main_cursor.execute("""
                DELETE FROM database
                WHERE DATE(substr(date, 7, 4) || '-' || substr(date, 4, 2) || '-' || substr(date, 1, 2)) < ?
            """, (cutoff_date_str,))
            main_conn.commit()

            # Reclaim unused space in the main database
            main_cursor.execute("VACUUM")
            main_conn.commit()

            print(f"Archived {len(old_data)} records to {ARCHIVE_DATABASE_PATH}")

        except Exception as e:
            print(f"Error archiving old data: {e}")
        finally:
            self.archive_window.destroy()
            main_conn.close()
            archive_conn.close()

    def open_reprocess_window(self):
        top = Toplevel(self)
        top.title("Reprocess Bets")
        top.geometry("365x150")

        ttk.Label(top, text="Days to go back:").grid(column=0, row=0, padx=10, pady=10)
        days_spinbox = ttk.Spinbox(top, from_=1, to=12, width=5)
        days_spinbox.grid(column=1, row=0, padx=10, pady=10)

        ttk.Label(top, text="Anything over a day can take up to 10 minutes to complete.").grid(column=0, row=1, columnspan=2, padx=10, pady=10)

        reprocess_button = ttk.Button(top, text="Reprocess", command=lambda: self.start_reprocess(int(days_spinbox.get()), top))
        reprocess_button.grid(column=0, row=2, columnspan=2, padx=10, pady=10)

    def start_reprocess(self, days_back, window):
        process_thread = threading.Thread(target=bet_import_handler.reprocess_bets, args=(days_back, get_path(), self))
        process_thread.start()
        window.destroy()
        
    def log_message(self, message):
        current_time = datetime.now().strftime('%H:%M:%S')
        self.text_area.insert(tk.END, f'{current_time}: {message}\n')  
        self.text_area.see(tk.END)

        max_lines = 1500
        lines = self.text_area.get('1.0', tk.END).splitlines()
        if len(lines) > max_lines:
            self.text_area.delete('1.0', f'{len(lines) - max_lines + 1}.0')

    def on_destroy(self, event):
        self.stop_main_loop = True

def main(app):
    event_handler = bet_import_handler.FileHandler(app)
    observer = None
    observer_started = False
    app.log_message('Bet Processor - import, parse and store daily bet data.\n')
    notification.log_notification("Processor Started")
    data_updater = data_fetcher.DataUpdater(app)
    schedule.every(50).seconds.do(notification.check_closures_and_race_times)

    notification.fetch_and_print_new_events()
    schedule.every(10).minutes.do(notification.fetch_and_print_new_events)

    notification.run_activity_report_notification()
    schedule.every(1).minute.do(notification.run_activity_report_notification)

    notification.run_staff_report_notification()
    schedule.every(2).hours.do(notification.run_staff_report_notification)

    schedule.every().day.at("00:05").do(notification.clear_processed)

    while not app.stop_main_loop:
        schedule.run_pending()

        if not os.path.exists(get_path()):
            print(f"Error: The path {get_path()} does not exist.")
            app.set_bet_path()
            if not os.path.exists(get_path()):
                continue  

        if not observer_started or datetime.now() - get_last_processed_time() > timedelta(minutes=3):
            if observer_started:
                observer.stop()
                observer.join()
            observer = Observer()
            observer.schedule(event_handler, get_path(), recursive=False)
            observer.start()
            observer_started = True
            app.log_message('Watchdog observer watching folder ' + get_path() + '\n' )
            set_last_processed_time(datetime.now())

        try:
            time.sleep(1) 
        except Exception as e:
            app.log_message(f"An error occurred: {e}")
            app.reprocess() 
            time.sleep(10)
        except KeyboardInterrupt:
            break

    if observer is not None:
        observer.stop()
        notification.log_notification("Processor Stopped")
        observer.join()

if __name__ == "__main__":
    app = Application()
    app.stop_main_loop = False
    app.main_loop = threading.Thread(target=main, args=(app,))
    app.main_loop.start()
    app.mainloop()