import json
import os
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

load_dotenv()

# Load Configuration
CLIENT_ID = os.getenv('YAHOO_CLIENT_ID')
CLIENT_SECRET = os.getenv('YAHOO_CLIENT_SECRET')
LEAGUE_ID = os.getenv('YAHOO_LEAGUE_ID')

# Load Token
with open('yahoo_token.json', 'r') as f:
    token = json.load(f)

# Create Session
yahoo = OAuth2Session(
    CLIENT_ID, 
    token=token,
    auto_refresh_url='https://api.login.yahoo.com/oauth2/get_token',
    auto_refresh_kwargs={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET},
    token_updater=lambda t: json.dump(t, open('yahoo_token.json', 'w'), indent=4)
)

print(f"Fetching standings for League {LEAGUE_ID}...\n")

# API Call
url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/standings?format=json'
response = yahoo.get(url)

if response.status_code == 200:
    data = response.json()
    
    # 1. Get League Name
    # 'league' is a list. Index 0 is metadata, Index 1 is the standings payload.
    league_name = data['fantasy_content']['league'][0]['name']
    
    # 2. Get the Teams Dictionary
    # 'standings' is a list. We take the first item [0], then grab ['teams'].
    teams_data = data['fantasy_content']['league'][1]['standings'][0]['teams']
    
    # 3. Get the Count
    # The count is actually inside the 'teams' dictionary, not the 'standings' list.
    count = teams_data['count']

    print(f"=== {league_name} Standings ===")
    print(f"{'Rank':<5} {'Team Name':<30} {'W-L-T':<10} {'Points':<10}")
    print("-" * 60)

    # Loop through the teams
    for i in range(count):
        # Yahoo uses string keys "0", "1", "2" for the teams
        team_wrapper = teams_data[str(i)]['team']
        
        # Team Name is in the first list element [0], index [2]
        name = team_wrapper[0][2]['name']
        
        # Stats are in the third list element [2]
        team_stats = team_wrapper[2]['team_standings']
        rank = team_stats['rank']
        
        outcome = team_stats['outcome_totals']
        record = f"{outcome['wins']}-{outcome['losses']}-{outcome['ties']}"
        
        points = team_stats['points_for']

        print(f"{rank:<5} {name:<30} {record:<10} {points:<10}")

else:
    print(f"Error {response.status_code}: {response.text}")