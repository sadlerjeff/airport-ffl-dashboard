import json
import os
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('YAHOO_CLIENT_ID')
CLIENT_SECRET = os.getenv('YAHOO_CLIENT_SECRET')
GAME_KEY = '461'  # The 2025 Season Key you just found

# Load the saved token
with open('yahoo_token.json', 'r') as f:
    token = json.load(f)

yahoo = OAuth2Session(
    CLIENT_ID, 
    token=token,
    auto_refresh_url='https://api.login.yahoo.com/oauth2/get_token',
    auto_refresh_kwargs={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET},
    token_updater=lambda t: json.dump(t, open('yahoo_token.json', 'w'), indent=4)
)

print(f"Searching for leagues in Game Key {GAME_KEY}...")

# API Call: Get the logged-in user's leagues for this game key
url = f'https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;game_keys={GAME_KEY}/leagues?format=json'
response = yahoo.get(url)

if response.status_code == 200:
    data = response.json()
    
    # Navigate through the messy JSON structure Yahoo returns
    try:
        users = data['fantasy_content']['users']
        # The '0' key holds the first user (you)
        leagues_data = users['0']['user'][1]['games']['0']['game'][1]['leagues']
        
        count = leagues_data['count']
        print(f"\nFound {count} league(s):")
        print("-" * 40)
        
        # Loop through leagues (Yahoo uses string keys '0', '1', etc.)
        for i in range(count):
            league = leagues_data[str(i)]['league'][0]
            name = league['name']
            league_key = league['league_key']
            num_teams = league['num_teams']
            print(f"Name:       {name}")
            print(f"League Key: {league_key}  <--- SAVE THIS!")
            print(f"Teams:      {num_teams}")
            print("-" * 40)
            
    except KeyError:
        print("No leagues found for this account in the 2025 season.")
        print("Are you sure you have joined a league yet?")
else:
    print(f"Error: {response.status_code}")
    print(response.text)