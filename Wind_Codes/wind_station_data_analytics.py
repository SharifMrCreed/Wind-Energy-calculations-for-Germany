"""
Wind Station Data Analytics
---------------------------
An interactive tool for exploring and visualizing wind energy datasets.

Launch with:
    python -m Wind_Codes.wind_station_data_analytics

Capabilities:
- Browse and select from available Excel and JSON datasets.
- Inspect data summaries and schemas.
- Generate a wide variety of plots:
    - Bar charts for station comparisons.
    - Time series graphs for trend analysis.
    - Heatmaps for temporal patterns (hourly, weekly, monthly).
    - Statistical distribution plots.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import warnings
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

# --- Setup ---
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
plt.style.use('default')
sns.set_palette("husl")
pd.options.mode.chained_assignment = None
console = Console()

# --- Configuration ---
try:
    HERE = Path(__file__).resolve().parent
    PROJECT_ROOT = HERE.parent
except NameError:
    HERE = Path.cwd()
    PROJECT_ROOT = HERE

GRAPH_DIR = PROJECT_ROOT / "Wind_Codes" / "graph"
DATA_DIR = PROJECT_ROOT / "Wind_Codes" / "retrieved_data"


# --- Helper Utilities ---

def pretty_title(title: str):
    """Prints a formatted title rule to the console."""
    console.rule(f"[bold cyan]{title}")


def display_plot(filename: str):
    """Saves the plot and displays it in an interactive matplotlib window."""
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    filepath = GRAPH_DIR / filename

    # Save a copy of the plot
    try:
        plt.savefig(filepath)
        rel_path = filepath.relative_to(PROJECT_ROOT)
        console.print(f"\n[bold green]📊 Plot saved to {rel_path}[/bold green]")
    except Exception as e:
        console.print(f"❌ [bold red]Error saving plot:[/] {e}", style="bold red")

    # Show the plot in an interactive window
    console.print("[yellow]A window with the chart is opening – close it to return to the menu.[/yellow]")
    try:
        plt.show()
    except Exception as e:
        console.print(f"❌ [bold red]Error displaying plot:[/] {e}", style="bold red")

    plt.close()  # Close the plot object to free memory after the window is closed
    console.print("[bold cyan]Chart window closed.[/bold cyan]\n")


def prompt_for_choice(prompt_text: str) -> str:
    """Handles user input and exit commands."""
    try:
        choice = Prompt.ask(prompt_text).strip().lower()
        if choice in ['q', 'quit', 'exit']:
            console.print("\n[bold magenta]Exiting. Goodbye![/bold magenta]")
            sys.exit()
        return choice
    except (KeyboardInterrupt):
        console.print("\n[bold magenta]Exiting. Goodbye![/bold magenta]")
        sys.exit()


# --- Plotting Functions ---

def plot_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str, filename: str):
    """Generates and displays a bar chart."""
    if x_col not in df.columns or y_col not in df.columns:
        console.print(f"❌ [bold red]Error:[/] Required columns '{x_col}' or '{y_col}' not in DataFrame.", style="bold red")
        return

    df_sorted = df.sort_values(by=y_col, ascending=False).head(20) # Top 20
    
    plt.figure(figsize=(12, 8))
    sns.barplot(data=df_sorted, x=x_col, y=y_col, palette='viridis')
    plt.title(title, fontsize=16)
    plt.xlabel(x_col, fontsize=12)
    plt.ylabel(y_col, fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    display_plot(filename)


def plot_time_series(df: pd.DataFrame, time_col: str, data_col: str, freq: str, filename: str):
    """Generates and displays a time series plot."""
    if time_col not in df.columns or data_col not in df.columns:
        console.print(f"❌ [bold red]Error:[/] Required columns not found for time series.", style="bold red")
        return

    df[time_col] = pd.to_datetime(df[time_col])
    ts_df = df.set_index(time_col)[data_col].resample(freq).sum().reset_index()
    
    plt.figure(figsize=(15, 7))
    plt.plot(ts_df[time_col], ts_df[data_col], marker='o', linestyle='-', markersize=4)
    plt.title(f'Time Series Analysis ({freq}) of {data_col}', fontsize=16)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel(f'Total {data_col}', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    display_plot(filename)


def plot_heatmap(df: pd.DataFrame, time_col: str, data_col: str, period: str, filename: str):
    """Generates and displays a heatmap for temporal analysis."""
    if time_col not in df.columns or data_col not in df.columns:
        console.print(f"❌ [bold red]Error:[/] Required columns not found for heatmap.", style="bold red")
        return

    df[time_col] = pd.to_datetime(df[time_col])
    
    if period == 'hourly':
        df['x_axis'] = df[time_col].dt.hour
        df['y_axis'] = df[time_col].dt.day_name()
        pivot = df.pivot_table(values=data_col, index='y_axis', columns='x_axis', aggfunc='mean')
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        pivot = pivot.reindex(day_order)
        title = f'Hourly Average of {data_col} by Day of Week'
    elif period == 'monthly':
        df['x_axis'] = df[time_col].dt.strftime('%b') # Month abbreviation
        df['y_axis'] = df[time_col].dt.year
        pivot = df.pivot_table(values=data_col, index='y_axis', columns='x_axis', aggfunc='mean')
        month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        pivot = pivot.reindex(columns=month_order)
        title = f'Monthly Average of {data_col} by Year'
    else:
        console.print("❌ [bold red]Error:[/] Invalid period for heatmap. Use 'hourly' or 'monthly'.", style="bold red")
        return
        
    plt.figure(figsize=(16, 8))
    sns.heatmap(pivot, annot=False, cmap='YlOrRd', cbar_kws={'label': f'Average {data_col}'})
    plt.title(title, fontsize=16)
    plt.xlabel(f"{'Hour of Day' if period == 'hourly' else 'Month'}", fontsize=12)
    plt.ylabel(f"{'Day of Week' if period == 'hourly' else 'Year'}", fontsize=12)
    plt.tight_layout()
    display_plot(filename)


def plot_roughness_polar(station: str, profile: dict, filename: str):
    """Create and display a polar bar chart of z0 vs wind direction."""
    directions = [int(d) for d in profile.keys() if d != "height"]
    z0_values = [float(profile[str(d)]) for d in directions]

    # Convert degrees to radians for polar plot, ensure sorted order
    if not directions:
        console.print("❌ [bold red]Error:[/] No direction data to plot.", style="bold red")
        return
        
    pairs = sorted(zip(directions, z0_values))
    directions_rad = [d * (np.pi / 180.0) for d, _ in pairs]
    z0_sorted = [v for _, v in pairs]

    plt.figure(figsize=(8, 8))
    ax = plt.subplot(111, polar=True)
    ax.bar(directions_rad, z0_sorted, width=np.pi/12, bottom=0.0, color="coral", alpha=0.7)
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_title(f"Roughness Length (z0)\n{station}", fontsize=16)
    display_plot(filename)


def explore_roughness_json(data: dict, filename_stem: str):
    """Interactive exploration for roughness_length JSON files."""
    stations = sorted(data.keys())

    while True:
        pretty_title("Roughness Profile Explorer")
        
        tbl = Table(title="Select a Station", header_style="bold green")
        tbl.add_column("#", justify="right", style="cyan")
        tbl.add_column("Station")
        for idx, name in enumerate(stations, 1):
            tbl.add_row(str(idx), name)
        tbl.add_row("0", "Back to File Selection")
        console.print(tbl)

        choice = prompt_for_choice("Choose a station to view its roughness profile")
        if choice == "0":
            break
        
        try:
            choice_idx = int(choice) - 1
            if not (0 <= choice_idx < len(stations)):
                console.print("⚠️ [bold yellow]Invalid number. Please try again.[/bold yellow]\n")
                continue
        except ValueError:
            console.print("⚠️ [bold yellow]Invalid input. Please enter a number.[/bold yellow]\n")
            continue

        station_name = stations[choice_idx]
        profile = data[station_name]
        directions = [k for k in profile.keys() if k != "height"]

        # Display profile table
        ptab = Table(title=f"Roughness profile for {station_name}", show_header=True, header_style="bold magenta")
        ptab.add_column("Direction (°)", style="cyan")
        ptab.add_column("z0 (m)", justify="right")
        for d in sorted(directions, key=int):
            ptab.add_row(d, str(profile[d]))
        console.print(ptab)

        # Plot polar graph
        plot_roughness_polar(station_name, profile, f"{filename_stem}_{station_name}_z0.png")
        console.print("\n[italic]Returning to the station list...[/italic]")


# --- Data Loading and Exploration ---

def load_and_explore(file_path: Path):
    """Loads a file into a DataFrame and presents an analytics menu."""
    pretty_title(f"Analyzing: {file_path.name}")
    try:
        if file_path.suffix.lower() == ".json":
            with open(file_path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            
            # Check for aggregated station data format
            if "Stations" in data and isinstance(data["Stations"], list):
                records = []
                for station in data.get("Stations", []):
                    metrics = data.get(station, {})
                    if "Power" in metrics and "Energy" in metrics:
                         records.append({
                            "Station": station,
                            "Power": metrics.get("Power", 0.0),
                            "Energy": metrics.get("Energy", 0.0),
                        })
                df = pd.DataFrame(records)
                # Proceed to the main analytics menu
                show_analytics_menu(df, file_path.stem)

            else: # Assuming roughness length or other format
                 explore_roughness_json(data, file_path.stem)
                 return # Return to file selection after finishing with roughness explorer
        
        elif file_path.suffix.lower() == ".xlsx":
            df = pd.read_excel(file_path)
            # Standardize column names to match plotting functions
            rename_map = {
                "Power_kW": "Power",
                "Energy_kWh": "Energy",
                "STATIONS_ID": "Station"
            }
            df.rename(columns=rename_map, inplace=True)
            show_analytics_menu(df, file_path.stem)
        else:
            console.print(f"❌ [bold red]Error:[/] Unsupported file type: {file_path.suffix}", style="bold red")
            return
    except Exception as e:
        console.print(f"❌ [bold red]Error loading or parsing file:[/] {e}", style="bold red")
        return

    if df.empty:
        console.print("⚠️ [bold yellow]Warning:[/] The loaded DataFrame is empty. No analysis can be performed.", style="bold yellow")
        return
        
    show_analytics_menu(df, file_path.stem)


def show_analytics_menu(df: pd.DataFrame, filename_stem: str):
    """Displays a menu of analytics options based on DataFrame columns."""
    while True:
        pretty_title("Analytics Menu")
        console.print(f"[bold]Dataset Columns:[/] {', '.join(df.columns)}\n")

        # Dynamically build menu
        menu = Table(show_header=False, title="What would you like to do?")
        menu.add_column("#", style="cyan", justify="right")
        menu.add_column("Action")

        menu.add_row("1", "Show Data Summary & Preview")
        
        has_time_col = "MESS_DATUM" in df.columns
        has_power_col = "Power" in df.columns
        has_station_col = "Station" in df.columns
        
        # Plotting options
        if has_station_col and has_power_col:
            menu.add_row("2", "Bar Chart: Power by Station")
        if has_time_col and has_power_col:
            menu.add_row("3", "Time Series Plot (Monthly)")
            menu.add_row("4", "Time Series Plot (Weekly)")
            menu.add_row("5", "Heatmap (Hourly Power vs. Day of Week)")
            menu.add_row("6", "Heatmap (Monthly Power vs. Year)")
        
        menu.add_row("0", "Back to File Selection")
        console.print(menu)

        choice = prompt_for_choice("Choose an analysis")

        if choice == "1":
            pretty_title("Data Summary")
            console.print(df.describe())
            pretty_title("Data Preview (First 5 Rows)")
            console.print(df.head())

        elif choice == "2" and has_station_col and has_power_col:
            plot_bar_chart(df, 'Station', 'Power', 'Power per Station', f"{filename_stem}_bar.png")
        
        elif choice == "3" and has_time_col and has_power_col:
            plot_time_series(df, 'MESS_DATUM', 'Power', 'M', f"{filename_stem}_ts_monthly.png")
            
        elif choice == "4" and has_time_col and has_power_col:
            plot_time_series(df, 'MESS_DATUM', 'Power', 'W', f"{filename_stem}_ts_weekly.png")
            
        elif choice == "5" and has_time_col and has_power_col:
            plot_heatmap(df, 'MESS_DATUM', 'Power', 'hourly', f"{filename_stem}_heatmap_hourly.png")

        elif choice == "6" and has_time_col and has_power_col:
            plot_heatmap(df, 'MESS_DATUM', 'Power', 'monthly', f"{filename_stem}_heatmap_monthly.png")

        elif choice == "0":
            console.print("[bold cyan]Returning to file selection...[/bold cyan]")
            break
        else:
            console.print("⚠️ [bold yellow]Invalid selection or requirements not met for this option. Please try again.[/bold yellow]")
        
        if choice in ["1", "2", "3", "4", "5", "6"]:
            console.print("\n[italic]Returning to the analytics menu...[/italic]")


# --- Main Application Loop ---

def main():
    """Main function to run the data explorer CLI."""
    pretty_title("🌬️ Wind Station Data Analytics 🌬️")
    console.print(Panel(
        "Welcome! This tool allows you to interactively explore and visualize wind energy datasets.",
        subtitle="Select a file to begin."
    ))

    if not DATA_DIR.exists():
        console.print(f"❌ [bold red]Error:[/] Data directory not found at '{DATA_DIR}'", style="bold red")
        return

    files = sorted([p for p in DATA_DIR.iterdir() if p.suffix.lower() in {".json", ".xlsx"}])
    if not files:
        console.print(f"⚠️ [bold yellow]Warning:[/] No .json or .xlsx files found in '{DATA_DIR}'", style="bold yellow")
        return

    while True:
        pretty_title("Available Datasets")
        file_table = Table(show_header=True, header_style="bold green")
        file_table.add_column("#", style="cyan", justify="right")
        file_table.add_column("Filename")
        file_table.add_column("Type")
        
        for idx, f in enumerate(files, 1):
            file_table.add_row(str(idx), f.name, f.suffix.lower())
        
        console.print(file_table)
        console.print("Enter 'q' to quit at any time.")

        choice = prompt_for_choice("\nSelect a dataset to explore by number")
        
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(files):
                load_and_explore(files[choice_idx])
            else:
                console.print("⚠️ [bold yellow]Invalid number. Please try again.[/bold yellow]\n")
        except ValueError:
            console.print("⚠️ [bold yellow]Invalid input. Please enter a number from the list.[/bold yellow]\n")


if __name__ == "__main__":
    main() 