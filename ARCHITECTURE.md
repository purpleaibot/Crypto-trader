# System Architecture

## Overview
The system follows a **Event-Driven Hive Architecture**.

```mermaid
graph TD
    UI[Streamlit Dashboard] -->|Writes Config| DB[(SQLite DB)]
    UI -->|Reads Status| DB
    
    Hive[Hive Engine (Monitoring Bot)] -->|Reads Config| DB
    Hive -->|Fetches Data| Exchanges[Binance/KuCoin/Gate]
    
    Hive -->|Signal Detected| Agent[Analyze Agent API]
    Agent -->|Validation| LLM[LLM / Tools]
    
    Agent -->|Approved| Trader[Trading Bot API]
    Trader -->|Execute Order| Exchanges
    Trader -->|Log Trade| DB
```

## Components

### 1. The Hive Engine (Monitoring Bot)
*   **Role:** The heartbeat of the system.
*   **Behavior:** 
    *   Loads all `ACTIVE` instances from `instances` table.
    *   Iterates through each instance's `pairs` list.
    *   Fetches market data (Optimized bulk fetch).
    *   Applies Technical Analysis (TA).
    *   Triggers the Agent if conditions are met.
*   **Scale:** Designed to handle 20+ instances and 2000+ pairs on a single 4GB RAM node.

### 2. Analyze Agent (NanoClaw)
*   **Role:** Trade Validator.
*   **Input:** Signal (Symbol, Price, Type, Trend).
*   **Process:** Checks news, sentiment, and market structure.
*   **Output:** `APPROVE` or `REJECT`.

### 3. Trading Bot (Executioner)
*   **Role:** Order Router.
*   **Input:** Approved Signal + Instance ID.
*   **Process:** Looks up API keys for the specific Instance and places the order.

### 4. Database Schema
*   `instances`: Stores configuration, watchlist, and status.
*   `trades`: Stores trade history linked to `instance_id`.
*   `candles`: Local cache of OHLCV data to reduce API calls.
