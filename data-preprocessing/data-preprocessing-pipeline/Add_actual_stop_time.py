import pandas as pd


df = pd.read_csv(r'operation.csv', low_memory=False)

def calculate_scheduled_stop_time(row):

    if row['actual_arrival_time'] == 0 or row['actual_departure_time'] == 0:
        return 0


    def time_to_minutes(time_str):
        try:

            if pd.isna(time_str) or not isinstance(time_str, str):
                return None
            parts = time_str.split(':')
            if len(parts) != 2:
                return None
            hours, minutes = map(int, parts)
            return hours * 60 + minutes
        except (ValueError, AttributeError):
            return None

    arrival_time = time_to_minutes(row['actual_arrival_time'])
    departure_time = time_to_minutes(row['actual_departure_time'])

    if arrival_time is None or departure_time is None:
        return pd.NA

    return departure_time - arrival_time


df['actual_stop_time'] = df.apply(calculate_scheduled_stop_time, axis=1)

df.to_csv('operation.csv', index=False)

