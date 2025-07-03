%A value close to 1 indicates a strong positive correlation.
% A value close to 0 indicates no linear correlation.
% A value close to -1 indicates a strong negative correlation.


% Replace NaN values with zero (or use interpolation for better accuracy)
DI_tp(isnan(DI_tp)) = 0;
DI_tr(isnan(DI_tr)) = 0;
DI_th(isnan(DI_th)) = 0;

% Compute correlation coefficients
corr_Perez_Reindl = corr(DI_tp.', DI_tr.', 'Type', 'Pearson');
corr_Perez_Hay = corr(DI_tp.', DI_th.', 'Type', 'Pearson');
corr_Reindl_Hay = corr(DI_tr.', DI_th.', 'Type', 'Pearson');

% Display correlation results
fprintf('Correlation between Perez and Reindl models: %.4f\n', corr_Perez_Reindl);
fprintf('Correlation between Perez and Hay models: %.4f\n', corr_Perez_Hay);
fprintf('Correlation between Reindl and Hay models: %.4f\n', corr_Reindl_Hay);

% Visual comparison of models
figure;
hold on;
plot(time, DI_tp, 'r', 'DisplayName', 'Perez Model');
plot(time, DI_tr, 'g', 'DisplayName', 'Reindl Model');
plot(time, DI_th, 'b', 'DisplayName', 'Hay Model');
hold off;
xlabel('Time');
ylabel('Irradiance [W/m^2]');
title('Comparison of Diffuse Irradiance Models');
legend('Location', 'best');
grid on;

% Annotate correlation coefficients on the plot
text(time(end-200), max(DI_tp), sprintf('Perez vs Reindl: %.2f', corr_Perez_Reindl), 'Color', 'r');
text(time(end-200), max(DI_tp)-50, sprintf('Perez vs Hay: %.2f', corr_Perez_Hay), 'Color', 'b');
text(time(end-200), max(DI_tp)-100, sprintf('Reindl vs Hay: %.2f', corr_Reindl_Hay), 'Color', 'g');
