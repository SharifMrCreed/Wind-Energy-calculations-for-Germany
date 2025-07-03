% Clear workspace
clear all;

% Reading input files
file = fopen("produkt_zehn_min_sd_20200101_20231231_01975.txt");
Datei = readmatrix("produkt_zehn_min_sd_20200101_20231231_01975.txt", 'OutputType', 'char');
panin = readmatrix("angels_hamburg.txt", 'OutputType', 'char');

% Initializations
rho = 0.2; % Albedo component
theta_t = 35; % Tilt angle of solar panel (degrees)
GHS = str2double(Datei(:, 5)); % Global Horizontal Sunlight (J/cm^2)
GHS = max(0, (GHS / 600) * 1e4); % Convert to W/m^2 and ensure non-negative
DHI = str2double(Datei(:, 4)); % Diffuse Horizontal Irradiance
DHI = max(0, (DHI / 600) * 1e4); % Convert to W/m^2 and ensure non-negative
DI = max(0, GHS - DHI); % Direct Irradiance, ensure non-negative

theta_z = str2double(panin(:, 6)); % Solar Zenith Angle
theta_z(theta_z > 87) = 0; % Set invalid zenith angles to 0
azim_theta = str2double(panin(:, 7)); % Solar Azimuth Angle

% Ensure arrays are of the same length
num_time_steps = min([length(GHS), length(DHI), length(theta_z), length(azim_theta)]);
GHS = GHS(1:num_time_steps);
DHI = DHI(1:num_time_steps);
DI = DI(1:num_time_steps);
theta_z = theta_z(1:num_time_steps);
azim_theta = azim_theta(1:num_time_steps);

% Time vector
start_date = datetime(2020, 1, 1, 0, 0, 0);
time = start_date + minutes(0:10:(num_time_steps - 1) * 10);

% Preallocate arrays
DNI = zeros(1, num_time_steps);
DI_tp = zeros(1, num_time_steps);
DI_tr = zeros(1, num_time_steps);
DI_th = zeros(1, num_time_steps);
F1 = zeros(1, num_time_steps);
F2 = zeros(1, num_time_steps);
AOI = zeros(1, num_time_steps);

% Empirical coefficients
f11 = [-0.008, 0.13, 0.33, 0.568, 0.873, 1.132, 1.06, 0.678];
f12 = [0.588, 0.683, 0.487, 0.187, -0.392, -1.237, -1.6, -0.327];
f13 = [-0.062, -0.151, -0.221, -0.295, -0.362, -0.412, -0.359, -0.25];

f21 = [-0.06, -0.019, 0.055, 0.109, 0.226, 0.288, 0.264, 0.156];
f22 = [0.072, 0.066, -0.064, -0.152, -0.462, -0.823, -1.127, -1.377];
f23 = [-0.022, -0.029, -0.026, -0.014, 0.001, 0.056, 0.131, 0.251];

% Loop through time steps
for index = 1:num_time_steps
    % Direct Normal Irradiance (DNI)
    if cosd(theta_z(index)) > 0
        DNI(index) = max(0, DI(index) / cosd(theta_z(index)));
    else
        DNI(index) = 0;
    end

    % Extraterrestrial Horizontal Irradiance
    EHI = 1361 * cosd(theta_z(index)); % Solar constant * cos(theta)
    Kt = (DHI(index) + DNI(index)) / max(DHI(index), 1e-10); % Prevent division by zero

    % Day of year
    n = mod(index / 144, 365);
    n(n == 0) = 365; % Wrap day of year

    % Extraterrestrial Radiation
    ETI = 1361 * (1 + 0.033 * cosd((2 * pi * n) / 365)); 
    delta = max(0, DHI(index) * str2double(panin(index, 5)) / ETI);

    % Determine clearness index bin
    epsilon = (Kt + 1.041 * theta_z(index)^3) / (1 + 1.041 * theta_z(index)^3);
    if epsilon <= 1.065, bin = 1;
    elseif epsilon <= 1.23, bin = 2;
    elseif epsilon <= 1.5, bin = 3;
    elseif epsilon <= 1.95, bin = 4;
    elseif epsilon <= 2.8, bin = 5;
    elseif epsilon <= 4.5, bin = 6;
    elseif epsilon <= 6.2, bin = 7;
    else, bin = 8;
    end

    % Calculate F1 and F2
    F1(index) = max(0, f11(bin) + f12(bin) * delta + f13(bin) * (pi * theta_z(index) / 180));
    F2(index) = max(0, f21(bin) + f22(bin) * delta + f23(bin) * (pi * theta_z(index) / 180));

    % Angle of Incidence (AOI)
    cos_aoi = cosd(theta_z(index)) * cosd(theta_t) + ...
              sind(theta_z(index)) * sind(theta_t) * cosd(azim_theta(index) - 180);
    AOI(index) = acosd(max(-1, min(1, cos_aoi))); % Clamp values to [-1, 1]

    % Perez Diffuse Irradiance on tilted panel
    a = max(0, cosd(AOI(index))); % Non-negative cosine
    b = max(cosd(85), cosd(theta_z(index))); % Prevent division by small values
    DI_tp(index) = DHI(index) * ((1 - F1(index)) * ((1 + cosd(theta_t)) / 2) + ...
                   (F1(index) * (a / b)) + (F2(index) * sind(theta_t))) + ...
                   GHS(index) * rho * ((1 - cosd(theta_t)) / 2);

    % Reindl Sky Diffuse Irradiance
    A = max(0, DNI(index) / ETI);
    R = max(0, cosd(AOI(index)) / cosd(azim_theta(index)));
    factor = max(0, DNI(index) * cosd(theta_z(index)) / max(GHS(index), 1e-10));
    DI_tr(index) = DHI(index) * (A * R + (1 - A) * ((1 + cosd(theta_t)) / 2) * ...
                  (1 + sqrt(factor) * sind(theta_t / 2)^3));

    % Hay and Davies Sky Diffuse Irradiance
    DI_th(index) = DHI(index) * (A * R + (1 - A) * (1 + cosd(theta_t)) / 2);
end

% Output data
varNames = {'Date', 'Global Horizontal Sunlight [GHS]', ...
            'Diffuse Horizontal Incidence [DHI]', ...
            'Zenith Angle (Degrees)', 'Direct Normal Irradiance [DNI]', ...
            'Perez Diffuse Ray on Panel', 'Reindl Sky Diffuse Irradiance', ...
            'Hay and Davies Sky Diffuse Irradiance'};
Data_test = table(time.', GHS, DHI, theta_z, DNI.', DI_tp.', DI_tr.', DI_th.', 'VariableNames', varNames);

writetable(Data_test, 'PerezModelOutput_Hamburg.xlsx');

% Plot results
figure;
subplot(4, 1, 1);
plot(time, DI_tp, 'r');
title('Perez Diffuse Irradiance');

subplot(4, 1, 2);
plot(time, DI_th, 'b');
title('Hay Diffuse Irradiance');

subplot(4, 1, 3);
plot(time, DI_tr, 'g');
title('Reindl Diffuse Irradiance');

subplot(4, 1, 4);
plot(time, DHI, 'k');
hold on
plot(time, DI_tp,'r');
title('Diffuse Horizontal Irradiance vs. Perez Model');
hold off

for i = 1:length(DHI)
    diff(i) = DHI(i)-DI_tp(i);
end

sum(diff)
corr_Perez_Reindl = corr(DI_tp.', DHI, 'Type', 'Pearson')