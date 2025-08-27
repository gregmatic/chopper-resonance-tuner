#!/usr/bin/env python3
# TMC drivers registers calibration tool (plotter)
#
# Copyright (C) 2024  Alexander Fedorov <altzbox@gmail.com>
# Copyright (C) 2024  Maksim Bolgov <maksim8024@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

#################################################################################################################
RESULTS_FOLDER = '~/printer_data/config/adxl_results/chopper_magnitude'
DATA_FOLDER = '/tmp/'
#################################################################################################################

import os, sys, csv
import numpy as np
from tqdm import tqdm
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime

RESULTS_FOLDER = os.path.expanduser(RESULTS_FOLDER)
FCLK = 12 # MHz
CUTOFF_RANGE = 5

def cleaner():
    #os.system('rm -f /tmp/*.csv')
    sys.exit(0)

def check_export_path(path):
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError as e:
            print(f'Error generate path {path}: {e}')

def parse_arguments():
    args = sys.argv[1:]
    parsed_args = {}
    for arg in args:
        name, value = arg.split('=')
        parsed_args[name] = int(value) if value.isdigit() else value
    return parsed_args

def calc_static_magnitude(file):
    data = np.array([
        [float(row["accel_x"]),
         float(row["accel_y"]),
         float(row["accel_z"])] for row in csv.DictReader(file)])
    return np.mean(data, axis=0)

def calc_md_magnitude(file, static_data=None): #new
    data = np.array([
        [float(row["accel_x"]),
         float(row["accel_y"]),
         float(row["accel_z"])] for row in csv.DictReader(file)])
    if static_data is not None:
        data = data - static_data    
    trim_size = len(data) // CUTOFF_RANGE
    data = data[trim_size:-trim_size]
    md_magnitude = np.median(np.linalg.norm(data, axis=1))
    return md_magnitude

def calc_avg_magnitude(file, static_data=None): #new
    data = np.array([
        [float(row["accel_x"]),
         float(row["accel_y"]),
         float(row["accel_z"])] for row in csv.DictReader(file)])
    if static_data is not None:
        data = data - static_data
    trim_size = len(data) // CUTOFF_RANGE
    data = data[trim_size:-trim_size]
    avg_magnitude = np.mean(np.linalg.norm(data, axis=1))
    return avg_magnitude

