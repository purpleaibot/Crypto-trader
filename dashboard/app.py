import streamlit as st
import sqlite3
import pandas as pd
import time

# Page Config
st.set_page_config(page_title="Crypto-Trader Dashboard", layout="wide", page_icon="📈")

# Database Connection
DB_PATH = "/data/trades.db"

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to DB: {e}")
        return None

# Sidebar
st.sidebar.title("🤖 Crypto-Trader")
st.sidebar.info("Autonomous Trading System")
menu = st.sidebar.radio("Navigation", ["Overview", "Live Monitor", "Post-Trade Review", "Settings"])

if menu == "Overview":
    st.title("📊 System Overview")
    
    conn = get_connection()
    if conn:
        # Get Latest State
        try:
            state_df = pd.read_sql("SELECT * FROM instance_state ORDER BY updated_at DESC LIMIT 1", conn)
            
            col1, col2, col3 = st.columns(3)
            if not state_df.empty:
                current_capital = state_df.iloc[0]['total_capital']
                current_level = state_df.iloc[0]['current_level']
                col1.metric("Total Equity", f"${current_capital:.2f}")
                col2.metric("Current Level", current_level)
                col3.metric("Status", "Active", delta_color="normal")
            else:
                col1.metric("Total Equity", "N/A")
                col2.metric("Current Level", "N/A")
        except:
            st.warning("No state data available yet.")
            
        st.markdown("### Recent Activity")
        try:
            trades_df = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10", conn)
            st.dataframe(trades_df)
        except:
            st.info("No trades recorded yet.")
            
        conn.close()

elif menu == "Live Monitor":
    st.title("🔴 Live Monitor")
    st.markdown("Watching for signals... (Refreshes every 10s)")
    
    # Placeholder for live chart (requires InfluxDB connection here or simple mocked chart)
    st.info("Live Charting Module Coming Soon (Phase 4)")
    
    if st.button("Refresh"):
        st.experimental_rerun()

elif menu == "Post-Trade Review":
    st.title("📝 Post-Trade Analysis (NanoClaw Training)")
    
    conn = get_connection()
    if conn:
        trades_df = pd.read_sql("SELECT * FROM trades WHERE status='CLOSED' OR status='OPEN'", conn)
        
        if not trades_df.empty:
            trade_id = st.selectbox("Select Trade to Review", trades_df['id'])
            
            trade = trades_df[trades_df['id'] == trade_id].iloc[0]
            
            st.markdown(f"**Symbol:** {trade['symbol']} | **Side:** {trade['side']} | **PnL:** ${trade['pnl']}")
            st.text_area("Agent Reasoning", value=trade.get('agent_notes', 'No notes'), disabled=True)
            
            st.subheader("Grade the Agent")
            grade = st.radio("Was this a good trade?", ["👍 Good", "👎 Bad"])
            user_notes = st.text_area("Your Notes (Teach NanoClaw)")
            
            if st.button("Submit Feedback"):
                # TODO: Update DB with feedback
                st.success("Feedback saved! NanoClaw will learn from this.")
        else:
            st.info("No trades available for review.")
            
        conn.close()

elif menu == "Settings":
    st.title("⚙️ Settings")
    
    st.subheader("Risk Management")
    risk = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0)
    
    st.subheader("Emergency")
    st.error("⚠️ KILL SWITCH: Halts all trading immediately.")
    if st.button("ACTIVATE KILL SWITCH"):
        st.stop()
