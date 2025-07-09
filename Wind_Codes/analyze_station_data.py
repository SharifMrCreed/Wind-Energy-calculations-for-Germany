"""
Wind Data Downloader & Analyzer
===============================
A unified, interactive tool for downloading, processing, and visualizing wind energy data from the DWD.

Launch with:
    python -m Wind_Codes.analyze_station_data

Capabilities:
- Download data for a single station or all available stations concurrently.
- Correctly handles historical timezone differences (pre-2000 MEZ/UTC).
- Immediately offers to analyze newly downloaded data.
- Provides a full suite of interactive plotting tools for any dataset.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import sys
import warnings
import zipfile
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import httpx
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from .formulas.wind_formulas import calculate_power, calculate_vz, find_roughness_length

# --- Setup & Configuration ---
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
plt.style.use('default')
sns.set_palette("husl")
pd.options.mode.chained_assignment = None
console = Console()

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    HERE = Path(__file__).resolve().parent
    PROJECT_ROOT = HERE.parent
except NameError:
    # Fallback for interactive environments
    HERE = Path.cwd()
    PROJECT_ROOT = HERE

BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/"
METADATA_URL = f"{BASE_URL}historical/zehn_min_ff_Beschreibung_Stationen.txt"
DATA_DIR = PROJECT_ROOT / "Wind_Codes" / "retrieved_data"
GRAPH_DIR = PROJECT_ROOT / "Wind_Codes" / "graph"
ROUGHNESS_FILE_PATH = DATA_DIR / 'roughness_length.json'

# --- Generic Helper Utilities ---

def pretty_title(title: str):
    """Prints a formatted title rule to the console."""
    console.rule(f"[bold cyan]{title}")

def prompt_for_choice(prompt_text: str, default: str = "") -> str:
    """Handles user input and exit commands."""
    try:
        choice = Prompt.ask(prompt_text, default=default).strip().lower()
        if choice in ['q', 'quit', 'exit']:
            console.print("\n[bold magenta]Exiting. Goodbye![/bold magenta]")
            sys.exit()
        return choice
    except (KeyboardInterrupt):
        console.print("\n[bold magenta]Exiting. Goodbye![/bold magenta]")
        sys.exit()

# --- Data Analytics & Plotting ---

def display_plot(filename: str):
    """Saves the plot and displays it in an interactive matplotlib window."""
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    filepath = GRAPH_DIR / filename
    try:
        plt.savefig(filepath)
        console.print(f"\n[bold green]📊 Plot saved to {filepath.relative_to(PROJECT_ROOT)}[/bold green]")
    except Exception as e:
        console.print(f"❌ [bold red]Error saving plot:[/] {e}")
    console.print("[yellow]A window with the chart is opening – close it to return to the menu.[/yellow]")
    try:
        plt.show()
    except Exception as e:
        console.print(f"❌ [bold red]Error displaying plot:[/] {e}")
    plt.close()
    console.print("[bold cyan]Chart window closed.[/bold cyan]\n")

def plot_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str, filename: str):
    """Generates and displays a bar chart."""
    df_sorted = df.sort_values(by=y_col, ascending=False).head(20)
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
    df[time_col] = pd.to_datetime(df[time_col])
    if period == 'hourly':
        df['x_axis'], df['y_axis'] = df[time_col].dt.hour, df[time_col].dt.day_name()
        pivot = df.pivot_table(values=data_col, index='y_axis', columns='x_axis', aggfunc='mean')
        pivot = pivot.reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
        title, xlabel, ylabel = f'Hourly Average of {data_col}', 'Hour of Day', 'Day of Week'
    elif period == 'monthly':
        df['x_axis'], df['y_axis'] = df[time_col].dt.strftime('%b'), df[time_col].dt.year
        pivot = df.pivot_table(values=data_col, index='y_axis', columns='x_axis', aggfunc='mean')
        pivot = pivot.reindex(columns=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
        title, xlabel, ylabel = f'Monthly Average of {data_col}', 'Month', 'Year'
    else:
        return

    plt.figure(figsize=(16, 8))
    sns.heatmap(pivot, annot=False, cmap='YlOrRd', cbar_kws={'label': f'Average {data_col}'})
    plt.title(title, fontsize=16)
    plt.xlabel(xlabel, fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.tight_layout()
    display_plot(filename)

def plot_roughness_polar(station: str, profile: dict, filename: str):
    """Create and display a polar bar chart of z0 vs wind direction."""
    directions = [int(d) for d in profile.keys() if d != "height"]
    if not directions:
        console.print("❌ [bold red]Error:[/] No direction data to plot.")
        return
    z0_values = [float(profile[str(d)]) for d in directions]
    pairs = sorted(zip(directions, z0_values))
    directions_rad = [d * (np.pi / 180.0) for d, _ in pairs]
    z0_sorted = [v for _, v in pairs]

    plt.figure(figsize=(8, 8))
    ax = plt.subplot(111, polar=True)
    ax.bar(directions_rad, z0_sorted, width=np.pi / 12, bottom=0.0, color="coral", alpha=0.7)
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
        if choice == "0": break
        try:
            station_name = stations[int(choice) - 1]
            profile = data[station_name]
            ptab = Table(title=f"Roughness profile for {station_name}", header_style="bold magenta")
            ptab.add_column("Direction (°)", style="cyan")
            ptab.add_column("z0 (m)", justify="right")
            for d in sorted([k for k in profile.keys() if k != "height"], key=int):
                ptab.add_row(d, str(profile[d]))
            console.print(ptab)
            plot_roughness_polar(station_name, profile, f"{filename_stem}_{station_name}_z0.png")
        except (ValueError, IndexError):
            console.print("⚠️ [bold yellow]Invalid input. Please enter a number from the list.[/bold yellow]\n")

def show_analytics_menu(df: pd.DataFrame, filename_stem: str):
    """Displays a menu of analytics options based on DataFrame columns."""
    while True:
        pretty_title("Analytics Menu")
        console.print(f"[bold]Dataset Columns:[/] {', '.join(df.columns)}\n")
        menu = Table(show_header=False, title="What would you like to do?")
        menu.add_column("#", style="cyan", justify="right")
        menu.add_column("Action")
        menu.add_row("1", "Show Data Summary & Preview")

        has_time_col, has_power_col, has_station_col = "MESS_DATUM" in df.columns, "Power" in df.columns, "Station" in df.columns
        if has_station_col and has_power_col: menu.add_row("2", "Bar Chart: Power by Station")
        if has_time_col and has_power_col:
            menu.add_row("3", "Time Series Plot (Monthly)")
            menu.add_row("4", "Time Series Plot (Weekly)")
            menu.add_row("5", "Heatmap (Hourly Power vs. Day of Week)")
            menu.add_row("6", "Heatmap (Monthly Power vs. Year)")
        menu.add_row("0", "Back to Main Menu")
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
            break
        else:
            console.print("⚠️ [bold yellow]Invalid selection or requirements not met for this option.[/bold yellow]")
        if choice in ["1", "2", "3", "4", "5", "6"]:
            console.print("\n[italic]Returning to the analytics menu...[/italic]")

# --- Data Acquisition ---

def compare(a, b): return SequenceMatcher(None, a, b).ratio()

def match_name(name, dictionary):
    best_match = max(dictionary.keys(), key=lambda k: compare(name, k), default=name)
    return best_match if compare(name, best_match) > 0.5 else name

def load_roughness_data():
    """Loads roughness length data from the JSON file."""
    if not ROUGHNESS_FILE_PATH.exists():
        logging.error(f"Roughness data not found at {ROUGHNESS_FILE_PATH}")
        return None
    with open(ROUGHNESS_FILE_PATH, 'r') as f:
        return json.load(f)

def perform_power_energy_calculations(df, station_roughness, station_height):
    """Applies power and energy calculations to a dataframe."""
    if not station_roughness or not station_height: return df.copy()
    hub_height = 200
    df['FF_10'] = pd.to_numeric(df['FF_10'], errors='coerce')
    df['DD_10'] = pd.to_numeric(df['DD_10'], errors='coerce')
    df.dropna(subset=['FF_10', 'DD_10'], inplace=True)
    df['DD_10'] = df['DD_10'].astype(int)
    df['z0'] = df['DD_10'].apply(lambda x: find_roughness_length(station_roughness, x))
    df.dropna(subset=['z0'], inplace=True)
    if df.empty: return df.copy()
    df['z0'] = df['z0'].astype(float)
    df[f'V({hub_height})'] = df.apply(lambda x: calculate_vz(x['FF_10'], x['z0'], station_height, hub_height), axis=1)
    df['Power_kW'] = df[f'V({hub_height})'].apply(lambda x: calculate_power(x) / 1000)
    df['Energy_kWh'] = df['Power_kW'] * (10 / 60)
    return df

async def get_stations_df():
    """Fetches and parses the station description file."""
    async with httpx.AsyncClient() as client:
        response = await client.get(METADATA_URL, timeout=30.0)
        response.raise_for_status()
    col_specs = [(0, 5), (6, 15), (15, 24), (24, 39), (39, 51), (51, 61), (61, 102), (102, -1)]
    return pd.read_fwf(
        io.StringIO(response.content.decode('latin-1')),
        colspecs=col_specs, skiprows=2,
        names=["Stations_id", "von_datum", "bis_datum", "Stationshoehe", "geoBreite", "geoLaenge", "Stationsname", "Bundesland"])

async def _get_all_file_urls(driver):
    """Scrapes all file URLs from the DWD data directories."""
    logging.warning("Pre-fetching all file URLs from DWD server...")
    file_urls_by_station = {}
    patterns = {
        "historical": re.compile(r'_(\d{5})_.*_hist\.zip$'),
        "recent": re.compile(r'_(\d{5})_akt\.zip$'),
        "now": re.compile(r'_(\d{5})\.zip$')
    }
    for key, pattern in patterns.items():
        url = f"{BASE_URL}{key}/"
        try:
            driver.get(url)
            for link in driver.find_elements(By.TAG_NAME, 'a'):
                href = link.get_attribute('href')
                if href and (match := pattern.search(href.split('/')[-1])):
                    station_id = match.group(1)
                    file_urls_by_station.setdefault(station_id, []).append(href)
        except Exception as e:
            logging.error(f"Failed to scrape {url}: {e}")
    logging.warning(f"Finished pre-fetching URLs for {len(file_urls_by_station)} stations.")
    return file_urls_by_station

async def process_station_data(station_id, start_date_str, end_date_str, stations_df, roughness_data, zip_files_urls):
    """Core data processing logic for a single station. Returns a DataFrame."""
    logging.info(f"Processing station {station_id} from {start_date_str} to {end_date_str}.")
    if not zip_files_urls: return None
    all_data = []
    async with httpx.AsyncClient(timeout=90.0) as client:
        responses = await asyncio.gather(*[client.get(url) for url in zip_files_urls], return_exceptions=True)
    for response in responses:
        if isinstance(response, httpx.Response) and response.status_code == 200:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                for file_name in zf.namelist():
                    if file_name.startswith("produkt"):
                        with zf.open(file_name) as f:
                            lines = f.read().decode('utf-8').strip().split('\n')[1:]
                            all_data.extend([row.split(';') for row in lines if ' -999' not in row])
    if not all_data: return None
    
    df = pd.DataFrame(all_data, columns=['STATIONS_ID', 'MESS_DATUM', 'QN_3', 'FF_10', 'DD_10', 'eor'])
    def parse_date(date_str):
        dt = datetime.strptime(date_str, '%Y%m%d%H%M')
        return pd.to_datetime(dt).tz_localize('Europe/Berlin' if dt.year < 2000 else 'UTC', ambiguous='NaT', nonexistent='NaT').tz_convert('UTC')
    df['MESS_DATUM'] = df['MESS_DATUM'].apply(parse_date)
    df.dropna(subset=['MESS_DATUM'], inplace=True)

    start_dt, end_dt = pd.to_datetime(start_date_str).tz_localize('UTC'), pd.to_datetime(end_date_str).tz_localize('UTC')
    df = df[(df['MESS_DATUM'] >= start_dt) & (df['MESS_DATUM'] <= end_dt)].copy()
    if df.empty: return None

    station_name_dwd = stations_df.loc[stations_df['Stations_id'] == int(station_id), 'Stationsname'].iloc[0]
    station_name_matched = match_name(station_name_dwd.replace('_', ' '), roughness_data)
    if station_name_matched not in roughness_data: return None
    
    station_roughness = roughness_data[station_name_matched]
    return perform_power_energy_calculations(df, station_roughness, station_roughness.get('height'))

async def download_all_stations_flow(stations_df, roughness_data, start_date_str, end_date_str, driver):
    """Concurrent download and aggregation for all stations."""
    file_urls = await _get_all_file_urls(driver)
    semaphore = asyncio.Semaphore(25)
    
    async def worker(station_row):
        async with semaphore:
            station_id = f"{station_row['Stations_id']:05d}"
            return await process_station_data(station_id, start_date_str, end_date_str, stations_df, roughness_data, file_urls.get(station_id, []))
            
    tasks = [worker(row) for _, row in stations_df.iterrows()]
    results = await asyncio.gather(*tasks)
    
    valid_dfs = [df for df in results if df is not None and not df.empty]
    if not valid_dfs: return None, None
    
    logging.warning(f"Aggregating data from {len(valid_dfs)} stations...")
    master_df = pd.concat(valid_dfs).groupby('MESS_DATUM')[['Power_kW', 'Energy_kWh']].sum().reset_index()
    
    filename = f"combined_{start_date_str}_to_{end_date_str}.xlsx"
    output_path = DATA_DIR / filename
    master_df['MESS_DATUM'] = master_df['MESS_DATUM'].dt.tz_localize(None)
    master_df.to_excel(output_path, index=False)
    logging.warning(f"Successfully saved aggregated data to {output_path}")
    return master_df, output_path

async def run_download_flow():
    """Guides user through downloading new data."""
    stations_df = await get_stations_df()
    roughness_data = load_roughness_data()
    if stations_df.empty or not roughness_data:
        logging.error("Could not load required station or roughness data.")
        return None, None

    pretty_title("Download New Data")
    choice = prompt_for_choice("Download for [1] All Stations or [2] A Single Station?", default="1")
    
    driver = None
    df, out_path = None, None
    try:
        driver = webdriver.Chrome()
        if choice == "1":
            start = prompt_for_choice("Enter start date (YYYY-MM-DD)", default="2022-01-01")
            end = prompt_for_choice("Enter end date (YYYY-MM-DD)", default="2023-01-01")
            
            roughness_names = set(roughness_data.keys())
            def has_data(name): return match_name(str(name).replace('_', ' '), roughness_data) in roughness_names
            filtered_df = stations_df[stations_df['Stationsname'].apply(has_data)].copy()
            logging.warning(f"Found {len(filtered_df)} stations with roughness data to process.")
            
            df, out_path = await download_all_stations_flow(filtered_df, roughness_data, start, end, driver)
        
        elif choice == "2":
            roughness_station_names = sorted(list(roughness_data.keys()))
            
            pretty_title("Select a Station")
            tbl = Table(title="Stations with available roughness data", header_style="bold green")
            tbl.add_column("#", justify="right", style="cyan")
            tbl.add_column("Station Name")
            for i, name in enumerate(roughness_station_names):
                tbl.add_row(str(i + 1), name)
            console.print(tbl)

            selected_station_id_str = None
            while True:
                station_input = prompt_for_choice(f"Enter the name or number of the station (1-{len(roughness_station_names)})")
                selected_name = None
                if station_input.isdigit() and (0 <= int(station_input) - 1 < len(roughness_station_names)):
                    selected_name = roughness_station_names[int(station_input) - 1]
                else:
                    name_match = next((name for name in roughness_station_names if name.lower() == station_input.lower()), None)
                    if name_match:
                        selected_name = name_match
                    else:
                        console.print("⚠️ [bold yellow]Invalid input. Please enter a valid name or number.[/bold yellow]")
                        continue
                
                # Find the corresponding station ID
                found_station_row = None
                for _, row in stations_df.iterrows():
                    dwd_name = str(row['Stationsname']).replace('_', ' ')
                    if match_name(dwd_name, roughness_data) == selected_name:
                        found_station_row = row
                        break
                
                if found_station_row is not None:
                    selected_station_id_str = f"{found_station_row['Stations_id']:05d}"
                    console.print(f"✅ Found DWD station: '[bold cyan]{found_station_row['Stationsname']}[/]' with ID [bold cyan]{selected_station_id_str}[/] for selected name '[bold cyan]{selected_name}[/]'")
                    break
                else:
                    console.print(f"❌ [bold red]Error:[/] Could not find a matching DWD station for '{selected_name}'.")

            if selected_station_id_str:
                all_urls = await _get_all_file_urls(driver)
                station_urls = all_urls.get(selected_station_id_str, [])
                
                start_date = prompt_for_choice("Enter start date (YYYY-MM-DD)", default="2022-01-01")
                end_date = prompt_for_choice("Enter end date (YYYY-MM-DD)", default="2023-01-01")

                df = await process_station_data(selected_station_id_str, start_date, end_date, stations_df, roughness_data, station_urls)
                
                if df is not None and not df.empty:
                    station_name_clean = selected_name.replace('/', '-').replace(' ', '_').replace(',', '')
                    filename = f"{station_name_clean}_{selected_station_id_str}_{start_date}_to_{end_date}.xlsx"
                    out_path = DATA_DIR / filename
                    df['MESS_DATUM'] = df['MESS_DATUM'].dt.tz_localize(None)
                    df.to_excel(out_path, index=False)
                    console.print(f"✅ [bold green]Successfully saved data to {out_path}[/bold green]")
                else:
                    console.print(f"⚠️ [bold yellow]Warning:[/] No data found or processed for the selected station and date range.")

    finally:
        if driver:
            driver.quit()
    
    return df, out_path

def run_analysis_flow():
    """Guides user through analyzing existing files."""
    if not DATA_DIR.exists():
        console.print(f"❌ [bold red]Error:[/] Data directory not found at '{DATA_DIR}'")
        return

    files = sorted([p for p in DATA_DIR.iterdir() if p.suffix.lower() in {".json", ".xlsx"}])
    if not files:
        console.print(f"⚠️ [bold yellow]Warning:[/] No .json or .xlsx files found in '{DATA_DIR}'")
        return

    while True:
        pretty_title("Analyze Existing Dataset")
        tbl = Table(show_header=True, header_style="bold green")
        tbl.add_column("#", style="cyan", justify="right")
        tbl.add_column("Filename"); tbl.add_column("Type")
        for idx, f in enumerate(files, 1): tbl.add_row(str(idx), f.name, f.suffix.lower())
        tbl.add_row("0", "Back to Main Menu")
        console.print(tbl)
        
        choice = prompt_for_choice("Select a dataset to explore by number")
        if choice == '0': break
        try:
            file_path = files[int(choice) - 1]
            pretty_title(f"Analyzing: {file_path.name}")
            if file_path.suffix == ".json":
                with open(file_path, "r") as fp:
                    explore_roughness_json(json.load(fp), file_path.stem)
            elif file_path.suffix == ".xlsx":
                df = pd.read_excel(file_path)
                rename_map = {"Power_kW": "Power", "Energy_kWh": "Energy", "STATIONS_ID": "Station"}
                df.rename(columns=rename_map, inplace=True)
                show_analytics_menu(df, file_path.stem)
        except (ValueError, IndexError):
            console.print("⚠️ [bold yellow]Invalid number. Please try again.[/bold yellow]\n")

async def main():
    """Main function to run the application."""
    pretty_title("🌬️ Wind Data Downloader & Analyzer 🌬️")
    console.print(Panel("Welcome! This tool unifies data downloading and analysis.", subtitle="Select an option to begin."))
    
    while True:
        menu = Table(show_header=False, title="Main Menu")
        menu.add_column("#", style="cyan", justify="right")
        menu.add_column("Action")
        menu.add_row("1", "Download New Data")
        menu.add_row("2", "Analyze Existing Data")
        menu.add_row("0", "Exit")
        console.print(menu)
        
        choice = prompt_for_choice("Choose an option")

        if choice == "1":
            new_df, new_path = await run_download_flow()
            if new_df is not None and not new_df.empty:
                analyze_now = prompt_for_choice(f"Data saved to {new_path.name}. Analyze it now? [Y/n]", default="y")
                if analyze_now == 'y':
                    rename_map = {"Power_kW": "Power", "Energy_kWh": "Energy", "STATIONS_ID": "Station"}
                    new_df.rename(columns=rename_map, inplace=True)
                    show_analytics_menu(new_df, new_path.stem)
        elif choice == "2":
            run_analysis_flow()
        elif choice == "0":
            console.print("\n[bold magenta]Exiting. Goodbye![/bold magenta]")
            break
        else:
            console.print("⚠️ [bold yellow]Invalid choice. Please try again.[/bold yellow]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"A top-level error occurred: {e}", exc_info=True) 