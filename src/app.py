import streamlit as st
import pandas as pd
import altair as alt
from utils import fetch_standings, fetch_all_weekly_scores, get_current_week

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Airport FFL Analytics", page_icon="🏈", layout="wide")

st.title("🏈 Airport FFL Analytics Center")

# --- DATA LOADING ---
with st.spinner('Syncing with Yahoo Fantasy...'):
    # 1. Get Live Standings (Real Records)
    standings_data = fetch_standings()
    df_standings = pd.DataFrame(standings_data)
    
    # 2. Get Historical Data (for Advanced Stats)
    current_week = get_current_week()
    analyze_week = max(1, current_week - 1) 
    
    history_data = fetch_all_weekly_scores(analyze_week)
    df_history = pd.DataFrame(history_data)

# --- TABS ---
# We now have 5 tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 Luck Index", "📊 Power Rankings", "⚔️ Rivalry", "📉 Trends", "📈 Raw Data"])

# === TAB 1: THE LUCK INDEX ===
with tab1:
    st.header(f"The Luck Index (Weeks 1-{analyze_week})")
    st.write("Who has the hardest schedule? We calculated your record if you played **EVERY** team, every week.")
    
    if not df_history.empty:
        luck_stats = []
        teams = df_history['Team'].unique()
        
        for team in teams:
            total_wins = 0
            total_losses = 0
            
            for week in range(1, analyze_week + 1):
                week_scores = df_history[df_history['Week'] == week]
                if week_scores.empty: continue
                
                my_team_row = week_scores[week_scores['Team'] == team]
                if my_team_row.empty: continue
                    
                my_score = my_team_row['Score'].values[0]
                
                wins = (week_scores['Score'] < my_score).sum()
                losses = (week_scores['Score'] > my_score).sum()
                
                total_wins += wins
                total_losses += losses
                
            total_games = total_wins + total_losses
            win_pct = total_wins / total_games if total_games > 0 else 0.0

            luck_stats.append({
                'Team': team,
                'All-Play Wins': total_wins,
                'All-Play Losses': total_losses,
                'All-Play Pct': win_pct
            })
            
        df_luck = pd.DataFrame(luck_stats)
        
        if not df_luck.empty:
            df_final = pd.merge(df_standings, df_luck, on='Team')
            df_final['Real Pct'] = df_final['W'] / (df_final['W'] + df_final['L'])
            df_final['Luck Factor'] = df_final['Real Pct'] - df_final['All-Play Pct']
            
            display_df = df_final[['Team', 'W', 'L', 'All-Play Wins', 'All-Play Losses', 'Luck Factor']].copy()
            display_df = display_df.sort_values('Luck Factor', ascending=True)
            
            st.dataframe(
                display_df,
                column_config={
                    "Luck Factor": st.column_config.ProgressColumn(
                        "Luck Meter",
                        help="Calculation: (Real Win %) - (All-Play Win %). Positive means you are winning more than your points suggest (Lucky).",
                        format="%.2f",
                        min_value=-0.5,
                        max_value=0.5,
                    ),
                    "All-Play Wins": st.column_config.NumberColumn("Theoretical Wins"),
                    "All-Play Losses": st.column_config.NumberColumn("Theoretical Losses")
                },
                use_container_width=True,
                hide_index=True
            )
            
            if len(display_df) > 0:
                most_unlucky = display_df.iloc[0]
                most_lucky = display_df.iloc[-1]
                col1, col2 = st.columns(2)
                col1.info(f"🍀 **Luckiest Team:** {most_lucky['Team']}")
                col2.error(f"💀 **Unluckiest Team:** {most_unlucky['Team']}")
        else:
            st.warning("Not enough data.")

