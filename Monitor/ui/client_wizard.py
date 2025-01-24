import os
import json
import time
import threading
import gspread
import requests
import gspread
import pyperclip
import tkinter as tk
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from oauth2client.service_account import ServiceAccountCredentials
from tkinter import ttk, messagebox
from utils import log_notification, user_login
from config import NETWORK_PATH_PREFIX, get_user, set_user

class ClientWizard:
    def __init__(self, root, default_tab="Factoring"):
        print(default_tab)
        self.root = root
        self.default_tab = default_tab
        self.toplevel = tk.Toplevel(self.root)
        self.toplevel.title("Client Reporting and Modifications")
        self.toplevel.geometry("600x300")
        self.toplevel.iconbitmap('Monitor/splash.ico')
        screen_width = self.toplevel.winfo_screenwidth()
        self.toplevel.geometry(f"+{screen_width - 1700}+700")
        self.username_entry = None

        # Load environment variables
        self.pipedrive_api_token = os.getenv('PIPEDRIVE_API_KEY')
        self.pipedrive_api_url = os.getenv('PIPEDRIVE_API_URL')

        # Ensure the API URL is loaded correctly
        if not self.pipedrive_api_url:
            raise ValueError("PIPEDRIVE_API_URL environment variable is not set")

        self.pipedrive_api_url = f'{self.pipedrive_api_url}?api_token={self.pipedrive_api_token}'
        # Load Google service account credentials from environment variables
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
        scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
        self.gc = gspread.authorize(credentials)

        self.confirm_betty_update_bool = tk.BooleanVar()
        self.confirm_betty_update_bool.set(False)
        self.send_confirmation_email_bool = tk.BooleanVar()
        self.send_confirmation_email_bool.set(True) 

        # Initialize UI components
        self.initialize_ui()

    def initialize_ui(self):
        self.wizard_frame = ttk.Frame(self.toplevel, style='Card')
        self.wizard_frame.place(x=5, y=5, width=590, height=290)

        self.wizard_notebook = ttk.Notebook(self.wizard_frame)
        self.wizard_notebook.pack(fill='both', expand=True)

        self.report_freebet_tab = self.apply_freebet_tab()
        self.rg_popup_tab = self.apply_rg_popup()
        self.closure_requests_tab = self.apply_closure_requests()
        self.add_factoring_tab = self.apply_factoring_tab()

        self.wizard_notebook.add(self.report_freebet_tab, text="Report Freebet")
        self.wizard_notebook.add(self.rg_popup_tab, text="RG Popup")
        self.wizard_notebook.add(self.add_factoring_tab, text="Apply Factoring")
        self.wizard_notebook.add(self.closure_requests_tab, text="Closure Requests")
        self.select_default_tab()

    def select_default_tab(self):
        tab_mapping = {
            "Freebet": 1,
            "Popup": 0,
            "Factoring": 2,
            "Closure": 3
        }
        
        tab_index = tab_mapping.get(self.default_tab, 0)
        print(tab_index)
        self.wizard_notebook.select(tab_index)

    def apply_rg_popup(self):
        custom_field_id = 'acb5651370e1c1efedd5209bda3ff5ceece09633'  # Your custom field ID

        def handle_submit():
            submit_button.config(state=tk.DISABLED)

            if not entry1.get():
                progress_note.config(text="Error: Please make sure all fields are completed.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            username = entry1.get().strip()

            search_url = os.getenv('PIPEDRIVE_PERSONS_SEARCH_API_URL')
            if not search_url:
                raise ValueError("PIPEDRIVE_PERSONS_SEARCH_API_URL environment variable is not set")

            update_base_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')
            if not update_base_url:
                raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

            params = {
                'term': username,
                'item_types': 'person',
                'fields': 'custom_fields',
                'exact_match': 'true',
                'api_token': self.pipedrive_api_token
            }

            response = requests.get(search_url, params=params)
            if response.status_code == 200:
                persons = response.json().get('data', {}).get('items', [])

                if not persons:
                    progress_note.config(text=f"No persons found for username: {username} in Pipedrive.", anchor='center', justify='center')
                    time.sleep(2)
                    submit_button.config(state=tk.NORMAL)
                    progress_note.config(text="---", anchor='center', justify='center')
                    return

                for person in persons:
                    person_id = person['item']['id']
                    update_url = f'{update_base_url}/{person_id}?api_token={self.pipedrive_api_token}'
                    update_data = {
                        custom_field_id: date.today().strftime('%m/%d/%Y')
                    }
                    update_response = requests.put(update_url, json=update_data)
                    if update_response.status_code == 200:
                        log_notification(f"{get_user()} applied RG Popup to {username.upper()}", True)
                        progress_note.config(text=f"Successfully updated {username} in Pipedrive.", anchor='center', justify='center')
                        time.sleep(2)
                        submit_button.config(state=tk.NORMAL)
                        entry1.delete(0, tk.END)
                        progress_note.config(text="---", anchor='center', justify='center')
                        return
                    else:
                        messagebox.showerror("Error", f"Error updating person {person_id}: {update_response.status_code}")
                        progress_note.config(text=f"Error updating {username} in Pipedrive.", anchor='center', justify='center')
                        time.sleep(2)
                        submit_button.config(state=tk.NORMAL)
                        progress_note.config(text="---", anchor='center', justify='center')
                        return
            else:
                print(f'Error: {response.status_code}')
                progress_note.config(text=f"An error occurred.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            # Re-enable the submit button
            submit_button.config(state=tk.NORMAL)

        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height

        # Left section
        left_frame = ttk.Frame(frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_rowconfigure(2, weight=1)  # Ensure the left frame takes up the entire height

        username_label = ttk.Label(left_frame, text="Client Username")
        username_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry1 = ttk.Entry(left_frame)
        entry1.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        submit_button = ttk.Button(left_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2", width=40)
        submit_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        tree_title = ttk.Label(right_frame, text="RG Popup", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        tree_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        tree_description = ttk.Label(right_frame, text="Apply a Responsible Gambling Questionnaire on users next login.", wraplength=200, anchor='center', justify='center')
        tree_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        progress_note.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Add the new tab to the notebook
        self.wizard_notebook.add(frame, text="RG Popup")

        return frame

    def apply_factoring_tab(self):
        def handle_submit():
            if not get_user():
                user_login()

            submit_button.config(state=tk.DISABLED)
            current_time = datetime.now().strftime("%H:%M:%S")
            current_date = datetime.now().strftime("%d/%m/%Y")

            if not entry1.get() or not entry3.get():
                progress_note.config(text="Error: Please make sure all fields are completed.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            try:
                float(entry3.get())
            except ValueError:
                progress_note.config(text="Error: Assessment rating should be a number.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return

            params = {
                'term': entry1.get(),
                'item_types': 'person',
                'fields': 'custom_fields',
                'exact_match': 'true',
                'api_token': self.pipedrive_api_token
            }

            copy_string = ""
            if entry2.get() in ["W - WATCHLIST", "M - BP ONLY NO OFFERS", "C - MAX £100 STAKE"]:
                copy_string = f"{current_date} - {entry2.get().split(' - ')[1]} {get_user()}"
            pyperclip.copy(copy_string)

            progress_note.config(text="Applying to get_user() on Pipedrive...\n\n", anchor='center', justify='center')
            response = requests.get(self.pipedrive_api_url, params=params)
            if response.status_code == 200:
                persons = response.json()['data']['items']
                if not persons:
                    progress_note.config(text=f"Error: No persons found in pipedrive for username: {entry1.get()}", anchor='center', justify='center')
                    time.sleep(2)
                    submit_button.config(state=tk.NORMAL)
                    progress_note.config(text="---", anchor='center', justify='center')
                    return

                for person in persons:
                    person_id = person['item']['id']

                    update_base_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')
                    if not update_base_url:
                        raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")

                    update_url = f'{update_base_url}/{person_id}?api_token={self.pipedrive_api_token}'
                    update_data = {
                        'ab6b3b25303ffd7c12940b72125487171b555223': entry2.get()
                    }
                    update_response = requests.put(update_url, json=update_data)

                    if update_response.status_code == 200:
                        print(f'Successfully updated person {person_id}')
                    else:
                        print(f'Error updating person {person_id}: {update_response.status_code}')
            else:
                print(f'Error: {response.status_code}')
                progress_note.config(text=f"Error: {response.status_code}", anchor='center', justify='center')
                time.sleep(1)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')

            progress_note.config(text="Factoring Applied on Pipedrive.\nReporting on Factoring Log...\n", anchor='center', justify='center')

            spreadsheet = self.gc.open('Factoring Diary')
            worksheet = spreadsheet.get_worksheet(4)
            
            progress_note.config(text="Adding entry to Factoring Log...\n\n", anchor='center', justify='center')

            next_row = len(worksheet.col_values(1)) + 1
            entry2_value = entry2.get().split(' - ')[0]
            worksheet.update_cell(next_row, 1, current_time)
            worksheet.update_cell(next_row, 2, entry1.get().upper())
            worksheet.update_cell(next_row, 3, entry2_value)
            worksheet.update_cell(next_row, 4, entry3.get())
            worksheet.update_cell(next_row, 5, get_user()) 
            worksheet.update_cell(next_row, 6, current_date)

            worksheet3 = spreadsheet.get_worksheet(3)
            username = entry1.get().upper()
            progress_note.config(text="Trying to find user in Factoring Diary...\n\n", anchor='center', justify='center')
            matching_cells = worksheet3.findall(username, in_column=2)

            if not matching_cells:
                progress_note.config(text=f"Error: No persons found in factoring diary for client: {username}. Factoring logged, but not updated in diary.", anchor='center', justify='center')
                time.sleep(1)
            else:
                progress_note.config(text="Found user in factoring Diary.\nUpdating...\n", anchor='center', justify='center')
                cell = matching_cells[0]
                row = cell.row
                worksheet3.update_cell(row, 9, entry2_value)  # Column I
                worksheet3.update_cell(row, 10, entry3.get())  # Column J
                worksheet3.update_cell(row, 12, current_date)  # Column L

            data = {
                'Time': current_time,
                'Username': entry1.get().upper(),
                'Risk Category': entry2_value,
                'Assessment Rating': entry3.get(),
                'Staff': get_user()
            }
            with open(os.path.join(NETWORK_PATH_PREFIX, 'logs', 'factoringlogs', 'factoring.json'), 'a') as file:
                file.write(json.dumps(data) + '\n')

            progress_note.config(text="Factoring Added Successfully.\n\n", anchor='center', justify='center')
            log_notification(f"{get_user()} Factored {entry1.get().upper()} - {entry2_value} - {entry3.get()}")
            time.sleep(1)
            submit_button.config(state=tk.NORMAL)
                
            # Clear the fields after successful submission
            entry1.delete(0, tk.END)
            entry2.set(options[0])
            entry3.delete(0, tk.END)

            progress_note.config(text="---", anchor='center', justify='center')

        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height

        # Left section
        left_frame = ttk.Frame(frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_rowconfigure(3, weight=1)  # Ensure the left frame takes up the entire height

        username_label = ttk.Label(left_frame, text="Client Username")
        username_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry1 = ttk.Entry(left_frame)
        entry1.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        riskcat_label = ttk.Label(left_frame, text="Risk Category")
        riskcat_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        options = ["", "W - WATCHLIST", "M - BP ONLY NO OFFERS", "C - MAX £100 STAKE"]
        entry2 = ttk.Combobox(left_frame, values=options, state="readonly")
        entry2.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        entry2.set(options[0])

        ass_rating_label = ttk.Label(left_frame, text="Assessment Rating")
        ass_rating_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        entry3 = ttk.Entry(left_frame)
        entry3.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        submit_button = ttk.Button(left_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2", width=40)
        submit_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        report_freebet_title = ttk.Label(right_frame, text="Modify Client Terms", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        report_freebet_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        tree_description = ttk.Label(right_frame, text="Apply factoring and report new assessment ratings for clients.", wraplength=200, anchor='center', justify='center')
        tree_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        progress_note.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="ew")

        return frame

    def apply_freebet_tab(self):
        current_month = datetime.now().strftime('%B')
        if not get_user():
            user_login()
    
        def handle_submit():
            # Disable the submit button while processing
            submit_button.config(state=tk.DISABLED)
    
            if not entry1.get() or not entry2.get() or not entry3.get():
                progress_note.config(text="Error: Please make sure all fields are completed.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return
            
            try:
                float(entry3.get())
            except ValueError:
                progress_note.config(text="Error: Freebet amount should be a number.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return
    
            progress_note.config(text="Finding Reporting Sheet", anchor='center', justify='center')
    
            spreadsheet_name = 'Reporting ' + current_month
            try:
                spreadsheet = self.gc.open(spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                progress_note.config(text=f"Error: {spreadsheet_name} not found.", anchor='center', justify='center')
                time.sleep(2)
                submit_button.config(state=tk.NORMAL)
                progress_note.config(text="---", anchor='center', justify='center')
                return
    
            progress_note.config(text=f"Found {spreadsheet_name}.\nFree bet for {entry1.get().upper()} being added.\n", anchor='center', justify='center')
    
            worksheet = spreadsheet.get_worksheet(5)
            next_row = len(worksheet.col_values(2)) + 1
    
            current_date = datetime.now().strftime("%d/%m/%Y")  
            current_time = datetime.now().strftime("%H:%M:%S")
            worksheet.update_cell(next_row, 2, current_date)
            worksheet.update_cell(next_row, 3, entry2.get().upper())
            worksheet.update_cell(next_row, 4, current_time)
            worksheet.update_cell(next_row, 5, entry1.get().upper())
            worksheet.update_cell(next_row, 6, entry3.get())
            worksheet.update_cell(next_row, 11, get_user())
    
            progress_note.config(text=f"Free bet for {entry1.get().upper()} added successfully to reporting {current_month}\n", anchor='center', justify='center')
            log_notification(f"{get_user()} applied £{entry3.get()} {entry2.get().capitalize()} to {entry1.get().upper()}")
    
            # Clear the fields after successful submission
            entry1.delete(0, tk.END)
            entry2.set(options[0])
            entry3.delete(0, tk.END)

            time.sleep(2)
            progress_note.config(text="---", anchor='center', justify='center')
            submit_button.config(state=tk.NORMAL)
    
        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height

        # Left section
        left_frame = ttk.Frame(frame)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_frame.grid_rowconfigure(3, weight=1)  # Ensure the left frame takes up the entire height

        username = ttk.Label(left_frame, text="Client Username")
        username.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        entry1 = ttk.Entry(left_frame)
        entry1.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
        type = ttk.Label(left_frame, text="Free bet Type")
        type.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        options = ["", "FREE BET", "DEPOSIT BONUS", "10MIN BLAST", "OTHER"]
        entry2 = ttk.Combobox(left_frame, values=options, state="readonly")
        entry2.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        entry2.set(options[0])
    
        amount = ttk.Label(left_frame, text="Amount")
        amount.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        entry3 = ttk.Entry(left_frame)
        entry3.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
    
        submit_button = ttk.Button(left_frame, text="Submit", command=lambda: threading.Thread(target=handle_submit).start(), cursor="hand2", width=40)    
        submit_button.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    
        report_freebet_title = ttk.Label(right_frame, text="Report a Free Bet", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        report_freebet_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        report_freebet_description = ttk.Label(right_frame, text="Enter the client username, free bet type, and amount to report a free bet.", wraplength=200, anchor='center', justify='center')
        report_freebet_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        progress_note.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        return frame
    
    def apply_closure_requests(self):
        restriction_mapping = {
            'Further Options': 'Self Exclusion'
        }
    
        def load_data():
            with open(os.path.join(NETWORK_PATH_PREFIX, 'Monitor', 'data.json'), 'r') as f:
                return json.load(f)
    
        def save_data(data):
            with open(os.path.join(NETWORK_PATH_PREFIX, 'Monitor', 'data.json'), 'w') as f:
                json.dump(data, f, indent=4)
    
        def handle_request(request):
            # Clear the left_frame
            for widget in self.left_frame.winfo_children():
                widget.destroy()
    
            log_notification(f"{get_user()} Handling {request['type']} request for {request['username']} ")
    
            request['type'] = restriction_mapping.get(request['type'], request['type'])
    
            current_date = datetime.now()
    
            length_mapping = {
                'One Day': timedelta(days=1),
                'One Week': timedelta(weeks=1),
                'Two Weeks': timedelta(weeks=2),
                'Four Weeks': timedelta(weeks=4),
                'Six Weeks': timedelta(weeks=6),
                'Six Months': relativedelta(months=6),
                'One Year': relativedelta(years=1),
                'Two Years': relativedelta(years=2),
                'Three Years': relativedelta(years=3),
                'Four Years': relativedelta(years=4),
                'Five Years': relativedelta(years=5),
            }
    
            length_in_time = length_mapping.get(request['period'], timedelta(days=0))
    
            reopen_date = current_date + length_in_time
    
            copy_string = f"{request['type']}"
    
            if request['period'] not in [None, 'None', 'Null']:
                copy_string += f" {request['period']}"
    
            copy_string += f" {current_date.strftime('%d/%m/%Y')}"
            copy_string = copy_string.upper()
    
            if request['type'] in ['Take-A-Break', 'Self Exclusion']:
                copy_string += f" (CAN REOPEN {reopen_date.strftime('%d/%m/%Y')})"
    
            copy_string += f" {get_user()}"
    
            pyperclip.copy(copy_string)
    
            def handle_submit():
                username = self.username_entry.get()  # Capture the username before destroying the widgets
    
                for widget in self.left_frame.winfo_children():
                    widget.destroy()
    
                if self.confirm_betty_update_bool.get():
                    try:
                        if self.send_confirmation_email_bool.get():
                            threading.Thread(target=self.send_email, args=(username, request['type'], request['period'])).start()
                            print(f"Email sent to {username} for {request['type']} request.")
                    except Exception as e:
                        print(f"Error sending email: {e}")
                        self.progress_note.config(text="Error sending email.", anchor='center', justify='center')
    
                    try:
                        threading.Thread(target=self.report_closure_requests, args=(request['type'], username, request['period'])).start()
                        print(f"Reported {request['type']} request for {username}.")
                    except Exception as e:
                        print(f"Error reporting closure requests: {e}")
                        self.progress_note.config(text="Error reporting closure requests.", anchor='center', justify='center')

                    request['completed'] = True
    
                    data = load_data()
                    for req in data.get('closures', []):
                        if req['username'] == request['username']:
                            req['completed'] = True
                            print(f"Marked {request['type']} request for {username} as completed.")
                            break
                    save_data(data)
    
                    if request['completed']:
                        refresh_closure_requests()
                        self.progress_note.config(text=f"{request['type']} request for {username} has been processed.", anchor='center', justify='center')
    
                else:
                    # messagebox.showerror("Error", "Please confirm that the client has been updated in Betty.")
                    self.progress_note.config(text="Please confirm that the client has been updated in Betty.", anchor='center', justify='center')
                    refresh_closure_requests()
    
            # Editable username entry
            ttk.Label(self.left_frame, text="Client Username").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            self.username_entry = ttk.Entry(self.left_frame, width=13)
            self.username_entry.insert(0, request['username'])
            self.username_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
            ttk.Label(self.left_frame, text=f"Restriction: {request['type']}").grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")
            ttk.Label(self.left_frame, text=f"Length: {request['period'] if request['period'] not in [None, 'Null'] else '-'}").grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    
            confirm_betty_update = ttk.Checkbutton(self.left_frame, text='Confirm Closed on Betty', variable=self.confirm_betty_update_bool, onvalue=True, offvalue=False, cursor="hand2")
            confirm_betty_update.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    
            send_confirmation_email = ttk.Checkbutton(self.left_frame, text='Send Pipedrive Confirmation Email', variable=self.send_confirmation_email_bool, onvalue=True, offvalue=False, cursor="hand2")
            send_confirmation_email.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    
            submit_button = ttk.Button(self.left_frame, text="Submit", command=handle_submit, cursor="hand2", width=33)
            submit_button.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        def refresh_closure_requests():
            for widget in self.left_frame.winfo_children():
                widget.destroy()
    
            data = load_data()
            requests = [request for request in data.get('closures', []) if not request.get('completed', False)]
            if not requests:
                ttk.Label(self.left_frame, text="No exclusion/deactivation requests.", anchor='center', justify='center', width=34).grid(row=0, column=1, padx=10, pady=2)
    
            for i, request in enumerate(requests):
                restriction = restriction_mapping.get(request['type'], request['type'])
    
                length = request['period'] if request['period'] not in [None, 'Null'] else ''
    
                tick_button = ttk.Button(self.left_frame, text="✔", command=lambda request=request: handle_request(request), width=2, cursor="hand2")
                tick_button.grid(row=i, column=0, padx=3, pady=2)
    
                request_label = ttk.Label(self.left_frame, text=f"{restriction} | {request['username']} | {length}")
                request_label.grid(row=i, column=1, padx=10, pady=2, sticky="w")
    
        frame = ttk.Frame(self.wizard_notebook)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_rowconfigure(0, weight=1)  # Ensure the frame takes up the entire height
    
        # Left section
        self.left_frame = ttk.Frame(frame)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.left_frame.grid_rowconfigure(3, weight=1)  # Ensure the left frame takes up the entire height
    
        # Right section
        right_frame = ttk.Frame(frame)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
    
        closure_requests_title = ttk.Label(right_frame, text="Closure Requests", font=("Helvetica", 12, "bold"), anchor='center', justify='center')
        closure_requests_title.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        closure_requests_description = ttk.Label(right_frame, text="Deactivation, Take-a-Break and Self Exclusion requests will appear here, ready for processing.", wraplength=200, anchor='center', justify='center')
        closure_requests_description.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        self.progress_note = ttk.Label(right_frame, text="---", wraplength=200, anchor='center', justify='center')
        self.progress_note.grid(row=4, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
    
        refresh_closure_requests()
    
        return frame

    def update_person(self, update_url, update_data, person_id):
        update_response = requests.put(update_url, json=update_data)
        if update_response.status_code == 200:
            print(f'Successfully updated person {person_id}')
            self.progress_note.config(text=f"Successfully updated in Pipedrive, email confirmation will be sent.", anchor='center', justify='center')
            time.sleep(2)
            self.progress_note.config(text="---", anchor='center', justify='center')
        else:
            print(f'Error updating person {person_id}: {update_response.status_code}')
            self.progress_note.config(text=f"Error updating in Pipedrive. Please send confirmation email manually.", anchor='center', justify='center')
            time.sleep(2)
            self.progress_note.config(text="---", anchor='center', justify='center')

    def send_email(self, username, restriction, length):
        params = {
            'term': username,
            'item_types': 'person',
            'fields': 'custom_fields',
            'exact_match': 'true',
            'api_token': self.pipedrive_api_token
        }
    
        try:
            response = requests.get(self.pipedrive_api_url, params=params)
            response.raise_for_status()
            print(response.status_code)
        except requests.exceptions.HTTPError as errh:
            print("Http Error:", errh)
            return
        except requests.exceptions.ConnectionError as errc:
            print("Error Connecting:", errc)
            return
        except requests.exceptions.Timeout as errt:
            print("Timeout Error:", errt)
            return
        except requests.exceptions.RequestException as err:
            print("Something went wrong", err)
            return
    
        persons = response.json()['data']['items']
        if not persons:
            self.progress_note.config(text=f"No persons found in Pipedrive for username: {username}. Please make sure the username is correct.", anchor='center', justify='center')
            time.sleep(2)
            self.progress_note.config(text="---", anchor='center', justify='center')
            return
    
        update_base_url = os.getenv('PIPEDRIVE_PERSONS_API_URL')
        if not update_base_url:
            raise ValueError("PIPEDRIVE_PERSONS_API_URL environment variable is not set")
    
        for person in persons:
            person_id = person['item']['id']
            update_url = f'{update_base_url}/{person_id}?api_token={self.pipedrive_api_token}'
    
            if restriction == 'Account Deactivation':
                update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': "Deactivated"}
                self.update_person(update_url, update_data, person_id)
    
            elif restriction == 'Self Exclusion':
                digit_length = length
                update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'SE {digit_length}'}
                self.update_person(update_url, update_data, person_id)
    
            elif restriction == 'Take-A-Break':
                digit_length = length
                update_data = {'6f5cec1b7cfd6b594a2ab443520a8c4837e9a0e5': f'TAB {digit_length}'}
                self.update_person(update_url, update_data, person_id)
        
    def report_closure_requests(self, restriction, username, length):
        current_date = datetime.now().strftime("%d/%m/%Y")  
        try:
            spreadsheet = self.gc.open("Management Tool")
        except gspread.SpreadsheetNotFound:
            return

        print(restriction, username, length)
        if restriction == 'Account Deactivation':
            worksheet = spreadsheet.get_worksheet(18)
            next_row = len(worksheet.col_values(1)) + 1
            worksheet.update_cell(next_row, 2, username.upper())
            worksheet.update_cell(next_row, 1, current_date)

        elif restriction == 'Take-A-Break':
            worksheet = spreadsheet.get_worksheet(19)
            next_row = len(worksheet.col_values(1)) + 1
            worksheet.update_cell(next_row, 2, username.upper())
            worksheet.update_cell(next_row, 1, current_date)
            worksheet.update_cell(next_row, 3, length.upper())

        elif restriction == 'Self Exclusion':
            worksheet = spreadsheet.get_worksheet(20)
            next_row = len(worksheet.col_values(1)) + 1
            worksheet.update_cell(next_row, 2, username.upper())
            worksheet.update_cell(next_row, 1, current_date)
            worksheet.update_cell(next_row, 3, length)      

        else:
            print("Error: Invalid restriction")
            messagebox.showerror("Error", "Unknown error. Please tell Sam.")
