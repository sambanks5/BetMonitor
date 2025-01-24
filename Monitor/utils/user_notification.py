import tkinter as tk
from tkinter import ttk
from config import get_user
from utils.user_login import user_login
from utils.log_notification import log_notification

def user_notification(root):
    if not get_user():
        user_login()

    def submit():
        message = entry.get()
        message = (get_user() + ": " + message)
        log_notification(message, important=True, pinned=pin_message_var.get())
        window.destroy()

    window = tk.Toplevel(root)
    window.title("Enter Notification")
    window.iconbitmap('Monitor/splash.ico')
    window.geometry("300x170")
    screen_width = window.winfo_screenwidth()
    window.geometry(f"+{screen_width - 350}+50")

    label = ttk.Label(window, text="Enter your message:")
    label.pack(padx=5, pady=5)

    entry = ttk.Entry(window, width=50)
    entry.pack(padx=5, pady=5)
    entry.focus_set()
    entry.bind('<Return>', lambda event=None: submit())

    pin_message_var = tk.BooleanVar()
    pin_message_checkbutton = ttk.Checkbutton(window, text="Pin this message", variable=pin_message_var)
    pin_message_checkbutton.pack(padx=5, pady=5)

    button = ttk.Button(window, text="Submit", command=submit)
    button.pack(padx=5, pady=10)