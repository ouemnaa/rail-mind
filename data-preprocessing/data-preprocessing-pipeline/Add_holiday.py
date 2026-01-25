import pandas as pd


file_path = 'operation.csv'
df = pd.read_csv(file_path)


df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d', errors='coerce')

holidays = [
    pd.to_datetime('2024-01-01'),
    pd.to_datetime('2024-01-06'),
    pd.to_datetime('2024-04-20'),
    pd.to_datetime('2024-04-21'),
    pd.to_datetime('2024-04-25'),
    pd.to_datetime('2024-05-01'),
    pd.to_datetime('2024-06-02')
]


df['holiday'] = False


for holiday in holidays:
    df.loc[df['date'] == holiday, 'holiday'] = True


print(df[['date', 'holiday']])


output_file_path = 'operation.csv'
df.to_csv(output_file_path, index=False)