import pandas as pd


df = pd.read_csv('operation.csv', dtype=str)


actual_arrival = pd.to_datetime(df['actual_arrival_time'])
scheduled_arrival = pd.to_datetime(df['scheduled_arrival_time'])


arrival_delay = (actual_arrival - scheduled_arrival).dt.total_seconds() / 60


if 'arrival_delay' in df.columns:

    try:

        df['arrival_delay'].astype(int)

        df['arrival_delay'] = arrival_delay.round().astype(int).astype(str)
    except ValueError:

        df['arrival_delay'] = arrival_delay.round(1).astype(str)
else:

    df['arrival_delay'] = arrival_delay.round(1).astype(str)


df.to_csv('operation.csv', index=False)
