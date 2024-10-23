# models.py

from dataclasses import dataclass
from typing import Optional, ClassVar
import math
import numpy as np
from scipy.stats import norm
from scipy.integrate import quad
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
    brokerage_fee_per_contract: ClassVar[float] = 0.53 + 0.55 # Default value (adjust as needed)

    def calculate_escape_ratio(self) -> None:
        self.escape_ratio = min(
            abs(self.stock_price - self.upper_breakeven),
            abs(self.stock_price - self.lower_breakeven)
        ) / self.stock_price

    def calculate_probability_of_profit(self) -> None:
        """
        Calculates the Probability of Profit (POP) for the strangle strategy, incorporating brokerage fees.

        Estimates the likelihood that the strangle will reach a profitable position at expiration,
        based on implied volatility (IV), current stock price, expiration date, both breakeven points.
        """
        # Use the earliest expiration date
        expiration_date_str = min(self.expiration_date_call, self.expiration_date_put)
        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        today = datetime.today()
        days_to_expiration = (expiration_date - today).days

        if days_to_expiration <= 0:
            self.profitability_probability = 0.0  # If expiration is today or has passed, probability is 0
            return

        # Calculate required price movements (as percentages) for both adjusted breakeven points
        move_to_upper_breakeven = (self.upper_breakeven - self.stock_price) / self.stock_price
        move_to_lower_breakeven = (self.stock_price - self.lower_breakeven) / self.stock_price

        # Convert price movements to z-scores (standard deviations)
        if days_to_expiration > 0:
            sigma = self.implied_volatility * math.sqrt(days_to_expiration / 365.0)
        else:
            self.probability_of_profit = 0.0
            return
        if sigma > 0:
            z_up = move_to_upper_breakeven / sigma
            z_down = move_to_lower_breakeven / sigma
        else:
            self.probability_of_profit = 0.0
            return



        # Use normal distribution CDF to calculate probabilities
        probability_up = 1 - norm.cdf(z_up)      # Probability of price going above adjusted upper breakeven
        probability_down = norm.cdf(-z_down)     # Probability of price going below adjusted lower breakeven

        # Total probability of profit (moving beyond either adjusted breakeven point)
        self.probability_of_profit = probability_up + probability_down

    def calculate_expected_gain(self) -> None:
        """
        Calculates the expected gain of the strangle by analytically computing the payoffs for both the 
        call and put options, weighted by their probabilities under a log-normal stock price distribution 
        at expiration.

        The method integrates the expected payoffs for stock prices above the call strike (for the call option) 
        and below the put strike (for the put option), along with subtracting the cost of the strangle 
        (premiums paid plus brokerage fees), without requiring numerical integration.

        The expected gain is returned as per strangle (assuming contracts of 100 shares per contract), not per share.

        Key points:
        - Drift is set to zero, and implied volatility is used to compute sigma for the log-normal distribution.
        - The call and put payoffs are computed using closed-form solutions based on cumulative normal distribution functions.
        - Total costs (premiums and brokerage fees) are deducted using an analytical formula based on expected stock price growth.
        - Adjust 'brokerage_fee_per_contract' at the class level as necessary to match your brokerage's fees.
        """

        # Use the earliest expiration date to work out days to expiration
        expiration_date_str = min(self.expiration_date_call, self.expiration_date_put)
        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
        today = datetime.today()
        days_to_expiration = (expiration_date - today).days

        # make some constants, for tidiness
        current_price = self.stock_price
        upper_strike = self.strike_price_call
        lower_strike = self.strike_price_put
        total_premium_per_share = self.premium_call + self.premium_put  # Sum of premiums paid per share
        total_brokerage_fees_per_share = (self.brokerage_fee_per_contract * 2) / 100  # Two contracts, convert to per share
        sigma = self.implied_volatility * np.sqrt(days_to_expiration / 365.0)
        if sigma <= 0:
            self.expected_gain = 0
            return 

        # the call payoff per share: int_{call_strike}^inf S*pdf(S) dS
        d_1 = (np.log(current_price / upper_strike) + 0.5 * sigma ** 2) / sigma
        d_2 = d_1 - sigma
        N_d1 = norm.cdf(d_1)
        N_d2 = norm.cdf(d_2)
        call_payoff_per_share = current_price * N_d1 - upper_strike * N_d2

        # the put payoff per share: int_0^{put_strike} S*pdf(S) dS
        d_1_put = (np.log(current_price / lower_strike) + 0.5 * sigma ** 2) / sigma
        d_2_put = d_1_put - sigma
        N_d1_put_neg = norm.cdf(-d_1_put)
        N_d2_put_neg = norm.cdf(-d_2_put)
        put_payoff_per_share = lower_strike * N_d2_put_neg - current_price * N_d1_put_neg

        # the cost payoff part (the loss): int_0^inf costs*PDF(S) dS = costs * 1
        loss_per_share = -(total_premium_per_share + total_brokerage_fees_per_share)

        # total expected gain or payoff per share
        expected_gain_per_share = loss_per_share + call_payoff_per_share + put_payoff_per_share

        # Convert to expected gain per contract (100 shares per option)
        expected_gain_per_contract = expected_gain_per_share * 100

        self.expected_gain = expected_gain_per_contract
