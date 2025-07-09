import asyncio
import httpx
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import io
import logging
import zipfile
import os
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from ..formulas.wind_formulas import calculate_vz, calculate_power, find_roughness_length

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/"
METADATA_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/historical/zehn_min_ff_Beschreibung_Stationen.txt"
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RETRIEVED_DATA_DIR = os.path.join(PARENT_DIR, 'retrieved_data')
ROUGHNESS_FILE_PATH = os.path.join(RETRIEVED_DATA_DIR, 'roughness_length.json')

# --- Utility functions from weatherstation.py ---
def compare(a, b):
    return SequenceMatcher(None, a, b).ratio()

def match_name(name, dictionary):
    best_match = {'name': '', 'score': 0}
    for station in dictionary.keys():
        s_name = station
        s_score = compare(name, s_name)
        if s_score > best_match['score']:
            best_match = {'name': s_name, 'score': s_score}
    if best_match['score'] > 0.5:
        return best_match['name']
    else:
        return name

def load_roughness_data():
    """Loads roughness length data from the JSON file."""
    if not os.path.exists(ROUGHNESS_FILE_PATH):
        logging.error(f"Roughness data not found at {ROUGHNESS_FILE_PATH}")
        logging.error("Please run 'roughness_length_retrieve.py' first to generate this file.")
        return None
    with open(ROUGHNESS_FILE_PATH, 'r') as f:
        return json.load(f)

# --- Calculation functions ---
def perform_power_energy_calculations(df, station_roughness, station_height):
    """Applies power and energy calculations to a dataframe."""
    if not station_roughness or not station_height:
        logging.warning("Missing roughness or height data. Skipping calculations.")
        return df

    hub_height = 200  # Standard hub height for calculations

    # Ensure data is numeric and clean invalid entries
    df['FF_10'] = pd.to_numeric(df['FF_10'], errors='coerce')
    df['DD_10'] = pd.to_numeric(df['DD_10'], errors='coerce')
    df.dropna(subset=['FF_10', 'DD_10'], inplace=True)
    df['DD_10'] = df['DD_10'].astype(int)

    df['z0'] = df['DD_10'].apply(lambda x: find_roughness_length(station_roughness, x))
    
    # Drop rows where a roughness length could not be determined
    df.dropna(subset=['z0'], inplace=True)
    if df.empty:
        logging.warning("No valid data rows remaining after calculating roughness length.")
        return df.copy()

    df['z0'] = df['z0'].astype(float)

    df[f'V({hub_height})'] = df.apply(lambda x: calculate_vz(x['FF_10'], x['z0'], station_height, hub_height), axis=1)
    df['Power_kW'] = df[f'V({hub_height})'].apply(lambda x: calculate_power(x) / 1000)
    df['Energy_kWh'] = df['Power_kW'] * (10 / 60)
    return df

async def get_stations_df():
    """Fetches and parses the station description file into a pandas DataFrame."""
    logging.info("Fetching station data from DWD.")
    async with httpx.AsyncClient() as client:
        response = await client.get(METADATA_URL, timeout=30.0)
        response.raise_for_status()
    logging.info("Successfully fetched station data.")

    col_specs = [
        (0, 5), (6, 15), (15, 24), (24, 39), (39, 51), (51, 61), (61, 102), (102, -1),
    ]
    
    stations_df = pd.read_fwf(
        io.StringIO(response.content.decode('latin-1')),
        colspecs=col_specs,
        skiprows=2,
        names=["Stations_id", "von_datum", "bis_datum", "Stationshoehe", "geoBreite", "geoLaenge", "Stationsname", "Bundesland"]
    )
    logging.info(f"Successfully parsed station data. Shape: {stations_df.shape}")
    logging.info("Station data head:\n" + stations_df.head().to_string())
    return stations_df

