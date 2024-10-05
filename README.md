
# [Edge Walker](https://edgewalker.co.uk)

![Edge Walker Logo](EdgeWalker_small.png)

## For experienced traders (TLDR)

Edge Walker is Python tool that uses the [https://polygon.io/](Polygon API) to searches a list of stock tickers for the best-balanced options strangles (strangles with the smallest breakeven differences).

## For those without options trading experience

Edge Walker is a software tool that searches for an idealized version of a trading strategy called a “strangle.” This strategy involves purchasing options—financial contracts that give you the right to buy or sell a stock at a certain price in the future. Here are some basics or key terms about options trading and the strangle strategy that Edge Walker tries to idealize:

- **Options**: Financial contracts that give the buyer the right, but not the obligation, to buy or sell a stock at a specific price before a set expiration date. There are two types of options: calls and puts.
- **Call Option**: A contract that gives the buyer the right to buy a stock at a specific price (the strike price) before the option expires. Traders use call options when they expect the stock’s price to increase.
- **Put Option**: A contract that gives the buyer the right to sell a stock at a specific price (the strike price) before the option expires. Traders use put options when they expect the stock’s price to decrease.
- **Expiration**: The date by which the buyer must decide whether to exercise the option or let it expire. After the expiration date, the option becomes worthless.
- **Strike Price**: The price at which the buyer of the option can buy (for a call) or sell (for a put) the stock. The strike price is agreed upon when the option is purchased.
- **Premium**: The cost of buying an option contract.
- **Breakeven Price**: The stock price at which an options strategy results in neither a profit nor a loss. For a call option, the breakeven price is the strike price plus the premium paid. For a put option, it’s the strike price minus the premium.
- **Straddle**: A strategy where an investor buys both a call option and a put option for the same stock with the same strike price and the same expiration date. This strategy is used when the investor expects a price movement but is unsure of the direction.
- **Upper and Lower Breakeven Prices**: In a straddle, the upper breakeven price is the point at which the stock price needs to rise for the call option to break even. The lower breakeven price is where the stock must fall for the put option to break even. When the stock price is between the upper and lower breakeven prices, exercising would result in a loss. When the stock price is above the upper breakeven price or below the lower breakeven price, exercising would result in a profit.
- **Strangle**: Similar to a straddle, but the call and put options have different strike prices. They will have a different total cost or premium than a straddle, but will also have a different sized gap between the upper and lower breakeven prices.

Edge Walker searches for the most “balanced” strangles—those with the smallest difference, or narrowest gap, or sharpest edge, between the upper and lower breakeven prices. By sharpening this edge, you reduce the conditions under which losses occur. Edge Walker was made to try and find trades as near as possible to the ideal scenario in which the upper and lower breakeven prices are identical.

## Page layout

Edgewalker's main output it designed to be easily incorporated into [a simple html interface like this](https://edgewalker.co.uk/eventually.html). 

![Edge Walker Logo](eventually.png)

## Disclaimer

Edge Walker does not account for transaction fees, although those could easily be factored into its calculations. It also focuses entirely on exercising options, not on any profits or losses that could be had by selling or trading the options themselves (a complex topic that concerns the market's perceived value of the time remaining until options expire).

Edge Walker is provided “as is” without any guarantees or warranties. Use this code at your own risk. The author makes no promises about the code being error-free or trustworthy.

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Understanding the Output](#understanding-the-output)
- [Customization](#customization)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contact](#contact)

## Introduction

An **options strangle** is an options strategy where an investor holds a position in both a call and a put with different strike prices but the same expiration date. Edge Walker automates the process of finding the most balanced strangles—those with minimal normalized breakeven differences—across multiple stock tickers.

## Features

- Fetches options data for a list of stock tickers using the Polygon.io API.
- Calculates breakeven points for various call and put combinations.
- Identifies the strangle with the smallest normalized breakeven difference for each ticker.
- Provides detailed output including strike prices, premiums, costs, and breakeven points.
- Measures execution time and provides performance metrics.
- Stores ticker collections in an external `tickers.json` file for easy management and customization.

## Requirements

- Python 3.11.5 or higher
- A Polygon.io API key with access to options data
- [pandas](https://pypi.org/project/pandas/)
- [requests](https://pypi.org/project/requests/)

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/sdrasco/EdgeWalker.git
   ```

2. **Navigate to the project directory**

   ```bash
   cd EdgeWalker
   ```

3. Install the required packages

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Prepare the list of stock tickers**

   The tickers are stored in a `tickers.json` file. Edit this file to add or remove tickers as needed.

2. **Run the script**
   
   ```python 
   python src/edge_walker.py
   ```

3. **View the results**
   The script will output the best-balanced strangle for each ticker, along with detailed information about the options contracts.

### Understanding the Output

For each ticker, the script provides:

- Expiration Date: The date when the options contracts expire.
- Call Strike and Premium: The strike price and premium for the call option.
- Put Strike and Premium: The strike price and premium for the put option.
- Cost of Strangle: The total cost to enter the strangle position.
- Breakeven Points: The upper and lower breakeven prices.
- Breakeven Difference: The absolute difference between the breakeven points.
- Normalized Breakeven Difference: The breakeven difference normalized by the average strike price.

An example of the output:

```
<div class="panel" data-position="1">FOUR<br>Normalized Breakeven Difference: 0.104Cost of strangle: $495.00<br>Expiration: 2024-10-18<br>Call strike: $95.00<br>Put strike: $95.00<br>Cost of call: $120.00<br>Cost of put: $375.00<br>Upper breakeven: $99.950<br>Lower breakeven: $90.050<br>Breakeven difference: $9.900<br></div>
```

### Execution Statistics

At the end of the execution, statistics are provided with details about the number of tickers processed, the number of requests sent to Polygon.io, the number of HTML panels generated, and the execution time. For example:

```
Number of tickers processed: 5
Number of requests sent to Polygon.io: 5
Number of HTML panels generated: 5
Execution time: 155.23 seconds
Execution time per ticker: 31.05 seconds
```

## Customization 

- **Limiting Expiration Dates:**
By default, the script considers all available expiration dates. To limit the search to the nearest N expiration dates, uncomment and adjust the following lines in the `find_balanced_strangle` function:
```python
   # N = 4  
   # expiration_dates = stock.options[:N]
```

- **Adjusting the Tickers List**
Modify the tickers list by editing the `tickers.json` file to include any stocks you’re interested in.
- **Changing Output Preferences**
Feel free to adjust the `show_findings` function to customize the output format.

## Contributing

Contributions are welcome! If you have suggestions or improvements, please fork the repository and create a pull request.

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## Contact

For questions or suggestions, please contact Steve Drasco at steve.drasco@gmail.com
