# makesequence.py

import numpy as np
import matplotlib.pyplot as plt

# --- LaTeX + serif font setup (must happen before plotting) ---
plt.rcParams['text.usetex'] = True
plt.rcParams['font.family'] = 'serif'

# Increase font size for publication
plt.rcParams['font.size'] = 14      # Base font size for all text
plt.rcParams['axes.labelsize'] = 16 # Axis labels

def plot_strangle(ax, P, C, K_P, K_C, S_min, S_max, y_min, y_max):
    """
    Plots the P/L diagram for a strangle strategy on a given Axes object.

    Parameters:
    - ax (matplotlib.axes.Axes): The Axes object to plot on.
    - P (float): Premium for the Put option.
    - C (float): Premium for the Call option.
    - K_P (float): Strike price for the Put option.
    - K_C (float): Strike price for the Call option.
    - S_min (float): Minimum underlying asset price.
    - S_max (float): Maximum underlying asset price.
    - y_min (float): Minimum y-axis value.
    - y_max (float): Maximum y-axis value.
    """
    # Line thickness
    line_thickness = 4  # Increased for prominence

    # Generate S values
    S = np.linspace(S_min, S_max, 400)

    # Compute varphi_P(S) = max(K_P - S, 0) - P
    varphi_P = np.maximum(K_P - S, 0) - P

    # Compute varphi_C(S) = max(S - K_C, 0) - C
    varphi_C = np.maximum(S - K_C, 0) - C

    # Compute total varphi = varphi_P + varphi_C
    varphi = varphi_P + varphi_C

    # Find the breakeven points where varphi = 0
    S_breakeven_low = K_P - P - C
    S_breakeven_high = K_C + P + C

    # Separate by sign of varphi to color differently
    mask_green_low = (varphi >= 0) & (S < S_breakeven_low)
    mask_green_mid = (varphi >= 0) & (S >= S_breakeven_low) & (S <= S_breakeven_high)
    mask_green_high = (varphi >= 0) & (S > S_breakeven_high)
    mask_red = (varphi < 0) & (S >= S_breakeven_low) & (S <= S_breakeven_high)

    # Define colors
    green_muted = "#66A266"
    red_muted = "#CC6666"

    # Plot green regions where varphi >= 0 (lower)
    ax.plot(S[mask_green_low], varphi[mask_green_low],
             color=green_muted, linewidth=line_thickness)

    # Plot red regions where varphi < 0
    ax.plot(S[mask_red], varphi[mask_red],
             color=red_muted, linewidth=line_thickness)

    # Plot green regions where varphi >= 0 (middle)
    ax.plot(S[mask_green_mid], varphi[mask_green_mid],
             color=green_muted, linewidth=line_thickness)

    # Plot green regions where varphi >= 0 (upper)
    ax.plot(S[mask_green_high], varphi[mask_green_high],
             color=green_muted, linewidth=line_thickness)

    # Add a single thin black horizontal line at varphi = 0
    ax.axhline(0, color='black', linewidth=0.8, linestyle='-')

    # Breakeven markers
    ax.plot(S_breakeven_low, 0, color='black', marker='<', markersize=16, 
             linestyle='None', zorder=5)
    ax.plot(S_breakeven_high, 0, color='black', marker='>', markersize=16, 
             linestyle='None', zorder=5)

    # Markers for K_P and K_C
    ax.plot(K_P, 0, color='black', marker='3', markersize=16, 
             linestyle='None', label=r'$S_{-}$', zorder=5)  
    ax.plot(K_C, 0, color='black', marker='4', markersize=16, 
             linestyle='None', label=r'$S_{+}$', zorder=5)  

    # Y-axis label
    ax.set_ylabel(r'$\varphi(S)$ (\$)')

    # X-axis and Y-axis limits
    ax.set_xlim([S_min, S_max])
    ax.set_ylim([y_min, y_max])

def main():
    """
    Main function to generate a single figure containing a sequence of strangle P/L plots with varying K_P and K_C.
    Only the bottom subplot gets the horizontal axis label.
    """
    # Define the premiums
    P = 1  # Premium for Put option
    C = 1  # Premium for Call option

    # Define the range of underlying asset prices
    S_min, S_max = 20, 30

    # Define the y-axis range
    y_min, y_max = -2.5, 6

    # Define the list of (K_P, K_C) pairs for the 5 plots
    K_pairs = [
        (24, 26),      
        (25, 25),      
        (25.5, 24.5),      
        (26, 24),      
        (27.5, 22.5)
    ]

    num_plots = len(K_pairs)

    # Create subplots
    fig, axes = plt.subplots(nrows=num_plots, ncols=1, figsize=(6, 2*num_plots), dpi=300, sharex=True)

    # If there's only one subplot, axes is not a list; make it a list for consistency
    if num_plots == 1:
        axes = [axes]

    # Iterate over the pairs and generate plots
    for idx, (ax, (K_P, K_C)) in enumerate(zip(axes, K_pairs)):
        plot_strangle(ax, P, C, K_P, K_C, S_min, S_max, y_min, y_max)
        
        # Remove subplot titles (eliminated as per user request)
        # ax.set_title(f'Sequence {idx+1}: $K_P$={K_P}, $K_C$={K_C}', fontsize=14)

        # Add x-axis label only to the bottom subplot
        if idx == num_plots - 1:
            ax.set_xlabel(r'$S$ (\$)')
        else:
            # Hide x-axis labels for other subplots
            ax.label_outer()

    # Adjust layout for better spacing
    plt.tight_layout()

    # Save the combined figure
    output_filename = 'strangle_sequence.pdf'
    plt.savefig(output_filename, bbox_inches='tight')
    plt.close()

    print(f'Generated {output_filename} with {num_plots} subplots.')

if __name__ == "__main__":
    main()