async def download_and_process_data(station_id, start_date_str, end_date_str, stations_df, roughness_data, zip_files_urls):
    """Downloads, processes, and saves data for a given station and date range using pre-fetched URLs."""
    logging.info(f"Starting data processing for station {station_id} from {start_date_str} to {end_date_str}.")
    
    start_date = pd.to_datetime(start_date_str)
    end_date = pd.to_datetime(end_date_str)

    if not zip_files_urls:
        logging.warning(f"No data files found for station {station_id}.")
        return

    # Download and process data
    all_data = []
    columns = None
    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = [client.get(url) for url in zip_files_urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    for response in responses:
        if isinstance(response, Exception) or response.status_code != 200:
            logging.error(f"Failed to download from a URL. Response: {response}")
            continue
        
        zip_file = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_file, 'r') as wind_zip:
            for file_name in wind_zip.namelist():
                if file_name.startswith("produkt"):
                    with wind_zip.open(file_name) as text_file:
                        if columns is None:
                            columns = text_file.readline().decode('utf-8').strip().split(';')
                        else:
                            text_file.readline()
                        for line in text_file:
                            row = line.decode('utf-8').strip().split(';')
                            if len(row) > 4 and row[4] != '     -999': # Check for quality flag
                                all_data.append(row)

    if not all_data:
        logging.warning(f"No valid data rows found for station {station_id} after processing files.")
        return
        
    df = pd.DataFrame(all_data, columns=columns)
    
    # --- Timezone Normalization ---
    def parse_date_with_timezone(date_str):
        dt = datetime.strptime(date_str, '%Y%m%d%H%M')
        if dt.year < 2000:
            return pd.to_datetime(dt).tz_localize('Europe/Berlin', ambiguous='NaT', nonexistent='NaT').tz_convert('UTC')
        else:
            return pd.to_datetime(dt).tz_localize('UTC')

    df['MESS_DATUM'] = df['MESS_DATUM'].apply(parse_date_with_timezone)
    df.dropna(subset=['MESS_DATUM'], inplace=True) # Drop ambiguous DST timestamps
    # --- End Timezone Normalization ---

    # --- Filter by Date Range ---
    start_date_dt = pd.to_datetime(start_date_str).tz_localize('UTC')
    end_date_dt = pd.to_datetime(end_date_str).tz_localize('UTC')
    df = df[(df['MESS_DATUM'] >= start_date_dt) & (df['MESS_DATUM'] <= end_date_dt)].copy()
    if df.empty:
        logging.warning("No data available for the selected date range after filtering.")
        return
    # --- End Filter by Date Range ---

    # Get station name for filename
    station_name = "unknown"
    try:
        station_name_series = stations_df.loc[stations_df['Stations_id'] == int(station_id), 'Stationsname']
        if not station_name_series.empty:
            station_name = station_name_series.iloc[0].replace('/', '-').replace(' ', '_').replace(',', '')
    except (ValueError, IndexError):
        pass # Keep name as "unknown" if lookup fails

    # --- Remove timezone for Excel compatibility ---
    df.loc[:, 'MESS_DATUM'] = df['MESS_DATUM'].dt.tz_localize(None)

    # Get roughness and height for calculations
    station_name_dwd = stations_df.loc[stations_df['Stations_id'] == int(station_id), 'Stationsname'].iloc[0]
    station_name_matched = match_name(station_name_dwd.replace('_', ' '), roughness_data)
    
    if station_name_matched not in roughness_data:
        logging.error(f"No roughness data found for {station_name_dwd}. Cannot perform calculations.")
        return

    station_roughness = roughness_data[station_name_matched]
    station_height = station_roughness.get('height')

    df = perform_power_energy_calculations(df, station_roughness, station_height)

    os.makedirs(RETRIEVED_DATA_DIR, exist_ok=True)
    output_path = os.path.join(RETRIEVED_DATA_DIR, f"{station_name}_{station_id}_{start_date_str}_to_{end_date_str}.xlsx")
    df.to_excel(output_path, index=False)
    logging.warning(f"Successfully saved filtered data to {output_path}") # Use warning to ensure it shows

