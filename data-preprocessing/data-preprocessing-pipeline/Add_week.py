import pandas as pd
from datetime import datetime


file_path = 'operation.csv'
df = pd.read_csv(file_path)



df['date'] = pd.to_datetime(df['date'], infer_datetime_format=True, errors='coerce')

if df['date'].isna().any():
    print(df[df['date'].isna()])


df['week'] = df['date'].dt.dayofweek + 1


output_file_path = 'operation.csv'
df.to_csv(output_file_path, index=False)
