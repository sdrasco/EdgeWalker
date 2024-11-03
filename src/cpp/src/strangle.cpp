#include "strangle.h"
#include <cmath>  // for std::abs

// Constructor to initialize attributes
Strangle::Strangle(double stock_price, double upper_breakeven, double lower_breakeven)
    : stock_price(stock_price), upper_breakeven(upper_breakeven), lower_breakeven(lower_breakeven) {}

// Method to calculate escape ratio
#include <cmath>  // for std::fabs and std::fmin
double Strangle::calculate_escape_ratio() {
    return std::fmin(std::fabs(stock_price - upper_breakeven), std::fabs(stock_price - lower_breakeven)) / stock_price;
}
