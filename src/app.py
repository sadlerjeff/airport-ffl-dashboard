import streamlit as st
import pandas as pd
import altair as alt
from utils import fetch_standings, fetch_all_weekly_scores, get_current_week, fetch_manager_efficiency, fetch_draft_results, fetch_impact_analysis

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Airport FFL Analytics", page_icon="🏈", layout="wide")

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏈 Menu")
page = st.sidebar.radio(
    "Go to:",
    ["🏆 Standings", "🍀 Luck Index", "📊 Power Rankings", "⚔️ Rivalry", "📉 Trends", "🧠 Manager Skill", "💎 Draft & Waivers", "📈 Raw Data"]
)

st.title("🏈 Airport FFL Analytics Center")

# --- DATA LOADING ---
with st.spinner('Syncing with Yahoo Fantasy...'):
    standings_data = fetch_standings()
    df_standings = pd.DataFrame(standings_data)
    
    current_week = get_current_week()
    analyze_week = max(1, current_week - 1) 
    
    history_data = fetch_all_weekly_scores(analyze_week)
    df_history = pd.DataFrame(history_data)

# =========================================================
# PAGE 1: STANDINGS
# =========================================================
if page == "🏆 Standings":
    st.header("🏆 Official League Standings")
    st.markdown("Current official standings from Yahoo. Rank is determined by Win/Loss record, with Total Points For (PF) acting as the tiebreaker.")
    if not df_standings.empty:
        df_standings['Rank'] = pd.to_numeric(df_standings['Rank'], errors='coerce').fillna(100).astype(int)
        df_display = df_standings.sort_values('Rank')
        st.dataframe(
            df_display[['Rank', 'Team', 'W', 'L', 'T', 'PF', 'PA']],
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", format="#%d", width="small", help="Official Yahoo league ranking."),
                "Team": st.column_config.TextColumn("Team", help="Team Name"),
                "W": st.column_config.NumberColumn("Wins", help="Total games won."),
                "L": st.column_config.NumberColumn("Losses", help="Total games lost."),
                "T": st.column_config.NumberColumn("Ties", help="Total games tied."),
                "PF": st.column_config.NumberColumn("Points For", format="%.2f", help="Total points scored by your starters."),
                "PA": st.column_config.NumberColumn("Points Against", format="%.2f", help="Total points scored against you."),
            }, use_container_width=True, hide_index=True
        )
    else:
        st.warning("⚠️ Could not load standings. Please refresh your Yahoo Token.")

# =========================================================
# PAGE 2: LUCK INDEX
# =========================================================
elif page == "🍀 Luck Index":
    st.header(f"The Luck Index (Weeks 1-{analyze_week})")
    st.info("Calculates your 'Theoretical Record' (All-Play) against every team, every week.")
    if not df_history.empty:
        luck_stats = []
        teams = df_history['Team'].unique()
        for team in teams:
            total_wins = 0
            total_losses = 0
            for week in range(1, analyze_week + 1):
                week_scores = df_history[df_history['Week'] == week]
                if week_scores.empty: continue
                my_row = week_scores[week_scores['Team'] == team]
                if my_row.empty: continue
                my_score = my_row['Score'].values[0]
                wins = (week_scores['Score'] < my_score).sum()
                losses = (week_scores['Score'] > my_score).sum()
                total_wins += wins
                total_losses += losses
            total_games = total_wins + total_losses
            win_pct = total_wins / total_games if total_games > 0 else 0.0
            luck_stats.append({'Team': team, 'All-Play Wins': total_wins, 'All-Play Losses': total_losses, 'All-Play Pct': win_pct})
        df_luck = pd.DataFrame(luck_stats)
        if not df_luck.empty and not df_standings.empty:
            df_final = pd.merge(df_standings, df_luck, on='Team')
            df_final['Real Pct'] = df_final['W'] / (df_final['W'] + df_final['L'])
            df_final['Luck Factor'] = df_final['Real Pct'] - df_final['All-Play Pct']
            df_display = df_final[['Team', 'W', 'L', 'All-Play Wins', 'All-Play Losses', 'Luck Factor']].sort_values('All-Play Wins', ascending=False)
            
            def color_luck(val):
                color = '#d4edda' if val > 0 else '#f8d7da' if val < 0 else ''
                text_color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                return f'background-color: {color}; color: {text_color}'
            
            st.dataframe(
                df_display.style.map(color_luck, subset=['Luck Factor']).format({"Luck Factor": "{:.2f}"}),
                column_config={
                    "Team": st.column_config.TextColumn("Team"),
                    "W": st.column_config.NumberColumn("Real Wins", help="Your actual record."),
                    "L": st.column_config.NumberColumn("Real Losses", help="Your actual record."),
                    "All-Play Wins": st.column_config.NumberColumn("Theoretical Wins", help="Wins you WOULD have if you played every team, every week."),
                    "All-Play Losses": st.column_config.NumberColumn("Theoretical Losses", help="Losses you WOULD have if you played every team, every week."),
                    "Luck Factor": st.column_config.NumberColumn("Luck Factor", help="Positive = Lucky, Negative = Unlucky")
                }, use_container_width=True, hide_index=True
            )
        else:
            st.warning("Missing data.")

