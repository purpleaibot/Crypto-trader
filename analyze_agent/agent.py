import os
import json
import logging
import requests
from typing import Dict, Any

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NanoClaw")

TRADING_BOT_URL = "http://trading-bot:8001/trade"

class AnalyzeAgent:
    def __init__(self, model_name="claude-3-sonnet"):
        self.model_name = model_name
        self.memory = [] # Simple ephemeral memory for V1
        self.tools = {}
        logger.info(f"NanoClaw Agent initialized with model: {model_name}")

    def register_tool(self, name, func):
        self.tools[name] = func
        logger.info(f"Tool registered: {name}")

    def analyze_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Receives signal from Monitoring Bot.
        """
        logger.info(f"Received Signal: {signal_data}")
        
        # 1. Gather Context (News, Sentiment, Fundamentals)
        context = self._gather_context(signal_data['symbol'])
        
        # 2. Reasoning (LLM Simulation for now, connection later)
        decision = self._reasoning_engine(signal_data, context)
        
        # 3. Execution Trigger (If Approved)
        if decision['decision'] == "APPROVE":
            self._trigger_execution(signal_data, decision)
            
        # 4. Output
        return decision

    def _trigger_execution(self, signal_data, decision):
        """
        Sends the approved signal to the Trading Bot for execution.
        """
        logger.info(">>> Signal APPROVED. Triggering Trading Bot...")
        payload = {
            "symbol": signal_data['symbol'],
            "side": signal_data['signal_type'], # BUY/SELL
            "price": float(signal_data['price']),
            "reason": decision['reasoning'],
            "agent_decision": decision['decision']
        }
        
        try:
            response = requests.post(TRADING_BOT_URL, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Trading Bot Response: {response.json()}")
            else:
                logger.error(f"Trading Bot Error: {response.text}")
        except Exception as e:
            logger.error(f"Failed to reach Trading Bot: {e}")

    def _gather_context(self, symbol):
        """
        Uses registered tools to find info.
        """
        context = {}
        if "web_search" in self.tools:
            context['news'] = self.tools["web_search"](f"latest news {symbol} crypto")
        
        if "crypto_api" in self.tools:
            context['price_data'] = self.tools["crypto_api"](symbol)
            
        return context

    def _reasoning_engine(self, signal, context):
        """
        The Brain. This will eventually call the actual LLM API.
        For V1 YOLO test, we use a heuristic mock.
        """
        logger.info("Thinking...")
        
        # Mock Logic: If we found "news" (simulated), we approve.
        # In production, this sends a prompt to GPT/Claude.
        
        sentiment_score = 0
        if context.get('news'):
            # Fake sentiment analysis
            sentiment_score = 5 
        
        decision = {
            "decision": "APPROVE" if sentiment_score >= 0 else "REJECT",
            "confidence": 0.85,
            "reasoning": f"Trend is {signal.get('trend', 'UNKNOWN')}. News sentiment seems neutral/positive. Market structure looks okay."
        }
        
        logger.info(f"Decision: {decision['decision']}")
        return decision

# Factory for easy instantiation
def create_agent():
    return AnalyzeAgent()
