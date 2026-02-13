import streamlit as st
import sqlite3
import pandas as pd
import ccxt
import time
import concurrent.futures
import uuid
import json

import sys
import os

# Add monitoring_bot to path for Strategy imports
sys.path.append(os.path.join(os.getcwd(), 'monitoring_bot'))
from strategy import Strategy

# Page Config
st.set_page_config(page_title="Crypto-Trader", layout="wide", page_icon="🦂", initial_sidebar_state="expanded")

# Initialize Strategy Engine for UI use
strategy_engine = Strategy()

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
    
    /* Buttons */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
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

    /* Start Trading Button */
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

    /* Trend Badge Styling */
    .trend-badge {
        padding: 2px 10px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 0.85em;
        text-transform: uppercase;
        display: inline-block;
        margin: 2px;
    }
    .trend-up { background-color: #052e16; color: #4ade80; border: 1px solid #14532d; }
    .trend-down { background-color: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
    .trend-neutral { background-color: #1e1b4b; color: #818cf8; border: 1px solid #312e81; }
    
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

# Register Instance in DB
def register_instance(config, pairs_list):
    try:
        conn = get_connection()
        if not conn: return False
        
        # Ensure table exists (also in main.py but good to have here)
        conn.execute('''CREATE TABLE IF NOT EXISTS instances (
            id TEXT PRIMARY KEY, name TEXT, exchange TEXT, base_currency TEXT, 
            market_type TEXT, strategy_config TEXT, pairs TEXT, 
            status TEXT DEFAULT 'STOPPED', created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        instance_id = str(uuid.uuid4())[:8]
        name = f"{config['exchange']}_{config['market_type']}_{instance_id}"
        
        conn.execute(
            "INSERT INTO instances (id, name, exchange, base_currency, market_type, strategy_config, pairs, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                instance_id,
                name,
                config['exchange'],
                config['base_currency'],
                config['market_type'],
                json.dumps(config['strategy']),
                json.dumps(pairs_list),
                'ACTIVE'
            )
        )
        conn.commit()
        conn.close()
        return name
    except Exception as e:
        st.error(f"Failed to register instance: {e}")
        return False

# OPTIMIZED: Fetch Top Gainers/Losers
@st.cache_data(ttl=120)
def get_market_movers(exchange_id):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'timeout': 5000, 'enableRateLimit': True})
        tickers = exchange.fetch_tickers()
        pairs = []
        for symbol, data in tickers.items():
            if '/USDT' in symbol and data['percentage'] is not None:
                pairs.append({
                    'Symbol': symbol,
                    'Price': data['last'],
                    'Change %': data['percentage']
                })
        df = pd.DataFrame(pairs)
        if df.empty: return pd.DataFrame(), pd.DataFrame()
        df = df.sort_values(by='Change %', ascending=False)
        return df.head(10), df.tail(10).sort_values(by='Change %', ascending=True)
    except Exception: return pd.DataFrame(), pd.DataFrame()

# OPTIMIZED: Fetch Top Pairs
@st.cache_data(ttl=300)
def get_top_pairs(exchange_id, market_type, base_currency):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'timeout': 15000, 'enableRateLimit': True})
        markets = exchange.load_markets()
        STABLECOINS = {'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'FDUSD', 'USDE', 'USDP', 'PYUSD', 'EUR', 'USD'}
        target_symbols = []
        for symbol, market in markets.items():
             if market['quote'] != base_currency: continue
             if market['base'] in STABLECOINS: continue
             if market_type == 'Spot' and not market.get('spot', False): continue
             if market_type == 'Futures' and not (market.get('future', False) or market.get('swap', False)): continue
             if not market.get('active', True): continue
             target_symbols.append(symbol)

        try:
             tickers = exchange.fetch_tickers(target_symbols) if len(target_symbols) > 0 else {}
        except:
             tickers = exchange.fetch_tickers()

        data = []
        for symbol in target_symbols:
            if symbol in tickers:
                t = tickers[symbol]
                vol = t['quoteVolume'] if t.get('quoteVolume') else (t['baseVolume'] * t['last'] if t.get('baseVolume') and t.get('last') else 0)
                data.append({
                    'Select': False,
                    'Symbol': symbol,
                    'Price': t['last'],
                    'Volume': vol,
                    'Change 24h %': t['percentage']
                })
        df = pd.DataFrame(data)
        if not df.empty: df = df.sort_values(by='Volume', ascending=False).head(100)
        return df
    except Exception: return pd.DataFrame()

# Initialize Session State Navigation
if 'page' not in st.session_state: st.session_state.page = "Home"

def navigate_to(page_name):
    st.session_state.page = page_name
    st.rerun()

# Sidebar Navigation
with st.sidebar:
    st.title("🦂 Crypto-Trader")
    st.markdown("---")
    selected_page = st.radio("Navigation", ["Home", "Strategy Builder", "Live Monitor", "Post-Trade Review", "Settings"], index=["Home", "Strategy Builder", "Live Monitor", "Post-Trade Review", "Settings"].index(st.session_state.page))
    if selected_page != st.session_state.page:
        st.session_state.page = selected_page
        st.rerun()

# --- PAGE ROUTING ---

if st.session_state.page == "Home":
    st.title("Crypto-Trader Dashboard")
    st.markdown("**Autonomous. Modular. Intelligent.** Select an exchange below to view live market movers.")
    st.markdown("---")
    if 'selected_exchange' not in st.session_state: st.session_state.selected_exchange = "binance"
    col1, col2, col3 = st.columns(3)
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
    st.markdown(f"### Market Movers: {selected_exchange.capitalize()}")
    
    with st.spinner(f"Fetching live data from {selected_exchange}..."):
        gainers, losers = get_market_movers(selected_exchange)
        
    if not gainers.empty:
        col_gain, col_loss = st.columns(2)
        with col_gain:
            st.markdown("#### 🚀 Top 10 Gainers (24h)")
            st.dataframe(gainers.style.format({'Price': '${:.4f}', 'Change %': '{:+.2f}%'}).background_gradient(subset=['Change %'], cmap='Greens'), use_container_width=True, hide_index=True)
        with col_loss:
            st.markdown("#### 🔻 Top 10 Losers (24h)")
            st.dataframe(losers.style.format({'Price': '${:.4f}', 'Change %': '{:+.2f}%'}).background_gradient(subset=['Change %'], cmap='Reds_r'), use_container_width=True, hide_index=True)
    else:
        st.error(f"⚠️ Could not fetch market data for {selected_exchange}.")

    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown('<div class="start-trading-btn">', unsafe_allow_html=True)
        if st.button("🚀 Start Trading", use_container_width=True): navigate_to("Strategy Builder")
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.page == "Strategy Builder":
    st.title("🧩 Strategy Builder")
    st.markdown("Configure your autonomous agent parameters.")
    
    if 'watchlist' not in st.session_state:
        st.session_state.watchlist = pd.DataFrame(columns=['Symbol', 'Price', 'Volume', 'Change 24h %'])

    # Layout: Left (Market Data) - Right (Strategy Panel)
    col_left, col_right = st.columns([2, 1])

    # --- LEFT PANEL: Market Data ---
    with col_left:
        # 1. Configuration Controls
        with st.container():
            c1, c2, c3 = st.columns(3)
            with c1: strat_exchange = st.selectbox("Exchange", ["binance", "kucoin", "gateio"], index=0)
            with c2: base_currency = st.selectbox("Base Currency", ["USDT", "USDC", "BTC", "ETH"], index=0)
            with c3: market_type = st.radio("Market Type", ["Spot", "Futures"], horizontal=True)

        st.markdown("---")
        
        # 2. Fetch Pairs Data
        st.subheader(f"Top 100 {market_type} Pairs ({base_currency})")
        with st.spinner("Scanning market data..."):
            pairs_df = get_top_pairs(strat_exchange, market_type, base_currency)
            
        if not pairs_df.empty:
            search_query = st.text_input("🔍 Search Token", placeholder="e.g., BTC, ETH, SOL")
            filtered_df = pairs_df[pairs_df['Symbol'].str.contains(search_query.upper())] if search_query else pairs_df

            if 'show_all_pairs' not in st.session_state: st.session_state.show_all_pairs = False
            display_limit = 20 if not st.session_state.show_all_pairs else 100
            
            # Prepare Data for Editor
            editor_df = filtered_df.head(display_limit).copy()
            cols = ['Select'] + [c for c in editor_df.columns if c != 'Select']
            editor_df = editor_df[cols]

            edited_df = st.data_editor(
                editor_df,
                hide_index=True,
                column_config={
                    "Select": st.column_config.CheckboxColumn("Add", default=False),
                    "Price": st.column_config.NumberColumn(format="$%.4f"),
                    "Volume": st.column_config.NumberColumn(format="$%.0f"),
                    "Change 24h %": st.column_config.NumberColumn(format="%.2f%%"),
                },
                disabled=["Symbol", "Price", "Volume", "Change 24h %"],
                use_container_width=True
            )
            
            selected_rows = edited_df[edited_df.Select]
            if not selected_rows.empty:
                new_picks = selected_rows.drop(columns=['Select'])
                combined = pd.concat([st.session_state.watchlist, new_picks])
                st.session_state.watchlist = combined.drop_duplicates(subset=['Symbol'])

            if len(filtered_df) > 20 and not st.session_state.show_all_pairs:
                if st.button(f"Show All {len(filtered_df)} Pairs"):
                    st.session_state.show_all_pairs = True
                    st.rerun()
            elif st.session_state.show_all_pairs:
                if st.button("Show Less"):
                    st.session_state.show_all_pairs = False
                    st.rerun()
        else:
            st.warning("No pairs found.")

        # Watchlist Section
        st.markdown("---")
        st.subheader("📋 Your Watchlist (Selected Pairs)")
        if not st.session_state.watchlist.empty:
            watchlist_editor = st.data_editor(
                st.session_state.watchlist,
                hide_index=True,
                column_config={"Price": st.column_config.NumberColumn(format="$%.4f")},
                disabled=["Symbol", "Price", "Volume", "Change 24h %"],
                use_container_width=True,
                key="watchlist_editor",
                num_rows="dynamic"
            )
            if not watchlist_editor.equals(st.session_state.watchlist):
                 st.session_state.watchlist = watchlist_editor
                 st.rerun()
            if st.button("🗑️ Clear Watchlist"):
                st.session_state.watchlist = pd.DataFrame(columns=['Symbol', 'Price', 'Volume', 'Change 24h %'])
                st.rerun()
        else:
            st.info("No pairs selected.")

    # --- RIGHT PANEL: Strategy Settings ---
    with col_right:
        st.markdown("### ⚙️ Strategy Settings")
        
        with st.container(border=True):
            st.subheader("💰 User Account")
            # Account Balance (Mocked for now, editable)
            user_account = st.number_input("Total Balance (USDT)", value=1000.0, step=100.0)
            
            st.subheader("🚀 Position Sizing")
            start_amount = st.number_input("Starting Amount (USDT)", min_value=10.0, value=100.0, step=10.0)
            liquidity = st.number_input("Liquidity Pool (USDT)", min_value=0.0, value=500.0, step=50.0)
            
            st.markdown("---")
            st.subheader("📊 Trading Levels (Martingale)")
            
            # Dynamic Levels
            max_levels = st.number_input("Max Levels", min_value=1, max_value=10, value=5, step=1)
            
            # Generate inputs based on max_levels
            levels = []
            for i in range(1, max_levels + 1):
                default_val = float(i * 100) # 100, 200, 300...
                lvl_val = st.number_input(f"Level {i} ($)", value=default_val, step=10.0, key=f"level_{i}")
                levels.append(lvl_val)
            
            st.markdown("#### 🛡️ Safe Levels")
            # Safe Level 1 (Default 80, Max = Level 1 value)
            sl1_max = levels[0] if levels else 100.0
            sl1 = st.number_input("SLevel 1 ($)", value=min(80.0, sl1_max), max_value=sl1_max, step=10.0)
            
            # Safe Level 2 (Default 60, Max = SLevel 1 value)
            sl2 = st.number_input("SLevel 2 ($)", value=min(60.0, sl1), max_value=sl1, step=10.0)
            
            st.markdown("---")
            st.subheader("⚖️ Risk Management")
            max_open_trades = st.number_input("Max Open Trades", min_value=1, value=5)
            
            risk_val = st.number_input("Risk Factor", value=1.0, step=0.1)
            reward_val = st.number_input("Reward Factor", value=3.0, step=0.1)
            st.caption(f"Risk:Reward Ratio = {risk_val}:{reward_val}")
            
            risk_per_trade = st.number_input("Risk Per Trade (%)", min_value=0.1, max_value=100.0, value=2.0, step=0.1)
            
            st.markdown("---")
            st.subheader("⏱️ Timeframes")
            tf_small = st.selectbox("Small TF", ["15m", "30m", "1h", "4h"], index=0)
            tf_medium = st.selectbox("Medium TF", ["30m", "1h", "4h", "1d"], index=2)
            tf_large = st.selectbox("Large TF", ["1h", "4h", "1d", "1w"], index=2)
            
            st.markdown("---")
            
            # Button Action
            if st.button("🚀 START INSTANCE", type="primary", use_container_width=True):
                # 1. Validate
                if st.session_state.watchlist.empty:
                    st.error("Please add pairs to your watchlist first!")
                else:
                    # 2. Build Config
                    config = {
                        "exchange": strat_exchange,
                        "base_currency": base_currency,
                        "market_type": market_type,
                        "strategy": {
                            "user_account": user_account,
                            "start_amount": start_amount,
                            "liquidity": liquidity,
                            "levels": levels,
                            "safe_levels": [sl1, sl2],
                            "risk": {"max_trades": max_open_trades, "rr": f"{risk_val}:{reward_val}", "pct": risk_per_trade},
                            "timeframes": [tf_small, tf_medium, tf_large]
                        }
                    }
                    
                    pairs_list = st.session_state.watchlist['Symbol'].tolist()
                    
                    # 3. Register Instance
                    instance_name = register_instance(config, pairs_list)
                    
                    if instance_name:
                        st.balloons()
                        st.success(f"Instance '{instance_name}' successfully launched! Monitoring {len(pairs_list)} pairs.")
                        # Clear watchlist after launch
                        st.session_state.watchlist = pd.DataFrame(columns=['Symbol', 'Price', 'Volume', 'Change 24h %'])
                        time.sleep(2)
                        navigate_to("Live Monitor") # Go to monitor

elif st.session_state.page == "Live Monitor":
    st.title("🔴 Live Monitor")
    
    conn = get_connection()
    # Also connect to candles for trend data
    c_conn = sqlite3.connect("candles.db")
    
    if conn:
        try:
            # Fetch Instances (exclude DELETED)
            df_instances = pd.read_sql("SELECT * FROM instances WHERE status != 'DELETED' ORDER BY created_at DESC", conn)
            
            if not df_instances.empty:
                st.subheader("Running Instances")
                
                for _, row in df_instances.iterrows():
                    with st.expander(f"🐝 {row['name']} ({row['status']})", expanded=True):
                        # --- ROW 1: Symmetrical Metrics ---
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("Exchange", row['exchange'].capitalize())
                        m2.metric("Market Type", row['market_type'])
                        
                        # Data placeholders (Fetch from ROI/State tables when logic implemented)
                        try:
                            state_df = pd.read_sql("SELECT current_level FROM instance_state WHERE id = ?", conn, params=(row['id'],))
                            current_level = state_df['current_level'].iloc[0] if not state_df.empty else "N/A"
                        except: current_level = "N/A"
                        
                        try:
                            trades_df = pd.read_sql("SELECT COUNT(*) as count, SUM(pnl) as total_pnl FROM trades WHERE instance_id = ?", conn, params=(row['id'],))
                            trades_count = trades_df['count'].iloc[0]
                            total_pnl = trades_df['total_pnl'].iloc[0] or 0.0
                            # ROI Calc: Simple placeholder (assuming start capital is first level or 1000)
                            roi = round((total_pnl / 1000) * 100, 2)
                        except: 
                            trades_count = 0
                            roi = 0.0

                        m3.metric("Current Level", current_level)
                        m4.metric("Trades / ROI", f"{trades_count} / {roi}%")
                        
                        # --- ROW 2: Pairs & Trends ---
                        st.markdown("#### 📊 Pairs Activity & Trends")
                        pairs = json.loads(row['pairs'])
                        config = json.loads(row['strategy_config'])
                        # If timeframes key is nested under strategy or top-level
                        tfs = config.get('timeframes', config.get('strategy', {}).get('timeframes', []))
                        
                        for p in pairs:
                            # 1.5 for symbol, remaining for TFs
                            p_cols = st.columns([1.5] + [1] * len(tfs))
                            p_cols[0].markdown(f"**{p}**")
                            
                            for i, tf in enumerate(tfs):
                                # Fetch recent candles to calc trend
                                candle_query = "SELECT * FROM candles WHERE instance_id=? AND symbol=? AND timeframe=? ORDER BY timestamp DESC LIMIT 250"
                                c_df = pd.read_sql(candle_query, c_conn, params=(row['id'], p, tf))
                                
                                trend_html = '<span class="trend-badge trend-neutral">SYNCING</span>'
                                if not c_df.empty:
                                    try:
                                        # Calculate indicators on current window
                                        df_ind = strategy_engine.calculate_indicators(c_df.sort_values('timestamp'))
                                        trend = strategy_engine.get_row_trend(df_ind.iloc[-1])
                                        if trend == 'UP': trend_html = f'<span class="trend-badge trend-up">▲ {tf} UP</span>'
                                        elif trend == 'DOWN': trend_html = f'<span class="trend-badge trend-down">▼ {tf} DOWN</span>'
                                        else: trend_html = f'<span class="trend-badge trend-neutral">● {tf} NEUTRAL</span>'
                                    except: pass
                                p_cols[i+1].markdown(trend_html, unsafe_allow_html=True)
                        
                        # --- ROW 3: Symmetrical Buttons ---
                        st.markdown("---")
                        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
                        with col_btn1:
                            if row['status'] == 'ACTIVE':
                                if st.button("Stop Instance", key=f"stop_{row['id']}"):
                                    conn.execute("UPDATE instances SET status='STOPPED' WHERE id=?", (row['id'],))
                                    conn.commit()
                                    st.rerun()
                            elif row['status'] == 'STOPPED':
                                if st.button("Restart Instance", key=f"start_{row['id']}"):
                                    conn.execute("UPDATE instances SET status='ACTIVE' WHERE id=?", (row['id'],))
                                    conn.commit()
                                    st.rerun()
                        with col_btn3:
                            if st.button("Delete Instance", key=f"delete_{row['id']}", type="secondary"):
                                conn.execute("UPDATE instances SET status='DELETED' WHERE id=?", (row['id'],))
                                conn.commit()
                                st.warning(f"Instance {row['id']} marked for deletion.")
                                st.rerun()
            else:
                st.info("No active instances. Go to Strategy Builder to launch one.")
        except Exception as e:
            st.error(f"Error loading instances: {e}")
        conn.close()
        c_conn.close()

elif st.session_state.page == "Post-Trade Review":
    st.title("📝 Review")
    st.info("Construction")

elif st.session_state.page == "Settings":
    st.title("⚙️ Settings")
    st.button("Kill Switch")
