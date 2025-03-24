from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QSplitter, 
                              QDockWidget, QTabWidget, QApplication, QHBoxLayout)
from PySide6.QtCore import Qt, QSize
from ui.betfeed import BetFeedWidget
from ui.activityframe import ActivityWidget  # You'll create this
from ui.betruns import BetRunsWidget    # You'll create this
from ui.tools import ToolsWidget        # Optional additional widget
from utils.db_manager import DatabaseManager

class MainWindow(QMainWindow):
    def __init__(self, database_manager):
        super().__init__()
        self.setWindowTitle("Bet Monitor")
        self.resize(900, 1000)
        
        # Apply font style to all widgets
        self.setStyleSheet("""
            * {
                font-family: 'Helvetica';
                font-size: 10pt;
            }
            QListView {
                font-size: 10pt;
                background-color: #242424;
                border: none;
            }
            QPushButton {
                font-size: 11pt;
                font-weight: normal;
                background-color: #333333;
                border: 1px solid #444444;
                color: #ffffff;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QDockWidget::title {
                background-color: #333333;
                color: #ffffff;
                padding-left: 5px;
            }
            QSplitter::handle {
                background-color: #333333;
            }
        """)
        
        # Store database manager
        self.database_manager = database_manager
        
        # Create the main central widget as a splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.main_splitter)
        
        # Create the left panel (Bet Feed)
        self.bet_feed = BetFeedWidget(self.database_manager)
        self.main_splitter.addWidget(self.bet_feed)
        
        # Create the right panel container
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create right panel widgets
        self.activity_widget = ActivityWidget(self.database_manager)
        self.betruns_widget = BetRunsWidget(self.database_manager)
        
        # Create a splitter for the right side
        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.addWidget(self.activity_widget)
        self.right_splitter.addWidget(self.betruns_widget)
        
        # Set initial sizes for right panel splits (30% activity, 70% bet runs)
        self.right_splitter.setSizes([420, 580])
        
        # Add the right splitter to the right panel layout
        self.right_layout.addWidget(self.right_splitter)
        
        # Add the right panel to the main splitter
        self.main_splitter.addWidget(self.right_panel)
        
        # Set initial sizes for main splitter (50% each side)
        self.main_splitter.setSizes([450, 450])
        
        # Create dock widgets for pop-out panels
        self.create_dock_widgets()
        
        # Setup menu bar and additional components
        self.setup_menu_bar()
    
    def create_dock_widgets(self):
        # Create a dock widget for tools/utilities
        self.tools_dock = QDockWidget("Tools", self)
        self.tools_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        self.tools_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        
        # Set a minimum/maximum size that fits your 900x270 constraint
        self.tools_dock.setMinimumSize(QSize(600, 200))
        self.tools_dock.setMaximumHeight(270)
        
        # Create a widget to hold the tools content
        tools_widget = ToolsWidget(self.database_manager)
        self.tools_dock.setWidget(tools_widget)
        
        # Add the dock widget to the main window - initially hidden
        self.addDockWidget(Qt.BottomDockWidgetArea, self.tools_dock)
        self.tools_dock.hide()  # Start hidden, show when needed
        
        # You can create additional dock widgets as needed
    
    def setup_menu_bar(self):
        # Create menu bar with options to show/hide panels
        menu_bar = self.menuBar()
        
        # View menu for showing/hiding panels
        view_menu = menu_bar.addMenu("View")
        
        # Action to show/hide tools panel
        tools_action = view_menu.addAction("Tools Panel")
        tools_action.setCheckable(True)
        tools_action.triggered.connect(self.toggle_tools_panel)
        
        # Add other menus for your application features
    
    def toggle_tools_panel(self, checked):
        if checked:
            # If Betty is open, position the dock widget below it
            screen = QApplication.primaryScreen().availableGeometry()
            # Calculate position to place below Betty (assuming Betty is at 0,0 with width x height)
            betty_width = 900  # Adjust based on actual Betty width
            betty_height = 730  # Adjust based on actual Betty height
            
            if self.tools_dock.isFloating():
                # Position below Betty
                self.tools_dock.setGeometry(betty_width, betty_height, 900, 270)
            
            self.tools_dock.show()
        else:
            self.tools_dock.hide()