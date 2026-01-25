import pandas as pd


df = pd.read_csv('operation.csv', dtype=str)


actual_arrival = pd.to_datetime(df['actual_departure_time'])
scheduled_arrival = pd.to_datetime(df['scheduled_departure_time'])


arrival_delay = (actual_arrival - scheduled_arrival).dt.total_seconds() / 60


if 'departure_delay' in df.columns:

    try:

        df['departure_delay'].astype(int)

        df['departure_delay'] = arrival_delay.round().astype(int).astype(str)
    except ValueError:

        df['departure_delay'] = arrival_delay.round(1).astype(str)
else:

    df['departure_delay'] = arrival_delay.round(1).astype(str)


df.to_csv('operation.csv', index=False)
