from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListView,
                              QLabel, QComboBox, QLineEdit, QCheckBox, 
                              QPushButton, QFrame, QScrollArea, QGridLayout, QDateEdit,
                              QDialog, QDialogButtonBox, QTextBrowser)
from PySide6.QtCore import Qt, QTimer, Signal, QDate, QTime
from ui.models.betmodel import BetListModel
from ui.delegates.betdelegate import BetDelegate
from utils import access_data
import time
import threading

class BetFeedWidget(QWidget):
    update_feed_signal = Signal(list, list, list, dict, str)
    clear_feed_signal = Signal()
    show_error_signal = Signal(str)

    def __init__(self, database_manager):
        super().__init__()
        self.database_manager = database_manager
        # Initialize other properties as before
        self.filters_visible = False  # Track the visibility of the filter frame, set to False to hide by default

        self.update_feed_signal.connect(self.update_feed_ui)
        self.clear_feed_signal.connect(self.clear_feed_ui)
        self.show_error_signal.connect(self.show_error_ui)

        self.feed_lock = threading.Lock()
        self.last_update_time = None
        self.previous_selected_date = None
        
        self.current_filters = {
            'username': None, 
            'unit_stake': None, 
            'risk_category': None, 
            'sport': None, 
            'selection': None, 
            'type': None
        }


        self.initialize_ui()
        self.start_feed_update()
    
    def bet_feed(self):
        """Fetch bet data and update the model"""
        print("Refreshing feed...")
        # Start a thread to fetch and display bets
        threading.Thread(target=self.fetch_and_display_bets, daemon=True).start()

    def fetch_and_display_bets(self):
        """Fetch bet data from database and signal UI update"""
        if not hasattr(self, 'feed_lock') or not self.feed_lock.acquire(blocking=False):
            print("Feed update already in progress. Skipping this update.")
            return
            
        try:
            print("Fetching bet data...")
            vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
            
            # Try to get database connection with retries
            retry_attempts = 2
            conn = cursor = None
            for attempt in range(retry_attempts):
                try:
                    conn, cursor = self.database_manager.get_connection()
                    if conn is not None:
                        break
                    elif attempt < retry_attempts - 1:
                        print("Error finding bets. Retrying in 2 seconds...")
                        time.sleep(2)
                    else:
                        self.show_error_signal.emit("Error finding bets. Please try refreshing.")
                        return
                except Exception as e:
                    print(f"Connection error: {e}")
                    if attempt < retry_attempts - 1:
                        time.sleep(2)
                    else:
                        self.show_error_signal.emit(f"Database connection error: {e}")
                        return
            
            # Get the selected date
            selected_date = self.date_edit.date().toString("dd/MM/yyyy")
            if hasattr(self, 'previous_selected_date') and self.previous_selected_date != selected_date:
                self.last_update_time = None
                self.previous_selected_date = selected_date
                
            # Initialize parameters and build query
            params = [selected_date]
            query = "SELECT * FROM database WHERE date = ?"
            
            # Apply filters if any
            filters_active = False
            if hasattr(self, 'current_filters'):
                for key, value in self.current_filters.items():
                    if value not in [None, '', 'none', 'Any']:
                        filters_active = True
                        if key == 'username':
                            query += " AND customer_ref LIKE ?"
                            params.append(f"%{value}%")
                        elif key == 'unit_stake':
                            query += " AND unit_stake >= ?"
                            params.append(float(value) if value.replace('.', '', 1).isdigit() else 0)
                        elif key == 'risk_category':
                            query += " AND risk_category = ?"
                            params.append(value)
                        elif key == 'sport':
                            query += " AND sport = ?"
                            params.append(value)
                        elif key == 'selection':
                            query += " AND selections LIKE ?"
                            params.append(f"%{value}%")
                        elif key == 'type':
                            if value == 'Bet':
                                query += " AND type = ?"
                                params.append('BET')
                            elif value == 'Knockback':
                                query += " AND type = ?"
                                params.append('WAGER KNOCKBACK')
                            elif value == 'SMS':
                                query += " AND type = ?"
                                params.append('SMS WAGER')
            
            # If no filters and we have a last update time, check if any new data
            if not filters_active and hasattr(self, 'last_update_time') and self.last_update_time and selected_date == QDate.currentDate().toString("dd/MM/yyyy"):
                cursor.execute("SELECT MAX(time) FROM database WHERE date = ?", (selected_date,))
                result = cursor.fetchone()
                if result is None or result[0] is None:
                    # No records exist for this date
                    self.clear_feed_signal.emit()
                    self.show_error_signal.emit("No bets found for this date.")
                    return
                else:
                    latest_time = result[0]
                    if latest_time <= self.last_update_time:
                        return
            
            # Order by time
            query += " ORDER BY time DESC"
            
            # Execute the query
            try:
                cursor.execute(query, params)
                filtered_bets = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]
            except Exception as e:
                self.show_error_signal.emit(f"Error executing query: {e}")
                return
                
            # Clear existing feed before adding new content
            self.clear_feed_signal.emit()
            
            if not filtered_bets:
                self.show_error_signal.emit("No bets found with the current filters or date.")
                return
                
            # Apply limit if checkbox is checked
            if hasattr(self, 'limit_bets_var') and self.limit_bets_var.isChecked():
                filtered_bets = filtered_bets[:150]
                
            # Update the model via signal
            self.update_feed_signal.emit(filtered_bets, column_names, 
                                        [todays_oddsmonkey_selections, vip_clients, newreg_clients], 
                                        reporting_data, selected_date)
            
            # Store the last update time
            if filtered_bets:
                self.last_update_time = max(bet[column_names.index('time')] for bet in filtered_bets)
                    
        except Exception as e:
            print(f"Error refreshing feed: {e}")
            self.show_error_signal.emit(f"Error refreshing feed: {e}")
        finally:
            if conn:
                conn.close()
                
            if hasattr(self, 'feed_lock'):
                self.feed_lock.release()

    def initialize_ui(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Feed frame setup
        feed_frame = QFrame()
        feed_frame.setFrameShape(QFrame.Panel)
        feed_frame.setFrameShadow(QFrame.Raised)
        feed_layout = QVBoxLayout(feed_frame)
        
        # Replace QTextEdit with QListView
        self.bet_model = BetListModel()
        self.feed_view = QListView()
        self.feed_view.setModel(self.bet_model)
        
        # Create and set the delegate
        self.bet_delegate = BetDelegate()
        self.bet_delegate.customerClicked.connect(self.show_customer_details)
        self.bet_delegate.selectionClicked.connect(self.show_selection_details)
        self.feed_view.setItemDelegate(self.bet_delegate)
        
        # Configure the view
        self.feed_view.setVerticalScrollMode(QListView.ScrollPerPixel)
        self.feed_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.feed_view.setSelectionMode(QListView.SingleSelection)
        self.feed_view.setUniformItemSizes(False)
        
        feed_layout.addWidget(self.feed_view)
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
        
    def update_feed_ui(self, filtered_bets, column_names, data_lists, reporting_data, selected_date):
        """Update the model with new data instead of formatting text"""
        # Update the model with new data
        self.bet_model.setBets(filtered_bets, column_names)
        
        # Store reference data that the delegate might need
        oddsmonkey_selections, vip_clients, newreg_clients = data_lists
        
        # Make sure your delegate has access to this data
        self.bet_delegate.set_reference_data(
            oddsmonkey_selections, 
            vip_clients, 
            newreg_clients, 
            reporting_data
        )

    def clear_feed_ui(self):
        # Clear the model
        self.bet_model.setBets([], [])
        
    def show_error_ui(self, message):
        # Clear the model and show error
        self.bet_model.setBets([], [])
        
        # Create a simple "error item" to display
        error_item = [{"type": "ERROR", "message": message}]
        self.bet_model.setBets(error_item, ["type", "message"])
        
    def toggle_filters(self):
        self.filters_visible = not self.filters_visible
        self.filter_frame.setVisible(self.filters_visible)

    # Add methods to handle clickable elements
    def show_customer_details(self, customer_ref):
        # Create and show a dialog with customer details
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Customer: {customer_ref}")
        dialog.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Create content - fetch customer details from database
        content = QTextBrowser()
        content.setOpenExternalLinks(True)
        
        # Fetch customer data - pseudocode, replace with actual queries
        conn, cursor = self.database_manager.get_connection()
        try:
            # Get customer info
            cursor.execute("SELECT * FROM customers WHERE customer_ref = ?", (customer_ref,))
            customer_data = cursor.fetchone()
            
            # Get recent bets
            cursor.execute(
                "SELECT * FROM database WHERE customer_ref = ? ORDER BY date DESC, time DESC LIMIT 20", 
                (customer_ref,)
            )
            recent_bets = cursor.fetchall()
            
            # Format HTML content
            html = f"<h2>Customer: {customer_ref}</h2>"
            
            if customer_data:
                html += "<h3>Customer Details</h3>"
                html += "<table>"
                for key, value in customer_data.items():
                    html += f"<tr><td><b>{key}</b></td><td>{value}</td></tr>"
                html += "</table>"
            
            html += f"<h3>Recent Activity ({len(recent_bets)} bets)</h3>"
            html += "<table border='1' cellpadding='4'>"
            html += "<tr><th>Date</th><th>Time</th><th>Type</th><th>Amount</th><th>Details</th></tr>"
            
            for bet in recent_bets:
                html += f"<tr>"
                html += f"<td>{bet['date']}</td>"
                html += f"<td>{bet['time']}</td>"
                html += f"<td>{bet['type']}</td>"
                html += f"<td>£{bet.get('unit_stake', 0)}</td>"
                html += f"<td>{bet.get('bet_details', '')}</td>"
                html += "</tr>"
            
            html += "</table>"
            
            content.setHtml(html)
            
        finally:
            conn.close()
        
        layout.addWidget(content)
        
        # Add close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        dialog.exec()
        
    def start_feed_update(self):
        # Update to use feed_view instead of feed_text
        scroll_value = self.feed_view.verticalScrollBar().value()
        if scroll_value <= 5:  # If scrolled near top
            current_date = self.date_edit.date().toString("dd/MM/yyyy")
            today = QDate.currentDate().toString("dd/MM/yyyy")
            if current_date == today:
                self.bet_feed()
        
        # Schedule the next update
        QTimer.singleShot(16000, self.start_feed_update)

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

    def show_selection_details(self, selection):
        # Similar to customer details, but for selections
        # You can show odds history, related bets, etc.
        pass