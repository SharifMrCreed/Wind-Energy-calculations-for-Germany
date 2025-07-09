"""
Created By @Coding Team: Adi Nurlybayev, Sarah Berment, Rilwan Adebayo
Updated By: Toluwalade Lawal  at WS2024/2025

# Code obtains wind data for individual stations and imports it into an Excel file
# The Excel file is stored in 'retrieved_data'
"""
import httpx
import asyncio
import pandas as pd
import zipfile
import io
import os
from local_data_and_classes.dates_fetcher import DatesFetcher
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from formulas.wind_formulas import *
from local_data_and_classes.weatherstation import Station

pd.options.mode.chained_assignment = None

base_url = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/10_minutes/wind/"
historical_wind_data_url = base_url + "historical/"
recent_wind_data_url = base_url + "recent/"


# This function allows several http requests at the same time
async def fetch(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response


# This is to speed up the data processing of the code
# This code is aimed to optimise memory use
def code_optimiser(stations, all_data):
    for station in stations:
        columns = all_data[f'{station.id}']['columns']
        data = all_data[f'{station.id}']['data']
        h_ref = station.roughness_lengths['height']
        yield station, columns, data, h_ref


# This creates Excel sheets for the stations in the list
def create_excel_file(stations, all_data, dates):
    should_be_combined = input("Should the data be combined?\n"
                               "[Yes|No]: ").strip().lower()
    text_to_print = "{" + f"'Stations': {[station.name for station in stations]},\n"

    date_fetcher = DatesFetcher(dates_dict=dates)
    date_fetcher.choose_date()
    start_date, end_date = (date_fetcher.chosen_start, date_fetcher.chosen_end)
    s_date = None
    e_date = None
    combined_time = pd.date_range(start_date, end_date, freq='10min')
    date_p_e_dict = {date: {'Power': 0, 'Energy': 0} for date in combined_time}

    height = 200

    parent_dir = os.getcwd().removesuffix('/code_to_retrieve_data')
    count = len(stations)
    output = code_optimiser(stations, all_data)

    for _ in range(count):
        station, columns, data, h_ref = next(output)

        if columns and data:

            df = pd.DataFrame(data, columns=columns)

            # To retrieve the date range from the dataframe
            df['MESS_DATUM'] = pd.to_datetime(df['MESS_DATUM'], format='%Y%m%d%H%M')

            # To allow the user choose a date to be retrieved
            s_date = start_date.date()
            e_date = end_date.date()

            # Filter data based on the start_date and end_date range
            filtered_df = df[(df['MESS_DATUM'] >= start_date) & (df['MESS_DATUM'] <= end_date)]

            # Set FF_10 values less than 0 to be 0
            filtered_df['FF_10'] = filtered_df['FF_10'].astype(float)
            filtered_df.loc[filtered_df['FF_10'] < 0, 'FF_10'] = 0

            filtered_df['z0'] = filtered_df['DD_10'].apply(lambda x: find_roughness_length(station.roughness_lengths, int(x)))

            filtered_df[f'V({height})'] = filtered_df.apply(lambda x: calculate_vz(x['FF_10'], x['z0'], h_ref, height),
                                                            axis=1)

            filtered_df['Power'] = filtered_df[f'V({height})'].apply(lambda x: calculate_power(x) / 1000)  # Convert W to kW

            power_sum = sum(filtered_df['Power'])

            filtered_df['Energy'] = filtered_df['Power'] * (10 / 60)  # Assuming 10-minute data, convert to kWh
            energy_sum = sum(filtered_df['Energy'])

            text_to_print += f"'{station.name}': " + "{" + f"'Power': {power_sum}, 'Energy': {energy_sum}" + "}\n"

            for index, row in filtered_df.iterrows():
                if row['MESS_DATUM'] in date_p_e_dict.keys():
                    date_p_e_dict[row['MESS_DATUM']]['Power'] += row['Power']
                    date_p_e_dict[row['MESS_DATUM']]['Energy'] += row['Energy']

            if should_be_combined == "no":
                filtered_df.to_excel(f'{parent_dir}/retrieved_data/{station.name.lower()}windnw_{s_date}_to_{e_date}.xlsx',
                                index=False)

        else:
            print('No data found in the retrieved zip file for ')

    if should_be_combined == "yes":
        combined_pd = {"MESS_DATUM": date_p_e_dict.keys(),
                       "Power": [date_p_e_dict[date].get('Power') for date in date_p_e_dict],
                       "Energy": [date_p_e_dict[date].get('Energy') for date in date_p_e_dict]}
        combined_columns = list(combined_pd.keys())
        combined_data = pd.DataFrame(combined_pd, columns=combined_columns)
        combined_data.to_excel(f'{parent_dir}/retrieved_data/combinedwindnw_{s_date}_to_{e_date}.xlsx',
                               index=False)
        text_to_print += "}"
        with open(f'{parent_dir}/retrieved_data/combinedwindnw_{s_date}_to_{e_date}.txt', 'w') as file:
            file.write(text_to_print)


async def retrieve_data():
    total_data = {}
    stations_list_dates = {}
    stations = Station(user_pick=True)
    stations.search()
    final_stations_used = []

    if stations.user_chose_list:
        stations = stations.list_of_stations
    else:
        stations.fetch_roughness_lengths()
        stations = [stations]

    driver = webdriver.Chrome()
    zip_files = {station.id: [] for station in stations}

    # Get historical data
    driver.get(historical_wind_data_url)
    for station in stations:
        text_to_look_for = f"wind_{station.id}"
        historical_files = driver.find_elements(By.XPATH, f"//a[contains(@href, '{text_to_look_for}')]")
        for document in historical_files:
            zip_files[station.id].append(document.get_attribute('href'))

    # Get recent data
    driver.get(recent_wind_data_url)
    for station in stations:
        text_to_look_for = f"10minutenwerte_wind_{station.id}_akt.zip"
        try:
            recent_file = driver.find_element(By.XPATH, f"//a[contains(@href, '{text_to_look_for}')]")
            zip_files[station.id].append(recent_file.get_attribute('href'))
        except NoSuchElementException:
            pass  # Not all stations have recent data

    driver.quit()

    for station in stations:
        try:
            total_rows_removed = 0
            data = []
            columns = None

            cur_zip_files = zip_files.get(station.id)

            if not cur_zip_files:
                raise NoSuchElementException

            task = [fetch(url) for url in cur_zip_files]
            responses = await asyncio.gather(*task)

            for wind_data_http_response in responses:
                rows_removed = 0
                zip_file = io.BytesIO(wind_data_http_response.content)
                with zipfile.ZipFile(zip_file, 'r') as wind_zip:
                    for file_name in wind_zip.namelist():
                        if file_name.startswith("produkt"):
                            with wind_zip.open(file_name) as text_file:
                                if columns is None:
                                    columns = text_file.readline().decode('utf-8').strip().split(';')
                                else:
                                    text_file.readline()  # Skip header of subsequent files
                                for line in text_file:
                                    row = line.decode('utf-8').strip().split(';')
                                    if len(row) > 4 and row[4] != '     -999':
                                        data.append(row)
                                    else:
                                        rows_removed += 1
                                        total_rows_removed += 1
                            print(f"Number of rows removed in file: {rows_removed}")
            
            if not data:
                print(f"No data found for station {station.name} after processing files.\n")
                continue

            print(f"Total number of rows removed for {station.name}: {total_rows_removed}\n")

            # Sort data by date
            data.sort(key=lambda x: x[1])

            start = pd.to_datetime(data[0][1], format='%Y%m%d%H%M')
            end = pd.to_datetime(data[-1][1], format='%Y%m%d%H%M')

            total_data[f'{station.id}'] = {'columns': columns, 'data': data}
            key = f'{station.name}_{station.id}'
            stations_list_dates[key] = {"start": start, "end": end}
            final_stations_used.append(station)

        except NoSuchElementException:
            print(f"The data of station {station.name} is unavailable.\n")

    if final_stations_used:
        create_excel_file(final_stations_used, total_data, stations_list_dates)
    else:
        print("\nNo stations found or no data available for the selected stations.")


asyncio.run(retrieve_data())
