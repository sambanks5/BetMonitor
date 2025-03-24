from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar)
import threading
from PySide6.QtCore import Qt, QTimer, Signal
from utils import schedule_data_updates

class LoadingScreen(QDialog):
    loading_complete = Signal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bet Monitor")
        self.setFixedSize(400, 200)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        
        layout = QVBoxLayout()
        
        # Loading message
        self.message_label = QLabel("Loading application data...")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Status message
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
    def update_progress(self, value, message=None):
        self.progress_bar.setValue(value)
        if message:
            self.status_label.setText(message)

    def start_loading(self, app_controller):
        """Start the loading process"""
        # Store controller reference to call methods later
        self.app_controller = app_controller
        
        # Create a timer to simulate loading (you'll replace this)
        self.timer_count = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.perform_loading_step)
        self.timer.start(100)  # Time in ms between steps
    
    def perform_loading_step(self):
        """Simulate loading steps - replace with real loading"""
        steps = [
            "Connecting to database...",
            "Scheduling data updates...",
            "Loading bet data...",
            "Preparing UI components...",
            "Loading oddsmonkey selections...",
            "Finalizing..."
        ]
        
        self.timer_count += 1
        progress = min(self.timer_count * 5, 100)  # 5% per step
        
        step_index = min(self.timer_count // 4, len(steps) - 1)
        self.update_progress(progress, steps[step_index])
        
        # When one of the steps completes, you would perform actual data loading
        # For example when at 20% complete:
        if progress == 20:
            # Fetch initial data
            self.app_controller.load_initial_data()
            
        # When complete
        if progress >= 100:
            self.timer.stop()
            self.loading_complete.emit()