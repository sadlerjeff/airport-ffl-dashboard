import streamlit as st
import pandas as pd
import altair as alt
from utils import fetch_standings, fetch_all_weekly_scores, get_current_week, fetch_manager_efficiency, fetch_draft_results, fetch_impact_analysis, fetch_projection_accuracy

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Airport FFL Analytics", page_icon="🏈", layout="wide")

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏈 Menu")
page = st.sidebar.radio(
    "Go to:",
    ["🏆 Standings", "🍀 Luck Index", "📊 Power Rankings", "⚔️ Rivalry", "📉 Trends", "🧠 Manager Skill", "🎯 Projections", "💎 Draft & Waivers", "📈 Raw Data"]
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
    st.info("**Current official standings from Yahoo.** Rank is determined by Win/Loss record, with Total Points For (PF) acting as the tiebreaker.")
    if not df_standings.empty:
        df_standings['Rank'] = pd.to_numeric(df_standings['Rank'], errors='coerce').fillna(100).astype(int)
        st.dataframe(df_standings.sort_values('Rank')[['Rank', 'Team', 'W', 'L', 'T', 'PF', 'PA']], use_container_width=True, hide_index=True)

# =========================================================
# PAGE 2: LUCK INDEX
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
# PAGE 3: POWER RANKINGS
# =========================================================
elif page == "📊 Power Rankings":
    st.header("📊 Power Rankings")
    st.info("**Strength of Roster.** This formula rewards high scoring but penalizes inconsistency (Volatility). High volatility means your team is unpredictable.")
    if not df_history.empty:
        power_stats = df_history.groupby('Team')['Score'].agg(['mean', 'std']).reset_index()
        power_stats['Power Score'] = power_stats['mean'] - (power_stats['std'] * 0.5)
        st.dataframe(power_stats.sort_values('Power Score', ascending=False), use_container_width=True, hide_index=True)

# =========================================================
# PAGE 4: RIVALRY
# =========================================================
elif page == "⚔️ Rivalry":
    st.header("⚔️ League Records")
    st.info("Season records and the head-to-head matrix. Check who you've dominated and who has your number.")
    if not df_history.empty:
        h, l = df_history.loc[df_history['Score'].idxmax()], df_history.loc[df_history['Score'].idxmin()]
        c1, c2, c3 = st.columns(3); c1.metric("🚀 Season High", f"{h['Score']} pts", h['Team']); c2.metric("📉 Season Low", f"{l['Score']} pts", l['Team'])
        losses = df_history[df_history['Result'] == 'L']; hb = losses.loc[losses['Score'].idxmax()] if not losses.empty else None
        if hb is not None: c3.metric("💔 Heartbreak", f"{hb['Score']} pts", hb['Team'])
        st.divider(); st.subheader("Head-to-Head Matrix")
        matrix = pd.DataFrame(index=sorted(df_history['Team'].unique()), columns=sorted(df_history['Team'].unique())).fillna("-")
        for team in matrix.index:
            for _, row in df_history[df_history['Team'] == team].iterrows(): matrix.at[team, row['Opponent']] = row['Result'] if matrix.at[team, row['Opponent']] == "-" else matrix.at[team, row['Opponent']] + f", {row['Result']}"
        st.dataframe(matrix, use_container_width=True)

# =========================================================
# PAGE 5: TRENDS
# =========================================================
elif page == "📉 Trends":
    st.header("📉 Season Trends")
    st.info("Tracking the cumulative race for points. See which teams are gaining ground and which are falling behind.")
    if not df_history.empty:
        df_cum = df_history.sort_values(['Team', 'Week'])
        df_cum['Total Points'] = df_cum.groupby('Team')['Score'].cumsum()
        st.altair_chart(alt.Chart(df_cum).mark_line(point=True).encode(x='Week:O', y='Total Points:Q', color='Team:N').interactive(), use_container_width=True)

# =========================================================
# PAGE 6: MANAGER SKILL (DETAILED EXPLORER)
# =========================================================
elif page == "🧠 Manager Skill":
    st.header("🧠 Manager Efficiency")
    st.info("""
    **Who sets the best lineup?** This tab analyzes how well each manager maximizes their roster's potential.
    * **Efficiency:** Percentage of 'Perfect Lineup' points you actually scored.
    * **Mistakes:** Count of times a bench player outscored a starter at the same position.
    * **Impact Analysis:** Click on a match below to see if your mistakes actually cost you the win.
    """)
    
    if 'efficiency_data' not in st.session_state: st.session_state.efficiency_data = None
    if st.session_state.efficiency_data is None:
        if st.button("Calculate Efficiency"):
            with st.spinner("Analyzing lineup decisions..."):
                st.session_state.efficiency_data = fetch_manager_efficiency(analyze_week, df_history['Team'].unique())
                st.rerun()
                
    if st.session_state.efficiency_data:
        df_eff = pd.DataFrame(st.session_state.efficiency_data)
        df_merged = pd.merge(df_eff, df_history, on=['Week', 'Team'], how='inner')
        df_merged['Points Left on Bench'] = df_merged['Max Points'] - df_merged['Roster Points']
        
        summary = df_merged.groupby('Team').agg({'Roster Points': 'sum', 'Max Points': 'sum', 'Mistake_Count': 'sum'}).reset_index()
        summary['Eff %'] = (summary['Roster Points'] / summary['Max Points']) * 100
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏆 Overall Efficiency")
            st.dataframe(summary[['Team', 'Eff %']].sort_values('Eff %', ascending=False), column_config={"Eff %": st.column_config.ProgressColumn("Efficiency %", format="%.1f%%", min_value=70, max_value=100)}, use_container_width=True, hide_index=True)
        with col2:
            st.subheader("🤡 Total Mistakes")
            st.dataframe(summary[['Team', 'Mistake_Count']].sort_values('Mistake_Count', ascending=False), use_container_width=True, hide_index=True)

        st.divider()
        
        # 1. Select Manager
        st.subheader("🔬 Match Impact Analysis")
        selected_team = st.selectbox("Select a Manager to Audit:", summary['Team'].unique())
        
        if selected_team:
            manager_weeks = df_merged[df_merged['Team'] == selected_team].sort_values('Week')
            
            def get_verdict(row):
                if row['Result'] == 'W': return "✅ Won"
                gap = row['Opponent Score'] - row['Score']
                if row['Points Left on Bench'] > gap: return "🚨 Caused Loss"
                return "💀 Outmatched"

            manager_weeks['Verdict'] = manager_weeks.apply(get_verdict, axis=1)
            
            st.markdown(f"**Season Log for {selected_team} (Click a row to see details):**")
            
            # CLICKABLE DATAFRAME
            event = st.dataframe(
                manager_weeks[['Week', 'Opponent', 'Result', 'Score', 'Opponent Score', 'Max Points', 'Verdict']],
                column_config={
                    "Score": st.column_config.NumberColumn("Actual Score", format="%.1f"),
                    "Max Points": st.column_config.NumberColumn("Potential Score", format="%.1f"),
                    "Verdict": st.column_config.TextColumn("Manager Performance")
                },
                use_container_width=True, 
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun"
            )
            
            # 2. Show Details Based on Selection
            if len(event.selection.rows) > 0:
                selected_index = event.selection.rows[0]
                selected_row = manager_weeks.iloc[selected_index]
                sel_week = selected_row['Week']
                gap = selected_row['Opponent Score'] - selected_row['Score']
                res = selected_row['Result']
                
                st.divider()
                st.markdown(f"### 🔎 Breakdown for Week {sel_week} vs {selected_row['Opponent']}")
                
                mistakes = selected_row['Mistakes']
                if mistakes:
                    swap_table = []
                    for m in mistakes:
                        cost = m['in']['points'] - m['out']['points']
                        if res == 'L':
                            if cost > gap: impact = "🔥 FATAL ERROR (Solely caused loss)"
                            elif (selected_row['Points Left on Bench'] > gap): impact = "⚠️ Contributor (Cumulative failure)"
                            else: impact = "No Impact (Would have lost anyway)"
                        else: impact = "None (Won Match)"
                            
                        swap_table.append({
                            "Pos": m['pos'],
                            "Played": f"{m['out']['name']} ({m['out']['points']})",
                            "Should Have": f"{m['in']['name']} ({m['in']['points']})",
                            "Cost": cost,
                            "Impact": impact
                        })
                    
                    st.dataframe(pd.DataFrame(swap_table), column_config={"Cost": st.column_config.NumberColumn("Pts Lost", format="+%.1f")}, use_container_width=True, hide_index=True)
                else:
                    st.success("No lineup mistakes made this week.")
            else:
                st.caption("👆 Select a week above to see the specific players involved.")

        if st.button("Reset Analysis"):
            st.session_state.efficiency_data = None
            st.rerun()

# =========================================================
# PAGE 7: PROJECTIONS
# =========================================================
elif page == "🎯 Projections":
    st.header("🎯 Projection Accuracy")
    st.info("**Did your team live up to the hype?** This compares Yahoo's pre-game projections against actual scores for every starter.")
    if 'proj_data' not in st.session_state: st.session_state.proj_data = None
    if st.session_state.proj_data is None:
        if st.button("Calculate Projection Accuracy"):
            with st.spinner("Analyzing Yahoo projections..."):
                st.session_state.proj_data = fetch_projection_accuracy(analyze_week)
                st.rerun()
    if st.session_state.proj_data:
        df_p = pd.DataFrame(st.session_state.proj_data)
        if not df_p.empty:
            starters = df_p[df_p['IsStarter']]
            if starters['Projected'].sum() == 0:
                st.warning("⚠️ Yahoo API is returning 0 for projections.")
            team_s = starters.groupby('Team').agg({'Actual': 'sum', 'Projected': 'sum', 'Diff': 'sum'}).reset_index()
            st.subheader("🏆 Team Reliability")
            st.dataframe(team_s.sort_values('Diff', ascending=False), column_config={"Diff": st.column_config.NumberColumn("Total Boom/Bust", format="%.1f pts", help="Points scored above or below projections.")}, use_container_width=True, hide_index=True)
            st.subheader("📈 Projection Scatter")
            st.altair_chart(alt.Chart(starters).mark_circle(size=60).encode(x=alt.X('Projected:Q'), y=alt.Y('Actual:Q'), color='Team:N', tooltip=['Player', 'Week', 'Actual', 'Projected']).interactive(), use_container_width=True)
        if st.button("Reset Analysis"): st.session_state.proj_data = None; st.rerun()

# =========================================================
# PAGE 8: DRAFT & WAIVERS
# =========================================================
elif page == "💎 Draft & Waivers":
    st.header("💎 Gem Mining (WAR Analysis)")
    st.info("""
    **Wins Above Replacement (WAR):**
    This measures if a player actually changed the outcome of your games.
    1. We find the **Value Over Bench** (Starter Pts - Best Bench scorer at that position).
    2. If your **Value Over Bench** was larger than your margin of victory, that player is credited with a **Critical Win**.
    """)
    if 'impact_data' not in st.session_state: st.session_state.impact_data = None
    if st.session_state.impact_data is None:
        if st.button("Calculate WAR Value"):
            with st.spinner("Analyzing wins created..."):
                draft = fetch_draft_results(); impact = fetch_impact_analysis(analyze_week)
                d_gems, w_gems = [], []
                for p in impact:
                    if p['Player Key'] in draft: 
                        p.update(draft[p['Player Key']]); d_gems.append(p)
                    else: w_gems.append(p)
                st.session_state.impact_data = {'draft': d_gems, 'waiver': w_gems}; st.rerun()
    if st.session_state.impact_data:
        st.subheader("🎯 Best Draft Picks (WAR)")
        st.dataframe(pd.DataFrame(st.session_state.impact_data['draft']).sort_values(['WAR', 'Starter Points'], ascending=False).head(20), column_config={"WAR": st.column_config.NumberColumn("WAR", help="Wins Created Above Replacement.")}, use_container_width=True, hide_index=True)
        st.divider(); st.subheader("🚀 Best Waiver Moves (WAR)")
        st.dataframe(pd.DataFrame(st.session_state.impact_data['waiver']).sort_values(['WAR', 'Starter Points'], ascending=False).head(20), use_container_width=True, hide_index=True)
        if st.button("Reset WAR Analysis"): st.session_state.impact_data = None; st.rerun()

elif page == "📈 Raw Data":
    st.header("📈 Raw Data Inspector")
    st.dataframe(df_history, use_container_width=True)