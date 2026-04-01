import pytesseract
from PIL import Image
import os


# Set path (Windows)
pytesseract.pytesseract.tesseract_cmd = r"import pytesseract"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_image(file_path):
    # print(f"[START] Processing IMAGE file: {file_path}")
    # print(f"[CHECK] Exists? {os.path.exists(file_path)}")

    text = ""

    try:
        # print("[INFO] Opening image...")
        img = Image.open(file_path)

        # print("[INFO] Performing OCR...")
        text = pytesseract.image_to_string(img)

        # print("[SUCCESS] OCR extraction completed")

    except Exception as e:
        print(f"[ERROR] Failed to process image: {file_path}")
        print(f"[ERROR DETAILS] {e}")

    # print("[END] Image extraction completed\n")

    return text