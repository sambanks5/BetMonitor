from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QPushButton, QFrame, QListWidgetItem, QSplitter
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont
import json
from datetime import datetime

class CustomerBetsDialog(QDialog):
    def __init__(self, customer_ref, database_manager, parent=None):
        super().__init__(parent)
        self.customer_ref = customer_ref
        self.database_manager = database_manager
        self.initUI()
        self.loadData()
        
    def initUI(self):
        self.setWindowTitle(f"Customer: {self.customer_ref}")
        self.setMinimumSize(800, 600)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Header with customer info
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #292929; border-radius: 8px; padding: 10px;")
        header_layout = QVBoxLayout(header_frame)
        
        # Customer reference header
        self.customer_label = QLabel(f"Customer: {self.customer_ref}")
        self.customer_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: white;")
        header_layout.addWidget(self.customer_label)
        
        # Risk category and stats
        self.stats_label = QLabel("Loading customer data...")
        self.stats_label.setStyleSheet("color: #e0e0e0;")
        header_layout.addWidget(self.stats_label)
        
        main_layout.addWidget(header_frame)
        
        # Splitter for bet list and details
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Bet list
        bet_list_frame = QFrame()
        bet_list_frame.setStyleSheet("background-color: #242424; border-radius: 8px;")
        bet_list_layout = QVBoxLayout(bet_list_frame)
        
        bet_list_label = QLabel("Recent Bets")
        bet_list_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: white;")
        bet_list_layout.addWidget(bet_list_label)
        
        self.bet_list = QListWidget()
        self.bet_list.setStyleSheet("""
            QListWidget {
                background-color: #292929;
                color: white;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)
        self.bet_list.currentItemChanged.connect(self.showBetDetails)
        bet_list_layout.addWidget(self.bet_list)
        
        # Right side - Bet details
        bet_details_frame = QFrame()
        bet_details_frame.setStyleSheet("background-color: #242424; border-radius: 8px;")
        bet_details_layout = QVBoxLayout(bet_details_frame)
        
        bet_details_label = QLabel("Bet Details")
        bet_details_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: white;")
        bet_details_layout.addWidget(bet_details_label)
        
        self.bet_details = QLabel("Select a bet to view details")
        self.bet_details.setStyleSheet("color: #e0e0e0; background-color: #292929; padding: 10px; border-radius: 4px;")
        self.bet_details.setWordWrap(True)
        self.bet_details.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.bet_details.setTextFormat(Qt.RichText)
        bet_details_layout.addWidget(self.bet_details)
        
        # Add frames to splitter
        splitter.addWidget(bet_list_frame)
        splitter.addWidget(bet_details_frame)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        close_button = QPushButton("Done")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
        
    def loadData(self):
        # Get a connection to the database
        conn, cursor = self.database_manager.get_connection()
        if not conn or not cursor:
            self.stats_label.setText("Error: Could not connect to database")
            return
            
        try:
            # Get customer info
            cursor.execute("""
                SELECT risk_category, COUNT(*) as bet_count, 
                       SUM(unit_stake) as total_stake,
                       date
                FROM database 
                WHERE customer_ref = ? 
                GROUP BY date
                ORDER BY date DESC
            """, (self.customer_ref,))
            
            customer_data = cursor.fetchall()
            
            if customer_data:
                # Get risk category from most recent bet
                risk_category = customer_data[0][0] or "Normal"
                total_bets = sum(row[1] for row in customer_data)
                total_stake = sum(row[2] or 0 for row in customer_data)
                active_days = len(customer_data)
                
                # Update customer info
                risk_color = "#c92a2a" if risk_category in ('M', 'C') else \
                             "#e67700" if risk_category == 'W' else "#20c997"
                
                self.stats_label.setText(
                    f"Risk Category: <span style='color: {risk_color};'>{risk_category}</span> | "
                    f"Total Bets: {total_bets} | Total Stake: £{total_stake:.2f} | "
                    f"Active Days: {active_days}"
                )
            else:
                self.stats_label.setText("No data found for this customer")
            
            # Get recent bets
            cursor.execute("""
                SELECT id, time, date, unit_stake, selections, bet_details, bet_type, type
                FROM database 
                WHERE customer_ref = ? 
                ORDER BY date DESC, time DESC
                LIMIT 50
            """, (self.customer_ref,))
            
            bets = cursor.fetchall()
            
            # Populate bet list
            for bet in bets:
                bet_id = bet[0]
                bet_time = bet[1]
                bet_date = bet[2]
                unit_stake = bet[3] or 0
                bet_type = bet[7]  # SMS, KNOCKBACK, or normal bet
                
                # Format item text
                if bet_type == "SMS WAGER":
                    display_text = f"{bet_date} {bet_time} - SMS"
                elif bet_type == "WAGER KNOCKBACK":
                    display_text = f"{bet_date} {bet_time} - KNOCKBACK"
                else:
                    bet_details = bet[5]
                    sport_type = bet[6]
                    display_text = f"{bet_date} {bet_time} - £{unit_stake:.2f} {bet_details} ({sport_type})"
                
                # Create item with the bet data
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, bet)
                
                # Style based on bet type
                if bet_type == "WAGER KNOCKBACK":
                    item.setForeground(QColor(173, 2, 2))
                elif bet_type == "SMS WAGER":
                    item.setForeground(QColor(0, 102, 204))
                
                self.bet_list.addItem(item)
            
        finally:
            conn.close()
    
    def showBetDetails(self, current, previous):
        if not current:
            self.bet_details.setText("Select a bet to view details")
            return
            
        bet_data = current.data(Qt.UserRole)
        if not bet_data:
            return
            
        bet_id = bet_data[0]
        bet_time = bet_data[1]
        bet_date = bet_data[2]
        unit_stake = bet_data[3] or 0
        selections = bet_data[4]
        bet_details = bet_data[5]
        sport_type = bet_data[6]
        bet_type = bet_data[7]
        
        # Format HTML content
        html_content = [f"<h3>Bet: {bet_id}</h3>"]
        html_content.append(f"<p><b>Date/Time:</b> {bet_date} {bet_time}</p>")
        
        if bet_type == "SMS WAGER":
            html_content.append("<p><b>Type:</b> <span style='color: #4dabf7;'>SMS WAGER</span></p>")
            html_content.append(f"<p><b>Message:</b><br/>{selections}</p>")
            
        elif bet_type == "WAGER KNOCKBACK":
            html_content.append("<p><b>Type:</b> <span style='color: #c92a2a;'>WAGER KNOCKBACK</span></p>")
            
            # Parse knockback details
            try:
                if isinstance(selections, str):
                    knockback_details = json.loads(selections)
                else:
                    knockback_details = selections
                    
                html_content.append("<p><b>Knockback Details:</b></p><ul>")
                
                # Handle different formats
                if isinstance(knockback_details, dict):
                    for key, value in knockback_details.items():
                        if key not in ['Selections', 'Knockback ID', 'Time', 'Customer Ref']:
                            html_content.append(f"<li>{key}: {value}</li>")
                    
                    if 'Selections' in knockback_details and knockback_details['Selections']:
                        html_content.append("<p><b>Selections:</b></p><ul>")
                        for selection in knockback_details['Selections']:
                            meeting = selection.get('- Meeting Name', '')
                            name = selection.get('- Selection Name', '')
                            price = selection.get('- Bet Price', '')
                            html_content.append(f"<li>{meeting}, {name}, {price}</li>")
                        html_content.append("</ul>")
                        
                elif isinstance(knockback_details, list):
                    html_content.append("<p><b>Selections:</b></p><ul>")
                    for selection in knockback_details:
                        if isinstance(selection, dict):
                            meeting = selection.get('- Meeting Name', '')
                            name = selection.get('- Selection Name', '')
                            price = selection.get('- Bet Price', '')
                            html_content.append(f"<li>{meeting}, {name}, {price}</li>")
                    html_content.append("</ul>")
                    
                html_content.append("</ul>")
                
            except Exception as e:
                html_content.append(f"<p>Error parsing knockback details: {str(e)}</p>")
                html_content.append(f"<p>Raw data: {selections}</p>")
                
        else:
            # Regular bet
            html_content.append(f"<p><b>Stake:</b> £{unit_stake:.2f}</p>")
            html_content.append(f"<p><b>Details:</b> {bet_details}</p>")
            html_content.append(f"<p><b>Type:</b> {sport_type}</p>")
            
            # Parse selections
            try:
                if isinstance(selections, str):
                    parsed_selections = json.loads(selections)
                else:
                    parsed_selections = selections
                    
                html_content.append("<p><b>Selections:</b></p><ul>")
                for i, selection in enumerate(parsed_selections):
                    if len(selection) >= 2:
                        html_content.append(f"<li>{selection[0]} at {selection[1]}</li>")
                html_content.append("</ul>")
                
            except Exception as e:
                html_content.append(f"<p>Error parsing selections: {str(e)}</p>")
                html_content.append(f"<p>Raw data: {selections}</p>")
                
        self.bet_details.setText("".join(html_content))