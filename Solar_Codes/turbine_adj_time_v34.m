function [PowerTable] = turbine_adj_time_v34(Sim_Time)
    % Simulate power output for an adjustable turbine over a specified time period
    % Input:
    %   Sim_Time - Duration of simulation in years
    %
    % Output:
    %   PowerTable - 1xn table containing power output for each hour

    Windkraftparameter = readtable('Simulationsparameter.xlsx','Sheet','Windkraftparameter');

    peak_power = Windkraftparameter.P_WK_max;   %Load the peak power from file
    hub_height = Windkraftparameter.Hub_height; %Load the hub height from file
    h0 = 10;                                    % Initial wind measurement height (m)
    load('RegensburgCompiled.mat', 'Data');     % Load wind speed data file

    % Preallocate variables
    total_hours = 365 * 24 * Sim_Time;
    %combined_power_output = zeros(1, total_hours);

    % Define the adjustable turbine
    turbine = defineCustomTurbine(peak_power);

    % Extract wind speed data for the simulation period
    datei_10m = Data(1:total_hours, 2);
    datei_100m = Data(1:total_hours, 3);

    % Calculate adjusted wind speeds at hub height
    wind_speed = zeros(total_hours, 1);

    for i = 1:total_hours
        if hub_height == 100
            wind_speed(i) = table2array(datei_100m(i, 1));
        else
            wind_speed(i) = (table2array(datei_10m(i, 1)) - 0.036) * ...
                            (log(hub_height / 0.5) / log(h0 / 0.5));
        end
    end

    % Calculate hourly power output and other statistics
    combined_power_output = calculateHourlyPowerOutput(wind_speed, turbine);

    stunden = 0;
    for i = 1: total_hours
        if combined_power_output(i) > 0
            stunden = stunden + 1;
        end
    end

    total_energy = sum(combined_power_output)   % Total energy output in kWh
    avg_power = total_energy/stunden     % Average power output in kW
    normalised_power = total_energy/peak_power/Sim_Time
    

    % Construct the output table
    PowerTable = combined_power_output;
end

function turbine = defineCustomTurbine(peak_power)
    % Define a custom turbine with adjustable peak power
    % Inputs:
    %   peak_power - Rated power (kW) of the turbine
    % Outputs:
    %   turbine - Structure containing turbine properties

    % Fixed parameters
    cut_in_speed = 3;    % Cut-in wind speed (m/s)
    rated_speed = 10.5;  % Rated wind speed (m/s)
    cut_out_speed = 25;  % Cut-out wind speed (m/s)

    % Base power curve (scaled for 3450 kW turbine)
    a = cut_in_speed:0.5:rated_speed;
    base_b = [34.5;113.3;211.8;329.9;472.6;645;850.7;1095;1377;1699;2058;2450.7;2854;3193;3414;3450];

    % Scale the power curve to match the new peak power
    scale_factor = peak_power / 3450;
    b_scaled = base_b * scale_factor;

    % Generate power curve data
    x = [];
    y = [];
    for i = cut_in_speed:0.5:cut_out_speed
        if i >= a(1) && i <= a(end)
            index = find(a == i);
            x = [x, i];
            y = [y, b_scaled(index)];
        else
            x = [x, i];
            y = [y, peak_power];
        end
    end

    turbine.x = x;
    turbine.y = y;
    turbine.rated_power = peak_power;
    turbine.cut_in_speed = cut_in_speed;
    turbine.rated_speed = rated_speed;
    turbine.cut_out_speed = cut_out_speed;
end

function power_output = calculateHourlyPowerOutput(wind_speed, turbine)
    % Calculate power output for each wind speed data point
    num_data_points = length(wind_speed);
    power_output = zeros(1, num_data_points);
    
    for i = 1:num_data_points
        if wind_speed(i) < turbine.cut_in_speed
            power_output(1, i) = 0; % No power below cut-in speed
        elseif wind_speed(i) >= turbine.cut_in_speed && wind_speed(i) <= turbine.cut_out_speed
            power_output(1, i) = interp1(turbine.x, turbine.y, wind_speed(i));
        else
            power_output(1, i) = 0; % No power above cut-out speed
        end
    end
end
