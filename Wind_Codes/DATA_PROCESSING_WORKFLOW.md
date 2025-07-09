# Data Processing Workflow

This document outlines the step-by-step process the `analyze_station_data.py` script uses to download, clean, calculate, and prepare wind data from the German Weather Service (DWD) for analysis.

### 1. Initialization and Configuration

- **Path Setup**: The script begins by setting up platform-agnostic paths using `pathlib` to locate the project root, the script's own directory, and the essential `retrieved_data` and `graph` folders.
- **Environment**: It configures logging to display important warnings, sets a default style for `matplotlib` plots, and initializes the `rich` library for formatted console output.

### 2. Data Acquisition

The data acquisition process is designed to be efficient and robust.

- **Station Metadata**: The script first fetches a master list of all DWD weather stations from a metadata URL. This list is parsed into a pandas DataFrame containing station IDs, names, geographic coordinates, and operational date ranges.
- **Efficient URL Pre-fetching**: To avoid thousands of slow web requests, the script launches a Selenium-controlled headless browser once. It navigates to the three primary DWD data directories (`/historical/`, `/recent/`, and `/now/`) and scrapes the complete URLs of all available data zip files. These URLs are stored in a Python dictionary, mapped to their corresponding station IDs. This reduces thousands of potential web page loads to just three.
- **User Selection**:
  - **All Stations**: The user can choose to download data for all stations that have corresponding roughness length profiles.
  - **Single Station**: The user is presented with an interactive menu to select a specific station by name or number. The script then finds the corresponding station ID.
- **Concurrent Downloading**: The script uses `asyncio` and `httpx` to download the data files concurrently, with a semaphore limiting the number of simultaneous connections to avoid overwhelming the server.
- **File Processing**: As each `.zip` file is downloaded into memory, it is opened, and the relevant `produkt_...` file containing the raw data is extracted and read.

### 3. Data Cleaning and Transformation

Raw data from the DWD requires significant cleaning and normalization.

- **Filtering Invalid Data**: Rows containing the `-999` placeholder for missing data are immediately discarded.
- **Timezone Normalization**: This is a critical step. The script correctly handles the DWD's historical use of different timezones:
  - Data from **before the year 2000** is parsed as `Europe/Berlin` time (MEZ/MESZ) and then converted to UTC.
  - Data from **2000 onwards** is parsed directly as UTC.
  - Ambiguous timestamps that can occur during Daylight Saving Time transitions are dropped to prevent errors.
- **Date Range Filtering**: The DataFrame is filtered to include only the dates specified by the user.
- **Type Conversion**: Data columns like wind speed (`FF_10`) and direction (`DD_10`) are converted to numeric types (`float`, `int`) for calculations.

### 4. Power and Energy Calculation

Once the data is clean, the script performs the core energy calculations.

- **Roughness Length Matching**: For each station, the script looks up its corresponding roughness length profile from the `roughness_length.json` file. It uses a fuzzy matching algorithm (`SequenceMatcher`) to correlate the station name from the DWD metadata with the names in the JSON file.
- **Applying Wind Formulas**:
    1. For each 10-minute interval, the correct roughness value (`z0`) is determined based on the recorded wind direction (`DD_10`).
    2. The wind speed is extrapolated from the measurement height (typically 10m) to a standard turbine hub height (200m) using the logarithmic law formula in `calculate_vz`.
    3. The theoretical power output in kilowatts (kW) is calculated from the hub-height wind speed using the `calculate_power` function, which is based on the standard wind power equation.
    4. The energy in kilowatt-hours (kWh) for the 10-minute interval is calculated by multiplying the power by the time duration (10/60 hours).
- **Aggregation (All Stations Mode)**: If running in "All Stations" mode, the script groups the data from all processed stations by their timestamp and sums the `Power_kW` and `Energy_kWh` values to create a single, aggregated national time series.

### 5. Data Storage and Analysis

- **Saving to Excel**: The final, processed DataFrame (either for a single station or the aggregated total) is saved as an `.xlsx` file in the `retrieved_data` directory. Timestamps are made timezone-unaware just before saving to ensure compatibility with Excel.
- **Handover to Analytics**: If the user agrees, the newly created DataFrame is passed directly to the analysis module, providing a seamless transition from data acquisition to visualization. The analysis module offers interactive menus for generating plots, heatmaps, and data summaries.
