from bs4 import BeautifulSoup
import csv

# Load the HTML file
with open('../html/edgewalker_report_20241018_111309.html', 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, 'html.parser')

# Create a CSV file to write the report
with open('../html/edgewalker_report_20241018_111309.csv', 'w', newline='', encoding='utf-8') as csvfile:
    # Define the CSV header
    fieldnames = ['Symbol', 'Stock Price', 'Normalized Breakeven Difference', 'Escape Ratio', 'Variability Ratio',
                  'Cost of Strangle', 'Contract Pairs Tried', 'Call Expiration', 'Call Strike', 'Call Premium',
                  'Put Expiration', 'Put Strike', 'Put Premium', 'Upper Breakeven', 'Lower Breakeven',
                  'Breakeven Difference']
    
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    # Find all panels except the header and logo panel
    panels = soup.find_all('div', class_='panel', attrs={'data-position': True})
    
    for panel in panels:
        # Skip header and logo panels
        if 'header' in panel['data-position'] or 'logo' in panel['data-position']:
            continue

        # Extract text content from the panel
        text_content = panel.get_text(separator='|').split('|')

        # The first part of text_content[0] will have the ticker and stock price
        ticker_info = text_content[0].split(':')
        symbol_and_price = ticker_info[0].strip()

        # Separate symbol and stock price
        symbol = symbol_and_price.split('(')[1].replace(')', '').strip()
        stock_price = ticker_info[1].strip().split(' ')[0]  # Extract the stock price (before any space)

        # Create a dictionary to hold the row data
        row_data = {
            'Symbol': symbol,
            'Stock Price': stock_price,
            'Normalized Breakeven Difference': text_content[1].split(':')[-1].strip(),
            'Escape Ratio': text_content[2].split(':')[-1].strip(),
            'Variability Ratio': text_content[3].split(':')[-1].strip(),
            'Cost of Strangle': text_content[4].split(':')[-1].strip(),
            'Contract Pairs Tried': text_content[5].split(':')[-1].strip(),
            'Call Expiration': text_content[6].split(':')[-1].strip(),
            'Call Strike': text_content[7].split(':')[-1].strip(),
            'Call Premium': text_content[8].split(':')[-1].strip(),
            'Put Expiration': text_content[9].split(':')[-1].strip(),
            'Put Strike': text_content[10].split(':')[-1].strip(),
            'Put Premium': text_content[11].split(':')[-1].strip(),
            'Upper Breakeven': text_content[12].split(':')[-1].strip(),
            'Lower Breakeven': text_content[13].split(':')[-1].strip(),
            'Breakeven Difference': text_content[14].split(':')[-1].strip(),
        }

        # Write the row to the CSV
        writer.writerow(row_data)

print("HTML Report has been successfully converted to CSV.")