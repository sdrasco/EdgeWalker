# models.py

from dataclasses import dataclass
from typing import Optional, ClassVar
import math
import numpy as np
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
    num_strangles_considered: int
    escape_ratio: Optional[float] = None  
    probability_of_profit: Optional[float] = None
    expected_gain: Optional[float] = None  

    # Class variable for brokerage fee per contract
    brokerage_fee_per_contract: ClassVar[float] = 0.53  # Default value (adjust as needed)

    def calculate_escape_ratio(self) -> None:
        self.escape_ratio = min(
            abs(self.stock_price - self.upper_breakeven),
            abs(self.stock_price - self.lower_breakeven)
        ) / self.stock_price

    def calculate_probability_of_profit(self) -> None:
        """
        Calculates the Probability of Profit (POP) for the strangle strategy, incorporating brokerage fees.

        Estimates the likelihood that the strangle will reach a profitable position at expiration,
        based on implied volatility (IV), current stock price, expiration date, both breakeven points,
        and brokerage fees.

        Note:
        - Brokerage fees are included in the calculation by adjusting the breakeven points.
        - The default brokerage fee is set to $0.53 per contract per option. Adjust 'brokerage_fee_per_contract'
          at the class level as necessary to match your brokerage's fees.
        """
        # Use the earliest expiration date
        expiration_date_str = min(self.expiration_date_call, self.expiration_date_put)
        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        today = datetime.today()
        days_to_expiration = (expiration_date - today).days

        if days_to_expiration <= 0:
            self.profitability_probability = 0.0  # If expiration is today or has passed, probability is 0
            return

        iv = self.implied_volatility
        current_price = self.stock_price

        # Calculate brokerage fees per share
        brokerage_fees_per_share = (self.brokerage_fee_per_contract * 2) / 100  # Two options in a strangle

        # Adjust breakeven points to include brokerage fees
        adjusted_upper_breakeven = self.upper_breakeven + brokerage_fees_per_share
        adjusted_lower_breakeven = self.lower_breakeven - brokerage_fees_per_share

        # Calculate required price movements (as percentages) for both adjusted breakeven points
        move_to_upper_breakeven = (adjusted_upper_breakeven - current_price) / current_price
        move_to_lower_breakeven = (current_price - adjusted_lower_breakeven) / current_price

        # Convert price movements to z-scores (standard deviations)
        z_up = move_to_upper_breakeven / (iv * math.sqrt(days_to_expiration / 365.0))
        z_down = move_to_lower_breakeven / (iv * math.sqrt(days_to_expiration / 365.0))

        # Use normal distribution CDF to calculate probabilities
        probability_up = 1 - norm.cdf(z_up)      # Probability of price going above adjusted upper breakeven
        probability_down = norm.cdf(-z_down)     # Probability of price going below adjusted lower breakeven

        # Total probability of profit (moving beyond either adjusted breakeven point)
        self.probability_of_profit = probability_up + probability_down

    def calculate_expected_gain(self) -> None:
        """
        Calculates the expected gain of the strangle by integrating over the possible
        stock prices at expiration, weighted by their probabilities.

        The expected gain is calculated per standard options contract (which controls 100 shares).

        Note:
        - Brokerage fees are included in the calculation. The default fee is set to $0.53 per contract per option.
          Adjust 'brokerage_fee_per_contract' at the class level as necessary to match your brokerage's fees.
        """
        # Use the earliest expiration date
        expiration_date_str = min(self.expiration_date_call, self.expiration_date_put)
        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        today = datetime.today()
        days_to_expiration = (expiration_date - today).days

        if days_to_expiration <= 0:
            # Loss is the total premium paid per contract plus brokerage fees
            total_brokerage_fees = self.brokerage_fee_per_contract * 2  # Two options in a strangle
            total_premium = (self.premium_call + self.premium_put) * 100  # Convert to per contract
            self.expected_gain = - (total_premium + total_brokerage_fees)
            return

        iv = self.implied_volatility
        current_price = self.stock_price
        upper_strike = self.strike_price_call
        lower_strike = self.strike_price_put
        total_premium_per_share = self.premium_call + self.premium_put  # Sum of premiums paid per share

        # Define a range of possible stock prices at expiration
        S = np.linspace(current_price * 0.5, current_price * 1.5, 1000)
        T = days_to_expiration / 365.0
        sigma = iv
        r = 0  # Assuming risk-neutral measure
        mu = 0  # Assuming zero drift in risk-neutral valuation

        # Calculate the probability density function of stock prices at expiration
        pdf = (1 / (S * sigma * np.sqrt(2 * np.pi * T))) * np.exp(
            -((np.log(S / current_price) - (mu - 0.5 * sigma ** 2) * T) ** 2) / (2 * sigma ** 2 * T)
        )

        # Calculate the payoff for each possible stock price per share
        payoff_per_share = (
            np.maximum(S - upper_strike, 0) 
            + np.maximum(lower_strike - S, 0) 
            - total_premium_per_share 
            - self.brokerage_fee_per_contract * 2
        )

        # Expected gain per share is the integral over all possible stock prices
        expected_gain_per_share = np.trapz(payoff_per_share * pdf, S)

        # Convert to expected gain per contract (100 shares per option)
        expected_gain_per_contract = expected_gain_per_share * 100

        self.expected_gain = expected_gain_per_contract