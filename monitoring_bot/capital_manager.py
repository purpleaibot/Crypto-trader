import logging

logger = logging.getLogger(__name__)

class CapitalManager:
    def __init__(self, start_amount, levels_config=None):
        self.start_amount = start_amount
        self.current_capital = start_amount
        self.realized_pnl = 0.0
        
        # Default Levels if none provided (Example logic)
        # Level 1: 100-199, Level 2: 200-299, etc.
        self.levels_config = levels_config if levels_config else self._generate_default_levels()
        
    def _generate_default_levels(self):
        """
        Generates standard levels based on starting amount.
        Level 1 starts at start_amount.
        """
        levels = {}
        # Example: Levels 1-10
        base = 100 # Assuming 100 is the base unit
        for i in range(1, 11):
            levels[f"Level{i}"] = {"min": base * i, "max": (base * (i+1)) - 0.01}
            
        # SLevels (Stop Levels)
        levels["SLevel1"] = {"min": base * 0.8, "max": base - 0.01} # 80-99
        levels["SLevel2"] = {"min": base * 0.6, "max": (base * 0.8) - 0.01} # 60-79
        
        return levels

    def update_capital(self, trade_pnl):
        """
        Updates capital after a closed trade and recalculates level.
        """
        self.realized_pnl += trade_pnl
        self.current_capital = self.start_amount + self.realized_pnl
        logger.info(f"Capital Updated: {self.current_capital} (PnL: {self.realized_pnl})")
        return self.get_current_level()

    def get_current_level(self):
        """
        Determines the current trading level based on Instance Capital.
        """
        for level_name, range_data in self.levels_config.items():
            if range_data["min"] <= self.current_capital <= range_data["max"]:
                return level_name, range_data["min"]
        
        # Fallback / Kill Switch Trigger Check
        if self.current_capital < self.levels_config["SLevel2"]["min"]:
            return "CRITICAL_LOW", 0
            
        return "UNKNOWN", 0

    def calculate_position_size(self, risk_percent):
        """
        Calculates risk amount based on the MINIMUM value of the current level.
        Risk = x% of Level Min.
        """
        level_name, level_min = self.get_current_level()
        if level_name == "CRITICAL_LOW":
            return 0.0
            
        risk_amount = level_min * risk_percent
        return risk_amount
