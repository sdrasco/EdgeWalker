# makesequence.py

import numpy as np
import matplotlib.pyplot as plt

def plot_strangle(P, C, K_P, K_C, S_min, S_max, y_min, y_max, filename):
    """
    Plots the P/L diagram for a strangle strategy and saves it to a file.

    Parameters:
    - P (float): Premium for the Put option.
    - C (float): Premium for the Call option.
    - K_P (float): Strike price for the Put option.
    - K_C (float): Strike price for the Call option.
    - S_min (float): Minimum underlying asset price.
    - S_max (float): Maximum underlying asset price.
    - y_min (float): Minimum y-axis value.
    - y_max (float): Maximum y-axis value.
    - filename (str): Name of the output PDF file.
    """
    # --- LaTeX + serif font setup (must happen before plotting) ---
    plt.rcParams['text.usetex'] = True
    plt.rcParams['font.family'] = 'serif'

    # Increase font size for publication
    plt.rcParams['font.size'] = 14      # Base font size for all text
    plt.rcParams['axes.labelsize'] = 16 # Axis labels

    # Increase line thickness
    line_thickness = 4

    # Generate S values
    S = np.linspace(S_min, S_max, 400)

    # Compute varphi_P(S) = max(K_P - S, 0) - P
    varphi_P = np.maximum(K_P - S, 0) - P

    # Compute varphi_C(S) = max(S - K_C, 0) - C
    varphi_C = np.maximum(S - K_C, 0) - C

    # Compute total varphi = varphi_P + varphi_C
    varphi = varphi_P + varphi_C

    # Find the breakeven points where varphi = 0
    # For a strangle with K_P != K_C, the breakeven points are:
    # S_breakeven_low = K_P - P - C
    # S_breakeven_high = K_C + P + C
    S_breakeven_low = K_P - P - C
    S_breakeven_high = K_C + P + C

    # Ensure S_breakeven_low <= S_breakeven_high
    if S_breakeven_low > S_breakeven_high:
        S_breakeven_low, S_breakeven_high = S_breakeven_high, S_breakeven_low

    # Separate by sign of varphi:
    #   - Green if varphi >= 0 (excluding the loss region)
    #   - Red if varphi < 0
    # To prevent unwanted lines, define separate masks for lower and upper green regions
    # Adjusted masks to exclude the exact breakeven points to prevent overlapping
    mask_green_low = (varphi >= 0) & (S < S_breakeven_low)
    mask_green_high = (varphi >= 0) & (S > S_breakeven_high)
    mask_red = (varphi < 0)

    # Define colors
    green_muted = "#66A266"
    red_muted = "#CC6666"

    # Create the plot
    plt.figure(figsize=(6, 4), dpi=300)

    # Plot green regions where varphi >= 0 (lower)
    plt.plot(S[mask_green_low], varphi[mask_green_low],
             color=green_muted, linewidth=line_thickness)

    # Plot red regions where varphi < 0
    plt.plot(S[mask_red], varphi[mask_red],
             color=red_muted, linewidth=line_thickness)

    # Plot green regions where varphi >= 0 (upper)
    plt.plot(S[mask_green_high], varphi[mask_green_high],
             color=green_muted, linewidth=line_thickness)

    # Add a single thin black horizontal line at varphi = 0
    plt.axhline(0, color='black', linewidth=0.8, linestyle='-')

    # Add left-pointing triangle marker at S_breakeven_low
    plt.plot(S_breakeven_low, 0, color='black', marker='<', markersize=16, 
             linestyle='None', zorder=5)

    # Add right-pointing triangle marker at S_breakeven_high
    plt.plot(S_breakeven_high, 0, color='black', marker='>', markersize=16, 
             linestyle='None', zorder=5)

    # Labels with (USD)
    plt.xlabel(r'$S$ (USD)')
    plt.ylabel(r'$\varphi(S)$ (USD)')

    # X-axis limits
    plt.xlim([S_min, S_max])

    # Y-axis limits
    plt.ylim([y_min, y_max])

    # Optional: Remove the legend since markers have no labels
    # plt.legend()

    # Tight layout for nicer spacing
    plt.tight_layout()

    # Save the plot
    plt.savefig(filename, bbox_inches='tight')
    plt.close()

def main():
    """
    Main function to generate a sequence of strangle P/L plots with varying K_P and K_C.
    """
    # Define the premiums
    P = 1  # Premium for Put option
    C = 1  # Premium for Call option

    # Define the range of underlying asset prices
    S_min, S_max = 20, 30

    # Define the y-axis range
    y_min, y_max = -2.5, 5

    # Define the list of (K_P, K_C) pairs for the 5 plots
    # Modify these pairs as needed for your specific scenarios
    K_pairs = [
        (24, 26),      # Sequence 1
        (25, 25),      # Sequence 2 (symmetric strangle)
        (25.5, 24.5),  # Sequence 3
        (27, 23),       # Sequence 4
        (28, 22)       # Sequence 5
    ]

    # Iterate over the pairs and generate plots
    for idx, (K_P, K_C) in enumerate(K_pairs, start=1):
        filename = f'sequence{idx}.pdf'
        plot_strangle(P, C, K_P, K_C, S_min, S_max, y_min, y_max, filename)
        print(f'Generated {filename} with K_P={K_P}, K_C={K_C}')

if __name__ == "__main__":
    main()