

import tkinter as tk
from tkinter import ttk, filedialog
import os
import shutil


####################################################################################
## GENERATE TKINTER UI
####################################################################################
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Bet Monitor Installer')
        self.geometry('500x250')

        self.iconbitmap('src/splash.ico')
        self.tk.call('source', 'src/Forest-ttk-theme-master/forest-light.tcl')
        ttk.Style().theme_use('forest-light')

        self.update_folder = 'F:\\GB Bet Monitor\\Update'
        self.local_folder = 'C:\\Users\\Public\\Documents\\betmonitor'

        self.title_frame = ttk.Frame(self)
        self.title_frame.pack(pady=10)
        self.title_label = ttk.Label(self.title_frame, text='Bet Monitor Installer', font=('Helvetica', 20))
        self.title_label.pack()

        self.update_frame = ttk.Frame(self)
        self.update_frame.pack(pady=10)
        self.update_label = ttk.Label(self.update_frame, text='Check for updates and apply if present.', font=('Helvetica', 12))
        self.update_label.pack()

        self.progress_frame = ttk.Frame(self)
        self.progress_frame.pack(pady=10)
        self.progress = ttk.Progressbar(self.progress_frame, orient='horizontal', length=400, mode='determinate')
        self.progress.pack()

        self.check_for_updates_button = ttk.Button(self, text='Check for Updates', command=self.check_for_updates)
        self.check_for_updates_button.pack(pady=10)

        self.update_button = ttk.Button(self, text='Update', command=self.update)
        self.update_button.pack(pady=10)
        self.update_button.config(state='disabled')

        # Add menu and menu option to change update folder
        self.menu = tk.Menu(self)
        self.config(menu=self.menu)
        self.menu.add_command(label='Change Update Folder', command=self.change_update_folder)

    def update(self):
        self.update_label.config(text='Updating...')
        self.progress.start(10)

        try:
            # Ensure local folder exists
            if not os.path.exists(self.local_folder):
                os.makedirs(self.local_folder)

            # Copy BetMonitorBETA.exe to local folder
            beta_exe_path = os.path.join(self.update_folder, 'BetMonitorBETA.exe')
            local_exe_path = os.path.join(self.local_folder, 'BetMonitor.exe')
            shutil.copy(beta_exe_path, local_exe_path)

            # Check for presence of _internal and src folders
            folders_to_check = ['_internal', 'src']
            total_files = 0

            for folder in folders_to_check:
                local_folder_path = os.path.join(self.local_folder, folder)
                update_folder_path = os.path.join(self.update_folder, folder)

                if not os.path.exists(local_folder_path):
                    # Count total files to copy
                    for root, dirs, files in os.walk(update_folder_path):
                        total_files += len(files)

            # Set progress bar maximum value
            self.progress.config(maximum=total_files)

            # Copy missing folders and track progress
            for folder in folders_to_check:
                local_folder_path = os.path.join(self.local_folder, folder)
                update_folder_path = os.path.join(self.update_folder, folder)

                if not os.path.exists(local_folder_path):
                    self.copy_tree_with_progress(update_folder_path, local_folder_path)

            self.update_label.config(text='Update completed successfully.')
        except Exception as e:
            self.update_label.config(text=f'Error: {e}')
            print(e)
        finally:
            self.progress.stop()

    def copy_tree_with_progress(self, src, dst):
        if not os.path.exists(dst):
            os.makedirs(dst)
        for root, dirs, files in os.walk(src):
            for dir in dirs:
                os.makedirs(os.path.join(dst, os.path.relpath(os.path.join(root, dir), src)), exist_ok=True)
            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(dst, os.path.relpath(src_file, src))
                shutil.copy2(src_file, dst_file)
                self.progress.step(1)
                self.update_idletasks()

    def change_update_folder(self):
        self.update_folder = filedialog.askdirectory()
        print(self.update_folder)

    def check_for_updates(self):
        self.update_label.config(text='Checking for updates...')
        self.progress.start(10)

        try:
            if os.path.exists(self.update_folder):
                beta_file_location = os.path.join(self.update_folder, 'BetMonitorBETA.exe')
                if os.path.exists(beta_file_location):
                    self.update_label.config(text='Update available. Click Update to install.')
                    self.update_button.config(state='normal')
                else:
                    self.update_label.config(text='No updates available.')
            else:
                self.update_label.config(text='Update folder not found. Please check the folder path.')
        except Exception as e:
            self.update_label.config(text=f'Error: {e}')
        finally:
            self.progress.stop()

def main():
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()