async def _get_all_file_urls(driver):
    """
    Scrapes all file URLs from the DWD data directories (historical, recent, now)
    and maps them to station IDs. This is much more efficient than querying for each station.
    """
    logging.warning("Pre-fetching all file URLs from DWD server... This may take a moment.")
    file_urls_by_station = {}

    # Regex patterns for different file types to reliably extract the station ID
    hist_pattern = re.compile(r'_(\d{5})_.*_hist\.zip$')
    akt_pattern = re.compile(r'_(\d{5})_akt\.zip$')
    now_pattern = re.compile(r'_(\d{5})\.zip$')

    urls_to_scrape = {
        "historical": (BASE_URL + "historical/", hist_pattern),
        "recent": (BASE_URL + "recent/", akt_pattern),
        "now": (BASE_URL + "now/", now_pattern)
    }

    for data_type, (url, pattern) in urls_to_scrape.items():
        logging.info(f"Scraping file links from {url}")
        try:
            driver.get(url)
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                href = link.get_attribute('href')
                if not href:
                    continue

                file_name = href.split('/')[-1]
                match = pattern.search(file_name)

                if match:
                    station_id = match.group(1)
                    if station_id not in file_urls_by_station:
                        file_urls_by_station[station_id] = []
                    # Add the full URL, not just file name
                    if href not in file_urls_by_station[station_id]:
                        file_urls_by_station[station_id].append(href)
        except Exception as e:
            logging.error(f"Failed to scrape {url}: {e}")

    logging.warning(f"Finished pre-fetching URLs for {len(file_urls_by_station)} stations.")
    return file_urls_by_station

