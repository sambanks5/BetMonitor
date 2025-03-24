from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QLabel, 
                              QLineEdit, QPushButton, QHBoxLayout, QGridLayout)

class ToolsWidget(QWidget):
    def __init__(self, database_manager):
        super().__init__()
        self.database_manager = database_manager
        self.initialize_ui()
    
    def initialize_ui(self):
        layout = QVBoxLayout(self)
        
        # Create a tab widget to organize tools
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444444;
                background-color: #242424;
            }
            QTabBar::tab {
                background-color: #333333;
                color: #cccccc;
                padding: 6px 12px;
                border: 1px solid #444444;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #242424;
                color: white;
            }
        """)
        
        # Customer lookup tool
        customer_tab = QWidget()
        customer_layout = QGridLayout(customer_tab)
        
        customer_layout.addWidget(QLabel("Customer Reference:"), 0, 0)
        customer_ref_input = QLineEdit()
        customer_layout.addWidget(customer_ref_input, 0, 1)
        
        search_button = QPushButton("Search")
        customer_layout.addWidget(search_button, 0, 2)
        
        customer_results = QLabel("Enter a customer reference to search")
        customer_layout.addWidget(customer_results, 1, 0, 1, 3)
        
        # Add more tools as needed
        tab_widget.addTab(customer_tab, "Customer Lookup")
        
        # Add other tabs for additional tools
        
        layout.addWidget(tab_widget)