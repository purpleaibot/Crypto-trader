from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from agent import create_agent
from tools.basic_tools import web_search_tool, crypto_api_tool

app = FastAPI(title="NanoClaw Analyze Agent")

# Initialize Agent
agent = create_agent()
agent.register_tool("web_search", web_search_tool)
agent.register_tool("crypto_api", crypto_api_tool)

class SignalRequest(BaseModel):
    symbol: str
    timeframe: str
    signal_type: str # BUY/SELL
    price: float
    indicators: dict
    trend: str

@app.post("/analyze")
async def analyze_signal(signal: SignalRequest):
    """
    Endpoint for Monitoring Bot to send signals.
    """
    try:
        decision = agent.analyze_signal(signal.dict())
        return decision
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "active", "model": agent.model_name}
