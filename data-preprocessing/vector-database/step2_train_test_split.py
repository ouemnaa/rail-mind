"""
Step 2: Train/Test Split (Time-Based)
======================================
Splits enriched data chronologically:
- Train: Earlier 80% of data (past incidents)
- Test: Later 20% of data (future incidents)

Time-based split is CORRECT for simulation because:
1. No data leakage (model doesn't see future)
2. Realistic prediction scenario
3. Enables chronological replay/simulation

Author: AI Rail Network Brain Team
Date: January 2026
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from config import (
    OUTPUT_DIR, TRAIN_RATIO, TEST_RATIO, RANDOM_SEED,
    TRAIN_DATA, TEST_DATA
)


def load_enriched_data():
    """Load enriched fault data."""
    print("Loading enriched data...")
    
    enriched_file = OUTPUT_DIR / "fault_data_enriched_full.json"
    
    if not enriched_file.exists():
        print(f"❌ Enriched data not found: {enriched_file}")
        print("   Run step1_enrich_data.py first")
        return None
    
    with open(enriched_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    print(f"  Loaded {len(df)} records")
    
    return df


def create_time_based_split(df):
    """
    Create TIME-BASED train/test split for realistic simulation.
    
    This is the CORRECT approach for time-series data:
    - Train on PAST incidents (earlier dates)
    - Test on FUTURE incidents (later dates)
    
    This prevents data leakage and enables realistic simulation.
    """
    print(f"\nCreating TIME-BASED split: {int(TRAIN_RATIO*100)}% train (past) / {int(TEST_RATIO*100)}% test (future)...")
    
    # Parse datetime for sorting
    df['_sort_datetime'] = pd.to_datetime(df['incident_datetime'], errors='coerce')
    
    # For records without precise datetime, use date
    mask = df['_sort_datetime'].isna()
    df.loc[mask, '_sort_datetime'] = pd.to_datetime(df.loc[mask, 'date'], errors='coerce')
    
    # Sort by datetime (chronological order)
    df_sorted = df.sort_values('_sort_datetime').reset_index(drop=True)
    
    # Calculate split point
    split_idx = int(len(df_sorted) * TRAIN_RATIO)
    
    # Split chronologically
    train_df = df_sorted.iloc[:split_idx].copy()
    test_df = df_sorted.iloc[split_idx:].copy()
    
    # Get split date (for reporting)
    split_date = df_sorted.iloc[split_idx]['_sort_datetime']
    
    # Remove temporary column
    train_df = train_df.drop(columns=['_sort_datetime'])
    test_df = test_df.drop(columns=['_sort_datetime'])
    
    print(f"  ✅ Time-based split complete!")
    print(f"  Train set: {len(train_df)} records ({len(train_df)/len(df)*100:.1f}%)")
    print(f"  Test set: {len(test_df)} records ({len(test_df)/len(df)*100:.1f}%)")
    print(f"  Split date: {split_date}")
    
    return train_df, test_df, split_date


def analyze_split(train_df, test_df, split_date):
    """Analyze and print split statistics."""
    print("\n" + "=" * 60)
    print("TIME-BASED SPLIT ANALYSIS")
    print("=" * 60)
    
    # Date ranges
    print("\n📅 Date Ranges (Chronological):")
    print("-" * 40)
    train_start = pd.to_datetime(train_df['date']).min()
    train_end = pd.to_datetime(train_df['date']).max()
    test_start = pd.to_datetime(test_df['date']).min()
    test_end = pd.to_datetime(test_df['date']).max()
    
    print(f"  TRAIN (Past):   {train_start.strftime('%Y-%m-%d')} → {train_end.strftime('%Y-%m-%d')}")
    print(f"  TEST (Future):  {test_start.strftime('%Y-%m-%d')} → {test_end.strftime('%Y-%m-%d')}")
    print(f"  Split Point:    {split_date}")
    
    # Verify no overlap (important for time-based split)
    if train_end <= test_start:
        print("  ✅ No temporal overlap (correct!)")
    else:
        print("  ⚠️ Warning: Some temporal overlap detected")
    
    # Incident type distribution
    print("\n📊 Incident Type Distribution:")
    print("-" * 40)
    
    train_types = train_df['incident_type'].value_counts(normalize=True)
    test_types = test_df['incident_type'].value_counts(normalize=True)
    
    all_types = set(train_types.index) | set(test_types.index)
    
    print(f"{'Type':<20} {'Train %':<12} {'Test %':<12}")
    print("-" * 40)
    for itype in sorted(all_types):
        train_pct = train_types.get(itype, 0) * 100
        test_pct = test_types.get(itype, 0) * 100
        print(f"{itype:<20} {train_pct:>6.1f}%      {test_pct:>6.1f}%")
    
    # Severity distribution
    print("\n📈 Severity Score Statistics:")
    print("-" * 40)
    train_sev = train_df['severity_score'].describe()
    test_sev = test_df['severity_score'].describe()
    print(f"{'Metric':<15} {'Train':<12} {'Test':<12}")
    print("-" * 40)
    for metric in ['mean', 'std', 'min', 'max']:
        print(f"{metric:<15} {train_sev[metric]:>8.2f}     {test_sev[metric]:>8.2f}")
    
    # Simulation info
    print("\n🎬 Simulation Info:")
    print("-" * 40)
    print(f"  Training incidents: {len(train_df)} (learn patterns)")
    print(f"  Test incidents: {len(test_df)} (simulate prediction)")
    print(f"  Can replay {len(test_df)} incidents chronologically")


def save_splits(train_df, test_df, split_date):
    """Save train and test splits to JSON files."""
    print("\nSaving splits...")
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save train data
    train_records = train_df.to_dict(orient='records')
    with open(TRAIN_DATA, 'w', encoding='utf-8') as f:
        json.dump(train_records, f, indent=2, default=str)
    print(f"  ✅ Train data: {TRAIN_DATA}")
    
    # Save test data
    test_records = test_df.to_dict(orient='records')
    with open(TEST_DATA, 'w', encoding='utf-8') as f:
        json.dump(test_records, f, indent=2, default=str)
    print(f"  ✅ Test data: {TEST_DATA}")
    
    # Save split metadata
    metadata = {
        'split_type': 'time_based',
        'train_size': len(train_df),
        'test_size': len(test_df),
        'train_ratio': TRAIN_RATIO,
        'test_ratio': TEST_RATIO,
        'split_date': str(split_date),
        'train_date_range': {
            'start': str(pd.to_datetime(train_df['date']).min()),
            'end': str(pd.to_datetime(train_df['date']).max())
        },
        'test_date_range': {
            'start': str(pd.to_datetime(test_df['date']).min()),
            'end': str(pd.to_datetime(test_df['date']).max())
        },
        'train_incident_types': train_df['incident_type'].value_counts().to_dict(),
        'test_incident_types': test_df['incident_type'].value_counts().to_dict()
    }
    
    with open(OUTPUT_DIR / "split_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"  ✅ Metadata: {OUTPUT_DIR / 'split_metadata.json'}")


def main():
    """Main train/test split pipeline (TIME-BASED)."""
    print("=" * 60)
    print("TIME-BASED TRAIN/TEST SPLIT PIPELINE")
    print("(Correct for simulation & prediction)")
    print("=" * 60)
    
    # Load enriched data
    df = load_enriched_data()
    if df is None:
        return
    
    # Create TIME-BASED split (not random!)
    train_df, test_df, split_date = create_time_based_split(df)
    
    # Analyze split
    analyze_split(train_df, test_df, split_date)
    
    # Save splits
    save_splits(train_df, test_df, split_date)
    
    print("\n" + "=" * 60)
    print("✅ TIME-BASED SPLIT COMPLETE")
    print("=" * 60)
    print("\n💡 For simulation:")
    print("   1. Train model on TRAIN data (past incidents)")
    print("   2. Replay TEST data chronologically")
    print("   3. Predict resolution before seeing actual outcome")
    
    return train_df, test_df


if __name__ == "__main__":
    main()
