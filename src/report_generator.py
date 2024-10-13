# report_generator.py

import os
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from models import Strangle


class ReportGenerator:
    def __init__(self, template_file: str):
        self.template_file = template_file

    def display_strangle(self, strangle: Strangle) -> None:
        # Check if any required fields are missing
        if not strangle:
            return

        # Display the strangle details
        print(f"{strangle.company_name} ({strangle.ticker}): ${strangle.stock_price:.2f}")
        print(f"Normalized breakeven difference: {strangle.normalized_difference:.3f}")
        print(f"Variability Ratio: {strangle.variability_ratio:.3f}")
        print(f"Escape Ratio: {strangle.escape_ratio:.3f}")
        print(f"Cost of strangle: ${strangle.cost_call + strangle.cost_put:.2f}")
        print(f"Contract pairs tried: {strangle.num_strangles_considered:,}")
        print(f"Call Expiration: {strangle.expiration_date_call}")
        print(f"Call strike: {strangle.strike_price_call:.2f}")
        print(f"Call premium: ${strangle.cost_call / 100.0:.2f}")
        print(f"Put Expiration: {strangle.expiration_date_put}")
        print(f"Put strike: {strangle.strike_price_put:.2f}")
        print(f"Put premium: ${strangle.cost_put / 100.0:.2f}")
        print(f"Upper breakeven: ${strangle.upper_breakeven:.3f}")
        print(f"Lower breakeven: ${strangle.lower_breakeven:.3f}")
        print(f"Breakeven difference: ${strangle.breakeven_difference:.3f}\n")

    def generate_html_table(self, strangle: Strangle, position: int) -> Optional[str]:
        # Check if any of the required fields are None
        required_fields = [
            'company_name', 'ticker', 'stock_price', 'normalized_difference',
            'escape_ratio', 'variability_ratio', 'cost_call', 'cost_put',
            'num_strangles_considered', 'expiration_date_call', 'strike_price_call',
            'cost_call', 'expiration_date_put', 'strike_price_put', 'cost_put',
            'upper_breakeven', 'lower_breakeven', 'breakeven_difference'
        ]

        if any(getattr(strangle, field) is None for field in required_fields):
            return None  # Skip this strangle if any required value is None

        # Generate the HTML with the company name (or fallback to ticker symbol)
        return ''.join([
            f'<div class="panel" data-position="{position}">',
            f'{strangle.company_name} ({strangle.ticker}): ${strangle.stock_price:.2f}<br>',
            f'Normalized Breakeven Difference: {strangle.normalized_difference:.3f}<br>',
            f'Escape ratio: {strangle.escape_ratio:.3f}<br>',
            f'Variability Ratio: {strangle.variability_ratio:.3f}<br>',
            f'Cost of strangle: ${strangle.cost_call + strangle.cost_put:.2f}<br>',
            f'Contract pairs tried: {strangle.num_strangles_considered:,}<br>',
            f'Call expiration: {strangle.expiration_date_call}<br>',
            f'Call strike: ${strangle.strike_price_call:.2f}<br>',
            f'Call premium: ${strangle.cost_call / 100.0:.2f}<br>',
            f'Put expiration: {strangle.expiration_date_put}<br>',
            f'Put strike: ${strangle.strike_price_put:.2f}<br>',
            f'Put premium: ${strangle.cost_put / 100.0:.2f}<br>',
            f'Upper breakeven: ${strangle.upper_breakeven:.3f}<br>',
            f'Lower breakeven: ${strangle.lower_breakeven:.3f}<br>',
            f'Breakeven difference: ${strangle.breakeven_difference:.3f}',
            '</div>'
        ])

    def write_reports(self, results: List[Strangle], execution_details: dict) -> None:
        # Try to read the template file and handle the case where the file is not found
        try:
            with open(self.template_file, 'r') as file:
                soup = BeautifulSoup(file, 'html.parser')
        except FileNotFoundError:
            print(f"Error: Template file '{self.template_file}' not found. Aborting report generation.")
            return  # Exit the function if the template file is not found

        # Extract execution details
        num_tickers_processed = execution_details.get('num_tickers_processed')
        num_strangles_considered = execution_details.get('num_strangles_considered')
        execution_time = execution_details.get('execution_time')
        execution_time_per_ticker = execution_details.get('execution_time_per_ticker')

        # Generate the current date in the desired format
        current_date = datetime.now().strftime("%A, %d %B, %Y")  # Example: "Sunday, 6 October, 2024"

        # Create a wide header panel that spans all columns and includes the current date
        header_panel = (
            f'{current_date}: '
            f'Processed {num_tickers_processed} tickers. '
            f'Considered {num_strangles_considered:,} contract pairs. '
            f'Finished in {execution_time/60.0:.0f} minutes, or '
            f'{execution_time_per_ticker:.0f} seconds per ticker.'
        )

        # Find the header panel and insert the content
        header_div = soup.find("div", {"class": "header", "data-position": "header"})
        if header_div:
            header_div.clear()  # Clear any existing content
            header_div.append(BeautifulSoup(header_panel, 'html.parser'))

        # Sort the results
        filtered_results = [
            x for x in results
            if (
                x.cost_call is not None and
                x.cost_put is not None and
                x.normalized_difference is not None and
                x.num_strangles_considered is not None
            )
        ]

        sorted_results = sorted(
            filtered_results,
            key=lambda x: (
                x.normalized_difference,   # First priority (ascending)
                -x.variability_ratio,      # Second priority (descending)
                -x.num_strangles_considered,  # Third priority (descending)
                x.cost_call + x.cost_put,  # Fourth priority (ascending)
            )
        )

        # Generate all the HTML content once
        all_results = [
            result_html for idx, result in enumerate(sorted_results)
            if (result_html := self.generate_html_table(result, idx + 1)) is not None
        ]

        # Get the current time and format it for the filename
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'summary_report_{stamp}.html'
        full_output_file = f'full_report_{stamp}.html'

        # Find the grid container
        grid_container = soup.find("div", class_="grid-container")

        # Replace the top 8 panels (or fewer if there are not enough results)
        top_8_results = all_results[:8]  # Use the first 8 panels
        for idx, result in enumerate(top_8_results):
            data_position = idx + 1  # Data positions for panels are 1-indexed
            panel = grid_container.find("div", {"data-position": str(data_position)})
            if panel:
                new_content = BeautifulSoup(result, 'html.parser').div.decode_contents()  # Extract inner content
                panel.clear()  # Clear any existing content
                panel.append(BeautifulSoup(new_content, 'html.parser'))  # Insert the new content

        # Write the top 8 report to file
        with open(output_file, 'w') as file:
            file.write(str(soup))

        # Only create the full report if there are more than 8 panels
        if len(all_results) > 8:
            # Add the remaining results to the grid
            for idx, result in enumerate(all_results[8:], start=8):  # Continue from the 9th result
                new_panel = soup.new_tag("div", **{'class': 'panel', 'data-position': str(idx + 1)})
                new_content = BeautifulSoup(result, 'html.parser').div.decode_contents()  # Extract inner content
                new_panel.append(BeautifulSoup(new_content, 'html.parser'))  # Append the content
                grid_container.append(new_panel)

            # Write the full report to file
            with open(full_output_file, 'w') as file:
                file.write(str(soup))