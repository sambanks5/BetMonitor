from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QMessageBox, QLabel, QLineEdit, QComboBox, QVBoxLayout

def on_button_click():
    QMessageBox.information(None, "Info", "Button clicked!")

app = QApplication([])

window = QWidget()
window.setWindowTitle("PyQt Enhanced Example")

# Create layout
layout = QVBoxLayout()

# Add a label
label = QLabel("Enter your name:")
layout.addWidget(label)

# Add a line edit
line_edit = QLineEdit()
layout.addWidget(line_edit)

# Add a combo box
combo_box = QComboBox()
combo_box.addItems(["Option 1", "Option 2", "Option 3"])
layout.addWidget(combo_box)

# Add a button
button = QPushButton("Click Me")
button.clicked.connect(on_button_click)
layout.addWidget(button)

# Set the layout for the window
window.setLayout(layout)

window.resize(300, 200)
window.show()

app.exec_()