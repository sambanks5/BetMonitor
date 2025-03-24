import os
import json
import threading
import time
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
                              QLabel, QComboBox, QLineEdit, QCheckBox, 
                              QPushButton, QFrame, QScrollArea, QGridLayout, QDateEdit)
from PySide6.QtCore import Qt, QTimer, Signal, QDate, QTime
from PySide6.QtGui import QColor, QTextCursor, QTextCharFormat, QFont

class BetFeedWidget(QWidget):
    def __init__(self, database_manager):
        super().__init__()
        self.database_manager = database_manager
        self.current_filters = {
            'username': None, 
            'unit_stake': None, 
            'risk_category': None, 
            'sport': None, 
            'selection': None, 
            'type': None
        }
        self.feed_lock = threading.Lock()
        self.last_update_time = None
        self.previous_selected_date = None 
        self.filters_visible = False
        
        self.initialize_ui()
        self.initialize_text_formats()
        self.start_feed_update()
    
    def initialize_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Feed frame setup
        feed_frame = QFrame()
        feed_frame.setFrameShape(QFrame.Panel)
        feed_frame.setFrameShadow(QFrame.Raised)
        feed_layout = QVBoxLayout(feed_frame)
        
        # Feed text area
        self.feed_text = QTextEdit()
        self.feed_text.setReadOnly(True)
        self.feed_text.setStyleSheet("font-family: Helvetica; font-size: 10pt; font-weight: bold;")
        feed_layout.addWidget(self.feed_text)
        
        # Filter frame
        self.filter_frame = QFrame()
        filter_layout = QGridLayout(self.filter_frame)
        
        # Username filter
        self.username_filter_entry = QLineEdit()
        self.username_filter_entry.setPlaceholderText("Client")
        filter_layout.addWidget(self.username_filter_entry, 0, 0)
        
        # Unit stake filter
        self.unit_stake_filter_entry = QLineEdit()
        self.unit_stake_filter_entry.setPlaceholderText("£")
        filter_layout.addWidget(self.unit_stake_filter_entry, 0, 1)
        
        # Risk category filter
        self.risk_category_filter_entry = QComboBox()
        self.risk_category_filter_entry.addItems(["", "Any", "M", "W", "C"])
        self.risk_category_filter_entry.setPlaceholderText("Risk")
        filter_layout.addWidget(self.risk_category_filter_entry, 0, 2)
        
        # Type filter
        self.type_combobox_entry = QComboBox()
        self.type_combobox_entry.addItems(["", "Bet", "Knockback", "SMS"])
        self.type_combobox_entry.setPlaceholderText("Type")
        filter_layout.addWidget(self.type_combobox_entry, 0, 3)
        
        # Selection filter
        self.selection_filter_entry = QLineEdit()
        self.selection_filter_entry.setPlaceholderText("Selection")
        filter_layout.addWidget(self.selection_filter_entry, 1, 0, 1, 3)
        
        # Sport filter
        self.sport_combobox_entry = QComboBox()
        self.sport_combobox_entry.addItems(["", "Horses", "Dogs", "Other"])
        self.sport_combobox_entry.setPlaceholderText("Sport")
        filter_layout.addWidget(self.sport_combobox_entry, 1, 3)
        
        # Filter buttons
        self.tick_button = QPushButton("✔")
        self.tick_button.clicked.connect(self.apply_filters)
        filter_layout.addWidget(self.tick_button, 0, 5)
        
        self.reset_button = QPushButton("✖")
        self.reset_button.clicked.connect(self.reset_filters)
        filter_layout.addWidget(self.reset_button, 1, 5)
        
        # Limit checkbox
        self.limit_bets_var = QCheckBox("[:150]")
        self.limit_bets_var.setChecked(True)
        filter_layout.addWidget(self.limit_bets_var, 0, 8, 2, 1, Qt.AlignRight)
        
        # Hide filter frame by default
        self.filter_frame.setVisible(False)
        feed_layout.addWidget(self.filter_frame)
        
        # Bottom control bar
        bottom_bar = QHBoxLayout()
        
        # Toggle filter button
        self.show_hide_button = QPushButton("≡")
        self.show_hide_button.clicked.connect(self.toggle_filters)
        bottom_bar.addWidget(self.show_hide_button, 0, Qt.AlignLeft)
        
        # Date selector
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.dateChanged.connect(self.bet_feed)
        bottom_bar.addWidget(self.date_edit, 1, Qt.AlignCenter)
        
        # Refresh button
        self.refresh_button = QPushButton("⟳")
        self.refresh_button.clicked.connect(self.bet_feed)
        bottom_bar.addWidget(self.refresh_button, 0, Qt.AlignRight)
        
        feed_layout.addLayout(bottom_bar)
        main_layout.addWidget(feed_frame)
        
        # Activity frame
        activity_frame = QFrame()
        activity_frame.setFrameShape(QFrame.Panel)
        activity_frame.setFrameShadow(QFrame.Raised)
        activity_layout = QVBoxLayout(activity_frame)
        
        self.activity_text = QTextEdit()
        self.activity_text.setReadOnly(True)
        self.activity_text.setStyleSheet("font-family: Helvetica; font-size: 10pt; font-weight: bold;")
        activity_layout.addWidget(self.activity_text)
        
        main_layout.addWidget(activity_frame)
    
    def initialize_text_formats(self):
        # Create color formats for different types of text
        self.formats = {}
        
        # Define colors similar to your Tkinter tags
        self.formats["risk"] = self.create_format(QColor("#ad0202"))
        self.formats["watchlist"] = self.create_format(QColor("#e35f00"))
        self.formats["newreg"] = self.create_format(QColor("purple"))
        self.formats["vip"] = self.create_format(QColor("#009685"))
        self.formats["sms"] = self.create_format(QColor("#6CCFF6"))
        self.formats["knockback"] = self.create_format(QColor("#FF006E"))
        self.formats["oddsmonkey"] = self.create_format(QColor("#ff00e6"))
        
        # Bold formats
        bold_format = QTextCharFormat()
        bold_format.setFontWeight(QFont.Bold)
        bold_format.setForeground(QColor("#d0cccc"))
        self.formats["bold"] = bold_format
        
        # Customer reference formats
        self.formats["customer_ref_vip"] = self.create_format(QColor("#009685"), True)
        self.formats["customer_ref_newreg"] = self.create_format(QColor("purple"), True)
        self.formats["customer_ref_risk"] = self.create_format(QColor("#ad0202"), True)
        self.formats["customer_ref_watchlist"] = self.create_format(QColor("#e35f00"), True)
        self.formats["customer_ref_default"] = self.create_format(QColor("#000000"), True)
        
        # Basic colors
        self.formats["black"] = self.create_format(QColor("#000000"))
        self.formats["red"] = self.create_format(QColor("#ad0202"))
        self.formats["green"] = self.create_format(QColor("#009685"))
    
    def create_format(self, color, bold=False):
        text_format = QTextCharFormat()
        text_format.setForeground(color)
        if bold:
            text_format.setFontWeight(QFont.Bold)
        return text_format
    
    def toggle_filters(self):
        self.filters_visible = not self.filters_visible
        self.filter_frame.setVisible(self.filters_visible)
    
    def start_feed_update(self):
        # Check if we should update the feed (if at top and viewing today's date)
        scroll_value = self.feed_text.verticalScrollBar().value()
        if scroll_value <= 5:  # If scrolled near top
            current_date = self.date_edit.date().toString("dd/MM/yyyy")
            today = QDate.currentDate().toString("dd/MM/yyyy")
            if current_date == today:
                self.bet_feed()
        
        # Schedule the next update
        QTimer.singleShot(16000, self.start_feed_update)
    
    def bet_feed(self):
        # Start a thread to fetch and display bets
        threading.Thread(target=self.fetch_and_display_bets, daemon=True).start()
    
    def fetch_and_display_bets(self):
        if not self.feed_lock.acquire(blocking=False):
            print("Feed update already in progress. Skipping this update.")
            return
        
        try:
            print("Refreshing feed...")
            vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
            
            # Try to get database connection with retries
            retry_attempts = 2
            conn = cursor = None
            for attempt in range(retry_attempts):
                conn, cursor = self.database_manager.get_connection()
                if conn is not None:
                    break
                elif attempt < retry_attempts - 1:
                    print("Error finding bets. Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    self.feed_text.clear()
                    self.feed_text.append("Error finding bets. Please try refreshing.")
                    return
            
            # Get the selected date
            selected_date = self.date_edit.date().toString("dd/MM/yyyy")
            if self.previous_selected_date != selected_date:
                self.last_update_time = None
                self.previous_selected_date = selected_date
            
            # Update activity frame (stats panel)
            self.update_activity_frame(reporting_data, cursor, selected_date)
            
            # Check if any filters are active
            filters_active = any([
                self.current_filters['username'],
                self.current_filters['unit_stake'],
                self.current_filters['risk_category'],
                self.current_filters['sport'],
                self.current_filters['selection'],
                self.current_filters['type']
            ])
            
            # If no filters and we have a last update time, check if any new data
            if not filters_active and self.last_update_time and selected_date == QDate.currentDate().toString("dd/MM/yyyy"):
                cursor.execute("SELECT MAX(time) FROM database WHERE date = ?", (selected_date,))
                latest_time = cursor.fetchone()[0]
                if latest_time <= self.last_update_time:
                    return
            
            # Build query based on filters
            query = "SELECT * FROM database WHERE date = ?"
            params = [selected_date]
            
            # Add filter conditions
            if self.current_filters['username']:
                query += " AND customer_ref = ?"
                params.append(self.current_filters['username'].upper())
            
            if self.current_filters['unit_stake']:
                query += " AND unit_stake = ?"
                params.append(self.current_filters['unit_stake'])
            
            if self.current_filters['risk_category']:
                if self.current_filters['risk_category'] == 'Any':
                    query += " AND risk_category != '-'"
                else:
                    query += " AND risk_category = ?"
                    params.append(self.current_filters['risk_category'])
            
            if self.current_filters['sport']:
                sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
                sport_value = sport_mapping.get(self.current_filters['sport'])
                if sport_value is not None:
                    query += " AND EXISTS (SELECT 1 FROM json_each(database.sports) WHERE json_each.value = ?)"
                    params.append(sport_value)
            
            if self.current_filters['selection']:
                query += " AND selections LIKE ?"
                params.append(f"%{self.current_filters['selection']}%")
            
            if self.current_filters['type']:
                type_mapping = {'Bet': 'BET', 'Knockback': 'WAGER KNOCKBACK', 'SMS': 'SMS WAGER'}
                type_value = type_mapping.get(self.current_filters['type'])
                if type_value:
                    query += " AND type = ?"
                    params.append(type_value)
            
            query += " ORDER BY time DESC"
            
            # Execute the query
            cursor.execute(query, params)
            filtered_bets = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
            
            # Clear the feed
            self.feed_text.clear()
            
            if not filtered_bets:
                self.feed_text.append("No bets found with the current filters or date.")
                return
            
            # Apply limit if checkbox is checked
            if self.limit_bets_var.isChecked():
                filtered_bets = filtered_bets[:150]
            
            # Format and display each bet
            separator = '-' * 80 + '\n'
            for bet in filtered_bets:
                bet_dict = dict(zip(column_names, bet))
                
                if bet_dict['type'] != 'SMS WAGER' and bet_dict['selections'] is not None:
                    bet_dict['selections'] = json.loads(bet_dict['selections'])
                
                self.insert_formatted_bet(bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data, separator)
            
            # Store the last update time
            if filtered_bets:
                self.last_update_time = max(bet[2] for bet in filtered_bets)
                
        finally:
            if conn:
                conn.close()
            self.feed_lock.release()

    def apply_filters(self):
        # Get values from filter widgets
        self.current_filters['username'] = self.username_filter_entry.text()
        self.current_filters['unit_stake'] = self.unit_stake_filter_entry.text()
        self.current_filters['risk_category'] = self.risk_category_filter_entry.currentText()
        self.current_filters['sport'] = self.sport_combobox_entry.currentText()
        self.current_filters['selection'] = self.selection_filter_entry.text()
        self.current_filters['type'] = self.type_combobox_entry.currentText()
        
        # Clean up empty filters
        for key in self.current_filters:
            if self.current_filters[key] == "":
                self.current_filters[key] = None
        
        # Apply styling to the filter button if filters are active
        filters_applied = any(value not in [None, '', 'none'] for value in self.current_filters.values())
        if filters_applied:
            self.tick_button.setStyleSheet("background-color: #4CAF50; color: white;")
        else:
            self.tick_button.setStyleSheet("")
        
        # Update the feed
        self.bet_feed()
    
    def reset_filters(self):
        # Clear all filter widgets
        self.username_filter_entry.clear()
        self.unit_stake_filter_entry.clear()
        self.risk_category_filter_entry.setCurrentIndex(0)
        self.sport_combobox_entry.setCurrentIndex(0)
        self.selection_filter_entry.clear()
        self.type_combobox_entry.setCurrentIndex(0)
        
        # Reset filter values
        self.current_filters = {
            'username': None, 
            'unit_stake': None, 
            'risk_category': None, 
            'sport': None, 
            'selection': None, 
            'type': None
        }
        
        # Reset button style
        self.tick_button.setStyleSheet("")
        
        # Update the feed
        self.bet_feed()

def insert_formatted_bet(self, bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data, separator):
    cursor = self.feed_text.textCursor()
    cursor.movePosition(QTextCursor.End)
    
    # Format the bet based on its type
    if bet_dict['type'] == 'SMS WAGER':
        self.format_sms_wager(cursor, bet_dict, vip_clients, newreg_clients)
    elif bet_dict['type'] == 'WAGER KNOCKBACK':
        self.format_knockback(cursor, bet_dict, vip_clients, newreg_clients)
    else:
        self.format_regular_bet(cursor, bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data)
    
    # Add separator
    cursor.insertText(separator, self.formats["bold"])

def format_sms_wager(self, cursor, bet_dict, vip_clients, newreg_clients):
    wager_number = bet_dict.get('id', '')
    customer_reference = bet_dict.get('customer_ref', '')
    sms_wager_text = bet_dict.get('text_request', '')
    
    # Clean up the SMS text
    if sms_wager_text.startswith('"') and sms_wager_text.endswith('"'):
        sms_wager_text = sms_wager_text[1:-1]
    sms_wager_text = sms_wager_text.replace('\\n', '\n')
    
    # Insert customer reference with appropriate format
    tag = f"customer_ref_{self.get_customer_tag(customer_reference, vip_clients, newreg_clients)}"
    cursor.insertText(f"{customer_reference} {wager_number}", self.formats[tag])
    
    # Insert SMS WAGER label
    cursor.insertText(" - SMS WAGER:", self.formats["sms"])
    
    # Insert the SMS text
    cursor.insertText(f"\n{sms_wager_text}\n", self.formats["black"])

def format_knockback(self, cursor, bet_dict, vip_clients, newreg_clients):
    customer_ref = bet_dict.get('customer_ref', '')
    knockback_id = bet_dict.get('id', '')
    knockback_id = knockback_id.rsplit('-', 1)[0]
    knockback_details = bet_dict.get('selections', {})
    timestamp = bet_dict.get('time', '')
    
    # Format knockback details
    formatted_knockback_details = ""
    formatted_selections = ""
    
    if isinstance(knockback_details, dict):
        formatted_knockback_details = '\n   '.join([f'{key}: {value}' for key, value in knockback_details.items() 
                                                   if key not in ['Selections', 'Knockback ID', 'Time', 'Customer Ref', 'Error Message']])
        formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' 
                                            for selection in knockback_details.get('Selections', [])])
    elif isinstance(knockback_details, list):
        formatted_selections = '\n   '.join([f' - {selection["- Meeting Name"]}, {selection["- Selection Name"]}, {selection["- Bet Price"]}' 
                                           for selection in knockback_details])
    
    formatted_knockback_details += '\n   ' + formatted_selections
    error_message = bet_dict.get('error_message', '')
    if 'Maximum stake available' in error_message:
        error_message = error_message.replace(', Maximum stake available', '\n   Maximum stake available')
    formatted_knockback_details = f"Error Message: {error_message}   {formatted_knockback_details}"
    
    # Insert customer reference with appropriate format
    tag = f"customer_ref_{self.get_customer_tag(customer_ref, vip_clients, newreg_clients)}"
    cursor.insertText(f"{customer_ref} {timestamp} - {knockback_id}", self.formats[tag])
    
    # Insert WAGER KNOCKBACK label
    cursor.insertText(" - WAGER KNOCKBACK:\n", self.formats["knockback"])
    
    # Insert the knockback details
    cursor.insertText(f"{formatted_knockback_details}\n", self.formats["black"])

