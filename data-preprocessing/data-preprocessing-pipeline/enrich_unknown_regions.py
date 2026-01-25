"""
Enrich stations with Unknown region by adding correct region names.
Focuses on stations with null region_name values.
"""
import pandas as pd
from pathlib import Path

# Region mapping for stations with unknown/null regions
REGION_MAPPING = {
    # Italian stations with missing regions
    'BALESTRATE': 'Sicily',
    'CASTIGLIONCELLO': 'Tuscany',
    'MANAROLA': 'Liguria',
    'OLBIA MARITTIMA ISOLA BIANCA': 'Sardinia',
    'REGGIO CALABRIA LIDO': 'Calabria',
    'RIOMAGGIORE': 'Liguria',
    'ROCCAVALDINA': 'Sicily',
    'S SOSTENE': 'Campania',
    
    # Foreign stations (outside Italy)
    'DIVACA': 'Slovenia',
    'FONTAN SAORGE': 'France',
    'GIUBIASCO': 'Switzerland',
    'JENBACH': 'Austria',
    'KNITTEFELD': 'Austria',
    'LA BRIGUE': 'France',
    'MODANE': 'France',
    'MODANE FX': 'France',
    'NOVA GORICA': 'Slovenia',
    'OLTEN': 'Switzerland',
    'SEZANA': 'Slovenia',
    'VALLORBE': 'Switzerland'
}

def enrich_regions():
    """Enrich station data with correct region names."""
    
    # Load station data
    station_file = Path('Data/Processed/station_data_enriched.csv')
    if not station_file.exists():
        print(f"Error: {station_file} not found")
        return
    
    df = pd.read_csv(station_file)
    
    print(f"Total stations: {len(df)}")
    print(f"Stations with null region_name: {df['region_name'].isna().sum()}")
    
    # Apply mapping
    updated = 0
    for station_name, region_name in REGION_MAPPING.items():
        mask = df['name'] == station_name
        if mask.any():
            df.loc[mask, 'region_name'] = region_name
            updated += 1
            print(f"  ✓ {station_name} -> {region_name}")
    
    print(f"\nUpdated {updated} stations")
    print(f"Remaining null region_name: {df['region_name'].isna().sum()}")
    
    # Save enriched data
    df.to_csv(station_file, index=False)
    print(f"\n✅ Saved to {station_file}")
    
    # Show region distribution
    print("\nRegion distribution:")
    region_counts = df['region_name'].value_counts()
    for region, count in region_counts.head(25).items():
        print(f"  {region}: {count}")

if __name__ == '__main__':
    enrich_regions()
