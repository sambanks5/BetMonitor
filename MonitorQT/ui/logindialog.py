from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                              QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from utils import user

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        self.setFixedSize(300, 150)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        
        layout = QVBoxLayout()
        
        # Logo or welcome message
        self.welcome_label = QLabel("Welcome to Bet Monitor")
        self.welcome_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.welcome_label)
        
        # Instructions
        self.instructions = QLabel("Please enter your initials:")
        layout.addWidget(self.instructions)
        
        # Input field
        self.initials_input = QLineEdit()
        self.initials_input.setMaxLength(2)
        layout.addWidget(self.initials_input)
        
        # Login button
        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.attempt_login)
        layout.addWidget(self.login_button)
        
        self.setLayout(layout)
        
    def attempt_login(self):
        initials = self.initials_input.text().upper()
        if not initials:
            QMessageBox.warning(self, "Error", "Please enter your initials.")
            return
            
        if len(initials) > 2:
            QMessageBox.warning(self, "Error", "Maximum 2 characters allowed.")
            return
            
        if initials in user.USER_NAMES:
            user.set_user(initials)
            self.accept()  # Close dialog with success
        else:
            QMessageBox.warning(self, "Error", "Could not find staff member! Please try again.")