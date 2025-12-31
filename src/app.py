import streamlit as st
import pandas as pd
import altair as alt
from utils import (
    fetch_standings, 
    fetch_all_weekly_scores, 
    get_current_week, 
    fetch_manager_efficiency, 
    fetch_draft_results, 
    fetch_impact_analysis, 
    fetch_projection_accuracy, 
    fetch_positional_performance, 
    fetch_draft_season_totals,
    get_yahoo_session, 
    LEAGUE_ID 
)

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Airport FFL Analytics", page_icon="🏈", layout="wide")

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏈 Menu")

# Add a manual Refresh button to the sidebar
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

page = st.sidebar.radio(
    "Go to:",
    ["🏆 Standings", "🤖 Optimal Standings", "🍀 Luck Index", "📊 Power Rankings", "💪 Positional Power", "📉 Draft Analysis", "⚔️ Rivalry", "📉 Trends", "🧠 Manager Skill", "💎 Draft & Waivers", "📈 Raw Data"]
)

st.title("🏈 Airport FFL Analytics Center")

# --- DATA LOADING (BULK) ---
status_text = st.empty()
df_standings = pd.DataFrame()
df_history = pd.DataFrame()
analyze_week = 1

try:
    with st.spinner('Crunching the numbers...'):
        # 1. Fetch Basic Standings & History
        standings_data = fetch_standings()
        df_standings = pd.DataFrame(standings_data)

        current_week = get_current_week()
        analyze_week = max(1, current_week - 1) 
        
        history_data = fetch_all_weekly_scores(analyze_week)
        df_history = pd.DataFrame(history_data)

        # CRITICAL CHECK: If main data is empty, stop here and ask for retry
        if df_history.empty or df_standings.empty:
            st.warning("⚠️ League data could not be loaded. This often happens if the Yahoo token is expired or the API connection failed.")
            if st.button("Retry Connection"):
                st.cache_data.clear()
                st.rerun()
        else:
            # 2. Manager Efficiency
            if 'efficiency_data' not in st.session_state:
                status_text.text("Analyzing Manager Decisions...")
                st.session_state.efficiency_data = fetch_manager_efficiency(analyze_week, df_history['Team'].unique())
            
            # 3. Positional Power
            if 'pos_data' not in st.session_state:
                status_text.text("Calculating Positional Strength...")
                st.session_state.pos_data = fetch_positional_performance(analyze_week)

            # 4. Draft Analysis (Auto-Load)
            if 'draft_scatter' not in st.session_state:
                status_text.text("Evaluating Draft Class...")
                draft_res = fetch_draft_results()
                st.session_state.draft_scatter = fetch_draft_season_totals(draft_res)
            
            # 5. Impact Analysis (WAR) (Auto-Load)
            if 'impact_data' not in st.session_state:
                status_text.text("Calculating Wins Above Replacement (WAR)...")
                draft = fetch_draft_results() 
                impact = fetch_impact_analysis(analyze_week)
                d_gems, w_gems = [], []
                if impact:
                    for p in impact:
                        if p['Player Key'] in draft: 
                            p.update(draft[p['Player Key']]); d_gems.append(p)
                        else: w_gems.append(p)
                st.session_state.impact_data = {'draft': d_gems, 'waiver': w_gems}

except Exception as e:
    st.error(f"An error occurred during data loading: {e}")

status_text.empty() # Clear loading text


# =========================================================
# PAGE 1: STANDINGS
# =========================================================
if page == "🏆 Standings":
    st.header("🏆 Official League Standings")
    st.info("**Current official standings from Yahoo.** Rank is determined by Win/Loss record, with Total Points For (PF) acting as the tiebreaker.")
    if not df_standings.empty:
        df_standings['Rank'] = pd.to_numeric(df_standings['Rank'], errors='coerce').fillna(100).astype(int)
        st.dataframe(df_standings.sort_values('Rank')[['Rank', 'Team', 'W', 'L', 'T', 'PF', 'PA']], use_container_width=True, hide_index=True)
    else:
        st.write("No standings data available.")

