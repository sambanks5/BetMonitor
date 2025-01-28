import json
import requests
import asyncio
import re
import aiohttp
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

async def fetch_game_info(session, game_id):
    game_url = f"https://www.flashscore.co.uk/match/{game_id}/#/match-summary"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    async with session.get(game_url, headers=headers) as response:
        if response.status == 200:
            game_html = await response.text()
            return extract_game_info(game_html)
        else:
            print(f"Failed to retrieve game {game_id} with status code {response.status}")
            return None

def extract_game_info(game_html):
    soup = BeautifulSoup(game_html, 'html.parser')
    
    # Find the script tag containing window.environment
    script_tag = soup.find('script', string=lambda t: t and 'window.environment' in t)
    if not script_tag:
        print("No script tag with window.environment found")
        return None
    
    # Extract the JSON data from the script tag
    script_content = script_tag.string
    json_data_start = script_content.find('{')
    json_data_end = script_content.rfind('}') + 1
    json_data_str = script_content[json_data_start:json_data_end]
    
    try:
        json_data = json.loads(json_data_str)
    except json.JSONDecodeError as e:
        print("Error decoding JSON data from script tag")
        print("Error:", e)
        return None
    
    # Extract the required information from the JSON data
    tournament_text = json_data.get('header', {}).get('tournament', {}).get('tournament', 'N/A')
    date_time_text = datetime.fromtimestamp(json_data.get('eventStageStartTime', 0)).strftime('%d.%m.%Y %H:%M')
    home_team_text = json_data.get('participantsData', {}).get('home', [{}])[0].get('name', 'N/A')
    away_team_text = json_data.get('participantsData', {}).get('away', [{}])[0].get('name', 'N/A')
    match_status_text = json_data.get('eventStageTranslations', {}).get(str(json_data.get('eventStageTypeId', '')), 'N/A')
    
    # Extract the score from the page title
    title = soup.title.string
    score_match = re.search(r'(\d+)-(\d+)', title)
    if score_match:
        home_score = int(score_match.group(1))
        away_score = int(score_match.group(2))
    else:
        home_score, away_score = 0, 0

    return {
        "tournament": tournament_text,
        "date_time": date_time_text,
        "home_team": home_team_text,
        "away_team": away_team_text,
        "status": match_status_text,
        "home_score": home_score,
        "away_score": away_score
    }

async def check_game_status(favorites):
    if not favorites:
        print("No favorites data to check.")
        return
    
    game_info_list = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for game_id, game_data in favorites['data']['mygames']['data'].items():
            game_id_corrected = game_id.split('_')[2]
            print(f"Checking game {game_id_corrected}...")
            tasks.append(fetch_game_info(session, game_id_corrected))
        
        game_info_list = await asyncio.gather(*tasks)
    
    game_info_list = [info for info in game_info_list if info is not None]
    return game_info_list

def get_favorites():
    url = "https://lsid.eu/v4/getdata"
    headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "content-type": "application/json",
        "origin": "https://www.flashscore.co.uk",
        "referer": "https://www.flashscore.co.uk/",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    payload = {
        "loggedIn": {
            "id": "5e5f5af925726a803771706a",
            "hash": "4d408b5332e126046b2b9b3297e9450dd0549e79"
        }
    }
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        try:
            return response.json()
        except json.JSONDecodeError as e:
            print("Error decoding JSON response")
            print("Response content:", response.content)
            print("Error:", e)
            return None
    else:
        print(f"Request failed with status code {response.status_code}")
        print("Response content:", response.content)
        return None

def get_data():
    favorites = get_favorites()
    if favorites:
        return asyncio.run(check_game_status(favorites))
    return None