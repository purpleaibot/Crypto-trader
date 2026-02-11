import ccxt
import time
import logging
from config import Config
from db_manager import DBManager

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingBot")

class ExecutionEngine:
    def __init__(self, exchange_id='binance'):
        self.exchange = getattr(ccxt, exchange_id)()
        self.db = DBManager()
        self.current_capital = 150 # Start amount (simulated)
        self.level = "Level1"
        self.kill_switch_active = False

    def check_kill_switch(self):
        """
        Safety Check: If capital drops below threshold, STOP.
        """
        if self.current_capital < 50: # Example Threshold
            self.kill_switch_active = True
            logger.critical("KILL SWITCH ACTIVE: Capital < 50 USDT. Halting.")
            return True
        return False

    def execute_trade(self, signal):
        """
        Receives Approved Signal -> Places Limit Order -> Updates DB.
        """
        if self.check_kill_switch():
            return {"status": "HALTED", "reason": "Kill Switch Active"}

        symbol = signal['symbol']
        side = signal['side'].lower() # buy/sell
        price = signal['price']
        amount = 0.001 # TODO: Calculate position size based on Risk/Level

        logger.info(f"Executing {side.upper()} Limit Order for {symbol} at {price}")

        try:
            # REAL EXECUTION (Commented out for safety in V1)
            # order = self.exchange.create_limit_order(symbol, side, amount, price)
            
            # SIMULATION
            order = {
                "id": f"sim_{int(time.time())}",
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "status": "open"
            }
            
            # Log to DB
            self.db.log_trade(order)
            
            # Simulate Fill & PnL Update (Mocking a win)
            self.current_capital += 5 # Mock Profit
            self.db.update_capital(self.current_capital, self.level)
            
            logger.info(f"Trade Executed: {order['id']}")
            return {"status": "SUCCESS", "order_id": order['id']}

        except Exception as e:
            logger.error(f"Execution Failed: {e}")
            return {"status": "FAILED", "error": str(e)}

# Factory
def create_engine():
    return ExecutionEngine()