# =========================================================
# PAGE 3: POWER RANKINGS
# =========================================================
elif page == "📊 Power Rankings":
    st.header("📊 Power Rankings")
    st.markdown("Rewards high scoring but penalizes inconsistency.")
    if not df_history.empty:
        power_stats = df_history.groupby('Team')['Score'].agg(['mean', 'std', 'min', 'max']).reset_index()
        power_stats.columns = ['Team', 'Avg Score', 'Volatility', 'Min Score', 'Max Score']
        power_stats['Power Score'] = power_stats['Avg Score'] - (power_stats['Volatility'] * 0.5)
        power_stats = power_stats.sort_values('Power Score', ascending=False)
        power_stats['Rank'] = range(1, len(power_stats) + 1)
        st.dataframe(
            power_stats[['Rank', 'Team', 'Power Score', 'Avg Score', 'Volatility', 'Min Score', 'Max Score']],
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", format="#%d", width="small"),
                "Power Score": st.column_config.NumberColumn("Power Score", format="%.1f", help="Avg Score minus Volatility penalty."),
                "Avg Score": st.column_config.NumberColumn("Avg Score", format="%.1f", help="Average points per week."),
                "Volatility": st.column_config.NumberColumn("Volatility", format="%.1f", help="Standard Deviation. High = Unpredictable."),
                "Min Score": st.column_config.NumberColumn("Season Low", format="%.1f", help="Lowest score of the season."),
                "Max Score": st.column_config.NumberColumn("Season High", format="%.1f", help="Highest score of the season.")
            },
            use_container_width=True, hide_index=True
        )

# =========================================================
# PAGE 4: RIVALRY
# =========================================================
elif page == "⚔️ Rivalry":
    st.header("⚔️ League Records")
    if not df_history.empty:
        high = df_history.loc[df_history['Score'].idxmax()]
        low = df_history.loc[df_history['Score'].idxmin()]
        losses = df_history[df_history['Result'] == 'L']
        col1, col2, col3 = st.columns(3)
        col1.metric("🚀 Season High", f"{high['Score']} pts", high['Team'], help="Highest single game score.")
        col2.metric("📉 Season Low", f"{low['Score']} pts", low['Team'], help="Lowest single game score.")
        if not losses.empty:
            heartbreak = losses.loc[losses['Score'].idxmax()]
            col3.metric("💔 Heartbreak Award", f"{heartbreak['Score']} pts", f"{heartbreak['Team']} (Lost)", help="Highest score that still resulted in a loss.")
        st.divider()
        st.subheader("Head-to-Head Matrix")
        st.caption("Rows are YOU, Columns are OPPONENTS. Green = Win, Red = Loss.")
        teams = sorted(df_history['Team'].unique())
        matrix = pd.DataFrame(index=teams, columns=teams).fillna("-")
        for team in teams:
            team_games = df_history[df_history['Team'] == team]
            for _, row in team_games.iterrows():
                opp = row['Opponent']
                res = row['Result']
                curr = matrix.at[team, opp]
                matrix.at[team, opp] = res if curr == "-" else curr + f", {res}"
        def color_results(val):
            if not isinstance(val, str): return ''
            if 'W' in val and 'L' in val: return 'background-color: #fff3cd; color: black'
            if 'W' in val: return 'background-color: #d4edda; color: green'
            if 'L' in val: return 'background-color: #f8d7da; color: red'
            return ''
        st.dataframe(matrix.style.map(color_results), use_container_width=True)

# =========================================================
# PAGE 5: TRENDS
# =========================================================
elif page == "📉 Trends":
    st.header("📉 Season Trends")
    if not df_history.empty:
        df_cum = df_history.sort_values(['Team', 'Week'])
        df_cum['Total Points'] = df_cum.groupby('Team')['Score'].cumsum()
        c = alt.Chart(df_cum).mark_line(point=True).encode(
            x=alt.X('Week:O', title="Week"), y=alt.Y('Total Points:Q', scale=alt.Scale(zero=False), title="Cumulative Points"), color='Team:N', tooltip=['Team', 'Week', 'Total Points']
        ).interactive()
        st.altair_chart(c, use_container_width=True)