# =========================================================
# PAGE 2: OPTIMAL STANDINGS
# =========================================================
elif page == "🤖 Optimal Standings":
    st.header("🤖 Optimal Standings (What If?)")
    st.markdown("""
    **The Ultimate 'What If' Scenario:**
    This simulation answers: *"What if EVERY manager played their Perfect Lineup every single week?"*
    * **Fair Comparison:** We re-simulate the entire schedule assuming **BOTH** you and your opponent played your optimal lineups.
    * **Negative Wins:** If your 'Optimal Wins' is lower than your Actual Wins, it means you got lucky and beat opponents who made mistakes!
    """)
    
    # Use cached data
    if 'efficiency_data' in st.session_state and st.session_state.efficiency_data:
        df_eff = pd.DataFrame(st.session_state.efficiency_data)
        
        if not df_eff.empty and not df_history.empty:
            # Merge Schedule with Max Points
            schedule = df_history[['Week', 'Team', 'Opponent']].drop_duplicates()
            
            # 1. Get My Max Points
            sim_data = pd.merge(schedule, df_eff[['Week', 'Team', 'Max Points']], on=['Week', 'Team'], how='left')
            # 2. Get Opponent's Max Points
            sim_data = pd.merge(sim_data, df_eff[['Week', 'Team', 'Max Points']], left_on=['Week', 'Opponent'], right_on=['Week', 'Team'], suffixes=('', '_Opp'), how='left')
            
            # 3. Calculate Hypothetical Result
            sim_data['Optimal Win'] = sim_data['Max Points'] > sim_data['Max Points_Opp']
            
            # 4. Aggregate Season Totals
            optimal_standings = sim_data.groupby('Team').agg(
                Optimal_Wins=('Optimal Win', 'sum'),
                Potential_PF=('Max Points', 'sum')
            ).reset_index()
            
            # 5. Merge with Actual Standings for comparison
            final_comp = pd.merge(optimal_standings, df_standings[['Team', 'W', 'Rank']], on='Team')
            final_comp['Diff'] = final_comp['Optimal_Wins'] - final_comp['W']
            
            st.dataframe(
                final_comp.sort_values('Optimal_Wins', ascending=False),
                column_config={
                    "Optimal_Wins": st.column_config.NumberColumn("Optimal Wins", format="%d"),
                    "W": st.column_config.NumberColumn("Actual Wins", format="%d"),
                    "Diff": st.column_config.NumberColumn("Luck Factor (Wins)", format="%+d", help="Negative means you won games you 'should' have lost (Good Luck). Positive means you lost games you could have won (Bad Management/Luck)."),
                    "Potential_PF": st.column_config.NumberColumn("Max Potential PF", format="%.1f")
                },
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning("Could not calculate optimal standings. Ensure data is loaded correctly.")

# =========================================================
# PAGE 3: LUCK INDEX
# =========================================================
elif page == "🍀 Luck Index":
    st.header(f"The Luck Index (Weeks 1-{analyze_week})")
    st.info("**Are you good, or just lucky?** This calculates your **'All-Play' record**—simulating what your record would be if you played every single team, every single week.")
    if not df_history.empty:
        luck_stats = []
        for team in df_history['Team'].unique():
            w, l = 0, 0
            for wk in range(1, analyze_week + 1):
                wk_scores = df_history[df_history['Week'] == wk]
                match = wk_scores[wk_scores['Team'] == team]
                if match.empty: continue
                my_score = match['Score'].values[0]
                w += (wk_scores['Score'] < my_score).sum()
                l += (wk_scores['Score'] > my_score).sum()
            luck_stats.append({'Team': team, 'All-Play Wins': w, 'All-Play Losses': l, 'All-Play Pct': w/(w+l) if (w+l)>0 else 0})
        df_luck = pd.DataFrame(luck_stats)
        if not df_luck.empty and not df_standings.empty:
            df_final = pd.merge(df_standings, df_luck, on='Team')
            df_final['Luck Factor'] = (df_final['W']/(df_final['W']+df_final['L'])) - df_final['All-Play Pct']
            def color_luck(val): color = '#d4edda' if val > 0 else '#f8d7da'; return f'background-color: {color}; color: {"green" if val > 0 else "red"}'
            st.dataframe(df_final.sort_values('All-Play Wins', ascending=False).style.map(color_luck, subset=['Luck Factor']).format({"Luck Factor": "{:.2f}"}), use_container_width=True, hide_index=True)

# =========================================================
# PAGE 4: POWER RANKINGS
# =========================================================
elif page == "📊 Power Rankings":
    st.header("📊 Power Rankings")
    st.info("**Strength of Roster.** This formula rewards high scoring but penalizes inconsistency (Volatility). High volatility means your team is unpredictable.")
    if not df_history.empty:
        power_stats = df_history.groupby('Team')['Score'].agg(['mean', 'std']).reset_index()
        power_stats['Power Score'] = power_stats['mean'] - (power_stats['std'] * 0.5)
        st.dataframe(
            power_stats.sort_values('Power Score', ascending=False), 
            column_config={
                "Power Score": st.column_config.NumberColumn("Power Score", format="%.2f", help="Mean Score minus 0.5 * Volatility"),
                "mean": st.column_config.NumberColumn("Avg Score", format="%.1f"),
                "std": st.column_config.NumberColumn("Volatility (Std Dev)", format="%.1f")
            },
            use_container_width=True, 
            hide_index=True
        )

        st.divider()

        st.subheader("💥 Boom/Bust Analysis")
        st.caption("Visualizing team volatility. A wider box means the team is unpredictable (Boom/Bust).")
        sort_order = df_history.groupby('Team')['Score'].median().sort_values(ascending=False).index.tolist()
        chart = alt.Chart(df_history).mark_boxplot(extent='min-max', size=50).encode(
            x=alt.X('Team:N', sort=sort_order, title=None),
            y=alt.Y('Score:Q', title='Weekly Scores', scale=alt.Scale(zero=False)),
            color=alt.Color('Team:N', legend=None),
            tooltip=['Team', 'Week', 'Score']
        ).properties(height=500)
        st.altair_chart(chart, use_container_width=True)

# =========================================================
# PAGE 5: POSITIONAL POWER RANKINGS
# =========================================================
elif page == "💪 Positional Power":
    st.header("💪 Positional Power Rankings")
    st.info("""
    **Where is your team strongest?** This analyzes Points Per Game (PPG) for your **STARTERS ONLY**.
    * **Logic:** Calculates the League Average Starter PPG for every position.
    * **Comparison:** Compares your team's specific Starters PPG against that league baseline.
    * **Value:** +4.4 means your starters at that position score 4.4 points MORE than the average team.
    """)
    
    # Data is auto-loaded at startup
    if 'pos_data' in st.session_state and st.session_state.pos_data:
        raw_data = st.session_state.pos_data
        
        # 1. Calculate League Averages
        all_scores = {'QB': [], 'RB': [], 'WR': [], 'TE': [], 'K': [], 'DEF': []}
        for team, positions in raw_data.items():
            for pos, scores in positions.items():
                if pos in all_scores:
                    all_scores[pos].extend(scores)
                    
        league_avgs = {pos: (sum(s) / len(s)) if s else 0 for pos, s in all_scores.items()}
        
        # 2. Build Team Comparison Table
        rows = []
        for team, positions in raw_data.items():
            row = {'Team': team}
            for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
                team_scores = positions.get(pos, [])
                team_avg = sum(team_scores) / len(team_scores) if team_scores else 0
                diff = team_avg - league_avgs.get(pos, 0)
                row[f'{pos} Diff'] = diff
            rows.append(row)
            
        df_pos = pd.DataFrame(rows).set_index('Team')
        
        # 3. Styling
        def color_diff(val):
            color = '#d4edda' if val > 0 else '#f8d7da' if val < 0 else ''
            text_color = 'green' if val > 0 else 'red' if val < 0 else 'black'
            return f'background-color: {color}; color: {text_color}'

        st.subheader("📋 Positional Value Over Average")
        st.dataframe(
            df_pos.style.map(color_diff).format("{:+.1f}"), 
            use_container_width=True
        )
        
        st.divider()
        st.caption(f"League Averages (PPG): QB {league_avgs['QB']:.1f} | RB {league_avgs['RB']:.1f} | WR {league_avgs['WR']:.1f} | TE {league_avgs['TE']:.1f}")
    else:
        st.warning("Positional data not loaded. Please refresh.")

# =========================================================
# PAGE 6: DRAFT ANALYSIS (SCATTER PLOT)
# =========================================================
elif page == "📉 Draft Analysis":
    st.header("📉 Draft & Keeper Analysis")
    st.info("""
    **Draft Efficiency:** Analyzing the return on investment for every player.
    * **🛡️ Keepers (Left):** The foundation of your team. The higher the dot, the more value they retained.
    * **📉 Draft Picks (Right):**
        * **💎 The Steals (Top-Right):** Players drafted late who scored high. These win leagues.
        * **💣 The Busts (Bottom-Left):** Players drafted early who scored low. These lose leagues.
    """)
    
    # 1. Check if data key exists
    data_missing = 'draft_scatter' not in st.session_state
    
    # 2. Check if data is empty (loaded but found nothing)
    data_empty = False
    if not data_missing:
        if isinstance(st.session_state.draft_scatter, list) and len(st.session_state.draft_scatter) == 0:
            data_empty = True

    # 3. Main Logic
    if not data_missing and not data_empty:
        df_draft = pd.DataFrame(st.session_state.draft_scatter)
        
        # --- MERGE REAL TEAM NAMES (DRAFT) ---
        if not df_standings.empty and 'Team Key' in df_standings.columns:
            df_names = df_standings[['Team', 'Team Key']].rename(columns={'Team': 'Team Name'})
            if 'Team Key' in df_draft.columns:
                df_draft = pd.merge(df_draft, df_names, on='Team Key', how='left')
                df_draft['Team Name'] = df_draft['Team Name'].fillna(df_draft['Team Key'])
            else:
                df_draft['Team Name'] = "Unknown"
        else:
             df_draft['Team Name'] = df_draft['Team Key'] if 'Team Key' in df_draft.columns else "Unknown"

        # --- PRE-PROCESSING: CALCULATE 'VISUAL SLOT' ---
        league_size = len(df_standings) if not df_standings.empty else 12
        
        def calculate_visual_slot(row):
            # 1. Keepers: Fixed to the far left (negative value)
            if row['Type'] == 'Keeper':
                return -15 # Visual gap to the left
            
            # 2. Regular Draft: Actual Pick Number
            return (row['Round'] - 1) * league_size + row['Pick']

        df_draft['Visual Slot'] = df_draft.apply(calculate_visual_slot, axis=1)

        # --- FILTERS (STANDARD DROPDOWNS) ---
        with st.expander("🔎 Filter Options", expanded=True):
            c1, c2, c3 = st.columns(3)
            
            # 1. Type Filter (Selectbox)
            with c1:
                acq_types = ["All Players", "Regular Draft", "Keepers"]
                filter_type = st.selectbox("Type:", acq_types)
            
            # 2. Position Filter (Selectbox)
            with c2:
                # Get unique positions, sort, and add "All"
                unique_pos = sorted([x for x in df_draft['Position'].unique() if x])
                pos_options = ["All Positions"] + unique_pos
                selected_pos = st.selectbox("Position:", pos_options)
                
            # 3. Team Filter (Selectbox)
            with c3:
                unique_teams = sorted([str(x) for x in df_draft['Team Name'].unique() if x])
                team_options = ["All Teams"] + unique_teams
                selected_team = st.selectbox("Team:", team_options)

            # 4. Color By Preference
            color_by = st.selectbox("Color Bubbles By:", ["Position", "Team Name", "Type"], index=0)

        # --- APPLY FILTERS ---
        # Type
        if filter_type == "Regular Draft":
            df_draft = df_draft[df_draft['Type'] == 'Regular']
        elif filter_type == "Keepers":
            df_draft = df_draft[df_draft['Type'] == 'Keeper']
        
        # Position
        if selected_pos != "All Positions":
            df_draft = df_draft[df_draft['Position'] == selected_pos]
            
        # Team
        if selected_team != "All Teams":
            df_draft = df_draft[df_draft['Team Name'] == selected_team]

        # --- SCATTER PLOT ---
        if not df_draft.empty:
            chart = alt.Chart(df_draft).mark_point(filled=True, size=100).encode(
                x=alt.X('Visual Slot', title='Draft Order (Left=Keepers, Right=Late Rounds)', scale=alt.Scale(zero=False)),
                y=alt.Y('Total Points', title='Season Total Points', scale=alt.Scale(zero=False)),
                color=alt.Color(color_by, title=color_by),
                shape=alt.Shape('Type', title='Type'), 
                tooltip=['Player', 'Position', 'Round', 'Total Points', 'Type', 'Team Name']
            ).properties(height=600).interactive()
            
            st.altair_chart(chart, use_container_width=True)
            
            st.divider()
            
            # --- DATAFRAME VIEW ---
            st.subheader(f"💎 Roster Gems ({filter_type})")
            
            # Create a clean view
            display_cols = ['Player', 'Position', 'Type', 'Total Points', 'Team Name']
            if filter_type == "Regular Draft" or filter_type == "All Players":
                display_cols.insert(2, 'Round')
                
            st.dataframe(
                df_draft.sort_values('Total Points', ascending=False).head(20)[display_cols], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("No players match your filters.")
    
    else:
        # --- ERROR UI ---
        st.warning("Draft data is currently empty.")
        st.write("This often happens if the initial load timed out and the app cached the empty result.")
        
        if st.button("🔄 Retry Loading Draft Data"):
            fetch_draft_results.clear()
            st.rerun()

# =========================================================
# PAGE 7: RIVALRY
# =========================================================
elif page == "⚔️ Rivalry":
    st.header("⚔️ League Records")
    st.info("Season records and the head-to-head matrix. Check who you've dominated and who has your number.")
    if not df_history.empty:
        h, l = df_history.loc[df_history['Score'].idxmax()], df_history.loc[df_history['Score'].idxmin()]
        c1, c2, c3 = st.columns(3)
        c1.metric("🚀 Season High", f"{h['Score']} pts", h['Team'])
        c2.metric("📉 Season Low", f"{l['Score']} pts", l['Team'])
        losses = df_history[df_history['Result'] == 'L']
        if not losses.empty: 
            hb = losses.loc[losses['Score'].idxmax()]
            c3.metric("💔 Heartbreak", f"{hb['Score']} pts", hb['Team'], help="Highest score in a losing effort.")
        
        st.divider()
        
        if 'Opponent Score' in df_history.columns:
            df_history['Margin'] = df_history['Score'] - df_history['Opponent Score']
            df_history['AbsMargin'] = df_history['Margin'].abs()
            wins = df_history[df_history['Result'] == 'W']
            c4, c5, c6 = st.columns(3)
            
            if not wins.empty:
                bw = wins.loc[wins['Margin'].idxmax()]
                score_str = f"{bw['Team']} ({bw['Score']}) vs {bw['Opponent']} ({bw['Opponent Score']})"
                c4.metric("😤 Largest Victory", f"+{bw['Margin']:.2f}", score_str, help="Biggest blowout win.")
                
            nb = df_history.loc[df_history['AbsMargin'].idxmin()]
            nb_score_str = f"{nb['Team']} ({nb['Score']}) vs {nb['Opponent']} ({nb['Opponent Score']})"
            c5.metric("😬 The Nail Biter", f"{nb['AbsMargin']:.2f}", nb_score_str, help="Closest game of the season.")
            
            if not wins.empty:
                uw = wins.loc[wins['Score'].idxmin()]
                uw_score_str = f"{uw['Team']} ({uw['Score']}) vs {uw['Opponent']} ({uw['Opponent Score']})"
                c6.metric("🥴 The Ugly Win", f"{uw['Score']} pts", uw_score_str, help="Lowest score that resulted in a win.")

        st.divider()
        st.subheader("Head-to-Head Matrix")
        matrix = pd.DataFrame(index=sorted(df_history['Team'].unique()), columns=sorted(df_history['Team'].unique())).fillna("-")
        for team in matrix.index:
            for _, row in df_history[df_history['Team'] == team].iterrows(): 
                matrix.at[team, row['Opponent']] = row['Result'] if matrix.at[team, row['Opponent']] == "-" else matrix.at[team, row['Opponent']] + f", {row['Result']}"
        
        def color_results(val):
            if not isinstance(val, str) or val == "-": return ''
            wins = val.count('W')
            losses = val.count('L')
            if wins > losses: return 'background-color: #d4edda; color: green' 
            if losses > wins: return 'background-color: #f8d7da; color: red' 
            return 'background-color: #fff3cd; color: black' 

        st.dataframe(matrix.style.map(color_results), use_container_width=True)

# =========================================================
# PAGE 8: TRENDS
# =========================================================
elif page == "📉 Trends":
    st.header("📉 Season Trends")
    st.info("Tracking the cumulative race for points. See which teams are gaining ground and which are falling behind.")
    if not df_history.empty:
        df_cum = df_history.sort_values(['Team', 'Week'])
        df_cum['Total Points'] = df_cum.groupby('Team')['Score'].cumsum()
        st.altair_chart(alt.Chart(df_cum).mark_line(point=True).encode(x='Week:O', y='Total Points:Q', color='Team:N').interactive(), use_container_width=True)

# =========================================================
# PAGE 9: MANAGER SKILL
# =========================================================
elif page == "🧠 Manager Skill":
    st.header("🧠 Manager Efficiency")
    st.info("""
    **Who sets the best lineup?** * **Efficiency:** Percentage of potential points captured.
    * **Mistakes:** Count of bench players outscoring starters at the same position.
    * **Match Impact:** Click a row below to see if bad decisions caused a loss.
    """)
    
    # Data is pre-loaded; check just in case
    if 'efficiency_data' not in st.session_state or st.session_state.efficiency_data is None:
         st.warning("Data loading... please wait or reload.")
                
    if 'efficiency_data' in st.session_state and st.session_state.efficiency_data:
        df_eff = pd.DataFrame(st.session_state.efficiency_data)
        if not df_eff.empty:
            df_merged = pd.merge(df_eff, df_history, on=['Week', 'Team'], how='inner')
            df_merged['Points Left on Bench'] = df_merged['Max Points'] - df_merged['Roster Points']
            
            summary = df_merged.groupby('Team').agg({'Roster Points': 'sum', 'Max Points': 'sum', 'Mistake_Count': 'sum'}).reset_index()
            summary['Eff %'] = (summary['Roster Points'] / summary['Max Points']) * 100
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🏆 Efficiency Leaderboard")
                st.dataframe(summary[['Team', 'Eff %']].sort_values('Eff %', ascending=False), column_config={"Eff %": st.column_config.ProgressColumn("Efficiency %", format="%.1f%%", min_value=70, max_value=100)}, use_container_width=True, hide_index=True)
            with col2:
                st.subheader("🤡 Total Mistakes")
                st.dataframe(summary[['Team', 'Mistake_Count']].sort_values('Mistake_Count', ascending=False), use_container_width=True, hide_index=True)

            st.divider()
            
            st.subheader("🔬 Match Impact Analysis")
            selected_team = st.selectbox("Select a Manager to Audit:", summary['Team'].unique())
            
            if selected_team:
                manager_weeks = df_merged[df_merged['Team'] == selected_team].sort_values('Week')
                
                st.markdown(f"**Season Log for {selected_team} (Click row to view details):**")
                st.caption("Rows color-coded by outcome: Green = Won, Red = Lost, Yellow = Close Call")

                for _, row in manager_weeks.iterrows():
                    gap = row['Opponent Score'] - row['Score']
                    verdict_icon = "💀"
                    verdict_text = "Outmatched"
                    
                    if row['Result'] == 'W':
                        verdict_icon = "✅"
                        verdict_text = "Won"
                    elif row['Points Left on Bench'] > gap:
                        verdict_icon = "🚨"
                        verdict_text = "Caused Loss"
                    
                    header = f"{verdict_icon} Week {row['Week']} vs {row['Opponent']} | Score: {row['Score']:.1f} - {row['Opponent Score']:.1f} | {verdict_text}"
                    
                    with st.expander(header):
                        if row['Mistakes']:
                            swap_table = []
                            for m in row['Mistakes']:
                                cost = m['in']['points'] - m['out']['points']
                                impact = "No Impact"
                                if row['Result'] == 'L':
                                    if cost > gap: impact = "🔥 FATAL ERROR (Caused Loss)"
                                    elif (row['Points Left on Bench'] > gap): impact = "⚠️ Contributor"
                                
                                swap_table.append({
                                    "Pos": m['pos'],
                                    "You Played": f"{m['out']['name']} ({m['out']['points']})",
                                    "Should Have": f"{m['in']['name']} ({m['in']['points']})",
                                    "Cost": cost,
                                    "Impact": impact
                                })
                            st.dataframe(pd.DataFrame(swap_table), column_config={"Cost": st.column_config.NumberColumn("Pts Lost", format="+%.1f")}, use_container_width=True, hide_index=True)
                        else:
                            st.success("Perfect lineup! No points left on bench.")

# =========================================================
# PAGE 10: DRAFT & WAIVERS
# =========================================================
elif page == "💎 Draft & Waivers":
    st.header("💎 Gem Mining (WAR Analysis)")
    st.info("""
    **Analysis Methodology:**
    1.  **Tenure & Usage:** Points are ONLY counted if the player was in your starting lineup. Bench points are ignored.
    2.  **Normalized Value (VOB):** To fix skewing from dropping players, we compare your pickup's score to a **Replacement Baseline**.
        * **Baseline =** The higher of your actual bench player OR the League Average Bench score for that position.
    """)
    if 'impact_data' in st.session_state and st.session_state.impact_data:
        # GM LEADERBOARD
        df_w = pd.DataFrame(st.session_state.impact_data['waiver'])
        if not df_w.empty:
            st.subheader("🏆 GM of the Year: Best Waiver Wire Management")
            st.caption("Ranking managers by Normalized Value (VOB). This penalizes streaming bad players even if you had no backup.")
            
            waiver_summary = df_w.groupby('Team').agg({
                'Value Over Bench': 'sum',
                'WAR': 'sum',
                'Starter Points': 'sum',
                'Player': 'count'
            }).reset_index().rename(columns={'Player': 'Impact Pickups'})
            
            st.dataframe(
                waiver_summary.sort_values('Value Over Bench', ascending=False),
                column_config={
                    "Value Over Bench": st.column_config.NumberColumn("Normalized Value", format="%.1f", help="Points scored ABOVE the league average replacement level."),
                    "WAR": st.column_config.NumberColumn("Wins Added", format="%d"),
                    "Starter Points": st.column_config.NumberColumn("Total Raw Pts", format="%.1f")
                },
                use_container_width=True,
                hide_index=True
            )
            st.divider()

        st.subheader("🎯 Best Draft Picks (WAR)")
        
        # --- UPDATE FOR KEEPERS ---
        df_draft_gems = pd.DataFrame(st.session_state.impact_data['draft'])
        if not df_draft_gems.empty:
            if 'is_keeper' in df_draft_gems.columns:
                df_draft_gems['Type'] = df_draft_gems['is_keeper'].apply(lambda x: '🛡️ Keeper' if x else 'Regular')
            else:
                df_draft_gems['Type'] = 'Regular'
            
            st.dataframe(df_draft_gems.sort_values(['WAR', 'Value Over Bench'], ascending=False).head(20), 
                        column_config={
                            "WAR": st.column_config.NumberColumn("WAR", help="Wins Created Above Replacement."),
                            "Value Over Bench": st.column_config.NumberColumn("Value Over Bench", format="%.1f"),
                            "Type": st.column_config.TextColumn("Selection Type")
                        }, use_container_width=True, hide_index=True)
        
        st.divider(); st.subheader("🚀 Best Waiver Moves (WAR)")
        if not df_w.empty:
            st.dataframe(df_w.sort_values(['WAR', 'Value Over Bench'], ascending=False).head(20), 
                        column_config={
                            "WAR": st.column_config.NumberColumn("WAR", help="Wins Created Above Replacement."),
                            "Value Over Bench": st.column_config.NumberColumn("Value Over Bench", format="%.1f")
                        }, use_container_width=True, hide_index=True)
        
        if st.button("Recalculate Data"): 
            st.session_state.impact_data = None
            st.rerun()

elif page == "📈 Raw Data":
    st.header("📈 Raw Data Inspector")
    st.dataframe(df_history, use_container_width=True)