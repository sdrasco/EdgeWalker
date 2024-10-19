# models.py

from dataclasses import dataclass
from typing import Optional
import math
from scipy.stats import norm
from datetime import datetime

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
    implied_volatility: float
    escape_ratio: float
    num_strangles_considered: int
    profitability_probability: float

    def calculate_escape_ratio(self) -> None:
        self.escape_ratio = min(
            abs(self.stock_price - self.upper_breakeven),
            abs(self.stock_price - self.lower_breakeven)
        ) / self.stock_price

    def calculate_profitability_probability(self) -> None:
        """
        Estimates the probability of the strangle reaching a profitable position based on implied volatility (IV),
        current stock price, expiration date, and both breakeven points.
        """
        # Use the earliest expiration date
        expiration_date_str = min(self.expiration_date_call, self.expiration_date_put)

        # Convert expiration_date_str to datetime object
        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')

        # Calculate days until expiration
        today = datetime.today()
        days_to_expiration = (expiration_date - today).days

        if days_to_expiration <= 0:
            self.profitability_probability = 0.0  # If expiration is today or has passed, probability is 0
            return

        iv = self.implied_volatility
        current_price = self.stock_price
        upper_breakeven = self.upper_breakeven
        lower_breakeven = self.lower_breakeven

        # Calculate standard deviation of price movement
        std_dev = current_price * iv * math.sqrt(days_to_expiration / 365.0)

        # Calculate required price movements (as percentages) for both breakeven points
        move_to_upper_breakeven = (upper_breakeven - current_price) / current_price
        move_to_lower_breakeven = (current_price - lower_breakeven) / current_price

        # Convert price movements to z-scores (standard deviations)
        z_up = move_to_upper_breakeven / (iv * math.sqrt(days_to_expiration / 365.0))
        z_down = move_to_lower_breakeven / (iv * math.sqrt(days_to_expiration / 365.0))

        # Use normal distribution CDF to calculate probabilities
        probability_up = 1 - norm.cdf(z_up)  # Probability of price going above upper breakeven
        probability_down = norm.cdf(-z_down)  # Probability of price going below lower breakeven

        # Total probability of profitability (moving either above upper or below lower breakeven)
        probability_profit = probability_up + probability_down

        self.profitability_probability = probability_profit