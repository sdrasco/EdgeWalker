#include "strangle.h"
#include <cmath> // for math functions
#include <algorithm> // for std::min

// Constructor
Strangle::Strangle(double stock_price, double upper_breakeven, double lower_breakeven)
    : stock_price(stock_price), upper_breakeven(upper_breakeven), lower_breakeven(lower_breakeven) {}

// Method to calculate escape ratio
double Strangle::calculate_escape_ratio() {
    return std::min(std::abs(stock_price - upper_breakeven), std::abs(stock_price - lower_breakeven)) / stock_price;
}

// Method to calculate expected gain
double Strangle::calculate_expected_gain(double stock_price, double upper_strike, double lower_strike, 
                                         double implied_volatility, int seconds_to_expiration, 
                                         double total_premium_per_share, double brokerage_fees_per_share) {
    if (seconds_to_expiration <= 0) {
        return 0.0;
    }

    // Calculate sigma for seconds (scaled implied volatility)
    double sigma = implied_volatility * std::sqrt(static_cast<double>(seconds_to_expiration) / 31536000.0);
    if (sigma <= 0) {
        return 0.0;
    }

    // Calculating d1 and d2 for the call payoff
    double d_1 = (std::log(stock_price / upper_strike) + 0.5 * sigma * sigma) / sigma;
    double d_2 = d_1 - sigma;
    double call_payoff_per_share = stock_price * 0.5 * (1 + std::erf(d_1 / std::sqrt(2))) - 
                                   upper_strike * 0.5 * (1 + std::erf(d_2 / std::sqrt(2)));

    // Calculating d1 and d2 for the put payoff
    double d_1_put = (std::log(stock_price / lower_strike) + 0.5 * sigma * sigma) / sigma;
    double d_2_put = d_1_put - sigma;
    double put_payoff_per_share = lower_strike * 0.5 * (1 + std::erf(-d_2_put / std::sqrt(2))) - 
                                  stock_price * 0.5 * (1 + std::erf(-d_1_put / std::sqrt(2)));

    // Calculate the loss per share (total premiums and brokerage fees)
    double loss_per_share = -(total_premium_per_share + brokerage_fees_per_share);

    // Total expected gain per share
    double expected_gain_per_share = loss_per_share + call_payoff_per_share + put_payoff_per_share;

    // Convert to expected gain per contract (100 shares per option)
    return expected_gain_per_share * 100;
}

double Strangle::calculate_probability_of_profit(double stock_price, double upper_breakeven,
                                                 double lower_breakeven, double implied_volatility,
                                                 int seconds_to_expiration) {
    if (seconds_to_expiration <= 0) return 0.0;

    double move_to_upper_breakeven = (upper_breakeven - stock_price) / stock_price;
    double move_to_lower_breakeven = (stock_price - lower_breakeven) / stock_price;

    double sigma = implied_volatility * std::sqrt(seconds_to_expiration / 31536000.0);
    if (sigma <= 0) return 0.0;

    double z_up = move_to_upper_breakeven / sigma;
    double z_down = move_to_lower_breakeven / sigma;

    // Inline function defined within method scope
    auto normal_cdf = [](double z) {
        return 0.5 * (1.0 + std::erf(z / std::sqrt(2.0)));
    };

    // Use the local inline CDF function
    double probability_up = 1.0 - normal_cdf(z_up);
    double probability_down = normal_cdf(-z_down);

    return probability_up + probability_down;
}