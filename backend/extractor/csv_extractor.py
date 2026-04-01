import pandas as pd
import os

def extract_csv(file_path):
    # print(f"[START] Processing CSV file: {file_path}")
    # print(f"[CHECK] Exists? {os.path.exists(file_path)}")  # 🔥 VERY IMPORTANT

    text = ""

    try:
        # print("[INFO] Attempting to read CSV file...")
        df = pd.read_csv(file_path)
        # print("[SUCCESS] CSV file loaded successfully")

        # print(f"[INFO] Number of rows: {len(df)}")
        # print(f"[INFO] Columns: {list(df.columns)}")

        for index, row in df.iterrows():
            # print(f"[PROCESSING] Row {index}")

            try:
                row_text = " ".join([str(value) for value in row])
                text += row_text + "\n"
            except Exception as row_error:
                print(f"[ERROR] Failed at row {index}: {row_error}")

        # print("[SUCCESS] Finished processing all rows")

    except Exception as e:
        print(f"[ERROR] Failed to read CSV file: {file_path}")
        print(f"[ERROR DETAILS] {e}")

    # print("[END] CSV extraction completed\n")

    return text