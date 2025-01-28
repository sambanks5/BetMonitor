import tkinter as tk
from tkinter import ttk, font
from tkcalendar import DateEntry
import threading
import time
import json
from collections import defaultdict
from utils import access_data

class BetRuns:
    def __init__(self, root, database_manager):
        self.database_manager = database_manager
        self.root = root
        self.num_run_bets_var = tk.StringVar()
        self.combobox_var = tk.IntVar(value=50)
        self.num_run_bets = 2
        self.num_recent_files = 50
        self.previous_selected_date = None
        self.bet_runs_lock = threading.Lock()
        self.filters_visible = False  
        self.initialize_ui()
        self.initialize_text_tags()
        self.refresh_bets() 
    
    def initialize_ui(self):
        self.runs_frame = ttk.LabelFrame(self.root, style='Card', text="Runs on Selections")
        self.runs_frame.place(x=530, y=160, width=365, height=485)
        self.runs_frame.grid_columnconfigure(0, weight=1)
        self.runs_frame.grid_rowconfigure(0, weight=1)
        self.runs_frame.grid_columnconfigure(1, weight=0)

        self.runs_text = tk.Text(self.runs_frame, font=("Arial", 10), wrap='word', padx=10, pady=10, bd=0, fg="#000000", bg="#ffffff")
        self.runs_text.config(state='disabled') 
        self.runs_text.grid(row=0, column=0, sticky='nsew')

        self.spinbox_frame = ttk.Frame(self.runs_frame)
        self.spinbox_frame.grid(row=1, column=0, sticky='ew', pady=(2, 0))

        self.spinbox_frame.grid(row=1, column=0, sticky='ew')
        self.spinbox_frame.grid_columnconfigure(0, weight=1)
        self.spinbox_frame.grid_columnconfigure(1, weight=1)
        self.spinbox_frame.grid_columnconfigure(2, weight=1)

        self.spinbox = ttk.Spinbox(self.spinbox_frame, from_=2, to=10, textvariable=self.num_run_bets_var, width=2)
        self.num_run_bets_var.set("2")
        self.spinbox.grid(row=0, column=0, pady=(0, 3))
        self.num_run_bets_var.trace("w", self.set_num_run_bets)

        self.combobox_values = [20, 50, 100, 300, 1000, 2000]
        self.combobox = ttk.Combobox(self.spinbox_frame, textvariable=self.combobox_var, values=self.combobox_values, width=4)
        self.combobox_var.trace("w", self.set_recent_bets)
        self.combobox.grid(row=0, column=1, pady=(0, 3))

        style = ttk.Style()
        large_font = font.Font(size=13)
        style.configure('Large.TButton', font=large_font)

        self.runs_scroll = ttk.Scrollbar(self.runs_frame, orient='vertical', command=self.runs_text.yview, cursor="hand2")
        self.runs_scroll.grid(row=0, column=1, sticky='ns')
        self.runs_text.configure(yscrollcommand=self.runs_scroll.set)

        self.show_hide_button = ttk.Button(self.runs_frame, text='≡', command=self.toggle_filters, width=2, style='Large.TButton', cursor='hand2')
        self.show_hide_button.grid(row=2, column=0, pady=(2, 2), padx=5, sticky='w')

        self.refresh_button = ttk.Button(self.runs_frame, text='⟳', command=self.manual_refresh_bets, width=2, style='Large.TButton', cursor='hand2')
        self.refresh_button.grid(row=2, column=0, pady=(2, 2), padx=5, sticky='e')

        self.date_entry = DateEntry(self.runs_frame, width=15, background='#fecd45', foreground='white', borderwidth=1, date_pattern='dd/mm/yyyy')
        self.date_entry.grid(row=2, column=0, pady=(2, 2), padx=4, sticky='n')
        self.date_entry.bind("<<DateEntrySelected>>", lambda event: self.manual_refresh_bets())

        self.spinbox_frame.grid_remove()

    def toggle_filters(self):
        if self.filters_visible:
            self.spinbox_frame.grid_remove()
            self.show_hide_button.config(text='≡')
        else:
            self.spinbox_frame.grid()
            self.show_hide_button.config(text='≡')
        self.filters_visible = not self.filters_visible

    def set_recent_bets(self, *args):
        self.num_recent_files = self.combobox_var.get()
        self.manual_refresh_bets()

    def set_num_run_bets(self, *args):
        try:
            self.num_run_bets = int(self.num_run_bets_var.get())
            self.manual_refresh_bets()
        except ValueError:
            pass

    def bet_runs(self, num_bets, num_run_bets):
        def fetch_and_process_bets():
            if not self.bet_runs_lock.acquire(blocking=False):
                print("Bet runs update already in progress. Skipping this update.")
                return
            
            selected_date = self.date_entry.get_date().strftime('%d/%m/%Y')
            if self.previous_selected_date != selected_date:
                self.last_update_time = None
                self.previous_selected_date = selected_date

            try:
                retry_attempts = 3
                conn = None
                cursor = None

                for attempt in range(retry_attempts):
                    try:
                        conn, cursor = self.database_manager.get_connection()
                        if conn is not None and cursor is not None:
                            break
                    except Exception as e:
                        print(f"Attempt {attempt + 1}: Failed to connect to the database. Error: {e}")
                        if attempt < retry_attempts - 1:
                            print("Retrying in 2 seconds...")
                            time.sleep(2)
                        else:
                            self.update_ui_with_message("Failed to connect to the database after multiple attempts.")
                            return

                if conn is None or cursor is None:
                    self.update_ui_with_message("Failed to establish a database connection.")
                    return

                for attempt in range(retry_attempts):
                    try:
                        # current_date = datetime.now().strftime('%d/%m/%Y')
                        cursor.execute("SELECT id, selections FROM database WHERE date = ? ORDER BY time DESC LIMIT ?", (selected_date, num_bets,))
                        database_data = cursor.fetchall()

                        if not database_data:
                            self.update_ui_with_message("No bets found for the current date or database not found.")
                            return

                        selection_to_bets = defaultdict(list)

                        for bet in database_data:
                            bet_id = bet[0] 
                            if ':' in bet_id:
                                continue 
                            selections = bet[1] 
                            if selections:
                                try:
                                    selections = json.loads(selections) 
                                except json.JSONDecodeError:
                                    continue  
                                for selection in selections:
                                    selection_name = selection[0]
                                    selection_to_bets[selection_name].append(bet_id)

                        sorted_selections = sorted(selection_to_bets.items(), key=lambda item: len(item[1]), reverse=True)

                        self.update_ui_with_selections(sorted_selections, num_run_bets, cursor)
                        break 
                    except Exception as e:
                        print(f"Attempt {attempt + 1}: An error occurred while processing bets. Error: {e}")
                        if attempt < retry_attempts - 1:
                            print("Retrying in 2 seconds...")
                            time.sleep(2)
                        else:
                            self.update_ui_with_message(f"An error occurred after multiple attempts: {e}\nPlease try refreshing.")
                            return
            finally:
                if conn:
                    conn.close()
                self.bet_runs_lock.release()
        threading.Thread(target=fetch_and_process_bets, daemon=True).start()

    def update_ui_with_message(self, message):
        self.runs_text.config(state="normal")
        self.runs_text.delete('1.0', tk.END)
        self.runs_text.insert('end', message)
        self.runs_text.config(state="disabled")
    
    def update_ui_with_selections(self, sorted_selections, num_run_bets, cursor):
        vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
        enhanced_places = reporting_data.get('enhanced_places', [])
        self.runs_text.config(state="normal")
        self.runs_text.delete('1.0', tk.END)
        
        for selection, bet_numbers in sorted_selections:
            if len(bet_numbers) >= num_run_bets:
                selection_name = selection.split(' - ')[1] if ' - ' in selection else selection
        
                matched_odds = None
                for om_event, om_selections in todays_oddsmonkey_selections.items():
                    for om_sel in om_selections:
                        if selection_name == om_sel[0]:
                            matched_odds = float(om_sel[1])
                            break
                    if matched_odds is not None:
                        break
        
                if matched_odds is not None:
                    self.runs_text.insert(tk.END, f"{selection} | OM Lay: {matched_odds}\n", "oddsmonkey")
                else:
                    self.runs_text.insert(tk.END, f"{selection}\n")
        
                for bet_number in bet_numbers:
                    cursor.execute("SELECT time, customer_ref, risk_category, selections FROM database WHERE id = ?", (bet_number,))
                    bet_info = cursor.fetchone()
                    if bet_info:
                        bet_time = bet_info[0]
                        customer_ref = bet_info[1]
                        risk_category = bet_info[2]
                        selections = bet_info[3]
                        if selections:
                            try:
                                selections = json.loads(selections) 
                            except json.JSONDecodeError:
                                continue 
                            for sel in selections:
                                if selection == sel[0]:
                                    if risk_category == 'M' or risk_category == 'C':
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "risk")
                                    elif risk_category == 'W':
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "watchlist")
                                    elif customer_ref in vip_clients:
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "vip")
                                    elif customer_ref in newreg_clients:
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n", "newreg")
                                    else:
                                        self.runs_text.insert(tk.END, f" - {bet_time} - {bet_number} | {customer_ref} ({risk_category}) at {sel[1]}\n")
        
                meeting_time = ' '.join(selection.split(' ')[:2])
        
                if meeting_time in enhanced_places:
                    self.runs_text.insert(tk.END, 'Enhanced Place Race\n', "oddsmonkey")
                
                self.runs_text.insert(tk.END, f"\n")
    
        self.runs_text.config(state=tk.DISABLED)

    def initialize_text_tags(self):
        self.runs_text.tag_configure("risk", foreground="#ad0202")
        self.runs_text.tag_configure("watchlist", foreground="#e35f00")
        self.runs_text.tag_configure("vip", foreground="#009685")
        self.runs_text.tag_configure("newreg", foreground="purple")
        self.runs_text.tag_configure("oddsmonkey", foreground="#ff00e6")

    def manual_refresh_bets(self):
        num_bets = self.num_recent_files
        num_run_bets = self.num_run_bets
        self.bet_runs(num_bets, num_run_bets)
        
    def refresh_bets(self):
        scroll_pos = self.runs_text.yview()[0]

        num_bets = self.num_recent_files
        num_run_bets = self.num_run_bets

        if scroll_pos <= 0.04:
            self.bet_runs(num_bets, num_run_bets)
        else:
            pass

        self.root.after(20000, self.refresh_bets)
