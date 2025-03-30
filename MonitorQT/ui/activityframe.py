from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QSizePolicy, QPushButton,
                             QDateEdit, QMenu)  
from PySide6.QtCore import Qt, QDate, Signal, QTimer, QRect, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QAction  

import threading
from datetime import datetime, timedelta
from utils import access_data, user
import math

class SimpleHorizontalBarChart(QFrame):  # Changed from QWidget to QFrame
    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.values = []
        self.colors = []
        self.labels = []
        self.title = title
        self.setMinimumHeight(90)  # Reduced height
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Apply the same frame style as StatsPanel
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("background-color: #292929; border-radius: 8px; padding: 1px;")
        
    def setup(self, values, labels, colors):
        self.values = values
        self.labels = labels
        self.colors = colors
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Skip drawing the background since the frame style handles it
        
        # Skip drawing if no data
        if not self.values or sum(self.values) == 0:
            # Draw "No Data" text
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No data available")
            return
            
        # Calculate total for percentages
        total = sum(self.values)
        
        # Define the chart area with better padding
        width = self.width() - 20
        height = self.height() - 10
        bar_height = 16
        spacing = 6  # Reduced spacing
        
        # Center the bars vertically in the frame
        total_bars_height = (bar_height + spacing) * len(self.values) - spacing
        y_start = (height - total_bars_height) / 2 + 5  # Center vertically
                
        # Find max value for scaling
        max_value = max(self.values)
        
        # Calculate available width for bars
        label_width = 60  # Fixed width for labels
        value_width = 60  # Fixed width for values
        bar_width = width - label_width - value_width - 20
        
        # Draw each bar
        for i, value in enumerate(self.values):
            if i >= len(self.labels) or i >= len(self.colors):
                continue
                
            # Calculate y position
            y_pos = y_start + (bar_height + spacing) * i
            
            # Draw label
            painter.setPen(Qt.white)
            painter.drawText(
                10, 
                y_pos + bar_height - 2,
                self.labels[i]
            )
            
            # Calculate bar length proportional to value
            bar_length = (value / max_value) * bar_width if max_value > 0 else 0
            
            # Draw bar background (track)
            painter.setPen(QPen(QColor("#333333")))
            painter.setBrush(QBrush(QColor("#333333")))
            painter.drawRoundedRect(
                label_width + 10,
                y_pos,
                bar_width,
                bar_height,
                4, 4
            )
            
            # Draw the actual bar
            painter.setPen(QPen(self.colors[i].darker(120)))
            painter.setBrush(QBrush(self.colors[i]))
            painter.drawRoundedRect(
                label_width + 10,
                y_pos,
                bar_length,
                bar_height,
                4, 4
            )
            
            # Draw value and percentage
            percentage = (value / total * 100) if total > 0 else 0
            value_text = f"{value} ({percentage:.1f}%)"
            painter.setPen(Qt.white)
            
            # Position text after the bar
            painter.drawText(
                label_width + bar_width + 15,
                y_pos + bar_height - 2,
                value_text
            )

class StatsPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setStyleSheet("background-color: #292929; border-radius: 8px; padding: 1px;")
        
        layout = QGridLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        self.stats_labels = {}
        self.stats_values = {}
        
    def add_stat(self, row, col, label_text, initial_value="--", value_color="white"):
        # Create label
        label = QLabel(label_text)
        label.setStyleSheet("color: #aaaaaa; font-size: 9pt;")
        
        # Create value
        value = QLabel(initial_value)
        value.setStyleSheet(f"color: {value_color}; font-size: 10pt; font-weight: bold;")
        
        # Add to layout
        self.layout().addWidget(label, row, col * 2)
        self.layout().addWidget(value, row, col * 2 + 1)
        
        # Store references
        self.stats_labels[label_text] = label
        self.stats_values[label_text] = value
        
    def update_stat(self, label_text, new_value, color=None):
        if label_text in self.stats_values:
            self.stats_values[label_text].setText(new_value)
            if color:
                self.stats_values[label_text].setStyleSheet(f"color: {color}; font-size: 11pt; font-weight: bold;")

