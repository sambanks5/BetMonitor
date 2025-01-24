import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv('ALL_API_URL')

def get_next_weekday_name():
    """
        Get the name of the next weekday.
    """
    today = datetime.now()
    next_day = today + timedelta(days=1)
    return next_day.strftime("%A")

def import_reporting():
    """
        Import racing data from the API.
    """
    print("Importing reporting data...")
    import_data = {}

    # Get the next day's weekday name
    next_weekday_name = get_next_weekday_name()

    # Get the reporting data from the API
    try:
        url = API_URL
        if not url:
            raise ValueError("Environment variable is not set")
        response = requests.get(url)
        response.raise_for_status()
        api_data = response.json()
    except requests.RequestException as e:
        print("Error fetching data from GB API for Courses.")
        return
    except json.JSONDecodeError:
        print("Error decoding JSON from GB API response.")
        return

    if api_data:
        for event in api_data:
            if next_weekday_name in event['eventName']:
                for meeting in event['meetings']:
                    meeting_name = meeting['meetinName']
                    for race in meeting['events']:
                        race_time = race['time']
                        key = f"{meeting_name}, {race_time}"
                        import_data[key] = race

    print(import_data)

import_reporting()