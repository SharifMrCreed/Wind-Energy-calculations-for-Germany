"""
     This file retrieves the roughness
     lengths of stations and stores them
     in a file.

     Created by Toluwalade Lawal
"""

import time
import os
# For web automation
from selenium import webdriver
from selenium.webdriver.common.by import By

# A Dictionary of the Station group: The list of stations' links
LINKS_LIST = {"AbisBa": {}, "BbbisBz": {}, "CbisE": {}, "FbisG": {}, "HbisJ": {},
              "KbisL": {}, "MbisN": {}, "ObisR": {}, "SbisV": {}, "WbisZ": {}}

PARENT_DIR = os.getcwd().removesuffix('/code_to_retrieve_data')

output = {}

driver = webdriver.Chrome()
driver.get("https://arla-sentinel.th-deg.de:8443/uploads/DWD_Winddaten_Version6/Frameseiten/Navigationsseite.html")
curr = driver.current_url

time.sleep(0.1)

for group in LINKS_LIST:
    i_d = f"Ebene3_{group}"
    station_group = driver.find_elements(By.XPATH, f"//ul[@id='{i_d}']/li/a")

    # Gets the station names and links for a station group, stores them in links list
    for station in station_group:
        station_link = station.get_attribute('href')
        station_name = station_link.split("/")[-1].removesuffix("_nav.html")
        LINKS_LIST[group][station_name] = station_link

# This 'for' loop goes to each station link in order to retrieve the anemometer height and roughness lengths
for group in LINKS_LIST:
    stations = LINKS_LIST[group].keys()
    for station in stations:
        driver.get(LINKS_LIST[group][station])
        time.sleep(0.1)

        # To get the Anemometer height
        messung_doc = driver.find_element(By.XPATH, "//ul[@id='Zusatzinfos_Ebene2']/li[1]/a").get_attribute('href')
        driver.get(messung_doc)
        time.sleep(0.1)

        height_paragraph = driver.find_element(By.XPATH, '//body/p[2]').text
        locator = height_paragraph.find("Grund:")
        height = int(height_paragraph[locator: locator+9].removeprefix("Grund: "))

        driver.get(LINKS_LIST[group][station])

        # To open the document file of each station
        documentation = driver.find_element(By.XPATH, "//ul[@id='Zusatzinfos_Ebene2']/li[3]/a").get_attribute('href')
        driver.get(documentation)
        time.sleep(0.1)

        rows = driver.find_elements(By.XPATH, "//*[@id='TABELLE2']/tbody/tr")

        roughness_lengths = {"height": height}  # To store all the roughness lengths

        # This gets each grad referenz_rau from the table of the stations' Dokumentation der Umgebungseinflüsse
        for row in rows[1:]:
            grad = row.find_element(By.XPATH, ".//td[1]").accessible_name
            referenz_rau = row.find_element(By.XPATH, ".//td[3]").accessible_name
            roughness_lengths[f'{grad}'] = referenz_rau
        output[station] = roughness_lengths

        print(f"{station} completed")
print("\nDONE") # Shows that all stations are complete

# To improve the output's readability
edited_output = "{"
for (key, value) in output.items():
    edited_output += f"'{key}': {value},\n"
edited_output += "}"

# Saves the roughness lengths into a txt file
with open(f"{PARENT_DIR}/retrieved_data/roughness_length.txt", "w") as file:
    file.write(edited_output)

