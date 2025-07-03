"""
The purpose of this code is to create a class object of the weather stations
A list of the stations is in zehn_min_ff_Beschreibung_Stationen.txt
Information on a station can be printed out using self.info

By Toluwalade lawal
"""

import codecs
import os
import random
from difflib import SequenceMatcher


PARENT_DIR = os.getcwd().removesuffix('/code_to_retrieve_data')


# This function compares two strings and gives a value for their similarities (0<= x <=1)
def compare(a, b):
    return SequenceMatcher(None, a, b).ratio()


# This compares a station name with the names of those that are the dictionary keys
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


class Station:

    # The class attributes are based on the column heading of the zehn_min_ff_Beschreibung_Stationen.txt
    def __init__(self, station_id=None, start_date='', end_date='', height=None, latitude=None,
                 longitude=None, name='', state='', should_print=False, user_pick=False):
        self.id = station_id
        self.start_date = start_date
        self.end_date = end_date
        self.height = height
        self.latitude = latitude
        self.longitude = longitude
        self.name = name
        self.state = state
        self.user_chose_list = False
        self.list_of_stations = []
        self.roughness_lengths = {}
        self.should_print = should_print
        self.user_pick = user_pick
        self.user_chose_a_state = False

    def refresh(self):
        self.__init__()

    def get_all_stations(self):
        all_station_ids = []
        stations_file = PARENT_DIR + '/local_data_and_classes/zehn_min_ff_Beschreibung_Stationen.txt'
        with codecs.open(stations_file, 'r', encoding='utf-8',
                         errors='ignore') as file:
            rows = list(file.readlines())
            for row in rows[2:]:
                row = self.remove_empty_string(row)
                all_station_ids.append(row[0])
        self.get_stations(all_station_ids)

    # This method returns a list of station object
    def get_stations(self, li):
        output = []
        for station in li:
            station = station.strip()
            new_station = Station()
            new_station.search(station)
            new_station.user_chose_list = True
            new_station.fetch_roughness_lengths()

            if len(new_station.roughness_lengths) > 1:
                output.append(new_station)
        if len(li) > 30: # This ensures this is run only when li is a large list
            pick_at_random = input("Would you like to pick a number of stations at random (All are in northern germany)"
                                   "\n"
                                   "[Yes|No]: ").strip().lower()
            if pick_at_random == "yes":
                count = int(input("How many[<= 30]: "))
                output = random.sample([station for station in output if station.latitude > 51], count)
        self.list_of_stations += output

    # This method searches for the station info from zehn_min_ff_Beschreibung_Stationen.txt
    def search(self, user_input=None):
        self.refresh()
        output = []
        if user_input is None:
            user_input = input("Type in either the station's number,"
                               " station's name, state, or 'list' to type in a list of station numbers or 'all' "
                               "to search all stations available\n"
                               "Search: ").strip().lower()

            if user_input == "all":
                self.user_chose_list = True
                self.get_all_stations()
                return
            elif user_input == "list":
                self.user_chose_list = True
                station_list = input("\nPlease type in a list of the station numbers: number, number, number\n"
                                     "Your station list: ")
                self.get_stations(station_list.split(','))
                return

        if self.is_solar:
            stations_file = PARENT_DIR + '/local_data_and_classes/zehn_min_sd_Beschreibung_Stationen.txt'
        else:
            stations_file = PARENT_DIR + '/local_data_and_classes/zehn_min_ff_Beschreibung_Stationen.txt'

        with codecs.open(stations_file, 'r', encoding='utf-8',
                         errors='ignore') as file:
            rows = list(file.readlines())
            # Checks if the user entered the station ID
            if user_input.isnumeric() and len(user_input) == 5:
                for row in rows[2:]:
                    row = self.remove_empty_string(row)
                    if row[0] == user_input:
                        output = row
            # Checks if the user input is the station name or state
            elif user_input.replace("-", '').isalpha():
                for row in rows[2:]:
                    row = self.remove_empty_string(row)
                    if row[7].lower() == user_input:
                        self.state = row[7].title()
                        output.append(row)
                        self.user_chose_a_state = True
                    elif row[6].lower() == user_input:
                        output = row
            else:
                print("Invalid Input")
                self.search()

        if len(output) != 0:
            print("Search successful\n")
            self.match(output)
            return
        else:
            print(f"Search failed for {self.name}")
            print(output)
            self.search()

    # This matches the station's information with the class attributes
    def match(self, li):
        stations_in_state = []
        if self.user_chose_a_state and len(li) >= 1:
            for location in li:
                new_station = Station(location[0], location[1], location[2], location[3], location[4], location[5],
                                      location[6], location[7])

                stations_in_state.append(new_station)
            if self.user_pick:
                self.pick_station(stations_in_state)

        else:
            self.id = li[0]
            self.start_date = li[1]
            self.end_date = li[2]
            self.height = int(li[3])
            self.latitude = float(li[4])
            self.longitude = float(li[5])
            self.name = li[6]
            self.state = li[7]

        if self.should_print:
            if self.user_chose_a_state:
                print(f"Here are the stations in {self.state}\n")
                for each_case in stations_in_state:
                    each_case.info()
            else:
                self.info()

    # This is used to print out a station's or a list of stations information
    def info(self):
        print(f"Station_id: {self.id}\n"
              f"Start_date: {self.start_date[0:4]}-{self.start_date[4:6]}-{self.start_date[6:]}\n"
              f"End_end: {self.end_date[0:4]}-{self.end_date[4:6]}-{self.end_date[6:]}\n"
              f"Height: {self.height}\n"
              f"Latitude: {self.latitude}\n"
              f"Longitude: {self.longitude}\n"
              f"Station_name: {self.name}\n"
              f"State: {self.state}\n\n")

    @staticmethod
    def remove_empty_string(li2):
        li2 = li2.split(' ')
        output_list = []
        for char in li2:
            if len(char) != 0:
                output_list.append(char)
        output_list.pop()

        return output_list

    @staticmethod
    def change_special_letter(letter):
        match letter.lower():
            case "ü":
                return "ue"
            case "ö":
                return "oe"
            case "ä":
                return "ae"

    def fetch_roughness_lengths(self):
        name = ""
        for char in self.name:
            if char.lower() in ["ü", "ö", "ä"]:
                name += self.change_special_letter(char)
            else:
                name += char
        with open(f"{PARENT_DIR}/retrieved_data/roughness_length.txt", "r") as file:
            stations = eval(file.read())
            name = match_name(name, stations)
            if name in stations.keys() and len(stations.get(name)) > 1:
                self.roughness_lengths = {angle: (float(roughness_length.replace(",", ".")) if angle != 'height' else
                                                  roughness_length) for (angle, roughness_length) in
                                          stations[name].items()}
            else:
                print(f"Unfortunately the roughness length of {self.name} could not be found\n")
                if not self.user_chose_list:
                    print(self.user_chose_list)
                    print(f"Please try a different station\n\n")
                    self.refresh()
                    self.search()

    # This method tells the user to pick a station out of the several in a chosen state
    def pick_station(self, stations):
        stations_list = [sta_tion.name for sta_tion in stations]
        chosen_station = input(f"You selected a State that contains the following stations:\n"
                               f"{stations_list}\n\n"              
                               f"Select a station: ").title().strip()
        if chosen_station not in stations_list:
            print("Invalid station selected. Please try again\n")
            self.pick_station(stations)
        for stat in stations:
            if stat.name == chosen_station:
                self.id = stat.id
                self.start_date = stat.start_date
                self.end_date = stat.end_date
                self.height = int(stat.height)
                self.latitude = float(stat.latitude)
                self.longitude = float(stat.longitude)
                self.name = stat.name
                self.state = stat.state
