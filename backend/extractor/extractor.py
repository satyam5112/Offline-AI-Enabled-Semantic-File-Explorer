import os
from backend.configuration import BASE_FOLDER_ADDRESS

from backend.extractor.image_extractor import extract_image
from backend.extractor.pdf_extractor import extract_pdf
from backend.extractor.txt_extractor import extract_txt
from backend.extractor.csv_extractor import extract_csv
from backend.extractor.utils import clean_text

from backend.database.db import insert_file_content


def extract_file(file_id, file_path):
    # 🔥 FIX: Convert relative path → absolute path

    full_path = os.path.normpath(
        os.path.join(BASE_FOLDER_ADDRESS, file_path)
    )
    # print(f"[DEBUG] Full path: {full_path}")
    file_path = full_path
    
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        # print(f"Extracting PDF: {file_path}")
        content = extract_pdf(file_path)

    elif ext == ".txt":
        # print(f"[DEBUG] Extracting TXT: {file_path}")
        content = extract_txt(file_path)

    elif ext == ".csv":
        # print(f"[DEBUG] Extracting CSV: {file_path}")
        content = extract_csv(file_path)

    elif ext == ".jpg" or ext == ".jpeg" or ext == ".png":
        # print(f"[DEBUG] Extracting Image: {file_path}")
        content = extract_image(file_path)
    
    else:
        print(f"Unsupported file: {file_path}")
        return

    # Clean text
    cleaned_content = clean_text(content)

    # Store in DB
    insert_file_content(file_id, cleaned_content)