import os
import threading
import json
import requests
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox
from tkinter import ttk
from utils import notification, login, user
from config import NETWORK_PATH_PREFIX

class RaceUpdaton:
    def __init__(self, root):
        self.root = root
        self.current_page = 0
        self.courses_per_page = 6
        self.initialize_ui()
        self.display_courses_periodic()
        threading.Thread(target=self.get_courses, daemon=True).start()
    
    def initialize_ui(self):
        self.race_updation_frame = ttk.LabelFrame(self.root, style='Card', text="Race Updation")
        self.race_updation_frame.place(x=5, y=647, width=227, height=273)

    def display_courses_periodic(self):
        self.display_courses()
        self.root.after(15000, self.display_courses_periodic)

    def get_courses(self):
        today = date.today()
        self.courses = set()
        self.dog_courses = set()
        self.others_courses = set()
        api_data = []
        dogs_api_data = []
        others_api_data = []

        try:
            url = os.getenv('GET_COURSES_HORSES_API_URL')
            if not url:
                raise ValueError("GET_COURSES_HORSES_API_URL environment variable is not set")
            response = requests.get(url)
            response.raise_for_status()
            api_data = response.json()
        except requests.RequestException as e:
            print("Error fetching data from GB API for Courses.")
        except json.JSONDecodeError:
            print("Error decoding JSON from GB API response.")

        if api_data:
            for event in api_data:
                for meeting in event['meetings']:
                    self.courses.add(meeting['meetinName'])

        try:
            url = os.getenv('DOGS_API_URL')
            if not url:
                raise ValueError("DOGS_API_URL environment variable is not set")
            dogs_response = requests.get(url)
            dogs_response.raise_for_status()
            dogs_api_data = dogs_response.json()
        except requests.RequestException as e:
            print("Error fetching data from GB API for Dogs.")
        except json.JSONDecodeError:
            print("Error decoding JSON from GB API response.")

        if dogs_api_data:
            for event in dogs_api_data:
                if ' AUS ' not in event['eventName']:
                    for meeting in event['meetings']:
                        meeting_name = meeting['meetinName']
                        if not meeting_name.endswith(' Dg'):
                            meeting_name += ' Dg'
                        self.dog_courses.add(meeting_name)

        try:
            url = os.getenv('OTHERS_API_URL')
            if not url:
                raise ValueError("OTHERS_API_URL environment variable is not set")
            others_response = requests.get(url)
            others_response.raise_for_status()
            others_api_data = others_response.json()
        except requests.RequestException as e:
            print("Error fetching data from GB API for International Courses.")
        except json.JSONDecodeError:
            print("Error decoding JSON from GB API response.")

        if others_api_data:
            for event in others_api_data:
                for meeting in event['meetings']:
                    self.others_courses.add(meeting['meetinName'])

        self.courses = list(self.courses)
        print("Courses:", self.courses)

        update_times_path = os.path.join(NETWORK_PATH_PREFIX, 'update_times.json')

        try:
            with open(update_times_path, 'r') as f:
                update_data = json.load(f)
        except FileNotFoundError:
            update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {}}
            with open(update_times_path, 'w') as f:
                json.dump(update_data, f)

        if update_data['date'] != today.strftime('%Y-%m-%d'):
            update_data = {'date': today.strftime('%Y-%m-%d'), 'courses': {course: "" for course in self.courses}}
            with open(update_times_path, 'w') as f:
                json.dump(update_data, f)

        self.display_courses()
        return self.courses

    def display_courses(self):
        update_times_path = os.path.join(NETWORK_PATH_PREFIX, 'update_times.json')
        
        with open(update_times_path, 'r') as f:
            data = json.load(f)
    
        courses = list(data['courses'].keys())
        courses.sort(key=lambda x: (x.endswith(" Dg"), x))
    
        start = self.current_page * self.courses_per_page
        end = start + self.courses_per_page
        courses_page = courses[start:end]
    
        for widget in self.race_updation_frame.winfo_children():
            widget.destroy()
        
        button_frame = ttk.Frame(self.race_updation_frame)
        button_frame.grid(row=len(courses_page), column=0, padx=2, sticky='ew')
        
        add_button = ttk.Button(button_frame, text="+", command=self.add_course, width=2, cursor="hand2")
        add_button.pack(side='left')
        
        update_indicator = ttk.Label(button_frame, text="", foreground='red', font=("Helvetica", 12))
        update_indicator.pack(side='left', padx=2, expand=True)
        
        remove_button = ttk.Button(button_frame, text="-", command=self.remove_course, width=2, cursor="hand2")
        remove_button.pack(side='right')
        
        for i, course in enumerate(courses_page):
            course_button = ttk.Button(self.race_updation_frame, text=course, command=lambda course=course: self.update_course(course), width=15, cursor="hand2")
            course_button.grid(row=i, column=0, padx=5, pady=2, sticky="w")
        
            if course in data['courses'] and data['courses'][course]:
                last_updated_time = data['courses'][course].split(' ')[0]
                last_updated = datetime.strptime(last_updated_time, '%H:%M').time()
            else:
                last_updated = datetime.now().time()
        
            now = datetime.now().time()
        
            time_diff = (datetime.combine(date.today(), now) - datetime.combine(date.today(), last_updated)).total_seconds() / 60
        
            if course.endswith(" Dg"):
                if 60 <= time_diff < 90:
                    color = 'Orange'
                elif time_diff >= 90:
                    color = 'red'
                else:
                    color = 'black'
            else:
                if 25 <= time_diff < 35:
                    color = 'Orange'
                elif time_diff >= 35:
                    color = 'red'
                else:
                    color = 'black'
        
            if course in data['courses'] and data['courses'][course]:
                time_text = data['courses'][course]
            else:
                time_text = "Not updated"
        
            time_label = ttk.Label(self.race_updation_frame, text=time_text, foreground=color)
            time_label.grid(row=i, column=1, padx=5, pady=2, sticky="w")
        
        navigation_frame = ttk.Frame(self.race_updation_frame)
        navigation_frame.grid(row=len(courses_page), column=1, padx=2, pady=2, sticky='ew')
        
        back_button = ttk.Button(navigation_frame, text="<", command=self.back, width=2, cursor="hand2")
        back_button.grid(row=0, column=0, padx=2, pady=2)
        
        forward_button = ttk.Button(navigation_frame, text=">", command=self.forward, width=2, cursor="hand2")
        forward_button.grid(row=0, column=1, padx=2, pady=2)
        
        other_courses = [course for i, course in enumerate(courses) if i < start or i >= end]
        courses_needing_update = [course for course in other_courses if self.course_needs_update(course, data)]
        
        if courses_needing_update:
            update_indicator.config(text=str(len(courses_needing_update)))
            update_indicator.pack()
        else:
            update_indicator.pack_forget()
        
        if self.current_page == 0:
            back_button.config(state='disabled')
        else:
            back_button.config(state='normal')
        
        if self.current_page == len(courses) // self.courses_per_page:
            forward_button.config(state='disabled')
        else:
            forward_button.config(state='normal')

    def reset_update_times(self):
        update_times_path = os.path.join(NETWORK_PATH_PREFIX, 'update_times.json')
        
        if os.path.exists(update_times_path):
            os.remove(update_times_path)

        update_data = {'date': '', 'courses': {}}
        with open(update_times_path, 'w') as f:
            json.dump(update_data, f)
        
        self.display_courses()

    def course_needs_update(self, course, data):
        if course in data['courses'] and data['courses'][course]:
            last_updated_time = data['courses'][course].split(' ')[0]
            last_updated = datetime.strptime(last_updated_time, '%H:%M').time()
        else:
            last_updated = datetime.now().time()

        now = datetime.now().time()

        time_diff = (datetime.combine(date.today(), now) - datetime.combine(date.today(), last_updated)).total_seconds() / 60

        if course.endswith(" Dg"):
            return time_diff >= 60
        else:
            return time_diff >= 25

    def log_update(self, course, time, _user, last_update_time):
        now = datetime.now()
        date_string = now.strftime('%d-%m-%Y')
        log_file = os.path.join(NETWORK_PATH_PREFIX, 'logs', 'updatelogs', f'update_log_{date_string}.txt')
        score = 0.0

        search_course = course.replace(' Dg', '')

        try:
            if course.endswith(" Dg"):
                url = os.getenv('DOGS_API_URL')
            else:
                url = os.getenv('HORSES_API_URL')

            if not url:
                raise ValueError("API URL environment variable is not set")

            response = requests.get(url)
            response.raise_for_status()
            api_data = response.json()
        except requests.RequestException as e:
            print(f"Error fetching data from API: {e}")
            messagebox.showerror("Error", f"Failed to fetch courses data from API. You will be allocated 0.1 score for this update.")
            score = 0.1
            api_data = None
        except json.JSONDecodeError:
            print("Error decoding JSON from API response.")
            messagebox.showerror("Error", f"Failed to decode JSON from API response. You will be allocated 0.1 score for this update.")
            score = 0.1
            api_data = None
    
        try:
            if api_data:
                today = now.strftime('%A')
                tomorrow = (now + timedelta(days=1)).strftime('%A')
                morning_finished = False
    
                if course.endswith(" Dg"):
                    for event in api_data:
                        if today in event['eventName']:
                            for meeting in event['meetings']:
                                if search_course == meeting['meetinName'] or course == meeting['meetinName']:
                                    all_results = all(race['status'] == 'Result' for race in meeting['events'])
                                    if all_results:
                                        morning_finished = True
                                    else:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.1
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                    break
                            if morning_finished:
                                break
    
                    if morning_finished:
                        for event in api_data:
                            if today in event['eventName']:
                                for meeting in event['meetings']:
                                    if search_course + '1' == meeting['meetinName']:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.1
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                        break
    
                else:
                    print("Horse Race")
                    for event in api_data:
                        if today in event['eventName']:
                            for meeting in event['meetings']:
                                if search_course == meeting['meetinName']:
                                    all_results = all(race['status'] == 'Result' for race in meeting['events'])
                                    if all_results:
                                        morning_finished = True
                                    else:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.2
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                    break
                            if morning_finished:
                                print("breaking")
                                break
    
                    if morning_finished:
                        for event in api_data:
                            if tomorrow in event['eventName']:
                                for meeting in event['meetings']:
                                    if search_course == meeting['meetinName']:
                                        for race in meeting['events']:
                                            if race['status'] == '':
                                                score += 0.2
                                        if score == 0.0:
                                            messagebox.showerror("Error", f"Course {course} not found or meeting has finished. You will be allocated 0.2 base score for this update.\n")
                                            score = 0.2
                                        break
    
            surge_start = datetime.strptime('13:00', '%H:%M').time()
            surge_end = datetime.strptime('16:00', '%H:%M').time()
            if surge_start <= now.time() <= surge_end:
                score += 0.1
    
            score = round(score, 2)
            print(f"Score: {score}")
    
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        data = f.readlines()
                except IOError as e:
                    print(f"Error reading log file: {e}")
                    data = []
            else:
                data = []
    
            if last_update_time:
                last_updated = last_update_time.time()
                now_time = now.time()
                time_diff = (datetime.combine(date.today(), now_time) - datetime.combine(date.today(), last_updated)).total_seconds() / 60
                print(f"Time difference: {time_diff}")
                if time_diff < 10:
                    score *= 0.7
    
            update = f"{time} - {_user} - {score:.2f}\n"
            notification.log_notification(f"{_user} updated {course} ({score:.2f})")
    
            course_index = None
            for i, line in enumerate(data):
                if line.strip() == course + ":":
                    course_index = i
                    break
    
            if course_index is not None:
                data.insert(course_index + 1, update)
            else:
                data.append(f"\n{course}:\n")
                data.append(update)
    
            try:
                with open(log_file, 'w') as f:
                    f.writelines(data)
                print(f"Log updated for {course}")
            except IOError as e:
                print(f"Error writing to log file: {e}")
    
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def update_course(self, course):
        if not user.get_user():
            login.user_login()
    
        now = datetime.now()
        time_string = now.strftime('%H:%M')
    
        with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
            data = json.load(f)
    
        last_update_time = data['courses'].get(course, None)
        if last_update_time and last_update_time != "Not updated":
            last_update_time = last_update_time.split(' ')[0]
            try:
                last_update_time = datetime.strptime(last_update_time, '%H:%M')
            except ValueError:
                last_update_time = None
        else:
            last_update_time = None
    
        data['courses'][course] = f"{time_string} - {user.get_user()}"
        with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'w') as f:
            json.dump(data, f)
    
        threading.Thread(target=self.log_update, args=(course, time_string, user.get_user(), last_update_time), daemon=True).start()
        self.display_courses()

    def remove_course(self):
        def fetch_courses():
            with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                data = json.load(f)
    
            courses = [course for course in data['courses']]
    
            combobox['values'] = courses
            combobox.set('')
            loading_bar.stop()
            loading_bar.pack_forget()
            select_button.pack(pady=10)
    
        def on_select():
            selected_course = combobox.get()
            if selected_course:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                    data = json.load(f)

                del data['courses'][selected_course]
    
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'w') as f:
                    json.dump(data, f)
    
                notification.log_notification(f"'{selected_course}' removed by {user.get_user()}")
    
                self.display_courses()
                top.destroy()

        top = tk.Toplevel(self.root)
        top.title("Remove Course")
        top.geometry("300x120")
        top.iconbitmap('Monitor/splash.ico')
        screen_width = top.winfo_screenwidth()
        top.geometry(f"+{screen_width - 400}+200")

        combobox = ttk.Combobox(top, state='readonly')
        combobox.pack(fill=tk.BOTH, padx=10, pady=10)
    
        loading_bar = ttk.Progressbar(top, mode='indeterminate')
        loading_bar.pack(fill=tk.BOTH, padx=10, pady=10)
        loading_bar.start()
    
        select_button = ttk.Button(top, text="Select", command=on_select)
        select_button.pack_forget() 
    
        threading.Thread(target=fetch_courses, daemon=True).start()

    def add_course(self):
        def fetch_courses():
            self.get_courses()
    
            all_courses = sorted(set(self.courses) | self.dog_courses | self.others_courses)
            with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                data = json.load(f)
    
            all_courses = [course for course in all_courses if course not in data['courses']]
    
            combobox['values'] = all_courses
            combobox.set('')
            loading_bar.stop()
            loading_bar.pack_forget()
            select_button.pack(pady=10)
    
        def on_select():
            selected_course = combobox.get()
            if selected_course:
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
                    data = json.load(f)
    
                data['courses'][selected_course] = ""
    
                with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'w') as f:
                    json.dump(data, f)
    
                notification.log_notification(f"'{selected_course}' added by {user.get_user()}")
    
                self.display_courses()
                top.destroy()
    
        top = tk.Toplevel(self.root)
        top.title("Add Course")
        top.geometry("300x120")
        top.iconbitmap('Monitor/splash.ico')
        screen_width = top.winfo_screenwidth()
        top.geometry(f"+{screen_width - 400}+200")
    
        combobox = ttk.Combobox(top, state='readonly')
        combobox.pack(fill=tk.BOTH, padx=10, pady=10)
    
        loading_bar = ttk.Progressbar(top, mode='indeterminate')
        loading_bar.pack(fill=tk.BOTH, padx=10, pady=10)
        loading_bar.start()
    
        select_button = ttk.Button(top, text="Select", command=on_select)
        select_button.pack_forget()  
    
        threading.Thread(target=fetch_courses, daemon=True).start()

    def back(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_courses()

    def forward(self):
        with open(os.path.join(NETWORK_PATH_PREFIX, 'update_times.json'), 'r') as f:
            data = json.load(f)
        total_courses = len(data['courses'].keys())
        if (self.current_page + 1) * self.courses_per_page < total_courses:
            self.current_page += 1
            self.display_courses()
