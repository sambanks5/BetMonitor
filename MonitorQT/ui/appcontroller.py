import threading
from PySide6.QtCore import QObject, Signal, Slot
from ui.logindialog import LoginDialog
from ui.loading import LoadingScreen
from ui.root import MainWindow
from utils import access_data, schedule_data_updates

class AppController(QObject):
    data_loaded_signal = Signal()
    
    def __init__(self, app, database_manager):
        super().__init__()
        self.app = app
        self.main_window = None
        self.database_manager = database_manager
        
        # Connect signals
        self.data_loaded_signal.connect(self.on_data_loaded)
        
    def start(self):
        """Start the application flow"""
        # Show login dialog
        login_dialog = LoginDialog()
        if login_dialog.exec():  # Dialog accepted (user logged in)
            self.show_loading_screen()
        else:
            # User cancelled login
            self.app.quit()
            
    def show_loading_screen(self):
        """Show the loading screen and begin loading data"""
        self.loading_screen = LoadingScreen()
        self.loading_screen.loading_complete.connect(self.show_main_window)
        self.loading_screen.show()
        self.loading_screen.start_loading(self)
    
    def load_initial_data(self):
        """Load initial data in a background thread"""
        threading.Thread(target=self._load_data, daemon=True).start()
        
    def _load_data(self):
        """Background thread to load data"""
        try:
            # Force initial data loading
            threading.Thread(target=schedule_data_updates, daemon=True).start()
            threading.Thread(target=self.database_manager.periodic_cache_update, daemon=True).start()
            
            # Signal completion back to main thread
            self.data_loaded_signal.emit()
        except Exception as e:
            print(f"Error loading data: {e}")
            # Handle error - could emit a different signal
    
    @Slot()
    def on_data_loaded(self):
        """Handler called when data is loaded"""
        # Update loading screen progress
        self.loading_screen.update_progress(80, "Data loaded successfully!")
        
    def show_main_window(self):
        """Show the main application window"""
        self.loading_screen.hide()
        self.main_window = MainWindow(self.database_manager)
        self.main_window.show()