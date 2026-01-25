import pandas as pd
from geopy.distance import geodesic


df = pd.read_csv('routes.csv')


def calculate_distance(row):
    if row['station_order'] == 1:
        return 0.00
    else:

        prev_lat = df.loc[row.name - 1, 'lat']
        prev_lon = df.loc[row.name - 1, 'lon']
        distance = geodesic((prev_lat, prev_lon), (row['lat'], row['lon'])).kilometers
        return round(distance, 2)


df['distance'] = df.apply(calculate_distance, axis=1)


df['distance'] = df['distance'].round(2)

output_path = 'routes_distance.csv'
df.to_csv(output_path, index=False)

print(f"Processing completed, the results have been saved to：{output_path}")