def format_regular_bet(self, cursor, bet_dict, todays_oddsmonkey_selections, vip_clients, newreg_clients, reporting_data):
    enhanced_places = reporting_data.get('enhanced_places', [])
    
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
    
    # Format the selection text
    selection = "\n".join([f"   - {sel[0]} at {sel[1]}" for sel in parsed_selections])
    formatted_unit_stake = f"£{unit_stake:.2f}"
    text = f"{formatted_unit_stake} {bet_details}, {bet_type}:\n{selection}\n"
    
    # Insert customer reference with appropriate format
    tag = f"customer_ref_{self.get_customer_tag(customer_reference, vip_clients, newreg_clients, customer_risk_category)}"
    cursor.insertText(f"{customer_reference} ({customer_risk_category}) {timestamp} - {bet_no}", self.formats[tag])
    
    # Insert the bet details
    cursor.insertText(f" - {text}", self.formats["black"])
    
    # Check for oddsmonkey selections
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
                                    cursor.insertText(oddsmonkey_text, self.formats["oddsmonkey"])
        
        # Check for enhanced places
        parts = sel[0].split(' - ')
        if len(parts) > 1:
            meeting_info = parts[0].split(', ')
            if len(meeting_info) > 1 and ':' in meeting_info[1]:
                meeting_time = meeting_info[1]
                if f"{meeting_info[0]}, {meeting_time}" in enhanced_places:
                    enhanced_text = f"{sel[0]}  |  Enhanced Race\n"
                    cursor.insertText(enhanced_text, self.formats["oddsmonkey"])