# === TAB 2: POWER RANKINGS ===
with tab2:
    st.header("📊 Power Rankings & Consistency")
    
    if not df_history.empty:
        power_stats = df_history.groupby('Team')['Score'].agg(['mean', 'std', 'min', 'max']).reset_index()
        power_stats.columns = ['Team', 'Avg Score', 'Volatility', 'Min Score', 'Max Score']
        
        power_stats['Power Score'] = power_stats['Avg Score'] - (power_stats['Volatility'] * 0.5)
        power_stats = power_stats.sort_values('Power Score', ascending=False)
        power_stats['Rank'] = range(1, len(power_stats) + 1)
        
        st.dataframe(
            power_stats,
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", format="#%d"),
                "Power Score": st.column_config.NumberColumn("Power Score", help="Avg Score - (Volatility * 0.5)", format="%.1f"),
                "Avg Score": st.column_config.NumberColumn("Avg Score", format="%.1f"),
                "Volatility": st.column_config.NumberColumn("Volatility", help="Lower is better. Measures consistency.", format="%.1f"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.subheader("Risk vs. Reward Analysis")
        st.markdown("""
        * **Top Left:** Elite (High Scoring & Consistent)
        * **Top Right:** Dangerous/Risky (High Scoring but Volatile)
        * **Bottom Left:** Low Ceiling (Consistent but Low Scoring)
        * **Bottom Right:** The Danger Zone (Low Scoring & Volatile)
        """)
        
        st.scatter_chart(
            power_stats,
            x='Volatility',
            y='Avg Score',
            color='Team',
            size='Power Score' 
        )

# === TAB 3: RIVALRY & RECORDS ===
with tab3:
    st.header("⚔️ League Records & Superlatives")
    
    if not df_history.empty:
        # Superlatives
        high_score = df_history.loc[df_history['Score'].idxmax()]
        low_score = df_history.loc[df_history['Score'].idxmin()]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("🚀 Season High", f"{high_score['Score']} pts", high_score['Team'])
        col2.metric("📉 Season Low", f"{low_score['Score']} pts", low_score['Team'])
        
        losses = df_history[df_history['Result'] == 'L']
        if not losses.empty:
            heartbreak = losses.loc[losses['Score'].idxmax()]
            col3.metric("💔 Heartbreak Award", f"{heartbreak['Score']} pts", f"{heartbreak['Team']} (Lost)")
            
        st.divider()

        # Head-to-Head Matrix
        st.subheader("Head-to-Head Matrix")
        st.write("Read **Row vs Column**. Green means the Row Team won.")
        
        teams = sorted(df_history['Team'].unique())
        matrix = pd.DataFrame(index=teams, columns=teams).fillna("-")
        
        for team in teams:
            team_games = df_history[df_history['Team'] == team]
            for _, row in team_games.iterrows():
                opp = row['Opponent']
                result = row['Result']
                current_val = matrix.at[team, opp]
                if current_val == "-":
                    matrix.at[team, opp] = result
                else:
                    matrix.at[team, opp] += f", {result}"
        
        st.dataframe(matrix, use_container_width=True)

# === TAB 4: TRENDS & VISUALS (NEW!) ===
with tab4:
    st.header("📉 Season Trends & Visuals")
    
    if not df_history.empty:
        # 1. THE HORSE RACE (Cumulative Points)
        st.subheader("🏁 The Horse Race (Cumulative Points)")
        st.write("Trace the race for the scoring title week by week.")
        
        df_cumulative = df_history.copy()
        df_cumulative = df_cumulative.sort_values(['Team', 'Week'])
        df_cumulative['Total Points'] = df_cumulative.groupby('Team')['Score'].cumsum()
        
        st.line_chart(
            df_cumulative,
            x='Week',
            y='Total Points',
            color='Team'
        )
        
        st.divider()
        
        # 2. BOX PLOTS (Score Distribution)
        st.subheader("📦 Scoring Distribution (Box Plots)")
        st.write("""
        **How to read this:**
        * **Box:** The middle 50% of scores (Normal performance).
        * **Line:** Median score.
        * **Whiskers:** Range of typical scores.
        * **Dots:** Outliers (Boom/Bust weeks).
        * **Short Box:** Consistent. **Tall Box:** Volatile.
        """)
        
        chart = alt.Chart(df_history).mark_boxplot(extent='min-max').encode(
            x=alt.X('Team:N', title=None),
            y=alt.Y('Score:Q', title='Weekly Score', scale=alt.Scale(zero=False)),
            color='Team:N'
        ).properties(
            height=500
        ).configure_axis(
            labelFontSize=12,
            titleFontSize=14
        )
        
        st.altair_chart(chart, use_container_width=True)

# === TAB 5: RAW DATA ===
with tab5:
    st.subheader("Raw Data Inspector")
    st.dataframe(df_history, use_container_width=True)