import pandas as pd


file_path = 'operation.csv'
df = pd.read_csv(file_path)


def time_to_minutes(time_str):
    if pd.isna(time_str) or time_str == '0':
        return 0
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes


df['scheduled_arrival_time_minutes'] = df['scheduled_arrival_time'].apply(time_to_minutes)
df['scheduled_departure_time_minutes'] = df['scheduled_departure_time'].apply(time_to_minutes)


df['scheduled_running_time'] = 0


for i in range(1, len(df)):
    if df.loc[i, 'station_order'] != 1:

        df.loc[i, 'scheduled_running_time'] = df.loc[i, 'scheduled_arrival_time_minutes'] - df.loc[i-1, 'scheduled_departure_time_minutes']


df.drop(columns=['scheduled_arrival_time_minutes', 'scheduled_departure_time_minutes'], inplace=True)


output_file_path = 'operation.csv'
df.to_csv(output_file_path, index=False)
