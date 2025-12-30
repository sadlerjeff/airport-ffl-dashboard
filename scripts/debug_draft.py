import os
import json
import sys
from unittest.mock import MagicMock

# Mock streamlit before importing utils
sys.modules['streamlit'] = MagicMock()
import streamlit as st
st.secrets = {} # Mock secrets
st.cache_data = lambda ttl=None: lambda func: func # Mock cache decorator

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from utils import get_yahoo_session, LEAGUE_ID

def test_draft_fetch():
    yahoo = get_yahoo_session()
    if not yahoo:
        print("Auth failed or no token")
        return

    # 1. Draft Results
    print(f"\n--- Fetching Draft Results for League {LEAGUE_ID} ---")
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/draftresults?format=json'
    r = yahoo.get(url)
    if r.status_code == 200:
        data = r.json()
        draft_results = data['fantasy_content']['league'][1]['draft_results']
        count = draft_results['count']
        print(f"Success! Found {count} draft picks.")
        if count > 0:
            print("Sample Pick 0:")
            print(json.dumps(draft_results['0']['draft_result'], indent=2))
    else:
        print(f"Draft fetch failed: {r.status_code}")
        print(r.text)

    # 2. Roster inspection for acquisition data
    print(f"\n--- Fetching Roster for Team 1 to check keys ---")
    # Get team key for first team
    url_teams = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/teams?format=json'
    r_teams = yahoo.get(url_teams)
    if r_teams.status_code == 200:
        teams_data = r_teams.json()['fantasy_content']['league'][1]['teams']
        team_key = teams_data['0']['team'][0][0]['team_key']
        print(f"Team Key: {team_key}")
        
        url_roster = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{team_key}/roster;week=current/players/stats?format=json'
        r_roster = yahoo.get(url_roster)
        if r_roster.status_code == 200:
            # Navigate to players list
            # Structure: team -> 1 -> roster -> 0 -> players
            roster_data = r_roster.json()['fantasy_content']['team'][1]['roster']['0']['players']
            if roster_data['count'] > 0:
                print("Sample Player Data from Roster:")
                # player 0 is usually object with key 'player'
                player_entry = roster_data['0']['player']
                # flatten or dump the list
                print(json.dumps(player_entry, indent=2))
        else:
            print(f"Roster fetch failed: {r_roster.status_code}")

if __name__ == "__main__":
    test_draft_fetch()
