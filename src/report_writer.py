# report_writer.py

import os
import csv 
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from models import Strangle


class ReportWriter:
    def __init__(self, results: List[Strangle], execution_details: dict):
        self.results = results  # Assign the results to the instance
        
        # If the report directory doesn't exist, create it
        self.report_directory = '../html/'
        try:
            os.makedirs(self.report_directory, exist_ok=True)
        except OSError as e:
            print(f"Error: Failed to create directory for {self.report_directory}. {e}")
            return  # Exit the function if the report directory doesn't exist

        # make a base filename for report writing
        # stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # self.base_filename = f'{self.report_directory}edgewalker_report_{stamp}'
        self.base_filename = f'{self.report_directory}edgewalker_report'

        # Extract execution details
        self.num_tickers_processed = execution_details.get('num_tickers_processed')
        self.num_strangles_considered = execution_details.get('num_strangles_considered')
        self.execution_time = execution_details.get('execution_time')
        self.execution_time_per_ticker = execution_details.get('execution_time_per_ticker')

        # Clean the results (filter and sort)
        self.clean_results()

        # Generate the current date in the desired format
        self.current_date = datetime.now().strftime("%A, %d %B, %Y") 

    def clean_results(self):
        """Filter and sort the results by normalized difference and profitability probability."""
        filtered_results = [
            x for x in self.results
            if (
                x.normalized_difference is not None and
                x.probability_of_profit is not None
            )
        ]
        sorted_results = sorted(
            filtered_results,
            key=lambda x: (
                x.normalized_difference,   # First priority (ascending)
                -x.probability_of_profit # second priority (descending)
            )
        )
        self.results = sorted_results

    def generate_html_table(self, strangle: Strangle, position: int) -> Optional[str]:
        # Check if any of the required fields are None
        required_fields = [
            'company_name', 'ticker', 'stock_price', 'normalized_difference',
            'escape_ratio', 'probability_of_profit', 'cost_call', 'cost_put',
            'num_strangles_considered', 'expiration_date_call', 'strike_price_call',
            'cost_call', 'expiration_date_put', 'strike_price_put', 'cost_put',
            'upper_breakeven', 'lower_breakeven', 'breakeven_difference'
        ]

        if any(getattr(strangle, field) is None for field in required_fields):
            return None  # Skip this strangle if any required value is None

        # Generate the result card for the HTML report
        return ''.join([
            f'<div class="panel" data-position="{position}">',
            f'{strangle.company_name} ({strangle.ticker}): ${strangle.stock_price:.2f}<br>',
            f'Normalized Breakeven Difference: {strangle.normalized_difference:.3f}<br>',
            f'Implied Volatility: {strangle.implied_volatility:.3f}<br>',
            f'Probability of Profit: {strangle.probability_of_profit:.3f}<br>',
            f'Expected Gain: {"-$" if strangle.expected_gain < 0 else "$"}{abs(strangle.expected_gain):.2f}<br>'
            f'Escape ratio: {strangle.escape_ratio:.3f}<br>',
            f'Cost of strangle: ${strangle.cost_call + strangle.cost_put:.2f}<br>',
            f'Contract pairs tried: {strangle.num_strangles_considered:,}<br>',
            f'Call expiration: {strangle.expiration_date_call}<br>',
            f'Call strike: ${strangle.strike_price_call:.2f}<br>',
            f'Call premium: ${strangle.premium_call:.2f}<br>',
            f'Put expiration: {strangle.expiration_date_put}<br>',
            f'Put strike: ${strangle.strike_price_put:.2f}<br>',
            f'Put premium: ${strangle.premium_put:.2f}<br>',
            f'Upper breakeven: ${strangle.upper_breakeven:.3f}<br>',
            f'Lower breakeven: ${strangle.lower_breakeven:.3f}<br>',
            f'Breakeven difference: ${strangle.breakeven_difference:.3f}',
            '</div>'
        ])

    def write_html(self) -> None:
        # Try to read the template file and handle the case where the file is not found
        # build the template filename
        template_file = f'{self.report_directory}template_report.html'
        try:
            with open(template_file, 'r') as file:
                soup = BeautifulSoup(file, 'html.parser')
        except FileNotFoundError:
            print(f"Error: Template file '{template_file}' not found. Aborting report generation.")
            return  # Exit the function if the template file is not found

        # Create a wide header panel that spans all columns and includes the current date
        header_panel = (
            f'{self.current_date}: '
            f'Processed {self.num_tickers_processed} tickers. '
            f'Considered {self.num_strangles_considered:,} contract pairs. '
            f'Finished in {self.execution_time:.0f} seconds, or '
            f'{self.execution_time_per_ticker:.4f} seconds per ticker.'
        )

        # Find the header text and insert the content
        header_div = soup.find("div", {"class": "header-text"})
        if header_div:
            header_div.clear()  # Clear any existing content
            header_div.append(BeautifulSoup(header_panel, 'html.parser'))

        # Generate all the HTML content
        all_results = [
            result_html for idx, result in enumerate(self.results)
            if (result_html := self.generate_html_table(result, idx + 1)) is not None
        ]

        # Find the grid container
        grid_container = soup.find("div", class_="grid-container")

        # Replace or add panels
        for idx, result in enumerate(all_results):
            data_position = idx + 1  # Data positions for panels are 1-indexed
            panel = grid_container.find("div", {"data-position": str(data_position)})

            # If the panel exists, replace its content
            if panel:
                new_content = BeautifulSoup(result, 'html.parser').div.decode_contents()  # Extract inner content
                panel.clear()  # Clear any existing content
                panel.append(BeautifulSoup(new_content, 'html.parser'))  # Insert the new content
            else:
                # Create a new panel if it doesn't exist
                new_panel = soup.new_tag("div", **{"class": "panel", "data-position": str(data_position)})
                new_content = BeautifulSoup(result, 'html.parser').div.decode_contents()
                new_panel.append(BeautifulSoup(new_content, 'html.parser'))
                grid_container.append(new_panel)  # Append the new panel to the grid container

        # Write the report to file
        with open(f'{self.base_filename}.html', 'w') as file:
            file.write(str(soup))


    def write_csv(self) -> None:

        # Define the header for the CSV file
        csv_header = ["Company", "Symbol", "Stock Price", "Normalized Breakeven Difference",
                      "Lower Breakeven", "Upper Breakeven", "Breakeven Difference",
                      "Implied Volatility", "Probability of Profit", "Expected Gain", "Escape Ratio",
                      "Strangle Cost", "Pairs Tried", "Call Expiration", "Call Strike", 
                      "Call Premium", "Put Expiration", "Put Strike", "Put Premium"]

        # Open the CSV file for writing
        with open(f'{self.base_filename}.csv', mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=csv_header)
            writer.writeheader()

            # Iterate through each strangle result and write to CSV
            for strangle in self.results:
                writer.writerow({
                    "Company": strangle.company_name,
                    "Symbol": strangle.ticker,
                    "Stock Price": strangle.stock_price,
                    "Normalized Breakeven Difference": strangle.normalized_difference,
                    "Lower Breakeven": strangle.lower_breakeven,
                    "Upper Breakeven": strangle.upper_breakeven,
                    "Breakeven Difference": strangle.breakeven_difference,
                    "Implied Volatility": strangle.implied_volatility,
                    "Probability of Profit": strangle.probability_of_profit,
                    "Expected Gain": strangle.expected_gain,
                    "Escape Ratio": strangle.escape_ratio,
                    "Strangle Cost": strangle.cost_call,
                    "Pairs Tried": strangle.num_strangles_considered,
                    "Call Expiration": strangle.expiration_date_call,
                    "Call Strike": strangle.strike_price_call,
                    "Call Premium": strangle.premium_call,
                    "Put Expiration": strangle.expiration_date_put,
                    "Put Strike": strangle.strike_price_put,
                    "Put Premium": strangle.premium_put
                })