async def download_and_process_all_stations(stations_df, roughness_data, start_date_str, end_date_str):
    """Downloads and aggregates data for all stations concurrently."""
    logging.warning("Starting concurrent data download for ALL stations. This should be much faster.")
    
    start_date_dt = pd.to_datetime(start_date_str).tz_localize('UTC')
    end_date_dt = pd.to_datetime(end_date_str).tz_localize('UTC')
    
    master_df = pd.DataFrame(index=pd.date_range(start=start_date_dt, end=end_date_dt, freq='10min', tz='UTC'))
    master_df['Power_kW'] = 0.0
    master_df['Energy_kWh'] = 0.0

    driver = None
    try:
        driver = webdriver.Chrome()
        file_urls_by_station = await _get_all_file_urls(driver)

        # --- Concurrency Implementation ---
        semaphore = asyncio.Semaphore(20) # Limit to 20 concurrent stations
        tasks = []

        async def process_station_worker(station_row):
            """Worker to process a single station's data."""
            async with semaphore:
                station_id = f"{station_row['Stations_id']:05d}"
                station_name_dwd = station_row['Stationsname']
                
                station_name_matched = match_name(station_name_dwd.replace('_', ' '), roughness_data)
                
                if station_name_matched not in roughness_data:
                    logging.warning(f"No roughness data for {station_name_dwd} ({station_id}). Skipping.")
                    return None
                    
                station_roughness = roughness_data[station_name_matched]
                station_height = station_roughness.get('height')

                if not station_height:
                    logging.warning(f"No height data for station {station_name_dwd} ({station_id}). Skipping.")
                    return None
                
                zip_files_urls = file_urls_by_station.get(station_id, [])

                if not zip_files_urls:
                    return None

                logging.warning(f"Processing station: {station_name_dwd} ({station_id}) with {len(zip_files_urls)} file(s).")

                all_data = []
                # Use a single client for all downloads for this worker
                async with httpx.AsyncClient(timeout=60.0) as client:
                    download_tasks = [client.get(url) for url in zip_files_urls]
                    responses = await asyncio.gather(*download_tasks, return_exceptions=True)

                for response in responses:
                    if isinstance(response, Exception) or response.status_code != 200:
                        continue
                    
                    zip_file = io.BytesIO(response.content)
                    with zipfile.ZipFile(zip_file, 'r') as wind_zip:
                        for file_name in wind_zip.namelist():
                            if file_name.startswith("produkt"):
                                with wind_zip.open(file_name) as text_file:
                                    text_file.readline() # Skip header
                                    for line in text_file:
                                        row = line.decode('utf-8').strip().split(';')
                                        if len(row) > 4 and row[4] != '     -999':
                                            all_data.append(row)
                
                if not all_data:
                    return None

                columns = ['STATIONS_ID', 'MESS_DATUM', 'QN_3', 'FF_10', 'DD_10', 'eor']
                df = pd.DataFrame(all_data, columns=columns)
                
                def parse_date_with_timezone(date_str):
                    dt = datetime.strptime(date_str, '%Y%m%d%H%M')
                    if dt.year < 2000:
                        return pd.to_datetime(dt).tz_localize('Europe/Berlin', ambiguous='NaT', nonexistent='NaT').tz_convert('UTC')
                    else:
                        return pd.to_datetime(dt).tz_localize('UTC')
                
                df['MESS_DATUM'] = df['MESS_DATUM'].apply(parse_date_with_timezone)
                df.dropna(subset=['MESS_DATUM'], inplace=True)

                df = df[(df['MESS_DATUM'] >= start_date_dt) & (df['MESS_DATUM'] <= end_date_dt)].copy()
                
                if df.empty:
                    return None

                df['FF_10'] = df['FF_10'].astype(float)
                df['DD_10'] = df['DD_10'].astype(float)
                
                station_df_processed = perform_power_energy_calculations(df, station_roughness, station_height)
                
                if station_df_processed.empty or 'Power_kW' not in station_df_processed.columns:
                    logging.warning(f"Skipping station {station_name_dwd} ({station_id}) as it had no valid data after processing.")
                    return None

                return station_df_processed.set_index('MESS_DATUM')

        for _, station_row in stations_df.iterrows():
            tasks.append(process_station_worker(station_row))

        processed_dfs = await asyncio.gather(*tasks)

        # --- Aggregate results ---
        logging.warning("All stations processed. Aggregating results...")
        for station_df in processed_dfs:
            if station_df is not None and not station_df.empty:
                master_df = master_df.add(station_df[['Power_kW', 'Energy_kWh']], fill_value=0)

    finally:
        if driver:
            driver.quit()

    master_df.reset_index(inplace=True)
    master_df = master_df.rename(columns={'index': 'MESS_DATUM'})
    master_df.loc[:, 'MESS_DATUM'] = master_df['MESS_DATUM'].dt.tz_localize(None)

    output_path = os.path.join(RETRIEVED_DATA_DIR, f"combined_{start_date_str}_to_{end_date_str}.xlsx")
    master_df.to_excel(output_path, index=False)
    logging.warning(f"Successfully saved aggregated data to {output_path}")

