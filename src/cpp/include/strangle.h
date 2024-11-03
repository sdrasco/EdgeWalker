#ifndef STRANGLE_H
#define STRANGLE_H

class Strangle {
public:
    // Constructor to initialize attributes
    Strangle(double stock_price, double upper_breakeven, double lower_breakeven);

    // Method to calculate escape ratio
    double calculate_escape_ratio();

private:
    double stock_price;
    double upper_breakeven;
    double lower_breakeven;
};

#endif // STRANGLE_H