def get_customer_tag(self, customer_reference, vip_clients, newreg_clients, customer_risk_category=None):
    if customer_reference in vip_clients:
        return "vip"
    elif customer_reference in newreg_clients:
        return "newreg"
    elif customer_risk_category == 'W':
        return "watchlist"
    elif customer_risk_category in ('M', 'C'):
        return "risk"
    else:
        return "default"

    def update_activity_frame(self, reporting_data, cursor, selected_date_str):
        try:
            current_date = QDate.fromString(selected_date_str, "dd/MM/yyyy")
            previous_date = current_date.addDays(-7)
            current_time = QTime.currentTime().toString("HH:mm:ss")
            
            current_date_str = current_date.toString("dd/MM/yyyy")
            previous_date_str = previous_date.toString("dd/MM/yyyy")
            today_date_str = QDate.currentDate().toString("dd/MM/yyyy")
            is_today = selected_date_str == today_date_str
            
            # Query database for statistics - similar to your Tkinter version but adapted for Qt
            # This would be a long method with the same SQL queries as your original code
            
            # For brevity, I'm simplifying this method - you'll need to adapt your original
            # database queries to populate these variables
            
            # Populate the activity text
            self.activity_text.clear()
            
            # Format HTML for rich text
            html = f"""
            <div style='text-align:center'>
                <p><b>{current_date.toString("dddd")} {selected_date_str}
                {'  |  ' + user.USER_NAMES.get(user.get_user(), user.get_user()) if user.get_user() else ''}</b></p>
                
                <p>Bets: {current_bets:,} 
                <span style='color:{"green" if percentage_change_bets > 0 else "red"}'>
                    {bet_change_indicator}{percentage_change_bets:.2f}%
                </span>
                ({previous_date.toString("dd/MM")}: {previous_bets:,})</p>
                
                <p>Knbk: {current_knockbacks:,}
                <span style='color:{"red" if percentage_change_knockbacks > 0 else "green"}'>
                    {knockback_change_indicator}{percentage_change_knockbacks:.2f}%
                </span>
                ({previous_date.toString("dd/MM")}: {previous_knockbacks:,})</p>
                
                <p>Knbk %: {knockback_percentage:.2f}%
                ({previous_date.toString("dd/MM")}: {previous_knockback_percentage:.2f}%)</p>
                
                {f"<p>Turnover: {daily_turnover} | Profit: {daily_profit}</p>" if is_today else ""}
                
                <p>Clients: {current_total_unique_clients:,} | 
                   M: {current_unique_m_clients:,} | 
                   W: {current_unique_w_clients:,} | 
                   --: {current_unique_norisk_clients:,}</p>
                   
                <p>Horses: {horse_bets:,} | Dogs: {dog_bets:,} | Other: {other_bets:,}</p>
            </div>
            """
            
            self.activity_text.setHtml(html)
            
        except Exception as e:
            print(f"Error updating activity frame: {e}")
            self.activity_text.setPlainText("An error occurred while updating. Please try refreshing.")