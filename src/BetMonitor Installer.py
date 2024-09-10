import tkinter as tk
from tkinter import ttk, filedialog
import os
import shutil
import threading
import winshell

####################################################################################
## GENERATE TKINTER UI
####################################################################################
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Bet Monitor Installer')
        self.geometry('500x350')  # Increased height to accommodate the new checkbox

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
        self.update_label = ttk.Label(self.update_frame, text='Check for updates and apply if present.\n', font=('Helvetica', 12), justify='center')
        self.update_label.pack()

        self.progress_frame = ttk.Frame(self)
        self.progress_frame.pack(pady=10)
        self.progress = ttk.Progressbar(self.progress_frame, orient='horizontal', length=400, mode='determinate')
        self.progress.pack()

        self.checkbox_frame = ttk.Frame(self)
        self.checkbox_frame.pack(pady=10)

        self.clean_reinstall_var = tk.BooleanVar()
        self.clean_reinstall_checkbox = ttk.Checkbutton(self.checkbox_frame, text='Clean Reinstall', variable=self.clean_reinstall_var)
        self.clean_reinstall_checkbox.pack(side='left', padx=10)

        self.manager_terminal_var = tk.BooleanVar()
        self.manager_terminal_checkbox = ttk.Checkbutton(self.checkbox_frame, text='Manager Terminal', variable=self.manager_terminal_var)
        self.manager_terminal_checkbox.pack(side='left', padx=10)

        self.check_for_updates_button = ttk.Button(self, text='Check for Updates', command=self.check_for_updates)
        self.check_for_updates_button.pack(pady=10)

        self.update_button = ttk.Button(self, text='Update', command=self.start_update_thread)
        self.update_button.pack(pady=10)
        self.update_button.config(state='disabled')

        # Add menu and menu option to change update folder
        self.menu = tk.Menu(self)
        self.config(menu=self.menu)
        self.menu.add_command(label='Change Update Folder', command=self.change_update_folder)

    def start_update_thread(self):
        update_thread = threading.Thread(target=self.update)
        update_thread.start()

    def update(self):
        self.update_label.config(text='Updating...\n')
        self.progress.start(10)

        # Disable buttons
        self.check_for_updates_button.config(state='disabled')
        self.update_button.config(state='disabled')

        update_successful = True  # Flag to track the success of the update process

        try:
            # Check if manager terminal is selected
            if self.manager_terminal_var.get():
                self.update_folder = 'C:\\GB Bet Monitor\\Update'
                beta_exe_filename = 'BetMonitorBETAMGR.exe'
                print(f"Manager terminal selected: Update folder changed to {self.update_folder}")
            else:
                beta_exe_filename = 'BetMonitorBETA.exe'

            # Check if clean reinstall is selected
            if self.clean_reinstall_var.get():
                print(f"Performing clean reinstall: Removing all contents in {self.local_folder}")
                if os.path.exists(self.local_folder):
                    shutil.rmtree(self.local_folder)
                os.makedirs(self.local_folder)

            # Ensure local folder exists
            if not os.path.exists(self.local_folder):
                print(f"Creating local folder: {self.local_folder}")
                os.makedirs(self.local_folder)

            # Copy BetMonitorBETA.exe or BetMonitorBETAMGR.exe to local folder
            beta_exe_path = os.path.normpath(os.path.join(self.update_folder, beta_exe_filename))
            local_exe_path = os.path.normpath(os.path.join(self.local_folder, 'BetMonitor.exe'))
            print(f"Source path: {beta_exe_path}")
            print(f"Destination path: {local_exe_path}")

            if os.path.exists(beta_exe_path):
                print(f"Copying {beta_exe_path} to {local_exe_path}")
                shutil.copy(beta_exe_path, local_exe_path)
                if os.path.exists(local_exe_path):
                    print(f"File successfully copied to {local_exe_path}")
                else:
                    print(f"Failed to copy file to {local_exe_path}")
                    update_successful = False
            else:
                print(f"Source file {beta_exe_path} does not exist")
                update_successful = False

            # Check for presence of _internal and src folders
            folders_to_check = ['_internal', 'src']
            total_files = 0

            for folder in folders_to_check:
                local_folder_path = os.path.normpath(os.path.join(self.local_folder, folder))
                update_folder_path = os.path.normpath(os.path.join(self.update_folder, folder))

                if not os.path.exists(local_folder_path) or self.clean_reinstall_var.get():
                    # Count total files to copy
                    for root, dirs, files in os.walk(update_folder_path):
                        total_files += len(files)

            # Set progress bar maximum value
            self.progress.config(maximum=total_files)
            print(f"Total files to copy: {total_files}")

            # Copy missing folders and track progress
            for folder in folders_to_check:
                local_folder_path = os.path.normpath(os.path.join(self.local_folder, folder))
                update_folder_path = os.path.normpath(os.path.join(self.update_folder, folder))

                if not os.path.exists(local_folder_path) or self.clean_reinstall_var.get():
                    print(f"Copying folder {update_folder_path} to {local_folder_path}")
                    self.copy_tree_with_progress(update_folder_path, local_folder_path)

            # Create desktop shortcut
            self.create_desktop_shortcut(local_exe_path)

        except Exception as e:
            self.update_label.config(text=f'Error: {e}')
            print(f"Error during update: {e}")
            update_successful = False
        finally:
            self.progress.stop()
            # Re-enable buttons
            self.check_for_updates_button.config(state='normal')
            self.update_button.config(state='normal')

            # Update the label based on the success of the update process
            if update_successful:
                self.update_label.config(text='Update completed successfully.')
            else:
                self.update_label.config(text='Update failed!')

    def copy_tree_with_progress(self, src, dst):
        if not os.path.exists(dst):
            os.makedirs(dst)
        for root, dirs, files in os.walk(src):
            for dir in dirs:
                dst_dir = os.path.join(dst, os.path.relpath(os.path.join(root, dir), src))
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)
            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(dst, os.path.relpath(src_file, src))
                print(f"Copying file {src_file} to {dst_file}")
                shutil.copy2(src_file, dst_file)
                self.progress.step(1)
                self.update_idletasks()

    def create_desktop_shortcut(self, target_path):
        desktop = winshell.desktop()
        shortcut_path = os.path.join(desktop, 'Bet Monitor.lnk')
        icon_path = os.path.abspath('src/splash.ico')

        if not os.path.exists(shortcut_path):
            with winshell.shortcut(shortcut_path) as shortcut:
                shortcut.path = target_path
                shortcut.working_directory = os.path.dirname(target_path)
                shortcut.icon_location = (icon_path, 0)
            print(f"Desktop shortcut created at {shortcut_path}")
        else:
            print(f"Desktop shortcut already exists at {shortcut_path}")

    def change_update_folder(self):
        self.update_folder = filedialog.askdirectory()
        print(f"Update folder changed to: {self.update_folder}")

    def check_for_updates(self):
        self.update_label.config(text='Checking for updates...')
        self.progress.start(10)
        try:
            if os.path.exists(self.update_folder):
                beta_file_location = os.path.normpath(os.path.join(self.update_folder, 'BetMonitorBETA.exe'))
                if os.path.exists(beta_file_location):
                    self.update_label.config(text='Update available. Click Update to install.\nPlease make sure any instances of Bet Monitor are closed.')
                    self.update_button.config(state='normal')
                else:
                    self.update_label.config(text='No updates available.')
            else:
                self.update_label.config(text='Update folder not found. Please check the folder path.')
        except Exception as e:
            self.update_label.config(text=f'Error: {e}')
            print(f'Error during check for updates: {e}')
        finally:
            self.progress.stop()

def main():
    app = Application()
    app.mainloop()

if __name__ == "__main__":
    main()