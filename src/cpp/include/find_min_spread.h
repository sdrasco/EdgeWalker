// include/find_min_spread.h

#ifndef FIND_MIN_SPREAD_H
#define FIND_MIN_SPREAD_H

#include <vector>
#include <string>

// Struct for holding option contract details
struct Option {
    double premium;
    double strike_price;
    double implied_volatility;
    std::string contract_type;
};

// Struct for holding the best strangle combination details
struct StrangleCombination {
    Option call;
    Option put;
    double strangle_costs;
    double upper_breakeven;
    double lower_breakeven;
    double breakeven_difference;
    double average_strike_price;
    double normalized_difference;
};

// Function to find the best strangle with minimum normalized difference
StrangleCombination find_min_spread(const std::vector<Option>& calls, const std::vector<Option>& puts);

#endif // FIND_MIN_SPREAD_H