def main():
    print('Magnitude graphs generation...')
    args = parse_arguments()
    driver = args.get('driver')
    iterations = args.get('iterations')
    sense_resistor = round(float(args.get('sense_resistor')), 3)
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    # Calc static magnitude
    static_name = next((name for name in os.listdir(DATA_FOLDER) if name.endswith('stand_still.csv')), None)
    with open(f'{DATA_FOLDER}{static_name}', 'r') as file:
        static_data = calc_static_magnitude(file)
        accel_chip = static_name.split('-')[0]
    # Calc magnitudes (median and average, static and raw)
    samples_median_adjusted = {}
    samples_median_raw = {}
    samples_avg_adjusted = {}
    samples_avg_raw = {}
    datapoint_median_adjusted = []
    datapoint_median_raw = []
    datapoint_avg_adjusted = []
    datapoint_avg_raw = []
    empty_error = 0
    data_files = sorted(os.listdir(DATA_FOLDER), key=lambda x: os.
                        path.getmtime(os.path.join(DATA_FOLDER, x)), reverse=True)
    for name in data_files:
        print(f"Processing file: {name}")
        if name.endswith('__.csv'):
            with open(f'{DATA_FOLDER}{name}', 'r') as file:
                try:
                    curr, tbl, toff, hstrt, hend, tpfd, speed, freq, iter = name.split('__')[1].split('_')
                    iter = iter.rstrip('.csv')
                    print(f"Parsed parameters: curr={curr}, tbl={tbl}, toff={toff}, hstrt={hstrt}, hend={hend}, tpfd={tpfd}, speed={speed}, freq={freq}, iter={iter}")
                    out_name = (f'current={curr}_tbl={tbl}_toff={toff}_hstrt={hstrt}_hend={hend}'
                                f'_tpfd={tpfd}_speed={float(speed)/100:.2f}_freq={float(freq)/1000:.2f}kHz')
                except ValueError as e:
                    print(f"Error parsing file name {name}: {e}")
                    empty_error += 1
                    continue
    
                md_magnitude_adjusted = md_magnitude_raw = avg_magnitude_adjusted = avg_magnitude_raw = 0
                try:
                    md_magnitude_adjusted = calc_md_magnitude(file, static_data)
                    datapoint_median_adjusted.append(md_magnitude_adjusted)
                except Exception as e:
                    print(f"Error in calc_magnitude for {name}: {e}")
                    datapoint_median_adjusted.clear()
                    samples_median_adjusted[out_name] = 0
                    empty_error += 1
    
                try:
                    file.seek(0)
                    md_magnitude_raw = calc_md_magnitude(file)
                    datapoint_median_raw.append(md_magnitude_raw)
                except Exception as e:
                    print(f"Error in calc_md_magnitude for {name}: {e}")
                    datapoint_median_raw.clear()
                    samples_median_raw[out_name] = 0
                    empty_error += 1
    
                try:
                    file.seek(0)
                    avg_magnitude_adjusted = calc_avg_magnitude(file, static_data)
                    datapoint_avg_adjusted.append(avg_magnitude_adjusted)
                except Exception as e:
                    print(f"Error in calc_avg_magnitude (adjusted) for {name}: {e}")
                    datapoint_avg_adjusted.clear()
                    samples_avg_adjusted[out_name] = 0
                    empty_error += 1
    
                try:
                    file.seek(0)
                    avg_magnitude_raw = calc_avg_magnitude(file)
                    datapoint_avg_raw.append(avg_magnitude_raw)
                except Exception as e:
                    print(f"Error in calc_avg_magnitude (raw) for {name}: {e}")
                    datapoint_avg_raw.clear()
                    samples_avg_raw[out_name] = 0
                    empty_error += 1
    
                if int(iter) == iterations:
                    if datapoint_median_adjusted:
                        samples_median_adjusted[out_name] = np.mean(datapoint_median_adjusted, axis=0)
                    if datapoint_median_raw:
                        samples_median_raw[out_name] = np.mean(datapoint_median_raw, axis=0)
                    if datapoint_avg_adjusted:
                        samples_avg_adjusted[out_name] = np.mean(datapoint_avg_adjusted, axis=0)
                    if datapoint_avg_raw:
                        samples_avg_raw[out_name] = np.mean(datapoint_avg_raw, axis=0)
                    datapoint_median_adjusted.clear()
                    datapoint_median_raw.clear()
                    datapoint_avg_adjusted.clear()
                    datapoint_avg_raw.clear()

    # Graphs generation
    colors = ['', '#2F4F4F', '#12B57F', '#9DB512', '#DF8816', '#1297B5', '#5912B5', '#B51284', '#127D0C']
    plot_configs = [
        (samples_median_adjusted, 'median_adjusted', 'Median Magnitude vs Parameters (Static Subtracted)'),
        (samples_median_raw, 'median_raw', 'Median Magnitude vs Parameters (Raw Data)'),
        (samples_avg_adjusted, 'avg_adjusted', 'Average Magnitude vs Parameters (Static Subtracted)'),
        (samples_avg_raw, 'avg_raw', 'Average Magnitude vs Parameters (Raw Data)')
    ]
    plot_paths = []
    
    for samples, name_prefix, title in plot_configs:
        params = [reversed(list(samples.items())), sorted(samples.items(), key=lambda x: x[1])]
        names = ['', 'sorted_']
        for param, name in zip(params, names):
            fig = go.Figure()
            for entry in param:
                toff = int(entry[0].split('_')[2].split('=')[1])
                color = colors[toff if toff <= 8 else toff - 8]
                fig.add_trace(go.Bar(x=[entry[1]], y=[entry[0]], marker_color=color, orientation='h', showlegend=False))
            fig.update_layout(title=title, xaxis_title='Magnitude', yaxis_title='Parameters', coloraxis_showscale=True)
            plot_html_path = os.path.join(RESULTS_FOLDER, f'{name}{name_prefix}interactive_plot_{accel_chip}_tmc{driver}_{sense_resistor}_{now}.html')
            pio.write_html(fig, plot_html_path, auto_open=False)
            plot_paths.append(plot_html_path)
        
        # Check speed consistency for sorted plot
        speed1 = params[1][0][0].split('_')[6].split('=')[1]
        speed2 = params[1][1][0].split('_')[6].split('=')[1]
        if speed1 != speed2:
            break

    # Export Info
    try:
        print(f'Access to interactive plot at: {"/".join(plot_html_path.split("/")[:-1] + [plot_html_path.split(names[1])[1]])}')
    except IndexError:
        print(f'Access to interactive plot at: {plot_html_path}')
    if empty_error:
        print(f'Warning!!! Empty data cells detected ({empty_error}), make sure you dont run out of memory')

if __name__ == '__main__':
    if sys.argv[1] == 'cleaner':
        cleaner()
    check_export_path(RESULTS_FOLDER)
    main()
