from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from execution_engine import create_engine

app = FastAPI(title="Trading Bot Execution Engine")
engine = create_engine()

class TradeSignal(BaseModel):
    symbol: str
    side: str
    price: float
    reason: str
    agent_decision: str

@app.post("/trade")
async def execute_trade(signal: TradeSignal):
    """
    Receives APPROVED signal from Analyze Agent.
    """
    if signal.agent_decision != "APPROVE":
        raise HTTPException(status_code=400, detail="Only approved signals are executed.")
    
    try:
        result = engine.execute_trade(signal.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def status():
    return {
        "capital": engine.current_capital,
        "level": engine.level,
        "kill_switch": engine.kill_switch_active
    }
