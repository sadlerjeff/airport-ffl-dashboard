import os
import json
import time
import streamlit as st
import pandas as pd
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv('YAHOO_CLIENT_ID')
CLIENT_SECRET = os.getenv('YAHOO_CLIENT_SECRET')
LEAGUE_ID = os.getenv('YAHOO_LEAGUE_ID')

def get_yahoo_session():
    token = None
    try:
        if "yahoo_token" in st.secrets:
            token = json.loads(st.secrets["yahoo_token"]["token_json"])
    except Exception:
        pass
    if not token and os.path.exists('yahoo_token.json'):
        with open('yahoo_token.json', 'r') as f:
            token = json.load(f)
    if not token:
        st.error("No token found! Please run 'python scripts/auth.py'")
        return None

    def token_updater(new_token):
        if os.path.exists('yahoo_token.json'):
            with open('yahoo_token.json', 'w') as f:
                json.dump(new_token, f)

    extra = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
    return OAuth2Session(CLIENT_ID, token=token, auto_refresh_url='https://api.login.yahoo.com/oauth2/get_token', auto_refresh_kwargs=extra, token_updater=token_updater)

def fetch_standings():
    yahoo = get_yahoo_session()
    if not yahoo: return []
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/standings?format=json'
    try:
        response = yahoo.get(url)
        if response.status_code != 200: return []
        data = response.json()
        league_data = data.get('fantasy_content', {}).get('league', [])
        if len(league_data) < 2: return []
        teams_data = league_data[1].get('standings', [])[0].get('teams', {})
        count = teams_data.get('count', 0)
        parsed_teams = []
        for i in range(count):
            team_wrapper = teams_data.get(str(i), {}).get('team', [])
            name, logo = "Unknown", ""
            if len(team_wrapper) > 0:
                for item in team_wrapper[0]:
                    if isinstance(item, dict):
                        if 'name' in item: name = item['name']
                        if 'team_logos' in item: logo = item['team_logos'][0].get('url', '')
            stats = team_wrapper[2].get('team_standings', {}) if len(team_wrapper) > 2 else {}
            try: rank = int(stats.get('rank', 0))
            except: rank = 0
            outcome = stats.get('outcome_totals', {})
            parsed_teams.append({
                "Rank": rank, "Team": name, 
                "W": int(outcome.get('wins', 0)), "L": int(outcome.get('losses', 0)), "T": int(outcome.get('ties', 0)),
                "PF": float(stats.get('points_for', 0)), "PA": float(stats.get('points_against', 0)), "Logo": logo
            })
        return parsed_teams
    except Exception: return []

@st.cache_data(ttl=3600)
def fetch_all_weekly_scores(current_week):
    yahoo = get_yahoo_session()
    if not yahoo: return []
    all_matchups = []
    for week in range(1, current_week + 1):
        url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/scoreboard;week={week}?format=json'
        try:
            r = yahoo.get(url)
            if r.status_code == 200:
                data = r.json()
                matchups = data['fantasy_content']['league'][1]['scoreboard']['0']['matchups']
                for i in range(matchups['count']):
                    m = matchups[str(i)]['matchup']['0']['teams']
                    t0, t1 = m['0']['team'], m['1']['team']
                    s0, n0 = float(t0[1]['team_points']['total']), t0[0][2]['name']
                    s1, n1 = float(t1[1]['team_points']['total']), t1[0][2]['name']
                    all_matchups.append({'Week': week, 'Team': n0, 'Score': s0, 'Opponent': n1, 'Opponent Score': s1, 'Result': 'W' if s0>s1 else 'L' if s0<s1 else 'T'})
                    all_matchups.append({'Week': week, 'Team': n1, 'Score': s1, 'Opponent': n0, 'Opponent Score': s0, 'Result': 'W' if s1>s0 else 'L' if s1<s0 else 'T'})
        except: continue
    return all_matchups

def get_current_week():
    yahoo = get_yahoo_session()
    if not yahoo: return 1
    try:
        url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}?format=json'
        return int(yahoo.get(url).json()['fantasy_content']['league'][0]['current_week'])
    except: return 1

