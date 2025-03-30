from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                            QGridLayout, QSpinBox, QComboBox, QPushButton, 
                            QTextEdit, QDateEdit, QCheckBox)
from PySide6.QtCore import Qt, Signal, QDate, QThread, QTimer
from PySide6.QtGui import QColor, QFont
import json
import threading
from datetime import datetime
from collections import defaultdict
from utils import access_data

class BetRunsThread(QThread):
    resultReady = Signal(object, str)  # Signal to emit results or error message
    
    def __init__(self, database_manager, date_str, num_bets, num_run_bets):
        super().__init__()
        self.database_manager = database_manager
        self.date_str = date_str
        self.num_bets = num_bets
        self.num_run_bets = num_run_bets
        
    def run(self):
        try:
            conn, cursor = self.database_manager.get_connection()
            if not conn or not cursor:
                self.resultReady.emit(None, "Failed to connect to database")
                return
                
            try:
                # Get bets from database
                cursor.execute("SELECT id, selections FROM database WHERE date = ? ORDER BY time DESC LIMIT ?", 
                              (self.date_str, self.num_bets))
                database_data = cursor.fetchall()
                
                if not database_data:
                    self.resultReady.emit(None, "No bets found for the selected date")
                    return
                    
                # Process bets to find runs
                selection_to_bets = defaultdict(list)
                
                for bet in database_data:
                    bet_id = bet[0]
                    if ':' in bet_id:  # Skip SMS bets
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
                
                # Sort selections by number of bets (descending)
                sorted_selections = sorted(selection_to_bets.items(), 
                                          key=lambda item: len(item[1]), 
                                          reverse=True)
                
                # Process bet details in this same thread
                vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
                enhanced_places = reporting_data.get('enhanced_places', [])
                
                # Format full bet run details here
                runs_data = []
                
                for selection, bet_numbers in sorted_selections:
                    if len(bet_numbers) >= self.num_run_bets:
                        selection_name = selection.split(' - ')[1] if ' - ' in selection else selection
                        
                        # Check if in oddsmonkey selections
                        matched_odds = None
                        for om_event, om_selections in todays_oddsmonkey_selections.items():
                            for om_sel in om_selections:
                                if selection_name == om_sel[0]:
                                    matched_odds = float(om_sel[1])
                                    break
                            if matched_odds is not None:
                                break
                        
                        # Gather bet details for this selection
                        bet_details = []
                        for bet_number in bet_numbers:
                            cursor.execute("SELECT time, customer_ref, risk_category, selections FROM database WHERE id = ?", (bet_number,))
                            bet_info = cursor.fetchone()
                            if bet_info:
                                bet_time = bet_info[0]
                                customer_ref = bet_info[1]
                                risk_category = bet_info[2] or '-'
                                selections_data = bet_info[3]
                                
                                if selections_data:
                                    try:
                                        parsed_selections = json.loads(selections_data)
                                    except json.JSONDecodeError:
                                        continue
                                        
                                    for sel in parsed_selections:
                                        if selection == sel[0]:
                                            # Determine style based on risk category
                                            style = "normal"
                                            if risk_category in ('M', 'C'):
                                                style = "risk"
                                            elif risk_category == 'W':
                                                style = "watchlist"
                                            elif customer_ref in vip_clients:
                                                style = "vip"
                                            elif customer_ref in newreg_clients:
                                                style = "newreg"
                                                
                                            bet_details.append({
                                                "time": bet_time,
                                                "bet_id": bet_number,
                                                "customer_ref": customer_ref,
                                                "risk_category": risk_category,
                                                "odds": sel[1],
                                                "style": style
                                            })
                        
                        # Check for enhanced places
                        meeting_time = ' '.join(selection.split(' ')[:2])
                        is_enhanced = meeting_time in enhanced_places
                        
                        # Add to runs data
                        runs_data.append({
                            "selection": selection,
                            "matched_odds": matched_odds,
                            "bet_details": bet_details,
                            "is_enhanced": is_enhanced
                        })
                
                self.resultReady.emit(runs_data, "")
                
            finally:
                if conn:
                    conn.close()
                    
        except Exception as e:
            self.resultReady.emit(None, f"Error: {str(e)}")

