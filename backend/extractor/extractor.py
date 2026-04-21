from backend.configuration import DB_LOCATION

from backend.extractor.image_extractor import extract_image
from backend.extractor.pdf_extractor import extract_pdf
from backend.extractor.txt_extractor import extract_txt
from backend.extractor.csv_extractor import extract_csv
from backend.extractor.utils import clean_text


def extract_file(file_path):
    import os

    if os.path.isabs(file_path):
            full_path = file_path
    else:
        full_path = file_path
    
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        content = extract_pdf(full_path)

    elif ext == ".txt":
        content = extract_txt(full_path)

    elif ext == ".csv":
        content = extract_csv(full_path)

    elif ext in [".jpg", ".jpeg", ".png"]:
        content = extract_image(full_path)

    else:
        print(f"Unsupported file: {file_path}")
        return ""

    cleaned_content = clean_text(content)

    return cleaned_content