async def main():
    """Main function to run the DWD explorer."""
    print("DWD Wind Data Explorer")
    print("======================")

    stations_df = await get_stations_df()
    roughness_data = load_roughness_data()

    if stations_df.empty or not roughness_data:
        logging.error("Could not load required station or roughness data. Exiting.")
        return

    print("\nWhat wind data do you want?")
    print("1. All stations (aggregated)")
    print("2. A single station")
    
    main_choice = ""
    while main_choice not in ["1", "2"]:
        main_choice = input("Enter your choice (1-2): ").strip()

    if main_choice == "2": # Single Station
        roughness_station_names = sorted(list(roughness_data.keys()))
        
        print("\nPlease select a station from the list below (stations with available roughness data):")
        for i, name in enumerate(roughness_station_names):
            print(f"{i+1:3d}: {name}")

        selected_station_id_str = None
        while True: # Loop until a valid station is selected and its ID is found
            station_input = input(f"\nEnter the name or number of the station to explore (1-{len(roughness_station_names)}): ").strip()
            
            selected_name = None
            # User entered a number
            if station_input.isdigit():
                try:
                    station_idx = int(station_input) - 1
                    if 0 <= station_idx < len(roughness_station_names):
                        selected_name = roughness_station_names[station_idx]
                    else:
                        print("Invalid number. Please try again.")
                        continue
                except ValueError:
                    print("Invalid input. Please enter a valid name or number.")
                    continue
            # User entered a name
            else:
                match_found = False
                for name in roughness_station_names:
                    if name.lower() == station_input.lower():
                        selected_name = name
                        match_found = True
                        break
                if not match_found:
                    print("Invalid station name. Please choose a name or number from the list.")
                    continue

            # Find the corresponding station ID from the original stations_df
            found_station = False
            for _, row in stations_df.iterrows():
                dwd_name = str(row['Stationsname']).replace('_', ' ')
                matched_name = match_name(dwd_name, roughness_data)
                if matched_name == selected_name:
                    selected_station_id_str = f"{row['Stations_id']:05d}"
                    print(f"Found DWD station: '{row['Stationsname']}' with ID: {selected_station_id_str} for selected name '{selected_name}'")
                    found_station = True
                    break
            
            if found_station:
                break # Exit the loop as we have a valid ID
            else:
                # This case is unlikely but handled for safety
                print(f"Error: Could not find a matching station ID in the DWD master list for '{selected_name}'. Please try another station.")

        # Streamlined workflow: Create driver, get URLs, prompt for dates, and process.
        driver = None
        try:
            driver = webdriver.Chrome()
            all_file_urls = await _get_all_file_urls(driver)
            selected_station_urls = all_file_urls.get(selected_station_id_str, [])

            start_date_str = input("\nEnter start date (YYYY-MM-DD): ").strip()
            end_date_str = input("Enter end date (YYYY-MM-DD): ").strip()

            # Pre-flight check for date availability
            try:
                station_info = stations_df.loc[stations_df['Stations_id'] == int(selected_station_id_str)]
                station_start_str = station_info['von_datum'].iloc[0].astype(str)
                station_end_str = station_info['bis_datum'].iloc[0].astype(str)
                
                station_start_date = pd.to_datetime(station_start_str, format='%Y%m%d')
                station_end_date = pd.to_datetime(station_end_str, format='%Y%m%d')
                user_start_date = pd.to_datetime(start_date_str)
                user_end_date = pd.to_datetime(end_date_str)

                if user_start_date > station_end_date or user_end_date < station_start_date:
                    logging.warning(f"\nWarning: The selected date range ({start_date_str} to {end_date_str}) is outside this station's known data availability ({station_start_date.date()} to {station_end_date.date()}).")
                    logging.error("Aborting as no data will be found.")
                    return # Exit the script gracefully
            except (ValueError, IndexError):
                logging.warning("Could not validate date range against station availability. Proceeding with download attempt.")

            await download_and_process_data(selected_station_id_str, start_date_str, end_date_str, stations_df, roughness_data, selected_station_urls)
        finally:
            if driver:
                driver.quit()

    elif main_choice == "1": # All Stations
        # For 'All Stations', we still want to filter to only process relevant ones.
        roughness_station_names = list(roughness_data.keys())
        def has_roughness_data(station_name):
            cleaned_name = str(station_name).replace('_', ' ')
            matched_name = match_name(cleaned_name, roughness_data)
            return matched_name in roughness_station_names
        
        filtered_stations_df = stations_df[stations_df['Stationsname'].apply(has_roughness_data)].copy()
        logging.warning(f"Found {len(filtered_stations_df)} stations with corresponding roughness data to process.")

        print("\nEnter date range for ALL stations.")
        start_date_str = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date_str = input("Enter end date (YYYY-MM-DD): ").strip()
        await download_and_process_all_stations(filtered_stations_df, roughness_data, start_date_str, end_date_str)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"A top-level error occurred in the application: {e}", exc_info=True) 