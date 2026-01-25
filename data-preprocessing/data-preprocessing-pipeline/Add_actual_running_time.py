import pandas as pd


df = pd.read_csv('operation.csv')


df['actual_running_time'] = pd.NA


def safe_convert_time(time_str):
    try:

        return pd.to_datetime(time_str, format='%H:%M', errors='raise')
    except ValueError:

        return None


for i in range(len(df)):
    if df.loc[i, 'station_order'] == 1:
        df.loc[i, 'actual_running_time'] = 0
    else:
        current_arrival = safe_convert_time(df.loc[i, 'actual_arrival_time'])
        current_departure = safe_convert_time(df.loc[i, 'actual_departure_time'])

        if pd.notna(current_arrival):
            previous_arrival = safe_convert_time(df.loc[i - 1, 'actual_arrival_time'])
            previous_departure = safe_convert_time(df.loc[i - 1, 'actual_departure_time'])

            if pd.notna(previous_arrival) and pd.notna(previous_departure):
                df.loc[i, 'actual_running_time'] = (current_arrival - previous_departure).total_seconds() / 60
            else:
                j = i - 1
                while j >= 0:
                    previous_departure = safe_convert_time(df.loc[j, 'actual_departure_time'])
                    if pd.notna(previous_departure):
                        break
                    j -= 1
                if j >= 0 and pd.notna(previous_departure):
                    df.loc[i, 'actual_running_time'] = (current_arrival - previous_departure).total_seconds() / 60


df.loc[df['arrival_delay'] == 'S', 'actual_running_time'] = pd.NA


output_path = 'operation.csv'
df.to_csv(output_path, index=False)

