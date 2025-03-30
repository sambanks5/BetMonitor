# main.py - Application entry point
import sys
import threading
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui.appcontroller import AppController
from utils.db_manager import DatabaseManager



if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set application-wide font
    font = QFont("Helvetica", 10)  # Choose your preferred font and size
    app.setFont(font)
    database_manager = DatabaseManager() 

    # Start the application flow
    controller = AppController(app, database_manager)
    controller.start()
    
    sys.exit(app.exec())