from idlelib.iomenu import encoding

import pandas as pd
import os


a_file = r"operation.csv"
b_file = r"historical_weather_data.csv"

if not os.path.exists(a_file):
    raise FileNotFoundError(f"File {a_file} does not exist, please check the path.")

if not os.path.exists(b_file):
    raise FileNotFoundError(f"File {b_file} does not exist, please check the path.")


a_df = pd.read_csv(a_file)
b_df = pd.read_csv(b_file, encoding='gbk')


if a_df.empty:
    raise ValueError("operation.csv is empty, please check the data content.")

if b_df.empty:
    raise ValueError("historical_weather_data.csv is empty, please check the data content.")


b_df['station'] = b_df['station'].astype(str).str.strip().str.lower()
a_df['match_station'] = a_df['station_name'].astype(str).str.strip().str.lower()


a_df['date'] = pd.to_datetime(a_df['date'], errors='coerce')
b_df['date'] = pd.to_datetime(b_df['date'], errors='coerce')


a_df = a_df.dropna(subset=['date'])
b_df = b_df.dropna(subset=['date'])


merged_df = a_df.merge(
    b_df[['station', 'date', 'temperature_min', 'temperature_max', 'weather_condition']],
    left_on=['match_station', 'date'],
    right_on=['station', 'date'],
    how='left'
)


merged_df.drop(columns=['match_station', 'station'], inplace=True)


if merged_df.empty:
    raise ValueError("Merged data is empty, please check if `station_name`, `station` and `date` match correctly.")


output_file = "operation.csv"
merged_df.to_csv(output_file, index=False, encoding='utf-8')

