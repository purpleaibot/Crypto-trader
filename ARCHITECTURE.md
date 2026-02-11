# System Architecture - Crypto-Trader

## Overview
The system follows a microservices-inspired architecture, ensuring modularity, scalability, and fault tolerance.

## Components

### 1. Data Layer
*   **InfluxDB:** Stores high-frequency candle data.
*   **Relational DB (PostgreSQL/SQLite):** Stores User profiles, Instance configurations, Trade history (ROI), and Agent learning data.
*   **Redis (Optional):** Caching for real-time UI updates and inter-service messaging.

### 2. Service Layer
*   **Monitoring Service:**
    *   Runs scheduled jobs (Candle Fetch).
    *   Calculates Indicators (Pandas/TA-Lib).
    *   Manages Instance State (Levels).
*   **Analysis Service (NanoClaw):**
    *   Isolated Docker container.
    *   Interacts with LLM APIs.
    *   Performs Web Search.
*   **Execution Service:**
    *   Manages Exchange WebSocket connections for order updates.
    *   Executes Limit Orders via CCXT or direct API.

### 3. Interface Layer
*   **Web Dashboard:** Responsive frontend.
*   **Telegram Bot:** Push notifications and basic command control (e.g., `/stop`).

## Data Flow
1.  **Monitoring Bot** fetches candle -> Updates InfluxDB.
2.  **Monitoring Bot** runs strategy -> Detects Signal.
3.  **Monitoring Bot** sends Signal Context to **Analyze Agent**.
4.  **Analyze Agent** queries LLM + Web -> Returns Decision.
5.  If Approved: **Analyze Agent** sends Order Details to **Trading Bot**.
6.  **Trading Bot** places Limit Order -> Updates DB.
7.  **Trading Bot** monitors fill/TP/SL -> Updates DB on close.
8.  **Monitoring Bot** reads new PnL -> Adjusts Capital Level.

## Security
*   **API Keys:** Encrypted at rest.
*   **Sandboxing:** Analyze Agent runs with restricted network access (allowlist).
*   **Kill Switch:** Hard-coded logic in Execution Service to halt on equity breach.
