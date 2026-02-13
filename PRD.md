# Product Requirements Document (PRD) - Crypto-Trader

## 1. Executive Summary
Crypto-Trader is an autonomous, three-part cryptocurrency trading system designed for conservative, controlled-risk trading on major exchanges (Binance, KuCoin, Gate.io). It features a modular architecture consisting of a Monitoring Bot (Market Scanner), an Analyze Agent (NanoClaw - LLM-powered validation), and a Trading Bot (Execution Engine). The system prioritizes capital preservation, user-defined risk levels, and transparent post-trade analysis.

## 2. System Architecture

### Part 1: Monitoring Bot (The "Eyes")
*   **Role:** Market scanning, capital management, signal generation.
*   **Data Source:** Public Exchange APIs (Binance, KuCoin, Gate.io). Fetch method: `Candle Close + 5s` (Polling) with "Smart API" (staggered) backup.
*   **Persistence:** 
    *   **Local Storage:** Isolated fetch of the last 500 CLOSED candles for each pair/timeframe stored in local SQLite (`candles.db`), indexed by `instance_id` to prevent data collision.
    *   **Synchronization:** Every time a candle closes, the bot fetches the new closed candle (with a 5s buffer) and appends it to the isolated instance dataset.
    *   **Validation:** Strict timestamp continuity check ("Option B") ensures candles are in correct chronological order with no gaps.
*   **Strategy:** Multi-timeframe trend following (EMA, ADX) + Momentum triggers (RSI, EMA cross).
    *   **Filters:** Volatility (ATR) and Spread checks are mandatory.
    *   **Signal:** Only sends to Analyze Agent if "3 Correct Signals" (Higher TF Trend + Lower TF Trigger) match.
*   **Capital Management:**
    *   **Instances:** Independent deployments with specific capital, pairs, and risk settings.
    *   **Levels:** Dynamic trading levels (Level 1-10, SLevel 1-2) based on *Instance Capital* (Start + Realized PnL).
    *   **Risk:** User-defined `Risk %` applied to the *Level Minimum*. `Reward` is a multiple based on R:R ratio.

### Part 2: Analyze Agent (The "Brain" - NanoClaw)
*   **Role:** Trade validation using LLM reasoning and external data.
*   **Core:** Lightweight `nanoclaw` framework (Python), Dockerized for safety.
*   **Inputs:** Validated signal from Monitoring Bot, Chart Screenshots, News/Sentiment (Web Search), Fundamentals.
*   **Output:** `APPROVE` or `REJECT` decision with reasoning.
*   **Learning:**
    *   **Post-Trade Review:** UI allows users to "Grade" (Thumbs Up/Down) and add Notes.
    *   **Training Mode:** Live visualization of historical/simulated trading for logic validation.

### Part 3: Trading Bot (The "Hands")
*   **Role:** Precise execution and position management.
*   **Execution:** **Limit Orders** for Entry, Stop Loss (SL), and Take Profit (TP).
*   **Features:**
    *   **Trailing Stop:** User-selectable "Move to Break Even" (Option A) or Fixed SL/TP (Option C).
    *   **Kill Switch:** Immediate liquidation of all positions if Instance Equity drops below user-defined threshold (e.g., 50%).
    *   **State Recovery:** Auto-sync with exchange on restart.
    *   **ROI Database:** Tracks realized PnL and updates Monitoring Bot's capital levels.

## 3. User Interface (UI) Requirements
*   **Platform:** Responsive Web Application (Mobile & Desktop compatible).
*   **Tech Stack:** Modern framework (e.g., Next.js/React or Streamlit) for scalability.
*   **Key Views:**
    *   **Dashboard:** Real-time view of active Instances, Open Trades, and Total Equity.
    *   **Deployment:** Wizard to configure new Instances (Capital, Levels, Pairs, Strategy).
    *   **Post-Trade Analysis:** List of closed trades with Agent reasoning, Chart snapshots, and Grading/Notes tools.
    *   **Settings:** API Keys, Notification preferences (Telegram), Kill Switch threshold.

## 4. Technical Requirements
*   **Language:** Python (primary for Bots), TypeScript/Python (for UI).
*   **Database:** InfluxDB (Candles), SQLite/PostgreSQL (User Data/ROI).
*   **Infrastructure:** Dockerized containers for each component.
*   **External APIs:** Exchange APIs, LLM Provider (Google/Anthropic/OpenAI), Search API (Brave/Google).
*   **Notification:** Telegram Bot integration for real-time alerts.

## 5. Roadmap
*   **Phase 1:** Core Architecture & Monitoring Bot (Data Fetch + Strategy).
*   **Phase 2:** Analyze Agent (NanoClaw) integration & LLM validation.
*   **Phase 3:** Trading Bot (Execution) & UI Dashboard.
*   **Phase 4:** Testing (Backtesting, Paper Trading) & Refinement.
