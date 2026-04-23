import pandas as pd
import os

def extract_csv(file_path):
    text = ""

    try:
        df = pd.read_csv(file_path, nrows=1000)
        return df.to_string(index=False)

    except Exception as e:
        print(f"[ERROR] Failed to read CSV file: {file_path}")
        print(f"[ERROR DETAILS] {e}")

    return text