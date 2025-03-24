from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from ui.betfeed import BetFeedWidget
from utils.db_manager import DatabaseManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bet Monitor")
        self.resize(900, 1000)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create database manager
        database_manager = DatabaseManager()
        
        # Create and add the bet feed widget
        self.bet_feed = BetFeedWidget(database_manager)
        layout.addWidget(self.bet_feed)
        
        # Setup menu bar and additional components
        self.setup_menu_bar()
        
    def setup_menu_bar(self):
        # Create menu bar and menus similar to your original application
        pass