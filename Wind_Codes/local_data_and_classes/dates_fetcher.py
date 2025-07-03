"""
The purpose of the Class DataFetcher for the user to choose a date range to be used in wind_retrieve.py
Created By: Toluwalade Lawal at WS2024/2025
"""

import datetime
import calendar
from math import floor
from pandas.tseries.offsets import DateOffset


# This classes ar for the 'choose_date' function
class ZeroDifferenceError(Exception):
    pass


class InvalidCriteria(Exception):
    pass


class InvalidDateRange(Exception):
    pass


class DatesFetcher:
    def __init__(self, dates_dict):
        self.date_dict = dates_dict
        self.given_start = None
        self.given_end = None
        self.chosen_start = None
        self.chosen_end = None
        self.limit = 0
        self.criteria = ["Days", "Weeks", "Months", "Years", "Yes"]
        self.date_tuple = None

# This functions helps you select the start and end dates using a range of days, weeks, months, years
# or a manually selected date
    def choose_date(self):
        try:
            self.get_start_and_end()
            if self.date_tuple is not None:
                (y, m, d) = self.date_tuple
            else:
                print(f"\nSelect a date range. The dates available include the range\n"
                      f"Start Date: {self.given_start}\n"
                      f"End Date: {self.given_end}\n")

                self.date_tuple = None
                y = int(input(f"Select a start-year({self.given_start.year}-{self.given_end.year}): "))
                m = int(input(f"Select a start-month({self.month_guide(y, is_start_date=True)}): "))
                d = int(input(f"Select a start-day({self.day_guide(y, m, is_start_date=True)}): "))
                self.date_tuple = (y, m, d)
            self.chosen_start = datetime.datetime(y, m, d, 00, 00)

            date_range_criteria = input(f"\nWhat criteria should be used for the date range?\n"
                                        f"Pick one {self.criteria[0:-1]}\n"
                                        f"or type Yes to manually select an end date\n"
                                        f"Your input: ").title()
            if date_range_criteria in self.criteria:
                amount = 0
                if date_range_criteria != "Yes":
                    self.limit = self.date_difference(date_range_criteria)
                    amount = int(input(f"Number of {date_range_criteria} [limit = {self.limit}]: "))

                if date_range_criteria != "Yes" and self.limit == 0:
                    raise ZeroDifferenceError
                elif date_range_criteria == "Years" and amount <= self.limit:
                    self.chosen_end = self.chosen_start + DateOffset(years=amount) - DateOffset(days=1)
                elif date_range_criteria == "Months" and amount <= self.limit:
                    self.chosen_end = self.chosen_start + DateOffset(months=amount) - DateOffset(days=1)
                elif date_range_criteria == "Weeks" and amount <= self.limit:
                    self.chosen_end = self.chosen_start + DateOffset(weeks=amount)
                elif date_range_criteria == "Days" and amount <= self.limit:
                    self.chosen_end = self.chosen_start + DateOffset(days=amount)
                elif date_range_criteria == "Yes":
                    end_y = int(input(f"\nSelect a end-year({self.chosen_start.year}-{self.given_end.year}): "))
                    end_m = int(input(f"Select a end-month({self.month_guide(end_y)}): "))
                    end_d = int(input(f"Select a end-day({self.day_guide(end_y, end_m)}): "))
                    self.chosen_end = datetime.datetime(end_y, end_m, end_d, 23, 50)
                    if self.chosen_end < self.chosen_start:
                        raise InvalidDateRange
                else:
                    self.chosen_end = datetime.datetime(y, m, d, 23, 50)
            else:
                raise InvalidCriteria

        except ZeroDifferenceError:
            print("The difference between the date you chose and the latest data available is too small.\n"
                  "Please choose either a different date or criteria")
            self.date_tuple = None
            self.choose_date()
        except InvalidCriteria:
            print("Invalid criteria chosen! Please try again")
            self.choose_date()
        except InvalidDateRange:
            print("You chose an End-date that is before the Start date. Please select new dates")
            self.date_tuple = None
            self.choose_date()

    # This is to get the self.limit, which is the number of days, weeks, months or years between two dates
    def date_difference(self, criteria):
        years = self.given_end.year - self.chosen_start.year
        days_difference = (self.given_end - self.chosen_start).days
        month_difference = years * 12 + self.given_end.month - self.chosen_start.month
        year_difference = floor(month_difference / 12)
        match criteria:
            case "Days":
                return days_difference
            case "Weeks":
                return floor(days_difference / 7)
            case "Months":
                return month_difference
            case "Years":
                if year_difference >= 1:
                    return year_difference
                else:
                    return 0

    def get_start_and_end(self):
        # print(self.date_dict)
        for station in self.date_dict:
            start_date = self.date_dict[station]['start']
            end_date = self.date_dict[station]['end']
            if self.given_start is None:
                self.given_start = start_date
            elif self.given_start < start_date:
                self.given_start = start_date

            if self.given_end is None:
                self.given_end = end_date
            elif self.given_end > end_date:
                self.given_end = end_date

    # All the functions below are sub-functions of the self.choose_date()
# The help guide the user in selecting a start_date and end_date
    # e.g.  Select a start-year(1995-2023), Select a start-month(1-12)  Inside the brackets
# This function gets the number of days in a chosen month
    @staticmethod
    def no_of_days(month, year):
        month = str(month)
        monthly_day_counts = {"1": 31, "2": {'normal': 28, 'leap': 29},
                              "3": 31, "4": 30,
                              "5": 31, "6": 30,
                              "7": 31, "8": 31,
                              "9": 30, "10": 31,
                              "11": 30, "12": 31}
        if month == "2":
            if calendar.isleap(year):
                return monthly_day_counts['2'].get('leap')
            else:
                return monthly_day_counts['2'].get('normal')
        else:
            return monthly_day_counts.get(month)

    def month_guide(self, year, is_start_date=False):
        """
        This ensures the month part obeys:
        given_start_date <= chosen_start_date <= given_end_date
        chosen_start_date <= chosen_end_date <= given_end_date


        :param year: This is either the chosen start or end year
        :param is_start_date: This tells if the function is used for the start of end date
        :return: returns a string
        """
        if is_start_date:
            if year == self.given_start.year:
                if self.given_start.month == 12:
                    return "12"
                else:
                    return f"{self.given_start.month}-12"
            else:
                return "1-12"
        else:
            if year == self.chosen_start.year:
                if self.chosen_start.month == 12:
                    return "12"
                else:
                    return f"{self.chosen_start.month}-12"
            else:
                return "1-12"

    def day_guide(self, year, month, is_start_date=False):
        """
        This ensures the Day part obeys:
        given_start_date <= chosen_start_date <= given_end_date
        chosen_start_date <= chosen_end_date <= given_end_date

        :param month
        :param year: This is either the chosen start or end year
        :param is_start_date: This tells if the function is used for the start of end date
        :return: returns a string
        """
        last_day = self.no_of_days(month, year)
        if is_start_date:
            if month == self.given_start.month:
                if self.given_start.day == last_day:
                    return f"{last_day}"
                else:
                    return f"{self.given_start.day}-{last_day}"
            else:
                return f"1-{last_day}"
        else:
            if month == self.chosen_start.month:
                if self.chosen_start.day == last_day:
                    return f"{last_day}"
                else:
                    return f"{self.chosen_start.day}-{last_day}"
            else:
                return f"1-{last_day}"
