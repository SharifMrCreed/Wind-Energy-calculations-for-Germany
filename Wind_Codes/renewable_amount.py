"""
The purpose of this file is to plot the load values,
alsa the solar and wind values.

Created by Toluwalade Lawal
"""

from matplotlib import pyplot as plt
import pandas as pd
from pandas.tseries.offsets import DateOffset
from local_data_and_classes.dates_fetcher import DatesFetcher
import os

pd.options.mode.chained_assignment = None

FILE_FOLDER = f"{os.getcwd()}/retrieved_data"
FILES = os.listdir(FILE_FOLDER)

files = [file for file in FILES if "xlsx" in file]

available_files = {f"{files.index(file)+1}": file for file in files}
number_of_files = int(list(available_files.keys())[-1])
is_greater = False


def find_end_date(day):
    global is_greater
    if is_greater:
        month = day.month
        year = day.year
        end = day.replace(day=DatesFetcher.no_of_days(month, year))
    else:
        end = day + DateOffset(weeks=1)

    return end

def plot_graph():
    global is_greater
    try:
        chosen_file = input(f"The available files are {available_files}, type in a number to select the file.\n"
                            f"Your choice: ")
        if int(chosen_file) > number_of_files:
            return TypeError

        chosen_file = available_files.get(chosen_file)
        chosen_df = pd.read_excel(f"{FILE_FOLDER}/{chosen_file}")

        start_date = chosen_df["MESS_DATUM"][0].replace(day=1)
        end_date = chosen_df["MESS_DATUM"].iloc[-1].replace(day=1)

        year_dif = end_date.year - start_date.year
        month_dif = year_dif * 12 + end_date.month - start_date.month

        if month_dif > 3:
            frequency = "MS"
            freq_text = "Monthly"
            is_greater = True
        else:
            frequency = "W"
            freq_text = "Weekly"

        dates_range = pd.date_range(start_date, end_date, freq=f"{frequency}")
        x_axis = []

        total_power = []

        for day in dates_range:
            end = find_end_date(day)
            d_frame = chosen_df[(chosen_df["MESS_DATUM"] >= day) & (chosen_df["MESS_DATUM"] <= end)]

            d_frame["Power"] = d_frame["Power"].apply(lambda x: x/1000) # To change to MW

            power_sum = sum(d_frame["Power"])
            total_power.append(power_sum)
            x_axis.append(f"{day.year}-{day.month}")

        plt.plot(x_axis,total_power)
        plt.xlabel("Dates")
        plt.ylabel("POWER (MW)")
        plt.title(f"Graph of {freq_text} Power Generation Across Stations")
        plt.xticks(x_axis)
        plt.savefig(f"./graph/{chosen_file.replace('xlsx', 'png')}")

        plt.show()

    except TypeError:
        print("Invalid input, please try again\n")
        plot_graph()


plot_graph()
