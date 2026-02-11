# Crypto-Trader: Installation & Execution Guide

Since the environment lacks Docker, the system must be run manually using a Python virtual environment.

## 1. Prerequisites
* Python 3.12+
* `python3-venv` package installed

## 2. Installation

1. **Create a Virtual Environment:**
   ```bash
   python3 -m venv venv
   ```

2. **Activate & Install Dependencies:**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## 3. Running the System

You need to run four separate processes. It is recommended to run these in separate terminal tabs or use `nohup`/`tmux`.

### Step 1: Trading Bot (Port 8001)
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/trading_bot
venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8001
```

### Step 2: Analyze Agent (Port 8000)
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/analyze_agent
venv/bin/python -m uvicorn api:app --host 0.0.0.0 --port 8000
```

### Step 3: Monitoring Bot
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/monitoring_bot
venv/bin/python monitoring_bot/main.py
```

### Step 4: Dashboard (Port 8501)
```bash
venv/bin/streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0
```

## 4. Accessing the UI
* **Direct Access:** http://<your-ip>:8501 (Ensure Port 8501 is open in your firewall/Security Group).
* **SSH Tunnel (Safe):** 
  Run this on your local machine:
  `ssh -L 8501:localhost:8501 ubuntu@<your-ip>`
  Then open http://localhost:8501 in your browser.
