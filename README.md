
# [Edge Walker](https://edgewalker.co.uk)

![Edge Walker Logo](images/EdgeWalker_small.png)

## For experienced traders (TLDR)

Edge Walker is Python tool that uses the [Polygon API](https://polygon.io/) to search stock ticker collections for option contract pairs with the best-balanced strangles (strangles with the smallest breakeven differences).

## For those without options trading experience

Edge Walker is a software tool that searches for an idealized version of a trading strategy called a "strangle." This strategy involves purchasing options—financial contracts that give you the right to buy or sell a stock at a certain price in the future. Here are some basics or key terms about options trading and the strangle strategy that Edge Walker tries to idealize:

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

Edge Walker searches for the most "balanced" strangles—those with the smallest difference, or narrowest gap, or sharpest edge, between the upper and lower breakeven prices. By sharpening this edge, you reduce the conditions under which losses occur. Edge Walker was made to try and find trades as near as possible to the ideal scenario in which the upper and lower breakeven prices are identical.

## Screenshots

Edgewalker's main output is [a simple html report like this](https://edgewalker.co.uk/html/edgewalker_report.html). 

![HTML Report](images/screenshot.png)

You can use `/utility/html2csv.py` to convert that to [a spreadsheet if you want](https://edgewalker.co.uk/html/display_csv_report/edgewalker_report.csv.html).

![CSV Report](images/csv_report.png)

Another handy utility is [the simple html calculator for breakeven prices](https://edgewalker.co.uk/utility/calculator.html)

<p align="center">
  <img src="images/empty_calculator.png" alt="Empty Calculator" width="45%" valign="center"/>
  <img src="images/full_calculator.png" alt="Full Calculator" width="45%" valign="center"/>
</p>

## Disclaimer

Edge Walker does minimal accounting for transaction fees when working out the cost of each strangle.  You you should edit these accordingly in `/src/strangle_finder.py`.

```
# Calculate the strangle costs
contract_buy_and_sell_fee = 0.53 + 0.55 # Brokerage-dependent cost
merged_df['strangle_costs'] = (
   merged_df['premium_call'] + merged_df['premium_put'] +
   2.0 * contract_buy_and_sell_fee / 100.0
)
```
These are also hard coded in the simple html breakeven calculator `/utility/calculator.html`.
```
var contract_buy_and_sell_fee = 0.53 + 0.55
var strangle_costs = callPremium + putPremium + 2.0*contract_buy_and_sell_fee/100.0
```

Edge Walker focuses entirely on exercising options, not on any profits or losses that could be had by selling or trading the options themselves. Often simply selling the options is the easier and more profitable way to close your position, but pricing that kind of close isn't as simple.

Edge Walker is provided "as is" without any guarantees or warranties. Use this code at your own risk. The author makes no promises about the code being error-free or trustworthy.

### Directory Structure

The project is organized into the following directories:

- **/** (root directory): Project website and github configuration files
  
- **/html**: Generated reports, template reports, and recently generated CSV reports from Edge Walker's output.
  
- **/images**: Project logo and screenshots
  
- **/src**: The main Python modules responsible for Edge Walker's core functionality. It also contains ticker lists and other support files.
  
- **/utility**: Helpful tools such as ticker scrapers, [a simple html-based strangle breakeven calculator](https://edgewalker.co.uk/utility/calculator.html), and a script `html2csv.py` that converts the HTML reports into CSV format if you prefer to poke around at the results as a spreadsheet.

## Features

- Fetches options data for a list of stock tickers using the Polygon.io API.
- Calculates breakeven points for various call and put combinations.
- Identifies the strangle with the smallest normalized breakeven difference for each ticker.
- Provides detailed output including strike prices, premiums, costs, and breakeven points.
- Measures execution time and provides performance metrics.
- Stores ticker collections in an external `tickers.json` file for easy management and customization.

## Progress Status Notes

### Modular OOP Refactor Complete

The **Edge Walker** project has recently undergone a significant refactor to adopt a **modular, object-oriented (OOP)** architecture. Previously, the core logic was housed in a single script, but now the functionality has been broken out into well-structured modules to improve maintainability, readability, and scalability.

#### Key Improvements:
- Modular code organization: The project is now divided into multiple `/src/*.py` files, making it easier to extend and reuse components.
- Cleaner separation of concerns: Each module is focused on a specific area of functionality, following common OOP principles.
- Easier future development: This new structure is designed with future growth in mind, laying the groundwork for further optimizations and feature expansions.

### Current Development Focus: Asynchronous Processing and Polygon API Shift

The next major milestone for **Edge Walker** is transitioning from synchronous REST API calls to fully **asynchronous processing**. This will greatly improve the tool's efficiency by enabling it to handle real-time data in parallel, rather than sequentially.

#### Upcoming Changes:
- **Asynchronous API calls**: switching from Polygon's current REST-based API client (`polygon.RESTClient`) to its **URL-based endpoints** using async requests. This will fetch data for multiple stock tickers concurrently, reducing bottlenecks in the pipeline.
- **Enhanced performance**: This move is expected to drastically reduce execution time, particularly when processing large volumes of data.

## Requirements

- Python 3.11.5 or higher
- A Polygon.io API key with access to options data
- various python librarys described in `requirements.txt`

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

   The tickers are stored in a `tickers.json` file. Edit this file to add or remove tickers as needed.  Here's an example:
   ```
   {
     "5_tickers": [
       "BIDU", "JD", "BABA", "FOUR", "BCAB"
     ],
     "25_tickers": [
       "BIDU", "JD", "BABA", "FOUR", "ABNB", "UBER", "BA", "BCAB", "ARM", "F", 
       "AMZN", "GOOGL", "INTC", "IWM", "JD", "META", "MSFT", "NFLX", "NVDA", "QQQ", 
       "SPY", "TSLA", "AAPL", "GME", "GERN"
     ],
   }
   ```

3. **Run the script**
   
   ```python 
   python src/edge_walker.py
   ```

4. **View the results**
   The script will output the best-balanced strangle for each ticker, along with detailed information about the options contracts.

### Understanding the Output

For each ticker, the script outputs something to the console. It could just be like this example:

```
AMZN: Nothing interesting.
```

which means that the best put/call contract pair isn't sufficiently low risk bother keeping a record of. This is what you should expect to see for most tickers, 
unless you've set a somewhat large value of `max_normalized_difference`, which you can edit in these lines from `src/main.py`

```
# Only put interesting results into reports or output
max_normalized_difference = 0.06
````
In cases where something interesting is found (sufficiently small Normalized Breakeven Difference) you will see an output like this example:

```
PIMCO Active Bond (BOND): $93.05
Normalized Breakeven Difference: 0.032
Escape ratio: 0.011
Variability Ratio: 0.000
Cost of strangle: $200.00
Contract pairs tried: 2
Call expiration: 2024-11-15
Call strike: $93.00
Call premium: $0.73
Put expiration: 2024-11-15
Put strike: $94.00
Put premium: $1.27
Upper breakeven: $95.011
Lower breakeven: $91.989
Breakeven difference: $3.021
```

### Execution Statistics

At the end of the execution, statistics apear on the console describing the previous run, like this example:

```
Number of tickers processed: 7,723
Number of contract pairs tried: 7,146,806
Execution time: 7301.55 seconds
Execution time per ticker: 0.95 seconds
```

## Contributing

Contributions are welcome! If you have suggestions or improvements, please fork the repository and create a pull request.

## Licensing Information

This project is available under two license options:

1. **Open Source License (GPLv3)**:
   - You are free to use, modify, and distribute this project under the terms of the GPLv3 license.
   - If you choose this option, you must comply with the GPLv3 license, including the requirement to make any derivative works public under the same terms.

2. **Commercial License**:
   - For individuals or organizations wishing to use this project without complying with the GPLv3 terms (e.g., for private use or proprietary modifications), a commercial license is available.
   - Please contact Steve Drasco at steve.drasco@gmail.com for details on obtaining a commercial license.

For the full text of the GPLv3 license, see the [LICENSE](LICENSE) file in this repository.

## Contact

For questions or suggestions, please contact Steve Drasco at steve.drasco@gmail.com
