import os
from tkinter import simpledialog, messagebox
from config import USER_NAMES, get_user, set_user
from utils.log_notification import log_notification

def user_login():
    while True:
        user_input = simpledialog.askstring("Input", "Please enter your initials:")
        if user_input and len(user_input) <= 2:
            user_input = user_input.upper()
            if user_input in USER_NAMES:
                set_user(user_input)  # Update the user variable using the setter function
                full_name = USER_NAMES[user_input]
                log_notification(f"{user_input} logged in")
                break
            else:
                messagebox.showerror("Error", "Could not find staff member! Please try again.")
        else:
            messagebox.showerror("Error", "Maximum of 2 characters.")