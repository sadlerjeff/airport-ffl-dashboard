import streamlit as st
import pandas as pd
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
# We added "Rivalry & Records" as the 3rd tab
tab1, tab2, tab3, tab4 = st.tabs(["🏆 Luck Index", "📊 Power Rankings", "⚔️ Rivalry & Records", "📈 Raw Data"])

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
                    "All-Play Wins": st.column_config.NumberColumn(
                        "Theoretical Wins",
                        help="The number of wins you WOULD have if you played every team, every week."
                    ),
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
    st.write("A composite score combining **Average Points** and **Consistency**.")
    
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

# === TAB 3: RIVALRY & RECORDS (NEW!) ===
with tab3:
    st.header("⚔️ League Records & Superlatives")
    
    if not df_history.empty:
        # 1. CALCULATE SUPERLATIVES
        # Biggest Blowout
        df_history['Margin'] = abs(df_history['Score'] - df_history['Score'].shift(-1)) # Only works if rows are paired, let's do a safer way
        
        # We need to find the opponent score for every row to calculate margin correctly
        # Create a helper mapping
        # Since our df has two rows per game (Team A vs B, and B vs A), we can find margin easily
        # Actually, our fetch_all_weekly_scores already saves 'Score' and 'Opponent' but not 'Opponent Score'
        # Let's re-calculate Opponent Score by looking at the dataframe
        
        # Simple Superlatives
        high_score = df_history.loc[df_history['Score'].idxmax()]
        low_score = df_history.loc[df_history['Score'].idxmin()]
        
        # Calculate margins for "Heartbreak" and "Blowout"
        # We need to iterate carefully or merge
        # Quick hack: We know the structure is Team A, Team B in pairs usually, but let's be safe
        
        # Let's display the "Hall of Fame / Shame"
        col1, col2, col3 = st.columns(3)
        col1.metric("🚀 Season High", f"{high_score['Score']} pts", high_score['Team'])
        col2.metric("📉 Season Low", f"{low_score['Score']} pts", low_score['Team'])
        
        # Find "Heartbreak" (Highest score in a Loss)
        losses = df_history[df_history['Result'] == 'L']
        if not losses.empty:
            heartbreak = losses.loc[losses['Score'].idxmax()]
            col3.metric("💔 Heartbreak Award", f"{heartbreak['Score']} pts", f"{heartbreak['Team']} (Lost)")
            
        st.divider()

        # 2. HEAD TO HEAD MATRIX
        st.subheader("Head-to-Head Matrix")
        st.write("Read **Row vs Column**. Green means the Row Team won.")
        
        # Create a matrix
        teams = sorted(df_history['Team'].unique())
        matrix = pd.DataFrame(index=teams, columns=teams).fillna("-")
        
        for team in teams:
            team_games = df_history[df_history['Team'] == team]
            for _, row in team_games.iterrows():
                opp = row['Opponent']
                result = row['Result']
                
                # We want to record W or L
                # If they played multiple times, we might want to show record (e.g. "2-0")
                # For now, let's just append the result
                current_val = matrix.at[team, opp]
                if current_val == "-":
                    matrix.at[team, opp] = result
                else:
                    matrix.at[team, opp] += f", {result}"
        
        # Display the matrix
        st.dataframe(matrix, use_container_width=True)

# === TAB 4: RAW DATA ===
with tab4:
    st.subheader("Raw Data Inspector")
    st.dataframe(df_history, use_container_width=True)