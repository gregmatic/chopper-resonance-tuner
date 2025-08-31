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
import pandas as pd

RESULTS_FOLDER = os.path.expanduser(RESULTS_FOLDER)
FCLK = 12 # MHz
CUTOFF_RANGE = 5

def cleaner():
    os.system('rm -f /tmp/*.csv')
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
    #data = data[trim_size:-trim_size]
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
    #data = data[trim_size:-trim_size]
    avg_magnitude = np.mean(np.linalg.norm(data, axis=1))
    return avg_magnitude

def calc_all_magnitudes(file, static_data=None):
    """
    Parse accel data, calculate magnitude for each row, 
    adjust with static_data if provided, and return all magnitudes.
    """
    data = np.array([
        [float(row["accel_x"]),
         float(row["accel_y"]),
         float(row["accel_z"])] for row in csv.DictReader(file)])
    if static_data is not None:
        data = data - static_data
    trim_size = len(data) // CUTOFF_RANGE
    #data = data[trim_size:-trim_size]
    magnitudes = np.linalg.norm(data, axis=1)
    return magnitudes
    
def main():
    print("Magnitude graphs generation...")

    args = parse_arguments()
    driver = args.get("driver")
    iterations = int(args.get("iterations"))
    sense_resistor = round(float(args.get("sense_resistor")), 3)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")

    # --- Calc static magnitude ---
    static_name = next((name for name in os.listdir(DATA_FOLDER) if name.endswith("stand_still.csv")), None)
    with open(f"{DATA_FOLDER}{static_name}", "r") as file:
        static_data = calc_static_magnitude(file)
        accel_chip = static_name.split("-")[0]

    # --- Initialize structures ---
    samples_median_adjusted = {}
    samples_median_raw = {}
    samples_avg_adjusted = {}
    samples_avg_raw = {}
    boxplot_data = {}
    empty_error = 0

    # --- Get CSV files in creation order ---
    data_files = sorted(
        [name for name in os.listdir(DATA_FOLDER) if name.endswith("__.csv")],
        key=lambda x: os.path.getmtime(os.path.join(DATA_FOLDER, x)),
        reverse=False,
    )

    total_files = len(data_files)
    if not data_files:
        print("No CSV files found.")
        return

    # --- Process all files once ---
    for index, name in enumerate(data_files, start=1):
        try:
            curr, tbl, toff, hstrt, hend, tpfd, speed, freq, iter_str = name.split("__")[1].split("_")
            iter_num = int(iter_str.rstrip(".csv"))
        except ValueError as e:
            print(f"Error parsing file name {name}: {e}")
            empty_error += 1
            continue

        # Skip files beyond requested iterations
        if iter_num > iterations:
            continue
        print(f"Processing file #{index} from {total_files} found: {name}")
        out_name = (
            f"current={curr}_tbl={tbl}_toff={toff}_hstrt={hstrt}_hend={hend}"
            f"_tpfd={tpfd}_speed={float(speed)/100:.2f}_freq={float(freq)/1000:.2f}kHz"
        )

        # --- Initialize datapoints ---
        datapoint_median_adjusted = []
        datapoint_median_raw = []
        datapoint_avg_adjusted = []
        datapoint_avg_raw = []

        try:
            with open(f"{DATA_FOLDER}{name}", "r") as file:
                # Median adjusted
                md_adj = calc_md_magnitude(file, static_data)
                datapoint_median_adjusted.append(md_adj)

                #file.seek(0)
                #md_raw = calc_md_magnitude(file)
                #datapoint_median_raw.append(md_raw)

                file.seek(0)
                avg_adj = calc_avg_magnitude(file, static_data)
                datapoint_avg_adjusted.append(avg_adj)

                #file.seek(0)
                #avg_raw = calc_avg_magnitude(file)
                #datapoint_avg_raw.append(avg_raw)

                # Boxplot magnitudes
                file.seek(0)
                mags = calc_all_magnitudes(file, static_data)
                if out_name not in boxplot_data:
                    boxplot_data[out_name] = ([], int(toff))
                boxplot_data[out_name][0].extend(mags)

        except Exception as e:
            print(f"Error processing {name}: {e}")
            empty_error += 1
            continue

        # --- Aggregate results for main plots. Flush to lists. ---
        if datapoint_median_adjusted:
            samples_median_adjusted[out_name] = np.median(datapoint_median_adjusted)
        #if datapoint_median_raw:
        #    samples_median_raw[out_name] = np.median(datapoint_median_raw)
        if datapoint_avg_adjusted:
            samples_avg_adjusted[out_name] = np.mean(datapoint_avg_adjusted)
        #if datapoint_avg_raw:
        #    samples_avg_raw[out_name] = np.mean(datapoint_avg_raw)



    # --- Boxplots ---
    colors = ["", "#2F4F4F", "#12B57F", "#9DB512", "#DF8816", "#1297B5", "#5912B5", "#B51284", "#127D0C"]
    boxplot_config = [
        ("unsorted_boxplot", list(boxplot_data.items()), "Unsorted Boxplot: Magnitude Distribution"),
        ("sorted_boxplot", sorted(boxplot_data.items(), key=lambda kv: np.mean(kv[1][0])), "Sorted Boxplot (by Average Magnitude)"),
    ]
    boxplot_csv_output = False
    for prefix, items, base_title in boxplot_config:
        num_points = sum(len(mags) for _, (mags, _) in boxplot_data.items())
        title = f"{base_title} (Iterations = {iterations}, approx {round(num_points/len(items)/iterations)} points per trace)"
        fig = go.Figure()
        for param, (mags, toff) in items:
            color = colors[toff if toff <= 8 else toff - 8]
            fig.add_trace(
                go.Box(
                    x=mags,
                    y=[param] * len(mags),
                    name=param,
                    boxpoints=False, # "all" to show all, but too CPU intensive for visualization
                    jitter=0.5,
                    pointpos=0,
                    marker_color=color,
                    line_color=color,
                    orientation="h",
                    boxmean=True,
                )
            )
        fig.update_layout(title=title, xaxis_title="Magnitude", yaxis_title="Parameters", showlegend=False)
        boxplot_path = os.path.join(RESULTS_FOLDER, f"{prefix}_{now}.html")
        pio.write_html(fig, boxplot_path, auto_open=False)
        print(f"Plots saved: {boxplot_path}")
        
        # --- Export CSV only once ---
        if not boxplot_csv_output:
            boxplot_data_path = os.path.join(RESULTS_FOLDER, f"{prefix}_data_{now}.csv")
            csv_rows = []

            for param_str, (mags, _) in items:
                # Split the parameter string into individual key=value pairs
                param_dict = dict(kv.split('=') for kv in param_str.split('_'))
                
                # Append a row for each magnitude
                for mag in mags:
                    row = {**param_dict, 'Magnitude': round(mag)}
                    csv_rows.append(row)
            csv_df = pd.DataFrame(csv_rows)         
            columns_order = ['current','tbl','toff','hstrt','hend','tpfd','speed','freq','Magnitude']
            csv_df = csv_df[columns_order]
            csv_df.to_csv(boxplot_data_path, index=False)
            boxplot_csv_output = True
            print(f"Raw data saved to: {boxplot_data_path}")
    
    # --- Generate plots ---
    
    plot_configs = [
        (samples_median_adjusted, "median_adj", "Median Magnitude vs Parameters"),
        #(samples_median_raw, "median_raw", "Median Magnitude vs Parameters (Raw Data incl gravity)"),
        (samples_avg_adjusted, "avg_adj", "Average Magnitude vs Parameters (Static Subtracted)"),
        #(samples_avg_raw, "avg_raw", "Average Magnitude vs Parameters (Raw Data inc gravity)"),
    ]
    
    for samples, name_prefix, base_title in plot_configs:
        params_list = [list(samples.items()), sorted(samples.items(), key=lambda x: x[1])]
        names = ["unsorted_", "sorted_"]
        title = f"{base_title} (Iterations = {iterations}, approx {round(num_points/len(items)/iterations)} points per trace)"
        for param, name in zip(params_list, names):
            fig = go.Figure()
            for entry in param:
                toff = int(entry[0].split("_")[2].split("=")[1])
                color = colors[toff if toff <= 8 else toff - 8]
                fig.add_trace(
                    go.Bar(
                        x=[entry[1]],
                        y=[entry[0]],
                        marker_color=color,
                        orientation="h",
                        showlegend=False,
                    )
                )
            fig.update_layout(title=title, xaxis_title="Magnitude", yaxis_title="Parameters")
            plot_html_path = os.path.join(RESULTS_FOLDER, f"{name}{name_prefix}_{now}.html")
            pio.write_html(fig, plot_html_path, auto_open=False)
            print(f"Plots saved: {plot_html_path}")     

     
    if empty_error:
        print(f"Warning: {empty_error} files had errors or empty data cells.")
if __name__ == '__main__':
    if sys.argv[1] == 'cleaner':
        cleaner()
    check_export_path(RESULTS_FOLDER)
    main()
