
import numpy as np
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt

# Load input data
Datei = "produkt_zehn_min_sd_20200101_20231231_03366.txt"
panin = "angels_mühldorf.txt"


# Read the file
dwd_data = pd.read_csv(Datei, sep=";")
zen_data = pd.read_csv(panin, delim_whitespace=True)

# Extract and preprocess data
solar_zenith = zen_data['SolarZen']
azimuth = zen_data['Azim']
air_mass = zen_data['AirMass']
diffuse_sunlight = dwd_data['DS_10']
global_sunlight = dwd_data['GS_10']


GHS = np.maximum(0, (global_sunlight.astype(float) / 600) * 1e4)  # Convert to W/m^2
DHI = np.maximum(0, (diffuse_sunlight.astype(float) / 600) * 1e4)  # Convert to W/m^2
DI = np.maximum(0, GHS - DHI)

theta_z = solar_zenith.astype(float)
theta_z[theta_z > 87] = 0  # Zenith angle invalid values
azim_theta = azimuth.astype(float)

# Constants
rho = 0.2  # Albedo component
theta_t = 35  # Tilt angle of solar panel (degrees)
solar_constant = 1361  # Extraterrestrial solar constant (W/m^2)

# Ensure arrays are the same length
num_time_steps = min(len(GHS), len(DHI), len(theta_z), len(azim_theta))
GHS, DHI, DI, theta_z, azim_theta = [arr[:num_time_steps] for arr in [GHS, DHI, DI, theta_z, azim_theta]]

# Time vector
time = [dt.datetime(2020, 1, 1) + dt.timedelta(minutes=10 * i) for i in range(num_time_steps)]

# Preallocate arrays
DNI = np.zeros(num_time_steps)
DI_tp = np.zeros(num_time_steps)
DI_tr = np.zeros(num_time_steps)
DI_th = np.zeros(num_time_steps)
F1 = np.zeros(num_time_steps)
F2 = np.zeros(num_time_steps)
AOI = np.zeros(num_time_steps)


# Empirical Coefficients
f11 = [-0.008, 0.13, 0.33, 0.568, 0.873, 1.132, 1.06, 0.678]
f12 = [0.588, 0.683, 0.487, 0.187, -0.392, -1.237, -1.6, -0.327]
f13 = [-0.062, -0.151, -0.221, -0.295, -0.362, -0.412, -0.359, -0.25]

f21 = [-0.06, -0.019, 0.055, 0.109, 0.226, 0.288, 0.264, 0.156]
f22 = [0.072, 0.066, -0.064, -0.152, -0.462, -0.823, -1.127, -1.377]
f23 = [-0.022, -0.029, -0.026, -0.014, 0.001, 0.056, 0.131, 0.251]



def bin_epsilon(epsilon):
    """Determines the clearness index bin."""
    if epsilon <= 1.065:
        return 0
    elif epsilon <= 1.23:
        return 1
    elif epsilon <= 1.5:
        return 2
    elif epsilon <= 1.95:
        return 3
    elif epsilon <= 2.8:
        return 4
    elif epsilon <= 4.5:
        return 5
    elif epsilon <= 6.2:
        return 6
    else:
        return 7



# Loop through time steps
for i in range(num_time_steps):
    if np.cos(np.radians(theta_z[i])) > 0:
        DNI[i] = max(0, DI[i] / np.cos(np.radians(theta_z[i])))
    else:
        DNI[i] = 0

    EHI = solar_constant * np.cos(np.radians(theta_z[i]))
    Kt = (DHI[i] + DNI[i]) / max(DHI[i], 1e-10)
    n = (i // 144) % 365 or 365  # Day of year
    ETI = solar_constant * (1 + 0.033 * np.cos(2 * np.pi * n / 365))
    delta = max(0, DHI[i] * float(air_mass.iloc[i]) / ETI)

    epsilon = (Kt + 1.041 * theta_z[i]**3) / (1 + 1.041 * theta_z[i]**3)
    bin_index = bin_epsilon(epsilon)

    F1[i] = max(0, f11[bin_index] + f12[bin_index] * delta + f13[bin_index] * (np.pi * theta_z[i] / 180))
    F2[i] = max(0, f21[bin_index] + f22[bin_index] * delta + f23[bin_index] * (np.pi * theta_z[i] / 180))

    cos_aoi = (np.cos(np.radians(theta_z[i])) * np.cos(np.radians(theta_t)) +
               np.sin(np.radians(theta_z[i])) * np.sin(np.radians(theta_t)) *
               np.cos(np.radians(azim_theta[i] - 180)))
    AOI[i] = np.degrees(np.arccos(np.clip(cos_aoi, -1, 1)))

    a = max(0, np.cos(np.radians(AOI[i])))
    b = max(np.cos(np.radians(85)), np.cos(np.radians(theta_z[i])))
    DI_tp[i] = (DHI[i] * ((1 - F1[i]) * ((1 + np.cos(np.radians(theta_t))) / 2) +
                F1[i] * (a / b) + F2[i] * np.sin(np.radians(theta_t))) +
                GHS[i] * rho * ((1 - np.cos(np.radians(theta_t))) / 2))

    # Reindl Sky Diffuse Irradiance
    A = max(0, DNI[i] / ETI)
    R = max(0, np.cos(np.radians(AOI[i])) / np.cos(np.radians(theta_z[i])))
    factor = max(0, DNI[i] * np.cos(np.radians(theta_z[i])) / max(GHS[i], 1e-10))
    DI_tr[i] = DHI[i] * (A * R + (1 - A) * (1 + np.cos(np.radians(theta_t))) / 2)*1 + np.sqrt(factor) * np.sin(np.radians(theta_t / 2))**3

    # Hay and Davies Sky Diffuse Irradiance
    DI_th[i] = DHI[i] * (A * R + (1 - A) * (1 + np.cos(np.radians(theta_t))) / 2)

# Output results
df = pd.DataFrame({
54    'Date': time,
    'GHS': GHS,
    'DHI': DHI,
    'Theta_Z': theta_z,
    'DNI': DNI,
    'Perez_Irradiance': DI_tp,
    'Reindl_Irradiance': DI_tr,
    'HayDavies_Irradiance': DI_th
})

# Save to Excel
df.to_excel('PerezModelOutput_Müldorf.xlsx', index=False)

# Plot results
plt.figure(figsize=(10, 12))
plt.subplot(4, 1, 1)
plt.plot(time, DI_tp, 'r')
plt.title('Perez Diffuse Irradiance')

plt.subplot(4, 1, 2)
plt.plot(time, DI_tr, 'g')
plt.title('Reindl Sky Diffuse Irradiance')

plt.subplot(4, 1, 3)
plt.plot(time, DI_th, 'b')
plt.title('Hay and Davies Sky Diffuse Irradiance')

plt.subplot(4, 1, 4)
plt.plot(time, DNI, 'k')
plt.title('Direct Normal Irradiance')

plt.tight_layout()
plt.show()
