# models.py

import os  
import sys
from dataclasses import dataclass
from typing import Optional, ClassVar
import logging
import math
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta


# Add the cpp/build directory to the path for importing strangle_module
src_path = os.path.dirname(os.path.abspath(__file__))
cpp_build_path = os.path.join(src_path, "cpp/build")
sys.path.append(cpp_build_path)

# Import the C++ module
import strangle_module

# Configure basic logging.  show warning or higher for external modules.
logging.basicConfig(
    level=logging.WARNING,  
    format='%(message)s'
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Show info level logger events for this module
logger.setLevel(logging.INFO)

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
    num_strangles_considered: int
    escape_ratio: Optional[float] = None  
    probability_of_profit: Optional[float] = None
    expected_gain: Optional[float] = None  
    call_contract: Optional[str] = None 
    put_contract: Optional[str] = None  
    total_in: Optional[float] = None

    # Class variable for brokerage fee per contract
    brokerage_fee_per_contract: ClassVar[float] = 0.53 + 0.55 # Default value (adjust as needed)

    def __post_init__(self):
        # Build call and put contract tickers once
        expiration_call = self.expiration_date_call[2:].replace("-", "")
        expiration_put = self.expiration_date_put[2:].replace("-", "")
        self.call_contract_ticker = f"O:{self.ticker}{expiration_call}C{int(self.strike_price_call * 1000):08}"
        self.put_contract_ticker = f"O:{self.ticker}{expiration_put}P{int(self.strike_price_put * 1000):08}"

    def calculate_escape_ratio(self) -> None:
        # Use the C++ function from strangle_module to calculate the escape ratio
        cpp_strangle = strangle_module.Strangle(
            self.stock_price, self.upper_breakeven, self.lower_breakeven
        )
        self.escape_ratio = cpp_strangle.calculate_escape_ratio()

    def calculate_probability_of_profit(self) -> None:
        """
        Calculates the Probability of Profit (POP) for the strangle strategy, incorporating brokerage fees.
        
        Estimates the likelihood that the strangle will reach a profitable position at expiration,
        based on implied volatility (IV), current stock price, expiration date, both breakeven points.
        """
        # Use the earliest expiration date and set it to market close time (4:00 PM ET)
        expiration_date_str = min(self.expiration_date_call, self.expiration_date_put)
        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        market_close_time = datetime(
            expiration_date.year, expiration_date.month, expiration_date.day, 16, 0
        )
        expiration_datetime_utc = market_close_time - timedelta(hours=5)  # Convert 4 PM ET to UTC

        # Calculate seconds to expiration from the current UTC time
        today = datetime.utcnow()  # Use UTC for consistency
        seconds_to_expiration = int((expiration_datetime_utc - today).total_seconds())

        # Use the C++ function to calculate probability of profit
        self.probability_of_profit = strangle_module.Strangle.calculate_probability_of_profit(
            self.stock_price, self.upper_breakeven, self.lower_breakeven,
            self.implied_volatility, seconds_to_expiration
        )

    def calculate_expected_gain(self) -> None:
        """
        Calculates the expected gain of the strangle by analytically computing the payoffs for both the 
        call and put options, weighted by their probabilities under a log-normal stock price distribution 
        at expiration.
        """

        # Use the earliest expiration date at 4:00 PM ET
        expiration_date_str = min(self.expiration_date_call, self.expiration_date_put)
        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        market_close_time = datetime(
            expiration_date.year, expiration_date.month, expiration_date.day, 16, 0
        )
        expiration_datetime_utc = market_close_time - timedelta(hours=5)  # Convert 4 PM ET to UTC

        # Calculate seconds to expiration
        today = datetime.utcnow()  # Use UTC for consistency
        seconds_to_expiration = int((expiration_datetime_utc - today).total_seconds())

        # Sum the premiums and brokerage fees per share
        total_premium_per_share = float(self.premium_call + self.premium_put)
        total_brokerage_fees_per_share = float((self.brokerage_fee_per_contract * 2) / 100)  # Convert to per share

        # Ensure all parameters are explicitly cast to float as needed
        stock_price = float(self.stock_price)
        strike_price_call = float(self.strike_price_call)
        strike_price_put = float(self.strike_price_put)
        implied_volatility = float(self.implied_volatility)

        # Call the C++ function to calculate the expected gain
        self.expected_gain = strangle_module.Strangle.calculate_expected_gain(
            stock_price, strike_price_call, strike_price_put,
            implied_volatility, seconds_to_expiration,
            total_premium_per_share, total_brokerage_fees_per_share
        )