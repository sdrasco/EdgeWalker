# models.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class Strangle:
    ticker: str
    company_name: str
    stock_price: float
    expiration_date_call: str
    expiration_date_put: str
    strike_price_call: float
    strike_price_put: float
    premium_call: float
    premium_put: float
    cost_call: float
    cost_put: float
    upper_breakeven: float
    lower_breakeven: float
    breakeven_difference: float
    normalized_difference: float
    variability_ratio: float
    implied_volatility: float
    escape_ratio: float
    num_strangles_considered: int

    def calculate_variability_ratio(self, stock_sigma: float) -> None:
        if self.breakeven_difference == 0.0:
            self.variability_ratio = float('inf')
        else:
            self.variability_ratio = stock_sigma / self.breakeven_difference

    def calculate_escape_ratio(self) -> None:
        self.escape_ratio = min(
            abs(self.stock_price - self.upper_breakeven),
            abs(self.stock_price - self.lower_breakeven)
        ) / self.stock_price