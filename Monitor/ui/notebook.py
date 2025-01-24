import os
import json
import gspread
import threading
import fasteners
import tkinter as tk
import time
import requests
from collections import defaultdict
from collections import Counter
from tkinter import ttk
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2 import service_account
from config import NETWORK_PATH_PREFIX
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from utils import access_data, user_notification
from ui.client_wizard import ClientWizard


class Notebook:
    def __init__(self, root, database_manager):
        self.database_manager = database_manager
        self.root = root
        self.last_notification = None
        self.generated_string = None

        _, _, _, reporting_data = access_data()
        self.enhanced_places = reporting_data.get('enhanced_places', [])

        self.pipedrive_api_token = os.getenv('PIPEDRIVE_API_KEY')
        self.pipedrive_api_url = os.getenv('PIPEDRIVE_API_URL')

        if not self.pipedrive_api_url:
            raise ValueError("PIPEDRIVE_API_URL environment variable is not set")

        self.pipedrive_api_url = f'{self.pipedrive_api_url}?api_token={self.pipedrive_api_token}'

        google_creds = {
            "type": os.getenv('GOOGLE_SERVICE_ACCOUNT_TYPE'),
            "project_id": os.getenv('GOOGLE_PROJECT_ID'),
            "private_key_id": os.getenv('GOOGLE_PRIVATE_KEY_ID'),
            "private_key": os.getenv('GOOGLE_PRIVATE_KEY').replace('\\n', '\n'),
            "client_email": os.getenv('GOOGLE_CLIENT_EMAIL'),
            "client_id": os.getenv('GOOGLE_CLIENT_ID'),
            "auth_uri": os.getenv('GOOGLE_AUTH_URI'),
            "token_uri": os.getenv('GOOGLE_TOKEN_URI'),
            "auth_provider_x509_cert_url": os.getenv('GOOGLE_AUTH_PROVIDER_X509_CERT_URL'),
            "client_x509_cert_url": os.getenv('GOOGLE_CLIENT_X509_CERT_URL')
        }
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/analytics.readonly']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        self.gc = gspread.authorize(credentials)
        self.analytics_credentials = service_account.Credentials.from_service_account_info(google_creds, scopes=scope)

        self.initialize_ui()
        self.initialize_text_tags()
        self.update_notifications()
        self.start_live_users_thread() 
        self.run_factoring_sheet_thread()
        self.run_freebet_sheet_thread()
        self.run_popup_sheet_thread()

    def initialize_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.place(x=238, y=655, width=470, height=265)
        tab_1 = ttk.Frame(self.notebook)
        tab_1.grid_rowconfigure(0, weight=1)
        tab_1.grid_columnconfigure(0, weight=3) 
        tab_1.grid_columnconfigure(1, weight=0) 
        tab_1.grid_columnconfigure(2, weight=1)
        self.notebook.add(tab_1, text="Staff Feed")
        self.staff_feed = tk.Text(tab_1, font=("Helvetica", 10), bd=0, wrap='word', padx=2, pady=2, fg="#000000", bg="#ffffff")
        self.staff_feed.grid(row=0, column=0, sticky="nsew")
        self.staff_feed.tag_configure("spacing", spacing1=5, spacing3=5)
        self.staff_feed.tag_add("spacing", "1.0", "end")
        self.staff_feed_buttons_frame = ttk.Frame(tab_1)
        separator = ttk.Separator(tab_1, orient='vertical')
        separator.grid(row=0, column=1, sticky='ns')
        self.staff_feed_buttons_frame.grid(row=0, column=2, sticky='nsew')
        self.pinned_message_frame = ttk.Frame(self.staff_feed_buttons_frame, style='Card')
        self.pinned_message_frame.pack(side="top", pady=5, padx=(5, 0))
        self.pinned_message = tk.Text(self.pinned_message_frame, font=("Helvetica", 10, 'bold'), bd=0, wrap='word', pady=2, fg="#000000", bg="#ffffff", height=3, width=30)  # Adjust height as needed
        self.pinned_message.config(state='disabled')
        self.pinned_message.pack(side="top", pady=5, padx=5) 
        self.post_message_button = ttk.Button(self.staff_feed_buttons_frame, text="Post", command=lambda: user_notification(self.root), cursor="hand2", width=8)
        self.post_message_button.pack(side="top", pady=(5, 5))

        self.separator = ttk.Separator(self.staff_feed_buttons_frame, orient='horizontal')
        self.separator.pack(side="top", fill='x', pady=(5, 5))
        
        live_users_label = ttk.Label(self.staff_feed_buttons_frame, text=" Active Clients", font=("Helvetica", 10, 'bold'), wraplength=150)
        live_users_label.pack(side="top", pady=(18, 5))

        self.live_users_label = ttk.Label(self.staff_feed_buttons_frame, text="---", font=("Helvetica", 10))
        self.live_users_label.pack(side="top", pady=(5, 5))

        tab_2 = ttk.Frame(self.notebook)
        self.notebook.add(tab_2, text="Reporting")
        tab_2.grid_rowconfigure(0, weight=1)
        tab_2.grid_rowconfigure(1, weight=1)
        tab_2.grid_columnconfigure(0, weight=3)
        tab_2.grid_columnconfigure(1, weight=0) 
        tab_2.grid_columnconfigure(2, weight=1)
        self.report_ticket = tk.Text(tab_2, font=("Helvetica", 10), wrap='word', bd=0, padx=10, pady=10, fg="#000000", bg="#ffffff")
        self.report_ticket.insert('1.0', "Daily Report\nGenerate a report for the days' betting activity.\n\nMonthly Report\nGenerate a report on the months' betting activity.\n\nStaff Report\nGenerate a report on staff activity.\n\nTraders Screener\nScan for potential 'risk' users.\n\nRG Screener\nScan for indicators of irresponsible gambling.", "c")    
        self.report_ticket.config(state='disabled')
        self.report_ticket.grid(row=0, column=0, sticky="nsew") 
        separator_tab_2 = ttk.Separator(tab_2, orient='vertical')
        separator_tab_2.grid(row=0, column=1, sticky='ns')
        self.report_buttons_frame = ttk.Frame(tab_2)
        self.report_buttons_frame.grid(row=0, column=2, sticky='nsew')
        self.report_combobox = ttk.Combobox(self.report_buttons_frame, values=["Daily Report", "Monthly Report", "Staff Report", "Traders Screener", "RG Screener", "Client Report"], width=30, state='readonly')
        self.report_combobox.pack(side="top", pady=(10, 5), padx=(5, 0))
        self.report_combobox.bind("<<ComboboxSelected>>", self.on_report_combobox_select)
        self.report_button = ttk.Button(self.report_buttons_frame, text="Generate", command=self.generate_report, cursor="hand2", width=30)
        self.report_button.pack(side="top", pady=(5, 10), padx=(5, 0))
    
        self.progress_label = ttk.Label(self.report_buttons_frame, text="---", wraplength=150)
        self.progress_label.pack(side="top", pady=(20, 10), padx=(5, 0))
    
        tab_3 = ttk.Frame(self.notebook)
        self.notebook.add(tab_3, text="Factoring Log")
    
        self.factoring_tree = ttk.Treeview(tab_3)
        columns = ["A", "B", "C", "D", "E", "F"]
        headings = ["Date", "Time", "User", "Risk", "Rating", ""]
        self.factoring_tree["columns"] = columns
        for col, heading in enumerate(headings):
            self.factoring_tree.heading(columns[col], text=heading)
            self.factoring_tree.column(columns[col], width=84, stretch=tk.NO)
        self.factoring_tree.column("A", width=75, stretch=tk.NO)
        self.factoring_tree.column("B", width=60, stretch=tk.NO)
        self.factoring_tree.column("C", width=83, stretch=tk.NO)
        self.factoring_tree.column("D", width=40, stretch=tk.NO)
        self.factoring_tree.column("E", width=40, stretch=tk.NO)
        self.factoring_tree.column("F", width=32, stretch=tk.NO)
        self.factoring_tree.column("#0", width=10, stretch=tk.NO)
        self.factoring_tree.heading("#0", text="", anchor="w")
        self.factoring_tree.grid(row=0, column=0, sticky="nsew")
        tab_3.grid_columnconfigure(0, weight=1)
        tab_3.grid_rowconfigure(0, weight=1)
        tab_3.grid_columnconfigure(1, weight=0) 
    
        factoring_buttons_frame = ttk.Frame(tab_3)
        factoring_buttons_frame.grid(row=0, column=1, sticky='ns', padx=(10, 0))
    
        add_restriction_button = ttk.Button(factoring_buttons_frame, text="Add", command=lambda: ClientWizard(self.root, "Factoring"), cursor="hand2")
        add_restriction_button.pack(side="top", pady=(10, 5))
        refresh_factoring_button = ttk.Button(factoring_buttons_frame, text="Refresh", command=self.run_factoring_sheet_thread, cursor="hand2")
        refresh_factoring_button.pack(side="top", pady=(10, 5))
        self.last_refresh_label = ttk.Label(factoring_buttons_frame, text=f"Last Refresh:\n---")
        self.last_refresh_label.pack(side="top", pady=(10, 5))
    
        self.client_id_frame = ttk.Frame(self.report_buttons_frame)
        self.client_id_label = ttk.Label(self.client_id_frame, text="Username:")
        self.client_id_label.pack(side="top", padx=(5, 5))  
        self.client_id_entry = ttk.Entry(self.client_id_frame, width=15)
        self.client_id_entry.pack(side="top", padx=(5, 5)) 
        self.client_id_frame.pack(side="top", pady=(5, 10), padx=(5, 0))
        self.client_id_frame.pack_forget()  

        tab_4 = ttk.Frame(self.notebook)
        self.notebook.add(tab_4, text="Freebet Log")

        self.freebet_tree = ttk.Treeview(tab_4)
        columns = ["A", "B", "C", "E", "F"]
        headings = ["Date", "Time", "User", "Amount", ""]
        self.freebet_tree["columns"] = columns
        for col, heading in enumerate(headings):
            self.freebet_tree.heading(columns[col], text=heading)
            self.freebet_tree.column(columns[col], width=84, stretch=tk.NO)
        self.freebet_tree.column("A", width=75, stretch=tk.NO)
        self.freebet_tree.column("B", width=60, stretch=tk.NO)
        self.freebet_tree.column("C", width=83, stretch=tk.NO)
        self.freebet_tree.column("E", width=65, stretch=tk.NO)
        self.freebet_tree.column("F", width=32, stretch=tk.NO)
        self.freebet_tree.column("#0", width=10, stretch=tk.NO)
        self.freebet_tree.heading("#0", text="", anchor="w")
        self.freebet_tree.grid(row=0, column=0, sticky="nsew")
        tab_4.grid_columnconfigure(0, weight=1)
        tab_4.grid_rowconfigure(0, weight=1)
        tab_4.grid_columnconfigure(1, weight=0) 
    
        freebet_buttons_frame = ttk.Frame(tab_4)
        freebet_buttons_frame.grid(row=0, column=1, sticky='ns', padx=(10, 0))
    
        add_freebet_button = ttk.Button(freebet_buttons_frame, text="Add", command=lambda: ClientWizard(self.root, "Freebet"), cursor="hand2")
        add_freebet_button.pack(side="top", pady=(10, 5))
        refresh_freebets_button = ttk.Button(freebet_buttons_frame, text="Refresh", command=self.run_freebet_sheet_thread, cursor="hand2")
        refresh_freebets_button.pack(side="top", pady=(10, 5))
        self.last_refresh_freebets_label = ttk.Label(freebet_buttons_frame, text=f"Last Refresh:\n---")
        self.last_refresh_freebets_label.pack(side="top", pady=(10, 5))

        tab_5 = ttk.Frame(self.notebook)
        self.notebook.add(tab_5, text="Popup Log")

        self.popup_tree = ttk.Treeview(tab_5)
        columns = ["A", "B"]
        headings = ["User", "Date Applied"]
        self.popup_tree["columns"] = columns
        for col, heading in enumerate(headings):
            self.popup_tree.heading(columns[col], text=heading)
            self.popup_tree.column(columns[col], width=84, stretch=tk.NO)
        self.popup_tree.column("A", width=150, stretch=tk.NO)
        self.popup_tree.column("B", width=150, stretch=tk.NO)
        self.popup_tree.column("#0", width=10, stretch=tk.NO)
        self.popup_tree.heading("#0", text="", anchor="w")
        self.popup_tree.grid(row=0, column=0, sticky="nsew")
        tab_5.grid_columnconfigure(0, weight=1)
        tab_5.grid_rowconfigure(0, weight=1)
        tab_5.grid_columnconfigure(1, weight=0)
    
        popup_buttons_frame = ttk.Frame(tab_5)
        popup_buttons_frame.grid(row=0, column=1, sticky='ns', padx=(10, 0))
    
        add_popup_button = ttk.Button(popup_buttons_frame, text="Add", command=lambda: ClientWizard(self.root, "Popup"), cursor="hand2")
        add_popup_button.pack(side="top", pady=(10, 5))
        refresh_popup_button = ttk.Button(popup_buttons_frame, text="Refresh", command=self.run_popup_sheet_thread, cursor="hand2")
        refresh_popup_button.pack(side="top", pady=(10, 5))
        self.last_refresh_popup_label = ttk.Label(popup_buttons_frame, text=f"Last Refresh:\n---")
        self.last_refresh_popup_label.pack(side="top", pady=(10, 5))

    def initialize_text_tags(self):
        self.pinned_message.tag_configure('center', justify='center')
        self.report_ticket.tag_configure("risk", foreground="#ad0202")
        self.report_ticket.tag_configure("watchlist", foreground="#e35f00")
        self.report_ticket.tag_configure("newreg", foreground="purple")
        self.report_ticket.tag_configure('center', justify='center', font=('Helvetica', 10, 'bold'))
        self.report_ticket.tag_configure('c', justify='center')
        self.report_ticket.tag_configure('bold', font=('Helvetica', 10, 'bold'))

    def update_notifications(self):
        self.staff_feed.tag_configure("important", font=("TkDefaultFont", 10, "bold"))
        self.staff_feed.config(state='normal')  
        file_lock = fasteners.InterProcessLock(os.path.join(NETWORK_PATH_PREFIX, 'notifications.lock'))

        with file_lock:
            try:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'notifications.json'), 'r') as f:
                    notifications = json.load(f)

                pinned_notifications = [n for n in notifications if n.get('pinned', False)]
                regular_notifications = [n for n in notifications if not n.get('pinned', False)]

                self.pinned_message.config(state='normal') 
                self.pinned_message.delete('1.0', 'end')  
                if not pinned_notifications:
                    self.pinned_message.insert('end', "No bulletin message\n", "center")
                for notification in pinned_notifications:
                    self.pinned_message.insert('end', f"{notification['message']}\n")
                self.pinned_message.config(state='disabled') 

                if regular_notifications and (self.last_notification is None or self.last_notification != regular_notifications[0]):
                    last_index = next((index for index, notification in enumerate(regular_notifications) if notification == self.last_notification), len(regular_notifications))
                    for notification in reversed(regular_notifications[:last_index]):
                        time_str = notification['time']
                        message = notification['message']
                        important = notification.get('important', False)
                        if important:
                            message = f'{time_str}: {message}\n'
                            self.staff_feed.insert('1.0', message, "important")
                        else:
                            self.staff_feed.insert('1.0', f'{time_str}: {message}\n')
                    self.last_notification = regular_notifications[0] if regular_notifications else None

            except (FileNotFoundError, json.JSONDecodeError):
                pass
        self.staff_feed.config(state='disabled') 
        self.staff_feed.after(1500, self.update_notifications)

    def on_report_combobox_select(self, event):
        selected_report = self.report_combobox.get()
        if selected_report == "Client Report":
            self.client_id_frame.pack(side="top", pady=(5, 10), padx=(5, 0))
        else:
            self.client_id_frame.pack_forget()

    def generate_report(self):
        report_type = self.report_combobox.get()
        if report_type == "Daily Report":
            self.report_thread = threading.Thread(target=self.create_daily_report)
        elif report_type == "Monthly Report":
            self.report_thread = threading.Thread(target=self.create_monthly_report)
        elif report_type == "Staff Report":
            self.report_thread = threading.Thread(target=self.create_staff_report)
        elif report_type == "Traders Screener":
            self.report_thread = threading.Thread(target=self.update_traders_report)
        elif report_type == "RG Screener":
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "RG Screener not currently available")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        elif report_type == "Client Report":
            client_id = self.client_id_entry.get()
            self.report_thread = threading.Thread(target=self.create_client_report, args=(client_id,))
        else:
            return
        self.report_thread.start()

    def create_daily_report(self):
        try:
            conn, cursor = self.database_manager.get_connection()
            _, _, _, reporting_data = access_data()

            time = datetime.now()
            current_date_str = time.strftime("%d/%m/%Y")
            formatted_time = time.strftime("%H:%M:%S")

            current_date_obj = datetime.strptime(current_date_str, "%d/%m/%Y")
            current_date_iso = current_date_obj.strftime("%Y-%m-%d")
            start_of_current_week = current_date_obj - timedelta(days=current_date_obj.weekday())
            start_of_current_week_iso = start_of_current_week.strftime("%Y-%m-%d")
            start_of_previous_week = start_of_current_week - timedelta(days=7)
            start_of_previous_week_iso = start_of_previous_week.strftime("%Y-%m-%d")
            # total_deposits = reporting_data.get('total_deposits', 'N/A')
            # total_sum_deposits = reporting_data.get('total_sum', 'N/A')

            self.progress_label.config(text=f"Finding clients data")

            # Fetch the count of unique clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ?", (current_date_str,))
            total_unique_clients = cursor.fetchone()[0]
        
            # Fetch the count of M clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'M'", (current_date_str,))
            unique_m_clients = cursor.fetchone()[0]
        
            # Fetch the count of W clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'W'", (current_date_str,))
            unique_w_clients = cursor.fetchone()[0]
        
            # Fetch the count of no risk clients for the current day
            cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (risk_category = '-' OR risk_category IS NULL)", (current_date_str,))
            unique_norisk_clients = cursor.fetchone()[0]
        
            # Fetch the average count of unique clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_unique_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_unique_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of unique clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_unique_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_unique_clients_previous_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of M clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_m_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'M'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_m_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of M clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_m_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'M'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_m_clients_previous_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of W clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_w_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'W'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_w_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of W clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_w_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND risk_category = 'W'
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_w_clients_previous_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of no-risk clients for the current week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_norisk_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND (risk_category = '-' OR risk_category IS NULL)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_norisk_clients_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average count of no-risk clients for the previous week
            cursor.execute("""
                SELECT AVG(daily_count) as avg_norisk_clients
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        COUNT(DISTINCT customer_ref) as daily_count
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND (risk_category = '-' OR risk_category IS NULL)
                    GROUP BY day
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_norisk_clients_previous_week = cursor.fetchone()[0] or 0.0

            self.progress_label.config(text=f"Finding bets data")

            # Fetch the count of bets for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
            total_bets = cursor.fetchone()[0]
        
            # Fetch the count of knockbacks for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK'", (current_date_str,))
            total_wageralerts = cursor.fetchone()[0]
        
            # Fetch the count of SMS for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'SMS WAGER'", (current_date_str,))
            total_sms = cursor.fetchone()[0]
        
            # Fetch the count of bets for each sport for the current day
            cursor.execute("SELECT sports, COUNT(*) FROM database WHERE date = ? AND type = 'BET' GROUP BY sports", (current_date_str,))
            sport_counts = cursor.fetchall()
        
            self.progress_label.config(text=f"Finding knockback data")

            # Fetch the count of different types of wager alerts
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Has Changed%'", (current_date_str,))
            price_change = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Liability Exceeded: True%'", (current_date_str,))
            liability_exceeded = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Event Has Ended%'", (current_date_str,))
            event_ended = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Type Disallowed%'", (current_date_str,))
            price_type_disallowed = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Sport Disallowed%'", (current_date_str,))
            sport_disallowed = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%User Max Stake Exceeded%'", (current_date_str,))
            max_stake_exceeded = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message NOT LIKE '%Price Has Changed%' AND error_message NOT LIKE '%Liability Exceeded: True%' AND error_message NOT LIKE '%Event Has Ended%' AND error_message NOT LIKE '%Price Type Disallowed%' AND error_message NOT LIKE '%Sport Disallowed%' AND error_message NOT LIKE '%User Max Stake Exceeded%'", (current_date_str,))
            other_alert = cursor.fetchone()[0]
        
            cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Type Disallowed%' OR error_message LIKE '%Sport Disallowed%' OR error_message LIKE '%User Max Stake Exceeded%'", (current_date_str,))
            user_restriction = cursor.fetchone()[0]
        
            self.progress_label.config(text=f"Calculating stakes")

            # Fetch the total stakes for the current day
            cursor.execute("SELECT SUM(total_stake) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
            total_stakes = cursor.fetchone()[0] or 0.0
        
            # Fetch the top 5 highest stakes
            cursor.execute("SELECT customer_ref, SUM(total_stake) as total FROM database WHERE date = ? AND type = 'BET' GROUP BY customer_ref ORDER BY total DESC LIMIT 5", (current_date_str,))
            top_spenders = cursor.fetchall()
        
            # Fetch the top 5 clients with most bets
            cursor.execute("SELECT customer_ref, COUNT(*) as total FROM database WHERE date = ? AND type = 'BET' GROUP BY customer_ref ORDER BY total DESC LIMIT 5", (current_date_str,))
            top_client_bets = cursor.fetchall()
        
            # Fetch the top 3 clients with most knockbacks
            cursor.execute("SELECT customer_ref, COUNT(*) as total FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK' GROUP BY customer_ref ORDER BY total DESC LIMIT 3", (current_date_str,))
            top_wageralert_clients = cursor.fetchall()
        
            # Fetch the count of bets per hour for the current day
            cursor.execute("SELECT strftime('%H:00', time) as hour, COUNT(*) FROM database WHERE date = ? AND type = 'BET' GROUP BY hour", (current_date_str,))
            bets_per_hour = cursor.fetchall()
            
            self.progress_label.config(text=f"Calculating averages")

            # Fetch the average number of daily bets, knockbacks, and SMS text bets for the current week
            cursor.execute("""
                SELECT 
                    AVG(bets) as avg_bets, 
                    AVG(knockbacks) as avg_knockbacks, 
                    AVG(sms_bets) as avg_sms_bets
                FROM (
                    SELECT 
                        date,
                        COUNT(CASE WHEN type = 'BET' THEN 1 END) as bets,
                        COUNT(CASE WHEN type = 'WAGER KNOCKBACK' THEN 1 END) as knockbacks,
                        COUNT(CASE WHEN type = 'SMS WAGER' THEN 1 END) as sms_bets
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY date
                ) as daily_counts
            """, (start_of_current_week_iso, current_date_iso))
            avg_day_bets, avg_day_knockbacks, avg_day_sms_bets = cursor.fetchone()
            
            # Handle None values
            avg_day_bets = avg_day_bets if avg_day_bets is not None else 0
            avg_day_knockbacks = avg_day_knockbacks if avg_day_knockbacks is not None else 0
            avg_day_sms_bets = avg_day_sms_bets if avg_day_sms_bets is not None else 0
            
            # Fetch the average number of daily bets, knockbacks, and SMS text bets for the previous week
            cursor.execute("""
                SELECT 
                    AVG(bets) as avg_bets, 
                    AVG(knockbacks) as avg_knockbacks, 
                    AVG(sms_bets) as avg_sms_bets
                FROM (
                    SELECT 
                        date,
                        COUNT(CASE WHEN type = 'BET' THEN 1 END) as bets,
                        COUNT(CASE WHEN type = 'WAGER KNOCKBACK' THEN 1 END) as knockbacks,
                        COUNT(CASE WHEN type = 'SMS WAGER' THEN 1 END) as sms_bets
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                    GROUP BY date
                ) as daily_counts
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_bets, avg_knockbacks, avg_sms_bets = cursor.fetchone()
            
            # Handle None values
            avg_bets = avg_bets if avg_bets is not None else 0
            avg_knockbacks = avg_knockbacks if avg_knockbacks is not None else 0
            avg_sms_bets = avg_sms_bets if avg_sms_bets is not None else 0
        
            # Fetch the average total stakes for the current week
            cursor.execute("""
                SELECT AVG(daily_total) as avg_total_stake
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        SUM(total_stake) as daily_total
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND type = 'BET'
                    GROUP BY day
                ) as daily_totals
            """, (start_of_current_week_iso, current_date_iso))
            avg_total_stake_current_week = cursor.fetchone()[0] or 0.0

            # Fetch the average total stakes for the previous week
            cursor.execute("""
                SELECT AVG(daily_total) as avg_total_stake
                FROM (
                    SELECT DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) as day,
                        SUM(total_stake) as daily_total
                    FROM database
                    WHERE DATE(strftime('%Y-%m-%d', SUBSTR(date, 7, 4) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2))) 
                        BETWEEN DATE(?) AND DATE(?)
                        AND type = 'BET'
                    GROUP BY day
                ) as daily_totals
            """, (start_of_previous_week_iso, start_of_current_week_iso))
            avg_total_stake_previous_week = cursor.fetchone()[0] or 0.0

            conn.close()

            # Initialize sport counts
            horse_bets = 0
            dog_bets = 0
            other_bets = 0
            
            # Map the sport counts
            sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
            for sport, count in sport_counts:
                sport_list = eval(sport)
                if sport_mapping['Horses'] in sport_list:
                    horse_bets += count
                if sport_mapping['Dogs'] in sport_list:
                    dog_bets += count
                if sport_mapping['Other'] in sport_list:
                    other_bets += count
            

            total_sport_bets = horse_bets + dog_bets + other_bets
            percentage_horse_racing = (horse_bets / total_sport_bets) * 100
            percentage_greyhound = (dog_bets / total_sport_bets) * 100
            percentage_other = (other_bets / total_sport_bets) * 100

        except Exception as e:
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "An error occurred while generating the report.\nPlease try again.")
            self.progress_label.config(text="Error with Daily Report")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        finally:
            if conn:
                conn.close()

        separator = "-" * 69

        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)

        self.report_ticket.insert(tk.END, f"DAILY REPORT\nGenerated at {formatted_time}\n", 'center')
        self.report_ticket.insert(tk.END, f"{separator}\n")

        self.report_ticket.insert(tk.END, f"Today's Activity:\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets {total_bets:,} | KB {total_wageralerts:,} | KB % {total_wageralerts / total_bets * 100:.2f}%\n", 'c')
        self.report_ticket.insert(tk.END, f"This week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets {int(avg_day_bets):,} | KB {int(avg_day_knockbacks):,} | KB % {(avg_day_knockbacks / avg_day_bets * 100):.2f}%\n", 'c')
        self.report_ticket.insert(tk.END, f"Last week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets {int(avg_bets):,} | KB {int(avg_knockbacks):,} | KB % {(avg_knockbacks / avg_bets * 100):.2f}%\n", 'c')

        self.report_ticket.insert(tk.END, f"\nToday's Stakes:\n", 'center')
        self.report_ticket.insert(tk.END, f"Stakes £{total_stakes:,.2f} | Average Stake ~£{total_stakes / total_bets:,.2f}\n", 'c')
        self.report_ticket.insert(tk.END, f"This week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Stakes £{avg_total_stake_current_week:,.2f}  | Average Stake ~£{avg_total_stake_current_week / avg_day_bets:,.2f}\n", 'c')
        self.report_ticket.insert(tk.END, f"Last week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Stakes £{avg_total_stake_previous_week:,.2f}  | Average Stake ~£{avg_total_stake_previous_week / avg_bets:,.2f}\n", 'c')

        self.report_ticket.insert(tk.END, f"\nToday's Clients:\n", 'center')
        self.report_ticket.insert(tk.END, f"Total: {total_unique_clients:,} | --: {unique_norisk_clients:,} | M: {unique_m_clients:,} | W: {unique_w_clients:,}\n", 'c')
        self.report_ticket.insert(tk.END, f"This week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Total: {int(avg_unique_clients_current_week):,} | --: {int(avg_norisk_clients_current_week):,} | M: {int(avg_m_clients_current_week):,} | W: {int(avg_w_clients_current_week):,}\n", 'c')
        self.report_ticket.insert(tk.END, f"Last week daily average:\n", 'center')
        self.report_ticket.insert(tk.END, f"Total: {int(avg_unique_clients_previous_week):,} | --: {int(avg_norisk_clients_previous_week):,} | M: {int(avg_m_clients_previous_week):,} | W: {int(avg_w_clients_previous_week):,}\n", 'c')
        # self.report_ticket.insert(tk.END, f"\nToday's Deposits:\n", 'center')
        # self.report_ticket.insert(tk.END, f"Total: {total_deposits} | Total: £{total_sum_deposits:,.2f}\n", 'c')

        self.report_ticket.insert(tk.END, f"\nToday's Sports:\n", 'center')
        self.report_ticket.insert(tk.END, f"Horses: {horse_bets} ({percentage_horse_racing:.2f}%) | Dogs: {dog_bets} ({percentage_greyhound:.2f}%) | Other: {other_bets} ({percentage_other:.2f}%)\n", 'c')
        
        self.report_ticket.insert(tk.END, "\nHighest Stakes:\n", 'center')
        for rank, (customer, spend) in enumerate(top_spenders, start=1):
            self.report_ticket.insert(tk.END, f"\t{rank}. {customer} - Stakes: £{spend:,.2f}\n", 'c')

        self.report_ticket.insert(tk.END, "\nMost Bets:\n", 'center')
        for rank, (client, count) in enumerate(top_client_bets, start=1):
            self.report_ticket.insert(tk.END, f"\t{rank}. {client} - Bets: {count:,}\n", 'c')

        self.report_ticket.insert(tk.END, f"\nMost Knockbacks:\n", 'center')
        for rank, (client, count) in enumerate(top_wageralert_clients, start=1):
            self.report_ticket.insert(tk.END, f"\t{rank}. {client} - Knockbacks: {count:,}\n", 'c')


        self.report_ticket.insert(tk.END, f"\nKnockbacks by Type:", 'center')
        self.report_ticket.insert(tk.END, f"\nLiability: {liability_exceeded}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Price Change: {price_change}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Event Ended: {event_ended}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Price Type: {price_type_disallowed}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Sport: {sport_disallowed}  |  ", 'c')
        self.report_ticket.insert(tk.END, f"Max Stake: {max_stake_exceeded}", 'c')

        self.report_ticket.insert(tk.END, f"\n\nBets Per Hour:\n", 'center')
        for hour, count in bets_per_hour:
            self.report_ticket.insert(tk.END, f"\t{hour} - Bets: {count}\n", 'c')

        self.progress_label.config(text=f"---")

        self.report_ticket.config(state="disabled")
    
    def create_monthly_report(self):
        try:
            conn, cursor = self.database_manager.get_connection()
            report_output = ""
        
            # Get today's date
            today = datetime.now()
            formatted_time = today.strftime("%d/%m/%Y %H:%M:%S")
        
            # Calculate the date 30 days ago
            start_date = today - timedelta(days=30)
            separator = "-" * 69
        
            # Header for the monthly report
            report_output += f"MONTHLY REPORT TICKET\n Generated at {formatted_time}\n"
            report_output += f"{separator}\n"
        
            # Loop through each day in the last 30 days, starting from today
            for i in range(30):
                current_date = today - timedelta(days=i)
                current_date_str = current_date.strftime("%d/%m/%Y")

                self.progress_label.config(text=f"Generating {current_date_str}")
        
                # Fetch the count of bets for the current day
                cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
                total_bets = cursor.fetchone()[0]
        
                # Fetch the count of knockbacks for the current day
                cursor.execute("SELECT COUNT(*) FROM database WHERE date = ? AND type = 'WAGER KNOCKBACK'", (current_date_str,))
                total_knockbacks = cursor.fetchone()[0]
        
                # Fetch the count of unique clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ?", (current_date_str,))
                total_unique_clients = cursor.fetchone()[0]
        
                # Fetch the count of M clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'M'", (current_date_str,))
                unique_m_clients = cursor.fetchone()[0]
        
                # Fetch the count of W clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND risk_category = 'W'", (current_date_str,))
                unique_w_clients = cursor.fetchone()[0]
        
                # Fetch the count of no risk clients for the current day
                cursor.execute("SELECT COUNT(DISTINCT customer_ref) FROM database WHERE date = ? AND (risk_category = '-' OR risk_category IS NULL)", (current_date_str,))
                unique_norisk_clients = cursor.fetchone()[0]
        
                # Fetch the count of bets for each sport for the current day
                cursor.execute("SELECT sports, COUNT(*) FROM database WHERE date = ? AND type = 'BET' GROUP BY sports", (current_date_str,))
                sport_counts = cursor.fetchall()
        
                # Initialize sport counts
                horse_bets = 0
                dog_bets = 0
                other_bets = 0
        
                # Map the sport counts
                sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
                for sport, count in sport_counts:
                    sport_list = eval(sport)
                    if sport_mapping['Horses'] in sport_list:
                        horse_bets += count
                    if sport_mapping['Dogs'] in sport_list:
                        dog_bets += count
                    if sport_mapping['Other'] in sport_list:
                        other_bets += count
        
                # Fetch the total stakes for the current day
                cursor.execute("SELECT SUM(total_stake) FROM database WHERE date = ? AND type = 'BET'", (current_date_str,))
                total_stakes = cursor.fetchone()[0] or 0.0


                # Append the data for the current day to the report output
                report_output += f"Date: {current_date_str}\n"
                report_output += "----------------------------------------\n"
                report_output += f" - Bets  |  Knockbacks  |  Knockback % - \n"
                report_output += f"{total_bets:,}      |      {total_knockbacks:,}      |      {total_knockbacks / total_bets * 100:.2f}%\n"
                report_output += f"\n - Stakes   |   Average Stake - \n"
                report_output += f"£{total_stakes:,.2f}     |     ~£{total_stakes / total_bets:,.2f}\n"
                report_output += f"\nClients: {total_unique_clients:,} | --: {unique_norisk_clients:,} | M: {unique_m_clients:,} | W: {unique_w_clients:,}\n"
                report_output += f"\nHorses: {horse_bets} | Dogs: {dog_bets} | Other: {other_bets}\n\n"
            
            conn.close()

            self.progress_label.config(text=f"---")

            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', report_output)
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")

        except Exception as e:
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "An error occurred while generating the report.\nPlease try again.")
            self.progress_label.config(text="Error with Monthly Report")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        
        finally:
            if conn:
                conn.close()

    def create_client_report(self, client_id):
        try:
            conn, cursor = self.database_manager.get_connection()
            client_id = client_id.upper()
            
            # Get the current date in string format
            current_date_str = datetime.now().strftime("%d/%m/%Y")
            formatted_time = datetime.now().strftime("%H:%M:%S")
    
            self.progress_label.config(text=f"Finding client data")
    
            # Fetch the count of bets for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'BET'", (client_id, current_date_str))
            total_bets = cursor.fetchone()[0]
            
            # Fetch the total stakes for the client for the current day
            cursor.execute("SELECT SUM(total_stake) FROM database WHERE customer_ref = ? AND date = ? AND type = 'BET'", (client_id, current_date_str))
            total_stakes = cursor.fetchone()[0] or 0.0
            
            # Fetch the count of knockbacks for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK'", (client_id, current_date_str))
            total_wageralerts = cursor.fetchone()[0]
            
            # Fetch the count of SMS for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'SMS WAGER'", (client_id, current_date_str))
            total_sms = cursor.fetchone()[0]
            
            # Fetch the count of bets for each sport for the client for the current day
            cursor.execute("SELECT sports, COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'BET' GROUP BY sports", (client_id, current_date_str))
            sport_counts = cursor.fetchall()
            
            self.progress_label.config(text=f"Finding knockback data")
    
            # Fetch the count of different types of wager alerts for the client for the current day
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Has Changed%'", (client_id, current_date_str))
            price_change = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Liability Exceeded: True%'", (client_id, current_date_str))
            liability_exceeded = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Event Has Ended%'", (client_id, current_date_str))
            event_ended = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Price Type Disallowed%'", (client_id, current_date_str))
            price_type_disallowed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%Sport Disallowed%'", (client_id, current_date_str))
            sport_disallowed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message LIKE '%User Max Stake Exceeded%'", (client_id, current_date_str))
            max_stake_exceeded = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND error_message NOT LIKE '%Price Has Changed%' AND error_message NOT LIKE '%Liability Exceeded: True%' AND error_message NOT LIKE '%Event Has Ended%' AND error_message NOT LIKE '%Price Type Disallowed%' AND error_message NOT LIKE '%Sport Disallowed%' AND error_message NOT LIKE '%User Max Stake Exceeded%'", (client_id, current_date_str))
            other_alert = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM database WHERE customer_ref = ? AND date = ? AND type = 'WAGER KNOCKBACK' AND (error_message LIKE '%Price Type Disallowed%' OR error_message LIKE '%Sport Disallowed%' OR error_message LIKE '%User Max Stake Exceeded%')", (client_id, current_date_str))
            user_restriction = cursor.fetchone()[0]
            
            self.progress_label.config(text=f"Calculating stakes")
    
            conn.close()
    
            # Initialize sport counts
            horse_bets = 0
            dog_bets = 0
            other_bets = 0
            
            # Map the sport counts
            sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
            for sport, count in sport_counts:
                sport_list = eval(sport)
                if sport_mapping['Horses'] in sport_list:
                    horse_bets += count
                if sport_mapping['Dogs'] in sport_list:
                    dog_bets += count
                if sport_mapping['Other'] in sport_list:
                    other_bets += count
            
            total_sport_bets = horse_bets + dog_bets + other_bets
            percentage_horse_racing = (horse_bets / total_sport_bets) * 100 if total_sport_bets else 0
            percentage_greyhound = (dog_bets / total_sport_bets) * 100 if total_sport_bets else 0
            percentage_other = (other_bets / total_sport_bets) * 100 if total_sport_bets else 0
    
        except Exception as e:
            self.report_ticket.config(state="normal")
            self.report_ticket.delete('1.0', tk.END)
            self.report_ticket.insert('1.0', "An error occurred while generating the report.\nPlease try again.")
            self.progress_label.config(text="Error with Client Report")
            self.report_ticket.tag_configure("center", justify='center')
            self.report_ticket.tag_add("center", "1.0", "end")
            self.report_ticket.config(state="disabled")
            return
        finally:
            if conn:
                conn.close()
    
        separator = "-" * 69

        if total_bets > 0:
            knockback_percentage = f"{total_wageralerts / total_bets * 100:.2f}%"
        else:
            knockback_percentage = "N/A"

        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)
    
        self.report_ticket.insert(tk.END, f"CLIENT REPORT\nGenerated at {formatted_time}\n", 'center')
        self.report_ticket.insert(tk.END, f"{client_id} - {current_date_str}\n", 'center')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
        self.report_ticket.insert(tk.END, f"Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{total_bets}\n", 'c')
        self.report_ticket.insert(tk.END, f"Knockbacks: ", 'center')
        self.report_ticket.insert(tk.END, f"{total_wageralerts}\n", 'c')
        self.report_ticket.insert(tk.END, f"Knockback %: ", 'center')
        self.report_ticket.insert(tk.END, f"{knockback_percentage}\n", 'c')
        self.report_ticket.insert(tk.END, f"SMS Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{total_sms}\n", 'c')
        self.report_ticket.insert(tk.END, f"Stakes: ", 'center')
        self.report_ticket.insert(tk.END, f"£{total_stakes:,}\n", 'c')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
        self.report_ticket.insert(tk.END, f"Knockbacks:\n", 'center')
        self.report_ticket.insert(tk.END, f"Price Change: ", 'center')
        self.report_ticket.insert(tk.END, f"{price_change}\n", 'c')
        self.report_ticket.insert(tk.END, f"Liability Exceeded: ", 'center')
        self.report_ticket.insert(tk.END, f"{liability_exceeded}\n", 'c')
        self.report_ticket.insert(tk.END, f"Event Ended: ", 'center')
        self.report_ticket.insert(tk.END, f"{event_ended}\n", 'c')
        self.report_ticket.insert(tk.END, f"Price Type Disallowed: ", 'center')
        self.report_ticket.insert(tk.END, f"{price_type_disallowed}\n", 'c')
        self.report_ticket.insert(tk.END, f"Sport Disallowed: ", 'center')
        self.report_ticket.insert(tk.END, f"{sport_disallowed}\n", 'c')
        self.report_ticket.insert(tk.END, f"Max Stake Exceeded: ", 'center')
        self.report_ticket.insert(tk.END, f"{max_stake_exceeded}\n", 'c')
        self.report_ticket.insert(tk.END, f"Other: ", 'center')
        self.report_ticket.insert(tk.END, f"{other_alert}\n", 'c')
        self.report_ticket.insert(tk.END, f"User Restriction: ", 'center')
        self.report_ticket.insert(tk.END, f"{user_restriction}\n", 'c')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
        self.report_ticket.insert(tk.END, f"Horse Racing Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{horse_bets} ({percentage_horse_racing:.2f}%)\n", 'c')
        self.report_ticket.insert(tk.END, f"Greyhound Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{dog_bets} ({percentage_greyhound:.2f}%)\n", 'c')
        self.report_ticket.insert(tk.END, f"Other Bets: ", 'center')
        self.report_ticket.insert(tk.END, f"{other_bets} ({percentage_other:.2f}%)\n", 'c')
        self.report_ticket.insert(tk.END, separator + "\n", 'center')
    
        self.report_ticket.config(state="disabled")
    
    def create_staff_report(self):
        global USER_NAMES
    
        course_updates = Counter()
        staff_updates = Counter()
        staff_updates_today = Counter()
        staff_updates_count_today = Counter()
        staff_updates_count_month = Counter()  # New counter for total updates for the month
        factoring_updates = Counter()
        offenders = Counter()
        daily_updates = Counter()
        individual_update_scores = []  # List to track individual update scores
        today = datetime.now().date()
        current_date = datetime.now().date()
        month_ago = current_date.replace(day=1)
        days_in_month = (current_date - month_ago).days + 1
    
        log_files = os.listdir(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs'))
        log_files.sort(key=lambda file: os.path.getmtime(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', file)))
        # Read all the log files from the past month
        for i, log_file in enumerate(log_files):
            file_date = datetime.fromtimestamp(os.path.getmtime(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', log_file))).date()
            if month_ago <= file_date <= current_date:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', log_file), 'r') as file:
                    lines = file.readlines()
    
                update_counts = {}
    
                for line in lines:
                    if line.strip() == '':
                        continue
    
                    parts = line.strip().split(' - ')
    
                    if len(parts) == 1 and parts[0].endswith(':'):
                        course = parts[0].replace(':', '')
                        continue
    
                    if len(parts) == 3:
                        time, staff_initials, score = parts
                        score = float(score)
                        staff_name = USER_NAMES.get(staff_initials, staff_initials)
                        course_updates[course] += score
                        staff_updates[staff_name] += score
                        daily_updates[(staff_name, file_date)] += score
    
                        # Track individual update scores
                        individual_update_scores.append((staff_name, score))
    
                        if file_date == today:
                            current_time = datetime.strptime(time, '%H:%M')
                            if course not in update_counts:
                                update_counts[course] = {}
                            if staff_name not in update_counts[course]:
                                update_counts[course][staff_name] = Counter()
                            update_counts[course][staff_name][current_time] += 1
    
                            if update_counts[course][staff_name][current_time] > 1:
                                offenders[staff_name] += 1
    
                            staff_updates_today[staff_name] += score
                            staff_updates_count_today[staff_name] += 1  # Increment the count for today's updates
    
                        # Increment the count for the month's updates
                        staff_updates_count_month[staff_name] += 1
    
        # Filter out non-staff members from staff_updates_today and staff_updates
        staff_updates_today = Counter({staff: count for staff, count in staff_updates_today.items() if staff in USER_NAMES.values()})
        staff_updates = Counter({staff: count for staff, count in staff_updates.items() if staff in USER_NAMES.values()})
    
        # Calculate average updates per day for each staff member
        average_updates_per_day = Counter()
        for (staff, date), count in daily_updates.items():
            if staff in USER_NAMES.values():
                average_updates_per_day[staff] += count
    
        for staff in average_updates_per_day:
            average_updates_per_day[staff] /= days_in_month
    
        factoring_log_files = os.listdir(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs'))
        factoring_log_files.sort(key=lambda file: os.path.getmtime(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs', file)))
    
        for log_file in factoring_log_files:
            with open(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs', log_file), 'r') as file:
                lines = file.readlines()
    
            for line in lines:
                if line.strip() == '':
                    continue
    
                data = json.loads(line)
                staff_initials = data['Staff']
                staff_name = USER_NAMES.get(staff_initials, staff_initials)
                factoring_updates[staff_name] += 1
    
        # Calculate the ratio of score to updates for each user for the current month
        score_to_updates_ratio = {}
        for staff in staff_updates_count_month:
            if staff_updates_count_month[staff] > 0:
                ratio = staff_updates[staff] / staff_updates_count_month[staff]
                score_to_updates_ratio[staff] = ratio
    
        # Find the user with the lowest ratio (busiest idiot)
        busiest_idiot = min(score_to_updates_ratio, key=score_to_updates_ratio.get)
    
        # Find the user with the highest ratio (playing the system)
        playing_the_system = max(score_to_updates_ratio, key=score_to_updates_ratio.get)
    
        # Find the user with the highest single update score
        highest_single_update_score = max(individual_update_scores, key=lambda item: item[1])
    
        # Find the user with the lowest single update score
        lowest_single_update_score = min(individual_update_scores, key=lambda item: item[1])
    
        # Find the top 3 highest daily total scores
        top_daily_total_scores = sorted(daily_updates.items(), key=lambda item: item[1], reverse=True)[:3]
    
        # Find the day with the most points claimed
        daily_total_scores = Counter()
        for (staff, date), score in daily_updates.items():
            daily_total_scores[date] += score
    
        day_with_most_points = daily_total_scores.most_common(1)[0]
        day_with_most_points_date = day_with_most_points[0]
        day_with_most_points_score = day_with_most_points[1]
    
        # Calculate the percentage share of points for each user on the day with the most points
        points_share = {}
        for (staff, date), score in daily_updates.items():
            if date == day_with_most_points_date:
                points_share[staff] = (score / day_with_most_points_score) * 100
    
        separator = "-" * 69
    
        self.report_ticket.config(state="normal")
        self.report_ticket.delete('1.0', tk.END)
    
        self.report_ticket.insert(tk.END, "STAFF REPORT\n", 'center')
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
    
        employee_of_the_month, _ = staff_updates.most_common(1)[0]
        self.report_ticket.insert(tk.END, f"Employee Of The Month:\n", 'center')
        self.report_ticket.insert(tk.END, f"{employee_of_the_month}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
        self.report_ticket.insert(tk.END, "Current Day", 'center')    
        self.report_ticket.insert(tk.END, "\nToday's Staff Scores:\n", 'center')
        for staff, count in sorted(staff_updates_today.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nToday's Staff Updates:\n", 'center')
        for staff, count in sorted(staff_updates_count_today.items(), key=lambda item: item[1], reverse=True):  # Use the new counter
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
        
        if offenders:
            self.report_ticket.insert(tk.END, "\nUpdation Offenders Today:\n", 'center')
            for staff, count in sorted(offenders.items(), key=lambda item: item[1], reverse=True):
                self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
    
        self.report_ticket.insert(tk.END, "Current Month", 'center')    
        self.report_ticket.insert(tk.END, f"\nScores:\n", 'center')
        for staff, count in sorted(staff_updates.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"\nUpdates:\n", 'center')  # New section for total updates
        for staff, count in sorted(staff_updates_count_month.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"\nAverage Daily Score:\n", 'center')
        for staff, avg_count in sorted(average_updates_per_day.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {avg_count:.2f}\n", 'c')
        
        self.report_ticket.insert(tk.END, "\nTop 3 Highest Daily Total Scores:\n", 'center')
        for (staff, date), score in top_daily_total_scores:
            formatted_date = date.strftime('%d/%m')
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {formatted_date}  |  {score:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nDay with Most Points Claimed:\n", 'center')
        formatted_date = day_with_most_points_date.strftime('%d/%m')
        self.report_ticket.insert(tk.END, f"\t{formatted_date}  |  {day_with_most_points_score:.2f}\n", 'c')
        self.report_ticket.insert(tk.END, "Points Share:\n", 'c')
        for staff, share in sorted(points_share.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {share:.2f}%\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nBusiest Idiot:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{busiest_idiot}\n", 'c')
    
        self.report_ticket.insert(tk.END, "Playing the System:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{playing_the_system}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nHighest Single Update Score:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{highest_single_update_score[0]}  |  {highest_single_update_score[1]:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "Lowest Single Update Score:\n", 'center')
        self.report_ticket.insert(tk.END, f"\t{lowest_single_update_score[0]}  |  {lowest_single_update_score[1]:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, "\nScores Per Event:\n", 'center')
        for course, count in sorted(course_updates.items(), key=lambda item: item[1], reverse=True)[:10]:
            self.report_ticket.insert(tk.END, f"\t{course}  |  {count:.2f}\n", 'c')
    
        self.report_ticket.insert(tk.END, f"{separator}\n", 'c')
    
        self.report_ticket.insert(tk.END, "All Time Staff Factoring:\n", 'center')
        for staff, count in sorted(factoring_updates.items(), key=lambda item: item[1], reverse=True):
            self.report_ticket.insert(tk.END, f"\t{staff}  |  {count}\n", 'c')
    
        self.progress_label.config(text=f"---")
        self.report_ticket.config(state="disabled")

    # def create_rg_report(self):

    #     data = get_database()
    #     user_scores = {}
    #     virtual_events = ['Portman Park', 'Sprintvalley', 'Steepledowns', 'Millersfield', 'Brushwood']

    #     self.progress["maximum"] = len(data)
    #     self.progress["value"] = 0

    #     for bet in data:
    #         self.progress["value"] += 1

    #         wager_type = bet.get('type', '').lower()
    #         if wager_type == 'bet':
    #             details = bet.get('details', {})
    #             bet_time = datetime.strptime(bet.get('time', ''), "%H:%M:%S")
    #             customer_reference = bet.get('customer_ref', '')
    #             stake = float(details.get('unit_stake', '£0').replace('£', '').replace(',', ''))

    #             if customer_reference not in user_scores:
    #                 user_scores[customer_reference] = {
    #                     'bets': [],
    #                     'odds': [],
    #                     'total_bets': 0,
    #                     'score': 0,
    #                     'average_stake': 0,
    #                     'max_stake': 0,
    #                     'min_stake': float('inf'),
    #                     'deposits': [],  # New field for storing deposits
    #                     'min_deposit': None,  # Initialize to None
    #                     'max_deposit': 0,
    #                     'total_deposit': 0,
    #                     'total_stake': 0,
    #                     'virtual_bets': 0,
    #                     'early_bets': 0,
    #                     'scores': {
    #                         'num_bets': 0,
    #                         'long_period': 0,
    #                         'stake_increase': 0,
    #                         'high_total_stake': 0,
    #                         'virtual_events': 0,
    #                         'chasing_losses': 0,
    #                         'early_hours': 0,
    #                         'high_deposit_total': 0,
    #                         'frequent_deposits': 0,
    #                         'increasing_deposits': 0,
    #                         'changed_payment_type': 0,
    #                 }
    #             }

    #             # Add the bet to the user's list of bets
    #             user_scores[customer_reference]['bets'].append((bet_time.strftime("%H:%M:%S"), stake))

    #             # Add the odds to the user's list of odds
    #             selections = details.get('selections', [])
    #             for selection in selections:
    #                 odds = selection[1]
    #                 if isinstance(odds, str):
    #                     if odds.lower() == 'evs':
    #                         odds = 2.0
    #                     elif odds.lower() == 'sp':
    #                         continue
    #                     else:
    #                         try:
    #                             odds = float(odds)
    #                         except ValueError:
    #                             continue
    #                 user_scores[customer_reference]['odds'].append(odds)
    #                 if any(event in selection[0] for event in virtual_events):
    #                     user_scores[customer_reference]['virtual_bets'] += 1
    #                     break

    #             # Increase the total number of bets
    #             user_scores[customer_reference]['total_bets'] += 1

    #             # Update the total stake
    #             user_scores[customer_reference]['total_stake'] += stake

    #             # Skip this iteration if the user has placed fewer than 6 bets
    #             if len(user_scores[customer_reference]['bets']) < 6:
    #                 continue

    #             # Update the max and min stakes
    #             user_scores[customer_reference]['max_stake'] = max(user_scores[customer_reference]['max_stake'], stake)
    #             user_scores[customer_reference]['min_stake'] = min(user_scores[customer_reference]['min_stake'], stake)

    #             # Calculate the new average stake
    #             total_stake = sum(stake for _, stake in user_scores[customer_reference]['bets'])
    #             user_scores[customer_reference]['average_stake'] = total_stake / len(user_scores[customer_reference]['bets'])

    #             # Add a point if the user has placed more than 10 bets
    #             if len(user_scores[customer_reference]['bets']) > 10 and user_scores[customer_reference]['scores']['num_bets'] == 0:
    #                 user_scores[customer_reference]['scores']['num_bets'] = 1

    #             # Add a point if the user has been gambling for a long period of time
    #             first_bet_time = datetime.strptime(user_scores[customer_reference]['bets'][0][0], "%H:%M:%S")
    #             if (bet_time - first_bet_time).total_seconds() > 2 * 60 * 60 and user_scores[customer_reference]['scores']['long_period'] == 0:  # 2 hours
    #                 user_scores[customer_reference]['scores']['long_period'] = 1

    #             # Add a point if the user has increased their stake over the average
    #             half = len(user_scores[customer_reference]['bets']) // 2
    #             first_half_stakes = [stake for _, stake in user_scores[customer_reference]['bets'][:half]]
    #             second_half_stakes = [stake for _, stake in user_scores[customer_reference]['bets'][half:]]
    #             if len(first_half_stakes) > 0 and len(second_half_stakes) > 0:
    #                 first_half_avg = sum(first_half_stakes) / len(first_half_stakes)
    #                 second_half_avg = sum(second_half_stakes) / len(second_half_stakes)
    #                 if second_half_avg > first_half_avg and user_scores[customer_reference]['scores']['stake_increase'] == 0:
    #                     user_scores[customer_reference]['scores']['stake_increase'] = 1

    #             # Add a point if the user's total stake is over £1000
    #             if user_scores[customer_reference]['total_stake'] > 1000 and user_scores[customer_reference]['scores']['high_total_stake'] == 0:
    #                 user_scores[customer_reference]['scores']['high_total_stake'] = 1

    #             # Add a point if the user has placed a bet on a virtual event
    #             if user_scores[customer_reference]['virtual_bets'] > 0 and user_scores[customer_reference]['scores']['virtual_events'] == 0:
    #                 user_scores[customer_reference]['scores']['virtual_events'] = 1

    #             # Check if the bet is placed during early hours
    #             if 0 <= bet_time.hour < 7:
    #                 user_scores[customer_reference]['early_bets'] += 1


    #     now_local = datetime.now(timezone('Europe/London'))
    #     today_filename = f'logs/depositlogs/deposits_{now_local.strftime("%Y-%m-%d")}.json'

    #     # Load the existing messages from the JSON file for today's date
    #     if os.path.exists(today_filename):
    #         with open(today_filename, 'r') as f:
    #             deposits = json.load(f)
            
    #     # Create a dictionary to store deposit information for each user
    #     deposit_info = defaultdict(lambda: {'total': 0, 'times': [], 'amounts': [], 'types': set()})

    #     # Iterate over the deposits
    #     for deposit in deposits:
    #         username = deposit['Username'].upper()
    #         amount = float(deposit['Amount'])
    #         time = datetime.strptime(deposit['Time'], "%Y-%m-%d %H:%M:%S")
    #         type_ = deposit['Type']

    #         # Check if the user exists in the user_scores dictionary
    #         if username not in user_scores:
    #             user_scores[username] = {
    #                 'bets': [],
    #                 'odds': [],
    #                 'total_bets': 0,
    #                 'score': 0,
    #                 'average_stake': 0,
    #                 'max_stake': 0,
    #                 'min_stake': float('inf'),
    #                 'deposits': [],  # New field for storing deposits
    #                 'min_deposit': None,  # Initialize to None
    #                 'max_deposit': 0,
    #                 'total_deposit': 0,
    #                 'total_stake': 0,
    #                 'virtual_bets': 0,
    #                 'early_bets': 0,
    #                 'scores': {
    #                     'num_bets': 0,
    #                     'long_period': 0,
    #                     'stake_increase': 0,
    #                     'high_total_stake': 0,
    #                     'virtual_events': 0,
    #                     'chasing_losses': 0,
    #                     'early_hours': 0,
    #                     'high_deposit_total': 0,
    #                     'frequent_deposits': 0,
    #                     'increasing_deposits': 0,
    #                     'changed_payment_type': 0,
    #                 }
    #             }

    #         # Update the user's deposit information
    #         deposit_info[username]['total'] += amount
    #         deposit_info[username]['times'].append(time)
    #         deposit_info[username]['amounts'].append(amount)
    #         deposit_info[username]['types'].add(type_)

    #         user_scores[username]['deposits'].append(amount)

    #         # Check if the user's total deposit amount is over £500
    #         if deposit_info[username]['total'] > 500:
    #             if username not in user_scores:
    #                 user_scores[username] = {
    #                     'scores': {
    #                         'high_deposit_total': 0,
    #                         # Initialize other fields as needed
    #                     }
    #                 }
    #             user_scores[username]['scores']['high_deposit_total'] = 1

    #         # Check if the user has deposited more than 4 times in an hour
    #         deposit_info[username]['times'].sort()
    #         for i in range(4, len(deposit_info[username]['times'])):
    #             if (deposit_info[username]['times'][i] - deposit_info[username]['times'][i-4]).total_seconds() <= 3600:
    #                 if username not in user_scores:
    #                     user_scores[username] = {'scores': {'frequent_deposits': 0}}
    #                 user_scores[username]['scores']['frequent_deposits'] = 1
    #                 break

    #         # Check if the user's deposits have increased more than twice
    #         increases = 0
    #         for i in range(2, len(deposit_info[username]['amounts'])):
    #             if deposit_info[username]['amounts'][i] > deposit_info[username]['amounts'][i-1] > deposit_info[username]['amounts'][i-2]:
    #                 increases += 1
    #         if increases >= 2:
    #             if username not in user_scores:
    #                 user_scores[username] = {'scores': {'increasing_deposits': 0}}
    #             user_scores[username]['scores']['increasing_deposits'] = 1

    #         # Check if the user has changed payment type
    #         if len(deposit_info[username]['types']) > 1:
    #             if username not in user_scores:
    #                 user_scores[username] = {'scores': {'changed_payment_type': 0}}
    #             user_scores[username]['scores']['changed_payment_type'] = 1

    #     for username, info in user_scores.items():
    #         if info['deposits']:  # Check if the list is not empty
    #             info['min_deposit'] = min(info['deposits'])
    #             info['max_deposit'] = max(info['deposits'])
    #         else:
    #             info['min_deposit'] = 0
    #             info['max_deposit'] = 0
    #         info['total_deposit'] = deposit_info[username]['total']


    #     # After processing all bets, calculate the early hours score
    #     for user, scores in user_scores.items():
    #         if scores['early_bets'] > 3:
    #             scores['scores']['early_hours'] = 1

    #     # After processing all bets, calculate the chasing losses score
    #     for user, scores in user_scores.items():
    #         num_bets = len(scores['bets'])
    #         if num_bets >= 5:  # Only calculate if the user has placed at least 5 bets
    #             split_index = int(num_bets * 0.7)  # Calculate the index to split at 70%
    #             early_odds = scores['odds'][:split_index]
    #             late_odds = scores['odds'][split_index:]
    #             if early_odds and late_odds:  # Check that both lists are not empty
    #                 early_avg = sum(early_odds) / len(early_odds)
    #                 late_avg = sum(late_odds) / len(late_odds)
    #                 if late_avg - early_avg > 4:  # Set the threshold as needed
    #                     scores['scores']['chasing_losses'] = 1


    #     # Update the total score
    #     for user, scores in user_scores.items():
    #         scores['score'] = sum(scores['scores'].values())
                
    #     # Filter out the users who have a score of 0
    #     user_scores = {user: score for user, score in user_scores.items() if score['score'] > 0}

    #     return user_scores
    
    # def update_rg_report(self):
    #     print("Updating RG Report")
    #     user_scores = self.create_rg_report()
    #     print("RG Report Updated")
    #     user_scores = dict(sorted(user_scores.items(), key=lambda item: item[1]['score'], reverse=True))
    #     key_descriptions = {
    #         'num_bets': 'High Number of Bets',
    #         'stake_increase': 'Stakes Increasing',
    #         'virtual_events': 'Bets on Virtual events',
    #         'chasing_losses': 'Odds Increasing, Possibly Chasing Losses',
    #         'high_total_stake': 'High Total Stake',
    #         'early_hours': 'Active in the Early Hours',
    #         'high_deposit_total': 'Total Deposits Over £500',
    #         'frequent_deposits': 'More than 4 Deposits in an Hour',
    #         'increasing_deposits': 'Deposits Increasing',
    #         'changed_payment_type': 'Changed Payment Type'
    #     }

    #     report_output = ""
    #     report_output += f"\tRG SCREENER\n\n"

    #     for user, scores in user_scores.items():
    #         if scores['score'] > 1:
    #             report_output += f"\n{user} - Risk Score: {scores['score']}\n"
    #             report_output += f"This score is due to:\n"
    #             for key, value in scores['scores'].items():
    #                 if value == 1:
    #                     report_output += f"- {key_descriptions.get(key, key)}\n"
    #             report_output += f"\nBets: {scores['total_bets']}  |  "
    #             report_output += f"Total Stake: £{scores['total_stake']:.2f}\n"
    #             report_output += f"Avg Stake: £{scores['average_stake']:.2f}  |  "
    #             report_output += f"Max: £{scores['max_stake']:.2f}  |  "
    #             report_output += f"Min: £{scores['min_stake']:.2f}\n"
    #             report_output += f"Virtual Bets: {scores['virtual_bets']}  |  "
    #             report_output += f"Early Hours Bets: {scores['early_bets']}\n"
    #             report_output += f"Deposits: £{scores['total_deposit']:.2f}  |  "
    #             report_output += f"Max: £{scores['max_deposit']:.2f}  |  "
    #             report_output += f"Min: £{scores['min_deposit']:.2f}\n"
    #             report_output += "\n"

    #     self.report_ticket.config(state='normal')
    #     self.report_ticket.delete('1.0', tk.END)
    #     self.report_ticket.insert(tk.END, report_output)
    #     self.report_ticket.config(state='disabled')

    def create_traders_report(self):
        self.progress_label.config(text="Retrieving database")
        self.report_button.config(state="disabled")
        vip_clients, _, _, _ = access_data()
        conn = None
        cursor = None
        try:
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
            
            self.progress_label.config(text=f"Finding users beating the SP...")
            current_date = datetime.now().strftime('%d/%m/%Y')
            cursor.execute("SELECT DISTINCT customer_ref FROM database WHERE date = ?", (current_date,))
            customer_refs = [row[0] for row in cursor.fetchall()]
            print(f"Customer refs: {customer_refs}")
                
            self.progress_label.config(text=f"Retrieving client wagers...")
            client_wagers = self.get_client_wagers(conn, customer_refs)
            self.progress_label.config(text=f"Getting Results...")
            data = self.get_results_json()
            self.progress_label.config(text=f"Comparing odds to SP...")
            results = self.compare_odds(client_wagers, data)
            print(f"Results: {results}")
    
            # Initialize new lists
            selection_to_users = defaultdict(list)
            users_without_risk_category = set()
            
            self.progress_label.config(text=f"Finding potential W users...")
            cursor.execute("SELECT * FROM database WHERE date = ?", (current_date,))
            database_data = cursor.fetchall()
    
            for bet in database_data:
                try:
                    wager_type = bet[5]
                    if wager_type == 'BET':
                        # Parse the selections from the JSON string stored in the database
                        details = json.loads(bet[10])
                        customer_reference = bet[3]
                        customer_risk_category = bet[4]
                    
                        for selection in details:
                            selection_name = selection[0]
                            odds = selection[1]
                    
                            if isinstance(odds, str):
                                if odds == 'SP':
                                    continue  
                                elif odds.lower() == 'evs':
                                    odds = 2.0  
                                else:
                                    odds = float(odds)  
                    
                            selection_to_users[selection_name].append((customer_reference, customer_risk_category))
                except Exception as e:
                    print(f"Error processing bet: {bet}, Error: {e}")
                            
            for selection, users in selection_to_users.items():
                users_with_risk_category = [user for user in users if user[1] and user[1] != '-']
                users_without_risk_category_for_selection = [user for user in users if not user[1] or user[1] == '-']
            
                if len(users_with_risk_category) / len(users) > 0.6:
                    users_without_risk_category.update(users_without_risk_category_for_selection)
            
            # Exclude VIP clients from users_without_risk_category
            users_without_risk_category = {user for user in users_without_risk_category if user[0] not in vip_clients}
            print(f"Users without risk category: {users_without_risk_category}")
    
            self.progress_label.config(text=f"---")
            self.report_button.config(state="normal")
    
            return results, users_without_risk_category
                    
        except Exception as e:
            print(f"An error occurred: {e}")
            return [], set()
        finally:
            if conn:
                conn.close()
    
    def update_traders_report(self):
        results, users_without_risk_category = self.create_traders_report()
        self.initialize_text_tags()
    
        separator = "-" * 69
    
        self.report_ticket.config(state='normal')
        self.report_ticket.delete('1.0', tk.END)
        self.report_ticket.insert(tk.END, "TRADERS SCREENER\n", 'center')
        self.report_ticket.insert(tk.END, f"{separator}\n")
        self.report_ticket.insert(tk.END, "Please do your own research before taking any action.\n\n")
    
        self.report_ticket.insert(tk.END, "- Users beating the SP -\n", 'center')
        self.report_ticket.insert(tk.END, "Users who have placed > 5 bets and > 50% of their selections beat the SP - Horses & Dogs.\n")
        self.report_ticket.insert(tk.END, f"For best results, run this function at the end of the day when all results are in.\n\n")
        if results:
            # Sort results by percentage_beaten in descending order
            sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
            for customer_ref, percentage_beaten, total_bets in sorted_results:
                self.report_ticket.insert(tk.END, f"{customer_ref}: ", 'bold')
                self.report_ticket.insert(tk.END, f"{total_bets} slns, {percentage_beaten:.2f}% beat the SP.\n")
        else:
            self.report_ticket.insert(tk.END, "No users currently significantly beating the SP. This could be because\n- Results not yet available\n- Users not meeting criteria (over 5 bets, over 50% selections beat SP)\n\n")            
    
        self.report_ticket.insert(tk.END, f"\n{separator}\n")
        self.report_ticket.insert(tk.END, "- Clients wagering on selections containing multiple risk users -\n", 'center')
        self.report_ticket.insert(tk.END, "Clients who have wagered on selections where > 60% of other bets are from risk users.\nThis excludes any user from our 'VIP' list.\n\n")
    
        users_without_risk_category_str = '  |  '.join(user[0] for user in users_without_risk_category)
        self.report_ticket.insert(tk.END, users_without_risk_category_str)
    
        self.report_ticket.config(state='disabled')

    def compare_odds(self, client_wagers, race_results):
        results = []
        for customer_ref, wagers in client_wagers.items():
            total_bets = 0
            bets_beaten = 0 

            for betID, selections in wagers:
                for selection in selections:
                    if len(selection) >= 2:
                        race_name = selection[0]
                        placed_odds = selection[1]
                        
                        if " - " not in race_name:
                            continue
                        
                        total_bets += 1
                        
                        race_name_parts = race_name.split(" - ")
                        race_time = race_name_parts[0].split(", ")[1]
                        selection_name = race_name_parts[1]
                        
                        for event in race_results:
                            for meeting in event['meetings']:
                                for race in meeting['events']:
                                    if race['status'] == 'Result':
                                        race_start_time = race['startDateTime'].split('T')[1][:5]
                                        race_full_name = f"{meeting['meetinName']}, {race_start_time}"
                                        
                                        if race_full_name.lower() == race_name_parts[0].lower():
                                            for race_selection in race['selections']:
                                                if meeting['sportCode'] == 'g':
                                                    trap_number = 'Trap ' + race_selection['runnerNumber']
                                                    
                                                    if trap_number.lower() == selection_name.lower():
                                                        last_price_fractional = race_selection['lastPrice']
                                                        last_price_decimal = self.fractional_to_decimal(last_price_fractional)
                                                        
                                                        if placed_odds == 'SP':
                                                            placed_odds = last_price_decimal
                                                        if placed_odds == 'evs':
                                                            placed_odds = 2.0
                                                        
                                                        if placed_odds > last_price_decimal:
                                                            bets_beaten += 1
                                                else:
                                                    if race_selection['name'].lower() == selection_name.lower():
                                                        last_price_fractional = race_selection['lastPrice']
                                                        last_price_decimal = self.fractional_to_decimal(last_price_fractional)
                                                        
                                                        if placed_odds == 'SP':
                                                            placed_odds = last_price_decimal
                                                        if placed_odds == 'evs':
                                                            placed_odds = 2.0
                                                        
                                                        if placed_odds > last_price_decimal:
                                                            bets_beaten += 1
            
            if total_bets > 5:
                percentage_beaten = (bets_beaten / total_bets) * 100
                if percentage_beaten >= 50.0:
                    results.append((customer_ref, percentage_beaten, total_bets))
        
        return results
    
    def get_results_json(self):
        url = os.getenv('RESULTS_API_URL')

        # Ensure the API URL is loaded correctly
        if not url:
            raise ValueError("RESULTS_API_URL environment variable is not set")

        response = requests.get(url)
        response.raise_for_status()  # Ensure we raise an error for bad responses
        data = response.json()
        return data
    
    def get_client_wagers(self, conn, customer_refs):
        current_date_str = datetime.now().strftime("%d/%m/%Y")
        cursor = conn.cursor()
        
        # Convert customer_refs to a tuple for use in SQL IN clause
        customer_refs_tuple = tuple(customer_refs)
        
        # Construct the SQL query with the appropriate number of placeholders
        placeholders = ','.join(['?'] * len(customer_refs_tuple))
        query = f"SELECT * FROM database WHERE customer_ref IN ({placeholders}) AND date = ?"
        
        # Execute the query with the customer_refs and current_date_str as parameters
        cursor.execute(query, (*customer_refs_tuple, current_date_str))
        wagers = cursor.fetchall()
        
        # Process the results
        client_wagers = defaultdict(list)
        for bet in wagers:
            if bet[5] == 'BET':
                betID = bet[0]
                customer_ref = bet[3]
                selections = json.loads(bet[10])
                client_wagers[customer_ref].append((betID, selections))
        
        return client_wagers

    def fractional_to_decimal(self, fractional_odds):
        if fractional_odds.lower() == 'evens':
            return 2.0
        numerator, denominator = map(int, fractional_odds.split('-'))
        return (numerator / denominator) + 1
    
    def factoring_sheet(self):
        try:
            self.factoring_tree.delete(*self.factoring_tree.get_children())
            spreadsheet = self.gc.open('Factoring Diary')
            worksheet = spreadsheet.get_worksheet(4)
            data = worksheet.get_all_values()
            self.last_refresh_label.config(text=f"Last Refresh:\n{datetime.now().strftime('%H:%M:%S')}")
            for row in data[2:][::-1]: 
                self.factoring_tree.insert("", "end", values=[row[5], row[0], row[1], row[2], row[3], row[4]])
        except Exception as e:
            print(f"Error in factoring_sheet: {e}")
    
    def freebet_sheet(self):
        try:
            current_month = datetime.now().strftime('%B')
            spreadsheet_name = 'Reporting ' + current_month
            self.freebet_tree.delete(*self.freebet_tree.get_children())
            spreadsheet = self.gc.open(spreadsheet_name)
            worksheet = spreadsheet.get_worksheet(5)
            data = worksheet.get_all_values()
            self.last_refresh_freebets_label.config(text=f"Last Refresh:\n{datetime.now().strftime('%H:%M:%S')}")
            for row in data[2:][::-1]:
                if row[2]: 
                    self.freebet_tree.insert("", "end", values=[row[1], row[3], row[4], row[5], row[10]])
        except Exception as e:
            print(f"Error in freebet_sheet: {e}")

    def popup_sheet(self):
        try:
            filter_id = 65
            custom_field_id = 'acb5651370e1c1efedd5209bda3ff5ceece09633'
            pipedrive_persons_api_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')

            # Ensure the API URL is loaded correctly
            if not pipedrive_persons_api_url:
                raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

            filter_url = f'{pipedrive_persons_api_url}?filter_id={filter_id}&api_token={self.pipedrive_api_token}'
            response = requests.get(filter_url)
            if response.status_code == 200:
                persons = response.json().get('data', [])
                user_data = [(person['c1f84d7067cae06931128f22af744701a07b29c6'], person.get(custom_field_id, 'N/A')) for person in persons]
                self.last_refresh_popup_label.config(text=f"Last Refresh:\n{datetime.now().strftime('%H:%M:%S')}")

                user_data.sort(key=lambda x: x[1], reverse=True)
                for username, compliance_date in user_data:
                    self.popup_tree.insert('', tk.END, values=(username, compliance_date))
        except Exception as e:
            print(f"Error in popup_sheet: {e}")

    def get_realtime_users(self):
        analytics = build('analyticsdata', 'v1beta', credentials=self.analytics_credentials)
        response = analytics.properties().runRealtimeReport(
            property='properties/409643682',  # Replace with your Google Analytics Property ID
            body=
                {
                "metrics": [
                    {
                    "name": "activeUsers"
                    }
                ],
                "minuteRanges": [
                    {
                    "startMinutesAgo": 5,
                    "endMinutesAgo": 0
                    }
                ]
                }
        ).execute()
        return response

    def update_live_users(self):
        try:
            response = self.get_realtime_users()
            active_users = response['rows'][0]['metricValues'][0]['value']
            self.root.after(0, self.update_live_users_label, active_users)
        except Exception as e:
            print(f"Failed to update live users: {e}")
            self.root.after(0, self.update_live_users_label, "---")

    def update_live_users_label(self, active_users):
        self.live_users_label.config(text=active_users)

    def live_users_loop(self):
        while True:
            self.update_live_users()
            time.sleep(20)

    def start_live_users_thread(self):
        threading.Thread(target=self.live_users_loop, daemon=True).start()

    def run_factoring_sheet_thread(self):
        self.factoring_thread = threading.Thread(target=self.factoring_sheet, daemon=True)
        self.factoring_thread.start()
    
    def run_freebet_sheet_thread(self):
        self.freebet_thread = threading.Thread(target=self.freebet_sheet, daemon=True)
        self.freebet_thread.start()

    def run_popup_sheet_thread(self):
        self.popup_thread = threading.Thread(target=self.popup_sheet, daemon=True)
        self.popup_thread.start()
