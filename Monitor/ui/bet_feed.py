## bet_feed.py - UI component for displaying the bet feed and applying filters to the feed

import threading
import tkinter as tk
import tkinter.font as font
from datetime import datetime, timedelta
import sqlite3
import time
import json
from tkinter import ttk
from tkcalendar import DateEntry
from utils import access_data
from config import USER_NAMES, get_user, set_user

class BetFeed:
    def __init__(self, root, database_manager):
        self.database_manager = database_manager
        self.root = root
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None, 'selection': None, 'type': None}
        self.feed_lock = threading.Lock()
        self.last_update_time = None
        self.previous_selected_date = None 
        self.filters_visible = False  # Track the visibility of the filter frame, set to False to hide by default
        self.initialize_ui()
        self.initialize_text_tags()
        self.start_feed_update()

    def initialize_ui(self):
        style = ttk.Style()
        large_font = font.Font(size=13)
        style.configure('Large.TButton', font=large_font)

        self.feed_frame = ttk.LabelFrame(self.root, style='Card', text="Bet Feed")
        self.feed_frame.place(x=5, y=5, width=520, height=640)
        self.feed_frame.grid_columnconfigure(0, weight=1)
        self.feed_frame.grid_columnconfigure(1, weight=0)
        self.feed_frame.grid_rowconfigure(0, weight=1)

        self.limit_bets_var = tk.BooleanVar(value=True)

        self.feed_text = tk.Text(self.feed_frame, font=("Helvetica", 10, "bold"), wrap='word', padx=10, pady=10, bd=0, fg="#000000")
        self.feed_text.config(state='disabled')
        self.feed_text.grid(row=0, column=0, sticky='nsew')
        
        self.feed_scroll = ttk.Scrollbar(self.feed_frame, orient='vertical', command=self.feed_text.yview, cursor="hand2")
        self.feed_scroll.grid(row=0, column=1, sticky='ns')
        self.feed_text.configure(yscrollcommand=self.feed_scroll.set)

        self.filter_frame = ttk.Frame(self.feed_frame)
        self.filter_frame.grid(row=1, column=0, sticky='ew', pady=(2, 0), padx=(11, 0))

        self.filter_frame.grid_rowconfigure(0, weight=1)
        self.filter_frame.grid_rowconfigure(1, weight=1)
        self.filter_frame.grid_rowconfigure(2, weight=1)
        self.filter_frame.grid_columnconfigure(0, weight=0)
        self.filter_frame.grid_columnconfigure(1, weight=0)
        self.filter_frame.grid_columnconfigure(2, weight=1)
        self.filter_frame.grid_columnconfigure(3, weight=2)
        self.filter_frame.grid_columnconfigure(4, weight=1)
        self.filter_frame.grid_columnconfigure(5, weight=1)
        self.filter_frame.grid_columnconfigure(6, weight=1)
        self.filter_frame.grid_columnconfigure(7, weight=1)
        self.filter_frame.grid_columnconfigure(8, weight=1)
        self.filter_frame.grid_columnconfigure(9, weight=1)

        self.username_filter_entry = ttk.Entry(self.filter_frame, width=8)
        self.username_filter_entry.grid(row=0, column=0, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.username_filter_entry, 'Client')

        self.unit_stake_filter_entry = ttk.Entry(self.filter_frame, width=3)
        self.unit_stake_filter_entry.grid(row=0, column=1, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.unit_stake_filter_entry, '£')

        self.risk_category_combobox_values = ["", "Any", "M", "W", "C"]
        self.risk_category_filter_entry = ttk.Combobox(self.filter_frame, values=self.risk_category_combobox_values, width=3)
        self.risk_category_filter_entry.grid(row=0, column=2, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.risk_category_filter_entry, 'Risk')

        self.type_combobox_values = ["", "Bet", "Knockback", "SMS"]
        self.type_combobox_entry = ttk.Combobox(self.filter_frame, values=self.type_combobox_values, width=5)
        self.type_combobox_entry.grid(row=0, column=3, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.type_combobox_entry, 'Type')

        self.selection_filter_entry = ttk.Entry(self.filter_frame, width=6)
        self.selection_filter_entry.grid(row=1, column=0, pady=(0, 2), padx=4, sticky='ew', columnspan=3)
        self.set_placeholder(self.selection_filter_entry, 'Selection')

        self.sport_combobox_values = ["", "Horses", "Dogs", "Other"]
        self.sport_combobox_entry = ttk.Combobox(self.filter_frame, values=self.sport_combobox_values, width=5)
        self.sport_combobox_entry.grid(row=1, column=3, pady=(0, 2), padx=4, sticky='ew')
        self.set_placeholder(self.sport_combobox_entry, 'Sport')

        self.tick_button = ttk.Button(self.filter_frame, text='✔', command=self.apply_filters, width=2, cursor='hand2')
        self.tick_button.grid(row=0, column=5, sticky='ew', padx=2, pady=(0, 3))
        
        self.reset_button = ttk.Button(self.filter_frame, text='✖', command=self.reset_filters, width=2, cursor='hand2')
        self.reset_button.grid(row=1, column=5, sticky='ew', padx=2, pady=(0, 3)) 

        separator = ttk.Separator(self.filter_frame, orient='vertical')
        separator.grid(row=0, column=6, rowspan=2, sticky='ns', pady=1, padx=(12, 5))

        limit_bets_checkbox = ttk.Checkbutton(self.filter_frame, text="[:150]", variable=self.limit_bets_var, cursor='hand2')
        limit_bets_checkbox.grid(row=0, column=8, pady=(2, 4), padx=4, sticky='e', rowspan=2)

        self.activity_frame = ttk.LabelFrame(self.root, style='Card', text="Status")
        self.activity_frame.place(x=530, y=5, width=365, height=150)
        
        self.activity_text = tk.Text(self.activity_frame, font=("Helvetica", 10, "bold"), wrap='word', padx=5, pady=5, bd=0, fg="#000000")
        self.activity_text.config(state='disabled')
        self.activity_text.pack(fill='both', expand=True)

        self.show_hide_button = ttk.Button(self.feed_frame, text='≡', command=self.toggle_filters, width=2, style='Large.TButton', cursor='hand2')
        self.show_hide_button.grid(row=2, column=0, pady=(2, 2), padx=5, sticky='w')

        self.refresh_button = ttk.Button(self.feed_frame, text='⟳', command=self.bet_feed, width=2, style='Large.TButton', cursor='hand2')
        self.refresh_button.grid(row=2, column=0, pady=(2, 2), padx=5, sticky='e')
        
        self.date_entry = DateEntry(self.feed_frame, width=15, background='#fecd45', foreground='white', borderwidth=1, date_pattern='dd/mm/yyyy')
        self.date_entry.grid(row=2, column=0, pady=(2, 2), padx=4, sticky='n')
        self.date_entry.bind("<<DateEntrySelected>>", lambda event: self.bet_feed())
        self.filter_frame.grid_remove()

    def toggle_filters(self):
        if self.filters_visible:
            self.filter_frame.grid_remove()
            self.show_hide_button.config(text='≡')
        else:
            self.filter_frame.grid()
            self.show_hide_button.config(text='≡')
        self.filters_visible = not self.filters_visible

    def start_feed_update(self):
        scroll_pos = self.feed_text.yview()[0]
        if scroll_pos <= 0.05:
            if self.date_entry.get_date().strftime('%d/%m/%Y') == datetime.today().strftime('%d/%m/%Y'):
                self.bet_feed()
        else:
            pass
        
        self.feed_frame.after(16000, self.start_feed_update)
        
    def bet_feed(self, date_str=None):
        def fetch_and_display_bets():
            if not self.feed_lock.acquire(blocking=False):
                print("Feed update already in progress. Skipping this update.")
                return
            try:
                print("Refreshing feed...")
                vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
                retry_attempts = 2
                for attempt in range(retry_attempts):
                    conn, cursor = self.database_manager.get_connection()
                    if conn is not None:
                        break
                    elif attempt < retry_attempts - 1:
                        print("Error finding bets. Retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        self.feed_text.config(state="normal")
                        self.feed_text.delete('1.0', tk.END)
                        self.feed_text.insert('end', "Error finding bets. Please try refreshing.", "center")
                        self.feed_text.config(state="disabled")
                        return
    
                selected_date = self.date_entry.get_date().strftime('%d/%m/%Y')
                if self.previous_selected_date != selected_date:
                    self.last_update_time = None
                    self.previous_selected_date = selected_date
    
                self.update_activity_frame(reporting_data, cursor, selected_date)
    
                filters_active = any([
                    self.current_filters['username'],
                    self.current_filters['unit_stake'],
                    self.current_filters['risk_category'],
                    self.current_filters['sport'],
                    self.current_filters['selection'],
                    self.current_filters['type']
                ])
    
                if not filters_active and self.last_update_time and selected_date == datetime.today().strftime('%d/%m/%Y'):
                    cursor.execute("SELECT MAX(time) FROM database WHERE date = ?", (selected_date,))
                    latest_time = cursor.fetchone()[0]
                    if latest_time <= self.last_update_time:
                        return
    
                username = self.current_filters['username']
                unit_stake = self.current_filters['unit_stake']
                risk_category = self.current_filters['risk_category']
                sport = self.current_filters['sport']
                selection_search_term = self.current_filters['selection']
                type_filter = self.current_filters['type']
    
                sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
                sport_value = sport_mapping.get(sport)
    
                type_mapping = {'Bet': 'BET', 'Knockback': 'WAGER KNOCKBACK', 'SMS': 'SMS WAGER'}
                type_value = type_mapping.get(type_filter)
    
                query = "SELECT * FROM database WHERE date = ?"
                params = [selected_date]
    
                if username:
                    query += " AND customer_ref = ?"
                    params.append(username.upper())
                if unit_stake:
                    query += " AND unit_stake = ?"
                    params.append(unit_stake)
                if risk_category and risk_category != 'Any':
                    query += " AND risk_category = ?"
                    params.append(risk_category)
                elif risk_category == 'Any':
                    query += " AND risk_category != '-'"
                if sport_value is not None:
                    query += " AND EXISTS (SELECT 1 FROM json_each(database.sports) WHERE json_each.value = ?)"
                    params.append(sport_value)
                    print(sport_value)
                if selection_search_term:
                    query += " AND selections LIKE ?"
                    params.append(f"%{selection_search_term}%")
                if type_value:
                    query += " AND type = ?"
                    params.append(type_value)
    
                query += " ORDER BY time DESC"
    
                cursor.execute(query, params)
                filtered_bets = cursor.fetchall()
    
                self.feed_text.config(state="normal")
                self.feed_text.delete('1.0', tk.END)
                separator = '-------------------------------------------------------------------------------------------------\n'
                column_names = [desc[0] for desc in cursor.description]
    
                if not filtered_bets:
                    self.feed_text.insert('end', "No bets found with the current filters or date.", 'center')
                else:
                    if self.limit_bets_var.get():
                        filtered_bets = filtered_bets[:150]
    
                    text_to_insert = []
                    tags_to_apply = []
    
                    for bet in filtered_bets:
                        bet_dict = dict(zip(column_names, bet))
    
                        if bet_dict['type'] != 'SMS WAGER' and bet_dict['selections'] is not None:
                            bet_dict['selections'] = json.loads(bet_dict['selections']) 
    
                        text_segments = self.format_bet_text(bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data)
    
                        for text, tag in text_segments:
                            start_idx = sum(len(segment) for segment in text_to_insert)
                            text_to_insert.append(text)
                            end_idx = start_idx + len(text)
                            if tag:
                                tags_to_apply.append((tag, start_idx, end_idx))
    
                        sep_start_idx = sum(len(segment) for segment in text_to_insert)
                        text_to_insert.append(separator)
                        sep_end_idx = sep_start_idx + len(separator)
                        tags_to_apply.append(("bold", sep_start_idx, sep_end_idx))
    
                    self.feed_text.insert('end', ''.join(text_to_insert))
    
                    optimized_tags = []
                    if tags_to_apply:
                        current_tag, current_start, current_end = tags_to_apply[0]
                        for tag, start, end in tags_to_apply[1:]:
                            if tag == current_tag and start == current_end:
                                current_end = end
                            else:
                                optimized_tags.append((current_tag, current_start, current_end))
                                current_tag, current_start, current_end = tag, start, end
                        optimized_tags.append((current_tag, current_start, current_end))
    
                    for tag, start_idx, end_idx in optimized_tags:
                        start_idx = f"1.0 + {start_idx}c"
                        end_idx = f"1.0 + {end_idx}c"
                        self.feed_text.tag_add(tag, start_idx, end_idx)
    
                self.feed_text.config(state="disabled")
    
                if filtered_bets:
                    self.last_update_time = max(bet[2] for bet in filtered_bets)
            finally:
                self.feed_lock.release()
                conn.close()
    
        threading.Thread(target=fetch_and_display_bets, daemon=True).start()

    def update_activity_frame(self, reporting_data, cursor, selected_date_str):
        try:
            current_date = datetime.strptime(selected_date_str, '%d/%m/%Y')
            previous_date = current_date - timedelta(days=7)
            current_time = datetime.now().strftime('%H:%M:%S')
            
            current_date_str = current_date.strftime('%d/%m/%Y')
            previous_date_str = previous_date.strftime('%d/%m/%Y')
            today_date_str = datetime.today().strftime('%d/%m/%Y')
            is_today = selected_date_str == today_date_str
    
            retry_attempts = 3
            for attempt in range(retry_attempts):
                try:
                    query = """
                        SELECT 
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET' AND (? IS NULL OR time <= ?)) AS current_bets,
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET' AND (? IS NULL OR time <= ?)) AS previous_bets,
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND (? IS NULL OR time <= ?)) AS current_knockbacks,
                            (SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND (? IS NULL OR time <= ?)) AS previous_knockbacks,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (? IS NULL OR time <= ?)) AS current_total_unique_clients,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'M' AND (? IS NULL OR time <= ?)) AS current_unique_m_clients,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'W' AND (? IS NULL OR time <= ?)) AS current_unique_w_clients,
                            (SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (? IS NULL OR time <= ?) AND (risk_category = '-' OR risk_category IS NULL)) AS current_unique_norisk_clients
                    """
                    params = [
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        previous_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        previous_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None,
                        current_date_str, current_time if is_today else None, current_time if is_today else None
                    ]
                    cursor.execute(query, params)
                    (
                        current_bets, previous_bets, current_knockbacks, previous_knockbacks,
                        current_total_unique_clients, current_unique_m_clients, current_unique_w_clients,
                        current_unique_norisk_clients
                    ) = cursor.fetchone()
    
                    cursor.execute(
                        "SELECT sports, COUNT(*) FROM database WHERE date = ? AND type = 'BET' " + ("AND time <= ? GROUP BY sports" if is_today else "GROUP BY sports"),
                        (current_date_str, current_time) if is_today else (current_date_str,)
                    )
                    current_sport_counts = cursor.fetchall()
    
                    break
    
                except sqlite3.DatabaseError as e:
                    if attempt < retry_attempts - 1:
                        print(f"Database error: {e}. Retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        print(f"Database error: {e}. No more retries.")
                        raise
    
            if previous_bets > 0:
                percentage_change_bets = ((current_bets - previous_bets) / previous_bets) * 100
            else:
                percentage_change_bets = 0
    
            if previous_knockbacks > 0:
                percentage_change_knockbacks = ((current_knockbacks - previous_knockbacks) / previous_knockbacks) * 100
            else:
                percentage_change_knockbacks = 0
    
            horse_bets = 0
            dog_bets = 0
            other_bets = 0
    
            sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
            for sport, count in current_sport_counts:
                sport_list = eval(sport)
                if sport_mapping['Horses'] in sport_list:
                    horse_bets += count
                if sport_mapping['Dogs'] in sport_list:
                    dog_bets += count
                if sport_mapping['Other'] in sport_list:
                    other_bets += count
    
            knockback_percentage = (current_knockbacks / current_bets * 100) if current_bets > 0 else 0
            previous_knockback_percentage = (previous_knockbacks / previous_bets * 100) if previous_bets > 0 else 0
    
            daily_turnover = reporting_data.get('daily_turnover', 'N/A')
            daily_profit = reporting_data.get('daily_profit', 'N/A')
            daily_profit_percentage = reporting_data.get('daily_profit_percentage', 'N/A')
            full_name = USER_NAMES.get(get_user(), get_user())
    
            bet_change_indicator = "↑" if current_bets > previous_bets else "↓" if current_bets < previous_bets else "→"
            knockback_change_indicator = "↑" if current_knockbacks > previous_knockbacks else "↓" if current_knockbacks < previous_knockbacks else "→"
    
            turnover_profit_line = (
                f"Turnover: {daily_turnover} | Profit: {daily_profit}"
                if is_today else ''
            )
    
            current_day_name = current_date.strftime('%A')
            previous_day_short = previous_date.strftime('%d/%m')
    
            self.activity_text.config(state='normal')
            self.activity_text.delete('1.0', tk.END)
    
            # Line 1: Date and User
            self.activity_text.insert(tk.END, f"{current_day_name} {selected_date_str} {'  |  ' + full_name if get_user() else ''}\n", 'bold')

            # Line 2: Bets
            self.activity_text.insert(tk.END, f"Bets: {current_bets:,} ")
            self.activity_text.insert(tk.END, f"{bet_change_indicator}{percentage_change_bets:.2f}% ", 'green' if percentage_change_bets > 0 else 'red')
            self.activity_text.insert(tk.END, f"({previous_day_short}: {previous_bets:,})\n")

            # Line 3: Knockbacks
            self.activity_text.insert(tk.END, f"Knbk: {current_knockbacks:,} ")
            self.activity_text.insert(tk.END, f"{knockback_change_indicator}{percentage_change_knockbacks:.2f}% ", 'red' if percentage_change_knockbacks > 0 else 'green')
            self.activity_text.insert(tk.END, f"({previous_day_short}: {previous_knockbacks:,})\n")

            # Line 4: Knockback Percentage
            self.activity_text.insert(tk.END, f"Knbk %: {knockback_percentage:.2f}% ")
            self.activity_text.insert(tk.END, f"({previous_day_short}: {previous_knockback_percentage:.2f}%)\n")

            # Line 5: Turnover Profit Line
            self.activity_text.insert(tk.END, f"{turnover_profit_line}\n")

            # Line 6: Clients
            self.activity_text.insert(tk.END, f"Clients: {current_total_unique_clients:,} | M: {current_unique_m_clients:,} | W: {current_unique_w_clients:,} | --: {current_unique_norisk_clients:,}\n")

            # Line 7: Bets by Type
            self.activity_text.insert(tk.END, f"Horses: {horse_bets:,} | Dogs: {dog_bets:,} | Other: {other_bets:,}")

            self.activity_text.tag_add('center', '1.0', 'end')
    
            self.activity_text.config(state='disabled')
    
        except sqlite3.DatabaseError as e:
            print(f"Database error: {e}")
            self.activity_text.config(state='normal')
            self.activity_text.delete('1.0', tk.END)
            self.activity_text.insert(tk.END, "An error occurred while updating the activity frame. Please try refreshing the feed.")
            self.activity_text.config(state='disabled')
        except Exception as e:
            print(f"Unexpected error: {e}")
            self.activity_text.config(state='normal')
            self.activity_text.delete('1.0', tk.END)
            self.activity_text.insert(tk.END, "An unexpected error occurred. Please try refreshing the feed.")
            self.activity_text.config(state='disabled')

    def initialize_text_tags(self):
        self.feed_text.tag_configure("risk", foreground="#ad0202")
        self.feed_text.tag_configure("watchlist", foreground="#e35f00")
        self.feed_text.tag_configure("newreg", foreground="purple")
        self.feed_text.tag_configure("vip", foreground="#009685")
        self.feed_text.tag_configure("sms", foreground="#6CCFF6")
        self.feed_text.tag_configure("knockback", foreground="#FF006E")
        self.feed_text.tag_configure('center', justify='center')
        self.feed_text.tag_configure("oddsmonkey", foreground="#ff00e6", justify='center')
        self.feed_text.tag_configure('bold', font=('Helvetica', 11, 'bold'), foreground='#d0cccc')
        self.feed_text.tag_configure('customer_ref_vip', font=('Helvetica', 11, 'bold'), foreground='#009685')
        self.feed_text.tag_configure('customer_ref_newreg', font=('Helvetica', 11, 'bold'), foreground='purple')
        self.feed_text.tag_configure('customer_ref_risk', font=('Helvetica', 11, 'bold'), foreground='#ad0202')
        self.feed_text.tag_configure('customer_ref_watchlist', font=('Helvetica', 11, 'bold'), foreground='#e35f00')
        self.feed_text.tag_configure('customer_ref_default', font=('Helvetica', 11, 'bold'), foreground='#000000')
        self.feed_text.tag_configure('black', foreground='#000000')
        self.activity_text.tag_configure('red', foreground='#ad0202')
        self.activity_text.tag_configure('green', foreground='#009685')
        self.activity_text.tag_configure('center', justify='center')

    def format_bet_text(self, bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data):
        enhanced_places = reporting_data.get('enhanced_places', [])
        text_segments = []
        
        if bet_dict['type'] == 'SMS WAGER':
            wager_number = bet_dict.get('id', '')  
            customer_reference = bet_dict.get('customer_ref', '')  
            sms_wager_text = bet_dict.get('text_request', '') 

            # Remove surrounding quotes and replace \n with actual newlines
            if sms_wager_text.startswith('"') and sms_wager_text.endswith('"'):
                sms_wager_text = sms_wager_text[1:-1]
            sms_wager_text = sms_wager_text.replace('\\n', '\n')

            tag = f"customer_ref_{self.get_customer_tag(customer_reference, vip_clients, newreg_clients)}"
            text_segments.append((f"{customer_reference} {wager_number}", tag))
            text_segments.append((f" - SMS WAGER:", "sms"))
            text_segments.append((f"\n{sms_wager_text}\n", "black"))
            
        elif bet_dict['type'] == 'WAGER KNOCKBACK':
            customer_ref = bet_dict.get('customer_ref', '') 
            knockback_id = bet_dict.get('id', '') 
            knockback_id = knockback_id.rsplit('-', 1)[0]
            knockback_details = bet_dict.get('selections', {}) 
            timestamp = bet_dict.get('time', '')  
    
            if isinstance(knockback_details, dict):
                formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items() if key not in ['Selections', 'Knockback ID', 'Time', 'Customer Ref', 'Error Message']])
                formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' for selection in knockback_details.get('Selections', [])])
            elif isinstance(knockback_details, list):
                formatted_knockback_details = ''
                formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' for selection in knockback_details])
            else:
                formatted_knockback_details = ''
                formatted_selections = ''
    
            formatted_knockback_details += '\n   ' + formatted_selections
            error_message = bet_dict.get('error_message', '') 
            if 'Maximum stake available' in error_message:
                error_message = error_message.replace(', Maximum stake available', '\n   Maximum stake available')
            formatted_knockback_details = f"Error Message: {error_message}   {formatted_knockback_details}"
            
            tag = f"customer_ref_{self.get_customer_tag(customer_ref, vip_clients, newreg_clients)}"
            text_segments.append((f"{customer_ref} {timestamp} - {knockback_id}", tag))
            text_segments.append((f" - WAGER KNOCKBACK:\n", "knockback"))
            text_segments.append((f"{formatted_knockback_details}\n", "black"))
        else:
            bet_no = bet_dict.get('id', '')  
            details = bet_dict.get('selections', []) 
            if isinstance(details, list) and all(isinstance(item, list) for item in details):
                parsed_selections = details
            else:
                parsed_selections = []
            timestamp = bet_dict.get('time', '')  
            customer_reference = bet_dict.get('customer_ref', '')  
            customer_risk_category = bet_dict.get('risk_category', '')  
            bet_details = bet_dict.get('bet_details', '') 
            unit_stake = bet_dict.get('unit_stake', 0.0)  
            bet_type = bet_dict.get('bet_type', '')
            
            selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
            formatted_unit_stake = f"£{unit_stake:.2f}"
            text = f"{formatted_unit_stake} {bet_details}, {bet_type}:\n{selection}\n"
            tag = f"customer_ref_{self.get_customer_tag(customer_reference, vip_clients, newreg_clients, customer_risk_category)}"
            text_segments.append((f"{customer_reference} ({customer_risk_category}) {timestamp} - {bet_no}", tag))
            text_segments.append((f" - {text}", "black"))
        
            for sel in parsed_selections:
                for event_name, om_selections in todays_oddsmonkey_selections.items():
                    if ' - ' in sel[0]:
                        selection_parts = sel[0].split(' - ')
                        if len(selection_parts) > 1:
                            bet_event_name = selection_parts[0].strip()
                            bet_selection_name = selection_parts[1].strip()
                            om_event_name = event_name.strip()
                            
                            if ',' in bet_event_name:
                                bet_event_name = bet_event_name.replace(', ', ' ', 1)
                            
                            
                            if bet_event_name == om_event_name:
                                for om_selection, lay_odds in om_selections:
                                    if bet_selection_name == om_selection.strip():
                                        if sel[1] == 'evs':
                                            sel[1] = '2.0'
                                        if sel[1] != 'SP' and float(sel[1]) >= float(lay_odds):
                                            oddsmonkey_text = f"{sel[0]}  |  Lay Odds: {lay_odds}\n"
                                            text_segments.append((oddsmonkey_text, "oddsmonkey"))
            
                parts = sel[0].split(' - ')
                if len(parts) > 1:
                    meeting_info = parts[0].split(', ')
                    if len(meeting_info) > 1 and ':' in meeting_info[1]:
                        meeting_time = meeting_info[1]
                        if f"{meeting_info[0]}, {meeting_time}" in enhanced_places:
                            enhanced_text = f"{sel[0]}  |  Enhanced Race\n"
                            text_segments.append((enhanced_text, "oddsmonkey"))
            
        return text_segments
    
    def get_customer_tag(self, customer_reference, vip_clients, newreg_clients, customer_risk_category=None):
        if customer_reference in vip_clients:
            return "vip"
        elif customer_reference in newreg_clients:
            return "newreg"
        elif customer_risk_category == 'W':
            return "watchlist"
        elif customer_risk_category == 'M' or customer_risk_category == 'C':
            return "risk"
        else:
            return "default"
    
    def apply_filters(self):
        self.current_filters['username'] = '' if self.username_filter_entry.get() == 'Client' else self.username_filter_entry.get()
        self.current_filters['unit_stake'] = '' if self.unit_stake_filter_entry.get() == '£' else self.unit_stake_filter_entry.get()
        self.current_filters['risk_category'] = '' if self.risk_category_filter_entry.get() == 'Risk' else self.risk_category_filter_entry.get()
        self.current_filters['sport'] = '' if self.sport_combobox_entry.get() == 'Sport' else self.sport_combobox_entry.get()
        self.current_filters['selection'] = '' if self.selection_filter_entry.get() == 'Selection' else self.selection_filter_entry.get()
        self.current_filters['type'] = '' if self.type_combobox_entry.get() == 'Type' else self.type_combobox_entry.get()

        filters_applied = any(value not in [None, '', 'none'] for value in self.current_filters.values())
    
        if filters_applied:
            self.tick_button.configure(style='Accent.TButton')
        else:
            self.tick_button.configure(style='TButton')
    
        self.bet_feed()

    def set_placeholder(self, widget, placeholder):
        widget.insert(0, placeholder)
        widget.config(foreground='grey')
        widget.bind("<FocusIn>", lambda event: self.clear_placeholder(event, placeholder))
        widget.bind("<FocusOut>", lambda event: self.add_placeholder(event, placeholder))

    def clear_placeholder(self, event, placeholder):
        if event.widget.get() == placeholder:
            event.widget.delete(0, tk.END)
            event.widget.config(foreground='black')

    def add_placeholder(self, event, placeholder):
        if not event.widget.get():
            event.widget.insert(0, placeholder)
            event.widget.config(foreground='grey')

    def reset_filters(self):
        self.current_filters = {'username': None, 'unit_stake': None, 'risk_category': None, 'sport': None, 'selection': None, 'type': None}
        self.username_filter_entry.delete(0, tk.END)
        self.unit_stake_filter_entry.delete(0, tk.END)
        self.risk_category_filter_entry.delete(0, tk.END)
        self.sport_combobox_entry.set('')
        self.selection_filter_entry.delete(0, tk.END)
        self.type_combobox_entry.set('')
        self.set_placeholder(self.username_filter_entry, 'Client')
        self.set_placeholder(self.unit_stake_filter_entry, '£')
        self.set_placeholder(self.risk_category_filter_entry, 'Risk')
        self.set_placeholder(self.selection_filter_entry, 'Selection')
        self.set_placeholder(self.sport_combobox_entry, 'Sport')
        self.set_placeholder(self.type_combobox_entry, 'Type')

        self.tick_button.configure(style='TButton')

        self.bet_feed()