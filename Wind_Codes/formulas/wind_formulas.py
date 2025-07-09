import math

# Constant
POWER_CONSTANT = 6500


def find_roughness_length(roughness_dict, wind_direction):
    # If wind direction is invalid, we can't determine roughness.
    if not isinstance(wind_direction, int) or wind_direction < 0:
        return None  # Sentinel value for invalid data like -999

    angle_ranges = {'0': list(range(345, 361)) + list(range(0, 15)),
                    '30': list(range(15, 45)),
                    '60': list(range(45, 75)),
                    '90': list(range(75, 105)),
                    '120': list(range(105, 135)),
                    '150': list(range(135, 165)),
                    '180': list(range(165, 195)),
                    '210': list(range(195, 225)),
                    '240': list(range(225, 255)),
                    '270': list(range(255, 285)),
                    '300': list(range(285, 315)),
                    '330': list(range(315, 345)),
                    }

    found_angle_key = None
    for angle_key, degrees in angle_ranges.items():
        if wind_direction in degrees:
            found_angle_key = angle_key
            break
    
    if found_angle_key:
        return roughness_dict.get(found_angle_key)

    return None # Return None if no angle range matches or key not in dict


def calculate_power(wind_speed):
    # Wind speed cannot be negative. If it is, power is 0.
    # This also prevents the math.exp() from overflowing with large negative inputs.
    if wind_speed < 0:
        return 0.0
    return POWER_CONSTANT / (1 + math.exp((7.2 - wind_speed) / 0.53))


def log_model_formula(ff_10, z_0, h_ref, height):
    if z_0 == 0:
        z_0 = 0.0002
    return ff_10 * (math.log(height / z_0) / math.log(h_ref / z_0))


def modified_power_law_formula(ff_10, z_0, h_ref, height):

    if ff_10 > 0:
        a = ((z_0/h_ref)**0.2) * (1 - (0.55*(math.log(abs(ff_10), 10))))
        return ff_10 * ((height/h_ref)**a)
    else:
        return 0


# This calculates the wind speed at a new height using math models
def calculate_vz(ff_10, z_0, h_ref, height):
    """
    :param ff_10: Speed of wind at the reference height, (Vref)
    :param z_0: Roughness length
    :param h_ref: Reference height, (Anemometer height)
    :param height: Height at which the speed should be calculated
    """
    # This is the condition that determines which model is to be used
    if z_0 <= 0.001:
        wind_speed = log_model_formula(ff_10, z_0, h_ref, height)

    elif 0.001 < z_0 <= 0.09:
        wind_speed = modified_power_law_formula(ff_10, z_0, h_ref, height)

    elif 0.09 < z_0 < 0.2:
        if ff_10 <= 3:
            wind_speed = log_model_formula(ff_10, z_0, h_ref, height)
        else:
            wind_speed = modified_power_law_formula(ff_10, z_0, h_ref, height)

    else:  # z_0 >= 0.2
        if ff_10 <= 10:
            wind_speed = log_model_formula(ff_10, z_0, h_ref, height)
        else:
            wind_speed = modified_power_law_formula(ff_10, z_0, h_ref, height)

    return wind_speed