def find_key_recursive(data, target_key):
    if isinstance(data, dict):
        if target_key in data: return data[target_key]
        for key, value in data.items():
            result = find_key_recursive(value, target_key)
            if result is not None: return result
    elif isinstance(data, list):
        for item in data:
            result = find_key_recursive(item, target_key)
            if result is not None: return result
    return None

# --- MANAGER EFFICIENCY ---
@st.cache_data(ttl=3600) 
def fetch_manager_efficiency(current_week, team_list):
    yahoo = get_yahoo_session()
    if not yahoo: return []
    efficiency_data = []
    url_keys = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/teams?format=json'
    try:
        r = yahoo.get(url_keys)
        if r.status_code != 200: return []
        team_map = {} 
        teams_data = r.json()['fantasy_content']['league'][1]['teams']
        for i in range(teams_data['count']):
            t = teams_data[str(i)]['team']
            team_map[t[0][0]['team_key']] = t[0][2]['name']
    except Exception: return []

    my_bar = st.progress(0, text="Calculating Best Lineups...")
    total_steps = (current_week) * len(team_map)
    step_count = 0

    for week in range(1, current_week + 1):
        for team_key, team_name in team_map.items():
            step_count += 1
            my_bar.progress(min(step_count / total_steps, 0.99), text=f"Analyzing Week {week}: {team_name}")
            time.sleep(0.05) 
            url_roster = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{team_key}/roster;week={week}/players/stats?format=json'
            try:
                rr = yahoo.get(url_roster)
                if rr.status_code != 200: continue
                roster = rr.json()['fantasy_content']['team'][1]['roster']['0']['players']
                players = []
                for idx in range(roster['count']):
                    p_data = roster[str(idx)]['player']
                    points_obj = find_key_recursive(p_data, 'player_points')
                    points = float(points_obj['total']) if points_obj else 0.0
                    position = "BN"
                    if isinstance(p_data, list) and len(p_data) > 0:
                        position = find_key_recursive(p_data[0], 'display_position')
                        if not position: position = "BN"
                    players.append({'pos': position, 'points': points})
                players.sort(key=lambda x: x['points'], reverse=True)
                used_indices = set()
                def pick_best(pos_list, count):
                    picked = 0
                    score = 0
                    for i, p in enumerate(players):
                        if i in used_indices: continue
                        if picked >= count: break
                        if p['pos'] in pos_list:
                            score += p['points']
                            used_indices.add(i)
                            picked += 1
                    return score
                max_pts = 0
                max_pts += pick_best(['QB'], 1)
                max_pts += pick_best(['WR'], 3)
                max_pts += pick_best(['RB'], 2)
                max_pts += pick_best(['TE'], 1)
                max_pts += pick_best(['K'], 1)
                max_pts += pick_best(['DEF'], 1)
                if max_pts > 0: efficiency_data.append({'Week': week, 'Team': team_name, 'Max Points': max_pts})
            except Exception: continue
    my_bar.empty()
    return efficiency_data

# --- DRAFT ANALYSIS ---
@st.cache_data(ttl=3600)
def fetch_draft_results():
    yahoo = get_yahoo_session()
    if not yahoo: return {}
    url = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/draftresults?format=json'
    try:
        r = yahoo.get(url)
        if r.status_code != 200: return {}
        data = r.json()
        draft_results = data['fantasy_content']['league'][1]['draft_results']
        draft_map = {}
        for i in range(draft_results['count']):
            res = draft_results[str(i)]['draft_result']
            draft_map[res['player_key']] = {
                'round': res['round'],
                'pick': res['pick'],
                'team_key': res['team_key']
            }
        return draft_map
    except Exception: return {}

