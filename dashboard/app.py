import streamlit as st
import sqlite3
import pandas as pd
import ccxt
import time

# Page Config
st.set_page_config(page_title="Crypto-Trader", layout="wide", page_icon="🦂", initial_sidebar_state="expanded")

# Custom CSS for Dark Mode & Modern Look
st.markdown("""
<style>
    /* Global Background */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Sidebar Background */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* Force Sidebar Text Color */
    .css-17lntkn {
        color: #C9D1D9 !important;
    }
    
    /* Exchange Buttons - Modern Tab Style */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        font-weight: 600;
        background-color: #21262D;
        color: #C9D1D9;
        border: 1px solid #30363D;
        transition: all 0.2s ease;
    }
    div.stButton > button:hover {
        border-color: #8B5CF6;
        color: #FFFFFF;
        background-color: #30363D;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    div.stButton > button:active, div.stButton > button:focus {
        background-color: #8B5CF6 !important;
        color: white !important;
        border-color: #8B5CF6 !important;
    }

    /* Start Trading Button (Custom Class for Emphasis) */
    .start-trading-btn > button {
        background-color: #8B5CF6 !important;
        color: white !important;
        border: none !important;
        height: 4em !important;
        font-size: 1.2em !important;
    }

    /* Headers */
    h1, h2, h3, h4 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: #F0F6FC;
    }
    
    /* Metrics Cards */
    div[data-testid="stMetric"] {
        background-color: #21262D;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363D;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    /* Table Styling */
    div[data-testid="stDataFrame"] {
        border: 1px solid #30363D;
        border-radius: 8px;
        background-color: #0D1117;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Database Connection
DB_PATH = "trades.db"

def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to DB: {e}")
        return None

# Helper: Fetch Top Gainers/Losers
@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_market_movers(exchange_id):
    try:
        # Initialize Exchange
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class()
        
        # Load Markets (Crucial for Public API access)
        tickers = exchange.fetch_tickers()
        
        # Filter for USDT pairs only to keep it clean
        pairs = []
        for symbol, data in tickers.items():
            if '/USDT' in symbol and data['percentage'] is not None:
                pairs.append({
                    'Symbol': symbol,
                    'Price': data['last'],
                    'Change %': data['percentage']
                })
        
        df = pd.DataFrame(pairs)
        
        if df.empty:
             return pd.DataFrame(), pd.DataFrame()

        # Top 10 Gainers
        gainers = df.sort_values(by='Change %', ascending=False).head(10)
        
        # Top 10 Losers
        losers = df.sort_values(by='Change %', ascending=True).head(10)
        
        return gainers, losers
    except Exception as e:
        # st.error(f"API Error ({exchange_id}): {str(e)}") # debug
        return pd.DataFrame(), pd.DataFrame()

# Initialize Session State Navigation
if 'page' not in st.session_state:
    st.session_state.page = "Home"

# Function to handle navigation
def navigate_to(page_name):
    st.session_state.page = page_name
    st.rerun()

# Sidebar Navigation (Manual Control to sync with button)
with st.sidebar:
    st.title("🦂 Crypto-Trader")
    st.markdown("---")
    
    # We use a callback to sync the radio button with session state
    selected_page = st.radio(
        "Navigation", 
        ["Home", "Strategy Builder", "Live Monitor", "Post-Trade Review", "Settings"],
        index=["Home", "Strategy Builder", "Live Monitor", "Post-Trade Review", "Settings"].index(st.session_state.page)
    )
    
    if selected_page != st.session_state.page:
        st.session_state.page = selected_page
        st.rerun()

# --- PAGE ROUTING ---

if st.session_state.page == "Home":
    # Hero Section
    st.title("Crypto-Trader Dashboard")
    st.markdown("""
    **Autonomous. Modular. Intelligent.**  
    Welcome to your command center. Select an exchange below to view live market movers.
    """)
    
    st.markdown("---")
    
    # Initialize Session State for Exchange
    if 'selected_exchange' not in st.session_state:
        st.session_state.selected_exchange = "binance"
    
    # Exchange Selection (Three Columns)
    st.subheader("📡 Exchange Markets")
    col1, col2, col3 = st.columns(3)
    
    # Styling Hack: Use emojis to indicate selection
    b_label = "🔶 Binance " + ("✅" if st.session_state.selected_exchange == "binance" else "")
    k_label = "🟩 KuCoin " + ("✅" if st.session_state.selected_exchange == "kucoin" else "")
    g_label = "🚪 Gate.io " + ("✅" if st.session_state.selected_exchange == "gateio" else "")

    with col1:
        if st.button(b_label, key="btn_binance"):
            st.session_state.selected_exchange = "binance"
            st.rerun()
            
    with col2:
        if st.button(k_label, key="btn_kucoin"):
            st.session_state.selected_exchange = "kucoin"
            st.rerun()
            
    with col3:
        if st.button(g_label, key="btn_gateio"):
            st.session_state.selected_exchange = "gateio"
            st.rerun()
            
    selected_exchange = st.session_state.selected_exchange

    # Display Market Data
    st.markdown(f"### Market Movers: {selected_exchange.capitalize()}")
    
    with st.spinner(f"Fetching live data from {selected_exchange}..."):
        gainers, losers = get_market_movers(selected_exchange)
        
    if not gainers.empty:
        col_gain, col_loss = st.columns(2)
        
        with col_gain:
            st.markdown("#### 🚀 Top 10 Gainers (24h)")
            st.dataframe(
                gainers.style.format({'Price': '${:.4f}', 'Change %': '{:+.2f}%'})
                .background_gradient(subset=['Change %'], cmap='Greens'),
                use_container_width=True,
                hide_index=True
            )
            
        with col_loss:
            st.markdown("#### 🔻 Top 10 Losers (24h)")
            st.dataframe(
                losers.style.format({'Price': '${:.4f}', 'Change %': '{:+.2f}%'})
                .background_gradient(subset=['Change %'], cmap='Reds_r'),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.error(f"⚠️ Could not fetch market data for {selected_exchange}. The API might be rate-limited or the exchange is unreachable.")

    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Centered "Start Trading" Button
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown('<div class="start-trading-btn">', unsafe_allow_html=True)
        if st.button("🚀 Start Trading", use_container_width=True):
            navigate_to("Strategy Builder")
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == "Strategy Builder": # Renamed from Overview
    st.title("🧩 Strategy Builder")
    st.info("Configure your autonomous trading agent here.")
    
    conn = get_connection()
    if conn:
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
        except Exception:
            st.info("No active session data found.")
            
        st.markdown("### Recent Activity")
        try:
            trades_df = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10", conn)
            st.dataframe(trades_df, use_container_width=True)
        except Exception:
            st.info("No trades recorded yet.")
        conn.close()

elif st.session_state.page == "Live Monitor":
    st.title("🔴 Live Monitor")
    st.info("Real-time charting module is under construction.")

elif st.session_state.page == "Post-Trade Review":
    st.title("📝 Post-Trade Analysis")
    conn = get_connection()
    if conn:
        trades_df = pd.read_sql("SELECT * FROM trades WHERE status='CLOSED' OR status='OPEN'", conn)
        if not trades_df.empty:
            trade_id = st.selectbox("Select Trade", trades_df['id'])
            trade = trades_df[trades_df['id'] == trade_id].iloc[0]
            st.write(trade)
        else:
            st.info("No trades to review.")
        conn.close()

elif st.session_state.page == "Settings":
    st.title("⚙️ Settings")
    st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0)
    if st.button("ACTIVATE KILL SWITCH", type="primary"):
        st.stop()
