import json
import os
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

# Load credentials
load_dotenv()
CLIENT_ID = os.getenv('YAHOO_CLIENT_ID')
CLIENT_SECRET = os.getenv('YAHOO_CLIENT_SECRET')
LEAGUE_ID = os.getenv('YAHOO_LEAGUE_ID')

def run_debug():
    # 1. Load Token
    if not os.path.exists('yahoo_token.json'):
        print("❌ CRITICAL: No yahoo_token.json found. Run 'python scripts/auth.py' first.")
        return

    with open('yahoo_token.json') as f:
        token = json.load(f)
    
    # 2. Connect to Yahoo
    extra = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
    yahoo = OAuth2Session(CLIENT_ID, token=token, auto_refresh_url='https://api.login.yahoo.com/oauth2/get_token', auto_refresh_kwargs=extra)
    
    print("✅ Connected to Yahoo. Fetching league data...")

    # 3. Get the first team's key
    url_teams = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/teams?format=json'
    r = yahoo.get(url_teams)
    
    if r.status_code != 200:
        print(f"❌ Error fetching teams: {r.text}")
        return

    data = r.json()
    try:
        # Navigate the messy JSON to find the first team key
        first_team = data['fantasy_content']['league'][1]['teams']['0']['team']
        team_key = first_team[0][0]['team_key']
        team_name = first_team[0][2]['name']
        print(f"🎯 Target Acquired: {team_name} ({team_key})")
    except Exception as e:
        print(f"❌ Error parsing team structure: {e}")
        print(json.dumps(data, indent=2))
        return

    # 4. Get Week 1 Roster for that team
    print("🔍 Fetching Week 1 Roster...")
    url_roster = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{team_key}/roster;week=1?format=json'
    r_roster = yahoo.get(url_roster)
    roster_data = r_roster.json()

    # 5. Extract the first player
    try:
        player_list = roster_data['fantasy_content']['team'][1]['roster']['0']['players']
        first_player_data = player_list['0']['player']
        
        print("\n" + "="*40)
        print("🔥 RAW PLAYER DATA (COPY THIS) 🔥")
        print("="*40)
        print(json.dumps(first_player_data, indent=2))
        print("="*40)
        print("🔥 END DATA 🔥")
        print("="*40)
        
    except Exception as e:
        print(f"❌ Error finding player data: {e}")
        print(json.dumps(roster_data, indent=2))

if __name__ == "__main__":
    run_debug()