# --- IMPACT ANALYSIS (WAR: Wins Above Bench) ---
@st.cache_data(ttl=3600)
def fetch_impact_analysis(current_week):
    yahoo = get_yahoo_session()
    if not yahoo: return []
    
    # 1. Fetch Matchup Context
    matchups_data = fetch_all_weekly_scores(current_week)
    matchup_map = {} 
    for m in matchups_data:
        team = m['Team']
        week = m['Week']
        if team not in matchup_map: matchup_map[team] = {}
        matchup_map[team][week] = {'Result': m['Result'], 'Margin': m['Score'] - m['Opponent Score']}

    # 2. Get Teams
    url_teams = f'https://fantasysports.yahooapis.com/fantasy/v2/league/{LEAGUE_ID}/teams?format=json'
    team_keys = {} 
    try:
        r = yahoo.get(url_teams)
        if r.status_code == 200:
            teams_data = r.json()['fantasy_content']['league'][1]['teams']
            for i in range(teams_data['count']):
                t = teams_data[str(i)]['team']
                team_keys[t[0][0]['team_key']] = t[0][2]['name']
    except: return []

    impact_stats = {} 
    my_bar = st.progress(0, text="Calculating WAR (Wins Above Bench)...")
    total_steps = current_week * len(team_keys)
    step_count = 0

    for week in range(1, current_week + 1):
        for t_key, t_name in team_keys.items():
            step_count += 1
            my_bar.progress(min(step_count / total_steps, 0.99), text=f"Analyzing {t_name} Week {week}...")
            time.sleep(0.05) 

            # Get Roster
            url = f'https://fantasysports.yahooapis.com/fantasy/v2/team/{t_key}/roster;week={week}/players/stats?format=json'
            try:
                rr = yahoo.get(url)
                if rr.status_code != 200: continue
                roster = rr.json()['fantasy_content']['team'][1]['roster']['0']['players']
                
                starters = {} # {PlayerKey: {Data}}
                bench_by_pos = {} # {'QB': [Points, ...], 'WR': ...}
                
                # First Pass: Organize Roster
                for idx in range(roster['count']):
                    p_data = roster[str(idx)]['player']
                    p_key = p_data[0][0]['player_key']
                    
                    points_obj = find_key_recursive(p_data, 'player_points')
                    points = float(points_obj['total']) if points_obj else 0.0
                    
                    selected_pos = find_key_recursive(p_data, 'selected_position')
                    is_starter = selected_pos[1]['position'] != 'BN'
                    
                    display_pos = find_key_recursive(p_data, 'display_position')
                    
                    p_info = {
                        'key': p_key,
                        'name': p_data[0][2]['name']['full'],
                        'points': points,
                        'pos': display_pos
                    }
                    
                    if is_starter:
                        starters[p_key] = p_info
                    else:
                        if display_pos not in bench_by_pos: bench_by_pos[display_pos] = []
                        bench_by_pos[display_pos].append(points)
                        
                # Sort Bench for "Next Man Up"
                for pos in bench_by_pos:
                    bench_by_pos[pos].sort(reverse=True)
                
                # Second Pass: Calculate Impact
                game_ctx = matchup_map.get(t_name, {}).get(week, None)
                
                for p_key, p in starters.items():
                    # Initialize Stats
                    if p_key not in impact_stats:
                        impact_stats[p_key] = {
                            'Player': p['name'], 'Team': t_name, 'Player Key': p_key,
                            'Starter Points': 0.0, 'WAR': 0
                        }
                    
                    impact_stats[p_key]['Starter Points'] += p['points']
                    
                    # WAR CALCULATION
                    if game_ctx and game_ctx['Result'] == 'W':
                        # Find Replacement Points
                        rep_points = 0.0
                        if p['pos'] in bench_by_pos and bench_by_pos[p['pos']]:
                            rep_points = bench_by_pos[p['pos']][0] # Top bench scorer
                        
                        # Value Over Replacement
                        value_over_bench = p['points'] - rep_points
                        
                        # Did we need that value to cover the margin?
                        if value_over_bench > game_ctx['Margin']:
                            impact_stats[p_key]['WAR'] += 1

            except: continue
            
    my_bar.empty()
    return list(impact_stats.values())