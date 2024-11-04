// src/find_min_spread.cpp

#include "find_min_spread.h"
#include <algorithm>
#include <limits>
#include <vector>
#include <string>
#include <cmath>

// Function to find the best strangle with minimum normalized difference
StrangleCombination find_min_spread(const std::vector<Option>& calls, const std::vector<Option>& puts) {
    double min_normalized_diff = std::numeric_limits<double>::max();
    StrangleCombination best_combination;

    // Precompute the constant part of the strangle cost to avoid repeated calculations
    const double base_strangle_cost = 2 * (0.53 + 0.55) / 100.0;

    for (const auto& call : calls) {
        for (const auto& put : puts) {
            double strangle_costs = call.premium + put.premium + base_strangle_cost;
            double upper_breakeven = call.strike_price + strangle_costs;
            double lower_breakeven = put.strike_price - strangle_costs;
            double breakeven_difference = std::abs(upper_breakeven - lower_breakeven);
            double average_strike_price = 0.5 * (call.strike_price + put.strike_price);
            double normalized_difference = breakeven_difference / average_strike_price;

            if (normalized_difference < min_normalized_diff) {
                min_normalized_diff = normalized_difference;
                best_combination = {call, put, strangle_costs, upper_breakeven, lower_breakeven, breakeven_difference, average_strike_price, normalized_difference};
            }
        }
    }

    return best_combination;
}