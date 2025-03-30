from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QFrame, QListWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

class SelectionDialog(QDialog):
    def __init__(self, selection_name, database_manager, parent=None):
        super().__init__(parent)
        self.selection_name = selection_name
        self.database_manager = database_manager
        self.initUI()
        self.loadData()
        
    def initUI(self):
        self.setWindowTitle(f"Selection: {self.selection_name}")
        self.setMinimumSize(600, 500)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Header with selection info
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #292929; border-radius: 8px; padding: 10px;")
        header_layout = QVBoxLayout(header_frame)
        
        # Selection name header
        self.selection_label = QLabel(self.selection_name)
        self.selection_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: white;")
        header_layout.addWidget(self.selection_label)
        
        # Stats
        self.stats_label = QLabel("Loading selection data...")
        self.stats_label.setStyleSheet("color: #e0e0e0;")
        header_layout.addWidget(self.stats_label)
        
        main_layout.addWidget(header_frame)
        
        # Bet list
        bet_list_frame = QFrame()
        bet_list_frame.setStyleSheet("background-color: #242424; border-radius: 8px;")
        bet_list_layout = QVBoxLayout(bet_list_frame)
        
        bet_list_label = QLabel("Bets on this Selection")
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
        bet_list_layout.addWidget(self.bet_list)
        
        main_layout.addWidget(bet_list_frame)
        
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
            # This query is more complex - we need to find bets where the selection appears
            # in the JSON array of selections
            cursor.execute("""
                SELECT id, customer_ref, risk_category, time, date, unit_stake, 
                       bet_details, bet_type, selections
                FROM database 
                WHERE selections LIKE ? AND type != 'WAGER KNOCKBACK' AND type != 'SMS WAGER'
                ORDER BY date DESC, time DESC
            """, (f'%{self.selection_name}%',))
            
            bets = cursor.fetchall()
            
            # Calculate stats
            total_bets = len(bets)
            total_stake = sum(bet[5] or 0 for bet in bets)
            
            if bets:
                # Update selection info
                self.stats_label.setText(
                    f"Total Bets: {total_bets} | "
                    f"Total Stake: £{total_stake:.2f}"
                )
            else:
                self.stats_label.setText("No bets found for this selection")
            
            # Filter to only include bets that actually contain this selection
            filtered_bets = []
            for bet in bets:
                selections = bet[8]
                if not selections:
                    continue
                    
                try:
                    import json
                    if isinstance(selections, str):
                        parsed_selections = json.loads(selections)
                    else:
                        parsed_selections = selections
                        
                    # Check if the selection is in this bet
                    selection_found = False
                    for selection in parsed_selections:
                        if isinstance(selection, list) and len(selection) >= 1:
                            if self.selection_name in selection[0]:
                                selection_found = True
                                break
                                
                    if selection_found:
                        filtered_bets.append(bet)
                        
                except Exception:
                    continue
            
            # Update stats with filtered data
            total_filtered_bets = len(filtered_bets)
            total_filtered_stake = sum(bet[5] or 0 for bet in filtered_bets)
            
            self.stats_label.setText(
                f"Total Bets: {total_filtered_bets} | "
                f"Total Stake: £{total_filtered_stake:.2f}"
            )
            
            # Populate bet list
            for bet in filtered_bets:
                bet_id = bet[0]
                customer_ref = bet[1]
                risk_category = bet[2] or "-"
                bet_time = bet[3]
                bet_date = bet[4]
                unit_stake = bet[5] or 0
                bet_details = bet[6]
                bet_type = bet[7]
                
                # Format item text
                display_text = f"{bet_date} {bet_time} - {customer_ref} ({risk_category}) - £{unit_stake:.2f} {bet_details}"
                
                # Create item
                item = QListWidgetItem(display_text)
                
                # Style based on risk category
                if risk_category in ('M', 'C'):
                    item.setForeground(QColor(173, 2, 2))
                elif risk_category == 'W':
                    item.setForeground(QColor(227, 95, 0))
                
                self.bet_list.addItem(item)
            
        finally:
            conn.close()