# DWD Wind Data Analysis Project

This project provides a suite of interactive command-line tools to download, process, analyze, and visualize wind data from the German Weather Service (DWD) Climate Data Center.

## Features

- **Unified Interface**: A single script (`analyze_station_data.py`) handles both data downloading and analysis for a streamlined user experience.
- **Efficient Downloader**: Concurrently downloads data for single or multiple stations using `asyncio` for high performance.
- **Robust Data Processing**:
  - Automatically handles DWD's historical timezone changes (MEZ/MESZ to UTC).
  - Cleans and filters invalid or missing data points.
  - Calculates theoretical wind power and energy at a standard turbine hub height.
- **Interactive Analysis**:
  - A user-friendly, menu-driven interface powered by the `rich` library.
  - Generates and displays a variety of plots using `matplotlib` and `seaborn`.
  - Allows for the analysis of previously downloaded datasets.

## Getting Started

Follow these steps to set up and run the project on your local machine.

### Prerequisites

- Python 3.8 or newer.
- [Google Chrome](https://www.google.com/chrome/) installed. The scripts use Selenium to automatically manage the `chromedriver`.
- A terminal or command prompt.

### Installation

1. **Clone the Repository**

    ```sh
    git clone <your-repository-url>
    cd <your-repository-directory>
    ```

2. **Navigate to the `Wind_Codes` Directory**
    The main scripts and their requirements are located here.

    ```sh
    cd Wind_Codes
    ```

3. **Create and Activate a Virtual Environment** (Recommended)
    Using a virtual environment prevents conflicts with other Python projects.

    *On Windows:*

    ```sh
    python -m venv venv
    .\venv\Scripts\activate
    ```

    *On macOS/Linux:*

    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

4. **Install Required Packages**
    Install all the necessary libraries from the `requirements.txt` file.

    ```sh
    pip install -r requirements.txt
    ```

### Running the Scripts

**Important**: To ensure that Python can correctly find all the necessary modules, you must run the scripts as modules from the **project's root directory** (`EdwinAsha-ProjectWork`), not from within the `Wind_Codes` folder.

#### 1. The Main Tool: `analyze_station_data.py` (Recommended)

This is the primary, all-in-one script for both downloading and analyzing data.

**To Run:**

```sh
python -m Wind_Codes.analyze_station_data
```

**Workflow:**

1. The main menu will appear.
2. Choose **"1: Download New Data"** to fetch data from the DWD.
    - You will be asked to download for **"All Stations"** or **"A Single Station"**.
    - Follow the prompts to select a station (if applicable) and a date range.
    - The script will download, process, and save the data to an `.xlsx` file in `Wind_Codes/retrieved_data/`.
3. After a successful download, you will be prompted to analyze the new dataset immediately.
4. Choose **"2: Analyze Existing Data"** from the main menu to explore any `.xlsx` or `.json` file already present in the `retrieved_data` directory.
5. The analytics menu provides options to view data summaries and generate various plots.

#### 2. Data Fetching Only: `dwd_exploration.py`

This script is the legacy tool focused exclusively on downloading data.

**To Run:**

```sh
python -m Wind_Codes.code_to_retrieve_data.dwd_exploration
```

This script will guide you through a similar download process as the main tool but will not offer to analyze the data afterward.

#### 3. Analytics Only: `wind_station_data_analytics.py`

Use this script to analyze data files that you have already downloaded.

**To Run:**

```sh
python -m Wind_Codes.wind_station_data_analytics
```

This script will present a list of all compatible data files in the `retrieved_data` folder and allow you to choose one to explore and visualize.

## Project Structure

- `Wind_Codes/`
  - `analyze_station_data.py`: The main, unified script.
  - `dwd_exploration.py`: Legacy data downloading script.
  - `wind_station_data_analytics.py`: Legacy data analysis script.
  - `retrieved_data/`: Default location for all downloaded `.xlsx` and `.json` files.
  - `graph/`: Default location for all saved plots and charts.
  - `formulas/`: Contains the wind power and energy calculation logic.
  - `requirements.txt`: A list of all Python package dependencies.
  - `README.md`: This file.
  - `DATA_PROCESSING_WORKFLOW.md`: A detailed technical explanation of the data pipeline.
