#ifndef STRANGLE_H
#define STRANGLE_H

#include <cmath>

class Strangle {
public:
    // Constructor
    Strangle(double stock_price, double upper_breakeven, double lower_breakeven);

    // Methods
    double calculate_escape_ratio();
    static double calculate_probability_of_profit(double stock_price, double upper_breakeven, double lower_breakeven,
                                                  double implied_volatility, int seconds_to_expiration);
    static double calculate_expected_gain(double stock_price, double upper_strike, double lower_strike, 
                                          double implied_volatility, int seconds_to_expiration, 
                                          double total_premium_per_share, double brokerage_fees_per_share);

private:
    double stock_price;
    double upper_breakeven;
    double lower_breakeven;
};

#endif // STRANGLE_H