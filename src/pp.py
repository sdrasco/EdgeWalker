pp.py

import math
from scipy.stats import norm
from datetime import datetime

def estimate_strangle_profitability(iv: float, current_price: float, expiration_date: datetime, 
                                    upper_breakeven: float, lower_breakeven: float) -> float:
    """
    Estimates the probability of a strangle being profitable based on implied volatility (IV), 
    current stock price, expiration date, and both breakeven points.
    
    Args:
    iv (float): Implied volatility as a decimal (e.g., 0.30 for 30% IV)
    current_price (float): Current stock price
    expiration_date (datetime): Expiration date of the option
    upper_breakeven (float): Upper breakeven price for the strangle
    lower_breakeven (float): Lower breakeven price for the strangle
    
    Returns:
    float: Estimated probability of profitability (between 0 and 1)
    """
    
    # Calculate days until expiration
    today = datetime.today()
    days_to_expiration = (expiration_date - today).days
    
    if days_to_expiration <= 0:
        return 0.0  # If expiration is today or has passed, probability is 0
    
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
    
    return probability_profit