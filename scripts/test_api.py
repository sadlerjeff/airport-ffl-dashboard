import json
import os
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv('YAHOO_CLIENT_ID')
CLIENT_SECRET = os.getenv('YAHOO_CLIENT_SECRET')

# We load the token we just saved
with open('yahoo_token.json', 'r') as f:
    token = json.load(f)

# We create a session using that token
yahoo = OAuth2Session(
    CLIENT_ID, 
    token=token,
    auto_refresh_url='https://api.login.yahoo.com/oauth2/get_token',
    auto_refresh_kwargs={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET},
    token_updater=lambda t: json.dump(t, open('yahoo_token.json', 'w'), indent=4)
)

print("Fetching Fantasy Football Game Key...")

# API Call: Get the Game Key for NFL (code 'nfl')
# This is usually the first thing you need to query your leagues.
response = yahoo.get('https://fantasysports.yahooapis.com/fantasy/v2/game/nfl?format=json')

if response.status_code == 200:
    data = response.json()
    game_key = data['fantasy_content']['game'][0]['game_key']
    season = data['fantasy_content']['game'][0]['season']
    print(f"SUCCESS! Connection established.")
    print(f"Current Season: {season}")
    print(f"Game Key: {game_key}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)