class ActivityWidget(QWidget):
    refresh_signal = Signal()
    date_changed_signal = Signal(QDate)  # Signal to notify date changes

    def __init__(self, database_manager):
        super().__init__()
        self.database_manager = database_manager
        self.setMinimumHeight(300)
        
        # Connect signals
        self.refresh_signal.connect(self.update_ui)
        
        self.initialize_ui()
        self.start_data_refresh()
    
    def initialize_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header with date and refresh button
        header_layout = QHBoxLayout()
        
        # Create a date widget container
        date_container = QWidget()
        date_container_layout = QHBoxLayout(date_container)
        date_container_layout.setContentsMargins(0, 0, 0, 0)
        date_container_layout.setSpacing(5)
        
        # Date label now acts as a dropdown trigger
        self.date_label = QLabel("Today's Activity")
        self.date_label.setStyleSheet("""
            font-size: 14pt; 
            font-weight: bold; 
            color: white;
            padding: 2px 5px;
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 10);
        """)
        self.date_label.setCursor(Qt.PointingHandCursor)
        self.date_label.mousePressEvent = self.showDateMenu
        date_container_layout.addWidget(self.date_label)
        
        # Add a small dropdown indicator
        dropdown_indicator = QLabel("▼")
        dropdown_indicator.setStyleSheet("color: #aaaaaa; font-size: 8pt;")
        date_container_layout.addWidget(dropdown_indicator)
        
        # Add the date container to the header
        header_layout.addWidget(date_container)
        
        # User indicator (move to right side)
        self.user_label = QLabel("")
        self.user_label.setStyleSheet("color: #aaaaaa; font-size: 10pt;")
        header_layout.addWidget(self.user_label, 0, Qt.AlignRight)
        
        
        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setStyleSheet("font-size: 14pt;")
        self.refresh_button.setFixedWidth(30)
        self.refresh_button.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.refresh_button, 0, Qt.AlignRight)
        
        main_layout.addLayout(header_layout)
        

        # Create a date edit widget (hidden, used in menu)
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.dateChanged.connect(self.on_date_changed)
        self.date_edit.setVisible(False)  # Hidden by default
        
        # Stats panel - top row
        self.bet_stats_panel = StatsPanel()
        self.bet_stats_panel.add_stat(0, 0, "Bets:", "0")
        self.bet_stats_panel.add_stat(0, 1, "vs Last Week:", "0")
        self.bet_stats_panel.add_stat(1, 0, "Knockbacks:", "0")
        self.bet_stats_panel.add_stat(1, 1, "Knockback %:", "0.00%")
        main_layout.addWidget(self.bet_stats_panel)
        
        # Bet stats panel
        self.stats_panel = StatsPanel()
        self.stats_panel.add_stat(0, 0, "Turnover:", "£0.00")
        self.stats_panel.add_stat(0, 1, "Profit:", "£0.00")
        self.stats_panel.add_stat(1, 0, "Profit %:", "0.00%")
        main_layout.addWidget(self.stats_panel)

        # Bet Type stats panel
        self.bet_type_stats_panel = StatsPanel()
        self.bet_type_stats_panel.add_stat(0, 0, "Horse Bets:", "0")
        self.bet_type_stats_panel.add_stat(0, 1, "Dog Bets:", "0")
        self.bet_type_stats_panel.add_stat(1, 0, "Other Bets:", "0")
        main_layout.addWidget(self.bet_type_stats_panel)

        # Bar chart for visual representation - updated title
        self.chart = SimpleHorizontalBarChart("Client Risk Distribution")        
        main_layout.addWidget(self.chart)
    
    def start_data_refresh(self):
        # Initial update
        threading.Thread(target=self.update_activity_data, daemon=True).start()
        
        # Schedule periodic updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(30000)  # Update every 30 seconds
    
    def refresh_data(self):
        threading.Thread(target=self.update_activity_data, daemon=True).start()
    
    def update_activity_data(self):
        try:
            # Get the reporting data
            vip_clients, newreg_clients, todays_oddsmonkey_selections, reporting_data = access_data()
            
            # Get the selected date (assuming we're tracking current date)
            current_date = QDate.currentDate().toString("dd/MM/yyyy")
            previous_date = (datetime.now() - timedelta(days=7)).strftime('%d/%m/%Y')
            is_today = current_date == datetime.today().strftime('%d/%m/%Y')
            
            # Get current time for filtering
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # Connect to database
            conn, cursor = self.database_manager.get_connection()
            try:
                # Prepare query for bet stats
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
                    current_date, current_time if is_today else None, current_time if is_today else None,
                    previous_date, current_time if is_today else None, current_time if is_today else None,
                    current_date, current_time if is_today else None, current_time if is_today else None,
                    previous_date, current_time if is_today else None, current_time if is_today else None,
                    current_date, current_time if is_today else None, current_time if is_today else None,
                    current_date, current_time if is_today else None, current_time if is_today else None,
                    current_date, current_time if is_today else None, current_time if is_today else None,
                    current_date, current_time if is_today else None, current_time if is_today else None
                ]
                cursor.execute(query, params)
                
                (current_bets, previous_bets, current_knockbacks, previous_knockbacks,
                 current_total_unique_clients, current_unique_m_clients, current_unique_w_clients,
                 current_unique_norisk_clients) = cursor.fetchone()
                
                # Get sport counts
                cursor.execute(
                    "SELECT sports, COUNT(*) FROM database WHERE date = ? AND type = 'BET' " + 
                    ("AND time <= ? GROUP BY sports" if is_today else "GROUP BY sports"),
                    (current_date, current_time) if is_today else (current_date,)
                )
                current_sport_counts = cursor.fetchall()
                
                # Process sport counts
                horse_bets = 0
                dog_bets = 0
                other_bets = 0
                sport_mapping = {'Horses': 0, 'Dogs': 1, 'Other': 2}
                
                for sport, count in current_sport_counts:
                    try:
                        sport_list = eval(sport) if sport else []
                        if sport_mapping['Horses'] in sport_list:
                            horse_bets += count
                        if sport_mapping['Dogs'] in sport_list:
                            dog_bets += count
                        if sport_mapping['Other'] in sport_list:
                            other_bets += count
                    except:
                        # Handle invalid sport data
                        pass
                
                # Calculate statistics
                if previous_bets > 0:
                    percentage_change_bets = ((current_bets - previous_bets) / previous_bets) * 100
                else:
                    percentage_change_bets = 0
                
                if previous_knockbacks > 0:
                    percentage_change_knockbacks = ((current_knockbacks - previous_knockbacks) / previous_knockbacks) * 100
                else:
                    percentage_change_knockbacks = 0
                
                knockback_percentage = (current_knockbacks / current_bets * 100) if current_bets > 0 else 0
                previous_knockback_percentage = (previous_knockbacks / previous_bets * 100) if previous_bets > 0 else 0
                
                # Format data for display
                try:
                    # Handle currency values with pound symbols
                    turnover_str = str(reporting_data.get('daily_turnover', '0.00'))
                    profit_str = str(reporting_data.get('daily_profit', '0.00'))
                    
                    # Remove pound symbol and any other non-numeric characters except decimal point
                    turnover_str = ''.join(c for c in turnover_str if c.isdigit() or c == '.')
                    profit_str = ''.join(c for c in profit_str if c.isdigit() or c == '.')
                    
                    # Convert to float
                    daily_turnover = float(turnover_str) if turnover_str else 0.0
                    daily_profit = float(profit_str) if profit_str else 0.0
                    
                    # Handle percentage which might be null
                    profit_pct = reporting_data.get('daily_profit_percentage')
                    daily_profit_percentage = float(profit_pct) if profit_pct is not None else 0.0
                    
                except (ValueError, TypeError):
                    # Handle case where conversion fails
                    print("Warning: Failed to convert reporting data to float")
                    print(f"Original values: turnover={reporting_data.get('daily_turnover')}, profit={reporting_data.get('daily_profit')}, percentage={reporting_data.get('daily_profit_percentage')}")
                    daily_turnover = 0.0
                    daily_profit = 0.0
                    daily_profit_percentage = 0.0
                
                bet_change_indicator = "↑" if current_bets > previous_bets else "↓" if current_bets < previous_bets else "→"
                knockback_change_indicator = "↑" if current_knockbacks > previous_knockbacks else "↓" if current_knockbacks < previous_knockbacks else "→"
                
                current_day_name = datetime.strptime(current_date, '%d/%m/%Y').strftime('%A')
                previous_day_short = datetime.strptime(previous_date, '%d/%m/%Y').strftime('%d/%m')
                
                # Store data for UI update
                self.update_data = {
                    'date': f"{current_day_name} {current_date}",
                    'user': user.USER_NAMES.get(user.get_user(), user.get_user()) if hasattr(user, 'get_user') else "",
                    'turnover': f"£{daily_turnover:,.2f}",
                    'profit': f"£{daily_profit:,.2f}",
                    'profit_percentage': daily_profit_percentage,
                    'current_bets': current_bets,
                    'previous_bets': previous_bets,
                    'percentage_change_bets': percentage_change_bets,
                    'current_knockbacks': current_knockbacks,
                    'previous_knockbacks': previous_knockbacks,
                    'percentage_change_knockbacks': percentage_change_knockbacks,
                    'knockback_percentage': knockback_percentage,
                    'previous_knockback_percentage': previous_knockback_percentage,
                    'total_clients': current_total_unique_clients,
                    'risk_clients': current_unique_m_clients,
                    'watchlist_clients': current_unique_w_clients,
                    'normal_clients': current_unique_norisk_clients,
                    'horse_bets': horse_bets,
                    'dog_bets': dog_bets,
                    'other_bets': other_bets,
                    'bet_change_indicator': bet_change_indicator,
                    'knockback_change_indicator': knockback_change_indicator,
                    'previous_day_short': previous_day_short
                }
                
                # Signal UI update
                self.refresh_signal.emit()
                
            finally:
                if conn:
                    conn.close()
                
        except Exception as e:
            print(f"Error updating activity data: {e}")
            # Will retry on next timer tick
    
    def update_ui(self):
        """Update UI with the fetched data"""
        if not hasattr(self, 'update_data'):
            return
            
        data = self.update_data
        
        # Update bet stats
        self.bet_stats_panel.update_stat("Bets:", f"{data['current_bets']:,}")
        
        # Format bet change with indicator and color
        bet_change_color = "#20c997" if data['percentage_change_bets'] > 0 else "#fa5252"
        bet_change_text = f"{data['bet_change_indicator']} {abs(data['percentage_change_bets']):.1f}% ({data['previous_bets']:,})"
        self.bet_stats_panel.update_stat("vs Last Week:", bet_change_text, bet_change_color)
        
        # Update knockback stats
        self.bet_stats_panel.update_stat("Knockbacks:", f"{data['current_knockbacks']:,}")
        self.bet_stats_panel.update_stat("Knockback %:", f"{data['knockback_percentage']:.1f}% ({data['previous_knockback_percentage']:.1f}%)")
        
        # Update date/header
        user_info = f" {data['user']}" if data['user'] else ""
        self.date_label.setText(f"{data['date']}{user_info}")
        
        # Update main stats
        self.stats_panel.update_stat("Turnover:", data['turnover'])
        self.stats_panel.update_stat("Profit:", data['profit'])
        
        # Format profit percentage with color
        profit_pct_color = "#20c997" if data['profit_percentage'] >= 0 else "#fa5252"
        self.stats_panel.update_stat("Profit %:", f"{data['profit_percentage']:.1f}%", profit_pct_color)
        

        # Update bet type stats
        self.bet_type_stats_panel.update_stat("Horse Bets:", f"{data['horse_bets']:,}")
        self.bet_type_stats_panel.update_stat("Dog Bets:", f"{data['dog_bets']:,}")
        self.bet_type_stats_panel.update_stat("Other Bets:", f"{data['other_bets']:,}")
        
        # Update chart - now showing client risk categories instead of bet types
        values = [data['normal_clients'], data['watchlist_clients'], data['risk_clients']]
        labels = ["Normal", "Watchlist", "Risk 'M'"]
        
        # Colors: Green for normal, orange for watchlist, red for risk
        colors = [QColor("#20c997"), QColor("#e67700"), QColor("#c92a2a")]
        
        self.chart.setup(values, labels, colors)

    def showDateMenu(self, event):
        """Show a menu with date options when the date label is clicked"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #333333;
                color: white;
                border: 1px solid #555555;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 10px;
            }
            QMenu::item:selected {
                background-color: #555555;
            }
        """)
        
        # Add date options
        today_action = QAction("Today", self)
        today_action.triggered.connect(self.set_date_to_today)
        menu.addAction(today_action)
        
        yesterday_action = QAction("Yesterday", self)
        yesterday_action.triggered.connect(self.set_date_to_yesterday)
        menu.addAction(yesterday_action)
        
        menu.addSeparator()
        
        # Add option to show date picker
        pick_date_action = QAction("Pick Date...", self)
        pick_date_action.triggered.connect(self.show_date_picker)
        menu.addAction(pick_date_action)
        
        # Show the menu
        menu.exec(self.date_label.mapToGlobal(QPoint(0, self.date_label.height())))
    
    def set_date_to_today(self):
        """Set date to today"""
        today = QDate.currentDate()
        if self.date_edit.date() != today:
            self.date_edit.setDate(today)
            # Signal will be emitted by date_edit's dateChanged
    
    def set_date_to_yesterday(self):
        """Set date to yesterday"""
        yesterday = QDate.currentDate().addDays(-1)
        if self.date_edit.date() != yesterday:
            self.date_edit.setDate(yesterday)
            # Signal will be emitted by date_edit's dateChanged
    
    def show_date_picker(self):
        """Show the date picker dialog"""
        # Position and show the calendar popup
        self.date_edit.setVisible(True)
        self.date_edit.calendarWidget().setVisible(True)
        self.date_edit.calendarPopup().exec()
        self.date_edit.setVisible(False)
    
    def on_date_changed(self, new_date):
        """Handle date change from the date edit widget"""
        # Update the date label
        date_str = new_date.toString("dddd dd/MM/yyyy")
        self.date_label.setText(date_str)
        
        # Emit signal for other components
        self.date_changed_signal.emit(new_date)
        
        # Refresh data for new date
        self.refresh_data()