# =========================================================
# PAGE 6: MANAGER SKILL
# =========================================================
elif page == "🧠 Manager Skill":
    st.header("🧠 Manager Efficiency")
    st.info("Compares Actual Score vs. Max Potential Score.")
    if 'efficiency_data' not in st.session_state:
        st.session_state.efficiency_data = None
    if st.session_state.efficiency_data is None:
        if st.button("Calculate Efficiency (Click to Run)"):
            with st.spinner("Analyzing bench points..."):
                if not df_history.empty:
                    teams_list = df_history['Team'].unique()
                    st.session_state.efficiency_data = fetch_manager_efficiency(analyze_week, teams_list)
                    st.rerun()
    if st.session_state.efficiency_data:
        df_max = pd.DataFrame(st.session_state.efficiency_data)
        if not df_max.empty and not df_history.empty:
            df_merged = pd.merge(df_history, df_max, on=['Week', 'Team'], how='inner')
            df_merged['Efficiency %'] = (df_merged['Score'] / df_merged['Max Points']) * 100
            df_merged['Points Left on Bench'] = df_merged['Max Points'] - df_merged['Score']
            season_stats = df_merged.groupby('Team').agg({'Score': 'sum', 'Max Points': 'sum', 'Points Left on Bench': 'sum'}).reset_index()
            season_stats['Overall Efficiency'] = (season_stats['Score'] / season_stats['Max Points']) * 100
            season_stats = season_stats.sort_values('Overall Efficiency', ascending=False)
            st.dataframe(
                season_stats[['Team', 'Overall Efficiency', 'Points Left on Bench']], 
                column_config={
                    "Overall Efficiency": st.column_config.ProgressColumn("Efficiency %", format="%.1f%%", min_value=70, max_value=100, help="100% = You started the perfect lineup every week."),
                    "Points Left on Bench": st.column_config.NumberColumn("Points Left on Bench", format="%.0f", help="Points lost by leaving better players on the bench.")
                }, 
                use_container_width=True, hide_index=True
            )
            if st.button("Recalculate (Reset)"):
                st.session_state.efficiency_data = None
                st.rerun()

# =========================================================
# PAGE 7: DRAFT & WAIVERS (WAR ANALYSIS)
# =========================================================
elif page == "💎 Draft & Waivers":
    st.header("💎 Gem Mining (WAR Analysis)")
    st.info("""
    **Wins Above Replacement (WAR):**
    This checks if your starter actually mattered. 
    If you started a player who scored 20 pts, but you had a bench player who scored 18 pts, the starter only added **+2 Points of Value**.
    
    * **WAR (Wins):** The number of games you WON that you would have LOST if you had played your best bench option instead.
    """)
    
    if 'impact_data' not in st.session_state:
        st.session_state.impact_data = None

    if st.session_state.impact_data is None:
        if st.button("Calculate Value (Click to Run)"):
            with st.spinner("Running 'What-If' scenarios for every game..."):
                draft_data = fetch_draft_results()
                impact_stats = fetch_impact_analysis(analyze_week)
                
                if impact_stats:
                    draft_gems = []
                    waiver_gems = []
                    
                    for p in impact_stats:
                        p_key = p['Player Key']
                        # Classify Source
                        if draft_data and p_key in draft_data:
                            info = draft_data[p_key]
                            p['Round'] = info['round']
                            p['Pick'] = info['pick']
                            draft_gems.append(p)
                        else:
                            waiver_gems.append(p)
                    
                    st.session_state.impact_data = {'draft': draft_gems, 'waiver': waiver_gems}
                    st.rerun()

    if st.session_state.impact_data:
        draft_gems = st.session_state.impact_data['draft']
        waiver_gems = st.session_state.impact_data['waiver']
        
        # 1. Draft Gems
        st.subheader("🎯 Most Valuable Draft Picks (WAR)")
        if draft_gems:
            df_draft = pd.DataFrame(draft_gems)
            df_draft = df_draft.sort_values(['WAR', 'Starter Points'], ascending=[False, False]).head(20)
            
            st.dataframe(
                df_draft[['Team', 'Player', 'Starter Points', 'WAR', 'Round', 'Pick']],
                column_config={
                    "Starter Points": st.column_config.NumberColumn("Starter Pts", format="%.1f", help="Points scored while in the starting lineup."),
                    "WAR": st.column_config.NumberColumn("WAR (Wins)", format="%d 🏆", help="Critical Wins created by this player over a bench replacement."),
                    "Round": st.column_config.NumberColumn("Round", help="Draft Round."),
                    "Pick": st.column_config.NumberColumn("Pick", help="Overall Pick.")
                }, use_container_width=True, hide_index=True
            )
        
        st.divider()
        
        # 2. Waiver Gems
        st.subheader("🚀 Most Valuable Waiver Moves (WAR)")
        if waiver_gems:
            df_waiver = pd.DataFrame(waiver_gems)
            df_waiver = df_waiver.sort_values(['WAR', 'Starter Points'], ascending=[False, False]).head(20)
            
            st.dataframe(
                df_waiver[['Team', 'Player', 'Starter Points', 'WAR']],
                column_config={
                    "Starter Points": st.column_config.NumberColumn("Starter Pts", format="%.1f", help="Points scored while in the starting lineup."),
                    "WAR": st.column_config.NumberColumn("WAR (Wins)", format="%d 🏆", help="Critical Wins created by this player over a bench replacement."),
                }, use_container_width=True, hide_index=True
            )
            
        if st.button("Recalculate (Reset)"):
            st.session_state.impact_data = None
            st.rerun()

# =========================================================
# PAGE 8: RAW DATA
# =========================================================
elif page == "📈 Raw Data":
    st.header("📈 Raw Data Inspector")
    st.dataframe(
        df_history, 
        use_container_width=True,
        column_config={
            "Score": st.column_config.NumberColumn("Score", help="Matchup Score"),
            "Result": st.column_config.TextColumn("Result", help="W/L/T")
        }
    )