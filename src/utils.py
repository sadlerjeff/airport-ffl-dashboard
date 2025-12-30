import os
import json
import streamlit as st
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv('YAHOO_CLIENT_ID')
CLIENT_SECRET = os.getenv('YAHOO_CLIENT_SECRET')
LEAGUE_ID = os.getenv('YAHOO_LEAGUE_ID')

def get_yahoo_session():
    """
    Creates and returns an authenticated Yahoo OAuth2 session.
    Prioritizes Streamlit Secrets (for Cloud), falls back to local file (for local testing).
    """
    token = None

    # 1. Try loading from Streamlit Secrets (Cloud Method)
    # We wrap this in a try/except because accessing st.secrets locally crashes if no secrets file exists
    try:
        if "yahoo_token" in st.secrets:
            token = json.loads(st.secrets["yahoo_token"]["token_json"])
    except Exception:
        # If secrets aren't found (like on your laptop), just ignore and try the file next
        pass
            
    # 2. Fallback to local file (Local Laptop Method)
    if not token and os.path.exists('yahoo_token.json'):
        with open('yahoo_token.json', 'r') as f:
            token = json.load(f)
    
    if not token:
        st.error("No token found! If running locally, run scripts/auth.py. If in cloud, check Secrets.")
        return None

    # Dummy updater for cloud (since we can't write back to secrets easily)
    token_updater = lambda t: None 

    yahoo = OAuth2Session(
        CLIENT_ID,
        token=token,
        auto_refresh_url='https://api.login.yahoo.com/oauth2/get_token',
        auto_refresh_kwargs={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET},
        token_updater=token_updater
    )
    return yahoo

def fetch_standings():
    """
    Fetches the raw standings data from Yahoo API safely.
    """
    yahoo = get_yahoo_session()
    if not yahoo:
        return []

    url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/standings?format=json'
    response = yahoo.get(url)
    
    if response.status_code != 200:
        st.error(f"API Error {response.status_code}: {response.text}")
        return []

    data = response.json()
    try:
        # Extract the list of teams
        league_data = data.get('fantasy_content', {}).get('league', [])
        if len(league_data) < 2:
            return []
            
        teams_data = league_data[1].get('standings', [])[0].get('teams', {})
        count = teams_data.get('count', 0)
        
        parsed_teams = []
        for i in range(count):
            team_wrapper = teams_data.get(str(i), {}).get('team', [])
            
            # Defaults
            name = "Unknown Team"
            logo = "https://s.yimg.com/cv/apiv2/default/nfl/nfl_1.png"
            
            # 1. Metadata Extraction
            if len(team_wrapper) > 0:
                for item in team_wrapper[0]:
                    if isinstance(item, dict):
                        if 'name' in item:
                            name = item['name']
                        if 'team_logos' in item:
                            logos = item['team_logos']
                            if isinstance(logos, list) and len(logos) > 0:
                                logo = logos[0].get('url', logo)

            # 2. Stats Extraction
            stats = {}
            if len(team_wrapper) > 2:
                 stats = team_wrapper[2].get('team_standings', {})
            
            rank = stats.get('rank', 0)
            outcome = stats.get('outcome_totals', {'wins': 0, 'losses': 0})
            
            wins = int(outcome.get('wins', 0))
            losses = int(outcome.get('losses', 0))
            points = float(stats.get('points_for', 0.0))
            
            parsed_teams.append({
                "Rank": rank,
                "Team": name,
                "W": wins,
                "L": losses,
                "Points": points,
                "Logo": logo
            })
            
        return parsed_teams
        
    except Exception as e:
        print(f"Error parsing data: {e}")
        return []

@st.cache_data(ttl=3600)
def fetch_all_weekly_scores(current_week):
    """
    Fetches scoreboard data for every week up to the current week.
    """
    yahoo = get_yahoo_session()
    if not yahoo:
        return []

    all_matchups = []
    
    # Create a progress bar in the UI
    progress_text = "Analyzing historical data..."
    my_bar = st.progress(0, text=progress_text)

    for week in range(1, current_week + 1):
        my_bar.progress(week / current_week, text=f"Fetching Week {week} data...")
        
        url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/scoreboard;week={week}?format=json'
        response = yahoo.get(url)
        
        if response.status_code == 200:
            data = response.json()
            try:
                league_data = data.get('fantasy_content', {}).get('league', [])
                scoreboard = league_data[1].get('scoreboard', {})
                matchups = scoreboard.get('0', {}).get('matchups', {})
                count = matchups.get('count', 0)

                for i in range(count):
                    matchup = matchups.get(str(i), {}).get('matchup', {})
                    teams = matchup.get('0', {}).get('teams', {})
                    
                    # Team 0
                    team0 = teams.get('0', {}).get('team', [])
                    name0 = team0[0][2]['name']
                    score0 = float(team0[1]['team_points']['total'])
                    
                    # Team 1
                    team1 = teams.get('1', {}).get('team', [])
                    name1 = team1[0][2]['name']
                    score1 = float(team1[1]['team_points']['total'])

                    all_matchups.append({'Week': week, 'Team': name0, 'Score': score0, 'Opponent': name1, 'Result': 'W' if score0 > score1 else 'L' if score0 < score1 else 'T'})
                    all_matchups.append({'Week': week, 'Team': name1, 'Score': score1, 'Opponent': name0, 'Result': 'W' if score1 > score0 else 'L' if score1 < score0 else 'T'})

            except Exception as e:
                print(f"Error parsing week {week}: {e}")
                continue
    
    my_bar.empty()
    return all_matchups

def get_current_week():
    """Fetches the current week of the NFL season."""
    yahoo = get_yahoo_session()
    if not yahoo:
        return 1
        
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}?format=json'
    try:
        response = yahoo.get(url)
        data = response.json()
        current_week = data['fantasy_content']['league'][0]['current_week']
        return int(current_week)
    except:
        return 1