class BetRunsWidget(QWidget):
    def __init__(self, database_manager):
        super().__init__()
        self.database_manager = database_manager
        self.num_run_bets = 2
        self.num_recent_bets = 50
        self.filters_visible = False
        self.mutex = threading.Lock()  # For thread safety
        self.workerThread = None
        
        self.initUI()
        self.startPeriodicUpdate()
        
    def initUI(self):
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Feed frame setup - match BetFeedWidget style
        runs_frame = QFrame()
        runs_frame.setFrameShape(QFrame.Panel)
        runs_layout = QVBoxLayout(runs_frame)
        
        # Results text area
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setStyleSheet("""
            QTextEdit {
                background-color: #242424;
                color: #e0e0e0;
                border: none;
                padding: 10px;
                font-family: 'Segoe UI', Arial;
                font-size: 10pt;
            }
            QScrollBar:vertical {
                background-color: #292929;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        runs_layout.addWidget(self.results_text)
        
        # Filter frame - hidden by default
        self.filter_frame = QFrame()
        filter_layout = QGridLayout(self.filter_frame)
        filter_layout.setContentsMargins(5, 5, 5, 5)
        filter_layout.setSpacing(8)
        
        # Min runs setting
        min_runs_label = QLabel("Min Runs:")
        min_runs_label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        filter_layout.addWidget(min_runs_label, 0, 0)
        
        self.min_runs_spinbox = QSpinBox()
        self.min_runs_spinbox.setRange(2, 10)
        self.min_runs_spinbox.setValue(2)
        filter_layout.addWidget(self.min_runs_spinbox, 0, 1)
        
        # Number of bets to check
        bets_label = QLabel("Recent Bets:")
        bets_label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        filter_layout.addWidget(bets_label, 0, 2)
        
        self.bets_combobox = QComboBox()
        self.bets_combobox.addItems(["20", "50", "100", "300", "1000", "2000"])
        self.bets_combobox.setCurrentIndex(1)  # Default to 50
        filter_layout.addWidget(self.bets_combobox, 0, 3)
        
        # Apply filters button - match BetFeedWidget style
        self.tick_button = QPushButton("✔")
        self.tick_button.clicked.connect(self.applyFilters)
        filter_layout.addWidget(self.tick_button, 0, 4)
        
        # Reset filters button - match BetFeedWidget style
        self.reset_button = QPushButton("✖")
        self.reset_button.clicked.connect(self.resetFilters)
        filter_layout.addWidget(self.reset_button, 0, 5)
        
        filter_layout.setColumnStretch(6, 1)  # Add stretch to push elements to the left
        
        # Hide filter frame by default
        self.filter_frame.setVisible(False)
        runs_layout.addWidget(self.filter_frame)
        
        # Bottom control bar - match BetFeedWidget style
        bottom_bar = QHBoxLayout()
        
        # Toggle filter button
        self.show_hide_button = QPushButton("≡")
        self.show_hide_button.clicked.connect(self.toggleFilters)
        bottom_bar.addWidget(self.show_hide_button, 0, Qt.AlignLeft)
        
        # Date display label (replacing editable date picker)
        self.date_label = QLabel(QDate.currentDate().toString("dd/MM/yyyy"))
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("background-color: rgba(255, 255, 255, 10); padding: 4px 8px; border-radius: 4px;")
        bottom_bar.addWidget(self.date_label, 1, Qt.AlignCenter)
        
        # Keep date_edit but hide it
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setVisible(False)
        
        # Refresh button - match BetFeedWidget style
        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setFixedWidth(30)
        self.refresh_button.clicked.connect(self.manualRefresh)
        bottom_bar.addWidget(self.refresh_button, 0, Qt.AlignRight)
        
        runs_layout.addLayout(bottom_bar)
        main_layout.addWidget(runs_frame)
        
        # Initialize the text styles
        self.setupTextStyles()
        
        # Initial update
        self.manualRefresh()
        
    def setupTextStyles(self):
        # Store HTML color codes for different categories
        self.text_styles = {
            "normal": "#e0e0e0",
            "risk": "#ad0202",
            "watchlist": "#e35f00",
            "vip": "#009685",
            "newreg": "#800080",
            "oddsmonkey": "#ff00e6"
        }
        
    def toggleFilters(self):
        self.filters_visible = not self.filters_visible
        self.filter_frame.setVisible(self.filters_visible)
        
    def applyFilters(self):
        self.num_run_bets = self.min_runs_spinbox.value()
        self.num_recent_bets = int(self.bets_combobox.currentText())
        self.manualRefresh()
        
        # Apply styling to indicate filters are active
        self.apply_button.setStyleSheet("background-color: #4CAF50; color: white;")
        
    def resetFilters(self):
        self.min_runs_spinbox.setValue(2)
        self.bets_combobox.setCurrentIndex(1)  # Set back to 50
        self.num_run_bets = 2
        self.num_recent_bets = 50
        self.manualRefresh()
        
        # Reset button style
        self.apply_button.setStyleSheet("")
        
    def manualRefresh(self):
        # Cancel any running thread
        if self.workerThread and self.workerThread.isRunning():
            self.workerThread.terminate()
            self.workerThread.wait()
            
        # Get settings
        date_str = self.date_edit.date().toString("dd/MM/yyyy")
        num_bets = self.num_recent_bets
        num_run_bets = self.num_run_bets
        
        # Start new thread
        self.workerThread = BetRunsThread(self.database_manager, date_str, num_bets, num_run_bets)
        self.workerThread.resultReady.connect(self.processResults)
        self.workerThread.start()
        
        # Display loading message
        self.results_text.setText("Loading bet runs data...")
        
    def on_global_date_changed(self, new_date):
        """Handle global date change from ActivityWidget"""
        # Update our date editor without triggering a refresh
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(new_date)
        self.date_edit.blockSignals(False)
        
        # Update the visible date label
        self.date_label.setText(new_date.toString("dd/MM/yyyy"))
        
        # Now refresh data
        self.manualRefresh()

    def startPeriodicUpdate(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.checkForUpdate)
        self.timer.start(20000)  # Update every 20 seconds
        
    def checkForUpdate(self):
        # Only update if scrolled to top (like original code)
        scroll_value = self.results_text.verticalScrollBar().value()
        if scroll_value <= 5:  # Near top of scroll area
            # Only refresh if showing today's date
            current_date = self.date_edit.date().toString("dd/MM/yyyy")
            today = QDate.currentDate().toString("dd/MM/yyyy")
            if current_date == today:
                self.manualRefresh()
            
    def processResults(self, result, error_message):
        if error_message:
            self.results_text.setText(error_message)
            return
            
        runs_data = result
        
        # Build formatted HTML result
        html_content = []
        
        for run in runs_data:
            selection = run["selection"]
            matched_odds = run["matched_odds"]
            bet_details = run["bet_details"]
            is_enhanced = run["is_enhanced"]
            
            # Add selection heading
            if matched_odds is not None:
                html_content.append(f'<p style="color:{self.text_styles["oddsmonkey"]}"><b>{selection} | OM Lay: {matched_odds}</b></p>')
            else:
                html_content.append(f'<p><b>{selection}</b></p>')
            
            # Add each bet on this selection
            for bet in bet_details:
                style = bet["style"]
                html_content.append(
                    f'<p style="color:{self.text_styles[style]}; margin-left:15px">- {bet["time"]} - {bet["bet_id"]} | {bet["customer_ref"]} ({bet["risk_category"]}) at {bet["odds"]}</p>'
                )
            
            # Check for enhanced places
            if is_enhanced:
                html_content.append(f'<p style="color:{self.text_styles["oddsmonkey"]}">Enhanced Place Race</p>')
            
            html_content.append('<p>&nbsp;</p>')  # Add spacing
            
        # Set the content
        self.results_text.setHtml(''.join(html_content))