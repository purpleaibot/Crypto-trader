# Crypto-Trader (Hive Architecture)

An autonomous, modular cryptocurrency trading system designed for multi-instance scalability.

## 🐝 Hive Architecture (V2.1 - Total Isolation)
Unlike V1 (Process-per-Bot), V2 uses a "Hive" architecture to support scalability on limited resources, now featuring **Total Data Isolation**:

*   **Isolated Candle Storage:** `candles.db` uses a composite index of `instance_id` + `symbol` + `timeframe`. This ensures that multiple instances watching the same pair never collide or overwrite each other's data.
*   **Multi-Timeframe Engine:** The Hive Engine automatically syncs 500 historical candles for *every* configured timeframe (e.g., 15m, 1h, 4h, 1d) upon instance launch.
*   **Smart Sync:** Implements a strict 5-second post-close buffer to ensure only fully finalized candles are fetched from exchange APIs (Binance, KuCoin, Gate.io).
*   **Hive Engine (`monitoring_bot`):** A single optimized AsyncIO process that manages **multiple trading instances** simultaneously. It loops through active configurations in the database and processes signals for 100+ pairs per instance without spawning new processes.

*   **Analyze Agent (NanoClaw):** A centralized API service ("The Brain") that receives signals from the Hive, gathers context (News/Sentiment), and uses LLM logic to validate trades.
*   **Trading Bot:** A centralized execution service that routes orders to the correct exchange based on the Instance ID.
*   **Dashboard:** A Streamlit-based Command Center for building strategies, managing instances, and monitoring performance.

## Features
*   **Multi-Instance Support:** Run distinct strategies on Binance, KuCoin, and Gate.io simultaneously.
*   **Strategy Builder:** Visual interface to configure Martingale levels, Risk:Reward, and Timeframes.
*   **Watchlist Manager:** Select specific pairs (with Stablecoin filtering) to monitor.
*   **Live Monitor:** Real-time status of all active "Worker Bees" (Instances).

## Installation

1.  **Clone & Setup:**
    ```bash
    git clone https://github.com/purpleaibot/Crypto-trader.git
    cd Crypto-trader
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  **Run the Hive Stack:**
    The system requires 4 components running in parallel:
    *   `python monitoring_bot/main.py` (The Hive)
    *   `uvicorn analyze_agent.api:app` (The Brain)
    *   `uvicorn trading_bot.api:app` (The Executioner)
    *   `streamlit run dashboard/app.py` (The UI)

## Usage
1.  Open Dashboard (`localhost:8501`).
2.  Go to **Strategy Builder**.
3.  Select Exchange & Base Currency.
4.  Build your **Watchlist** (Tick pairs).
5.  Configure **Strategy** (Levels, Risk).
6.  Click **Start Instance**.
7.  Monitor progress in the **Live Monitor** tab.
