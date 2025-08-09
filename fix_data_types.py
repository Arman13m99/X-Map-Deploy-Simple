# fix_data_types.py - Quick fix for data type issues
import pandas as pd
import numpy as np
from datetime import datetime

def fix_timestamp_columns(df):
    """Convert timestamp columns to proper string format for SQLite"""
    for col in df.columns:
        if 'time' in col.lower() or 'date' in col.lower() or col == 'created_at' or col == 'updated_at':
            if col in df.columns:
                # Convert timestamp to string format
                df[col] = pd.to_datetime(df[col], errors='coerce')
                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
                # Fill any NaT values with None
                df[col] = df[col].replace('NaT', None)
    return df

def fix_vendor_grades(df_vendors, df_graded=None):
    """Fix vendor grade handling"""
    if df_graded is not None and 'vendor_code' in df_vendors.columns:
        # Reset the grade column first
        df_vendors = df_vendors.drop('grade', axis=1, errors='ignore')
        
        # Merge with grades
        df_graded['vendor_code'] = df_graded['vendor_code'].astype(str)
        df_vendors['vendor_code'] = df_vendors['vendor_code'].astype(str)
        
        df_vendors = pd.merge(
            df_vendors, 
            df_graded[['vendor_code', 'grade']], 
            on='vendor_code', 
            how='left'
        )
    
    # Fill missing grades
    if 'grade' in df_vendors.columns:
        df_vendors['grade'] = df_vendors['grade'].fillna('Ungraded').astype(str)
    else:
        df_vendors['grade'] = 'Ungraded'
    
    return df_vendors

# Test the fixes
if __name__ == "__main__":
    print("Data type fixes ready!")
    print("These functions will be automatically used by the optimized system.")