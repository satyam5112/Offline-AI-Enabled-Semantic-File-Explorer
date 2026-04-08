import os
from pdf2image import convert_from_path
import pytesseract
from concurrent.futures import ThreadPoolExecutor

# 🔥 Set Tesseract path (Windows only)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_pdf(file_path):
    text = ""

    # -------------------------------
    # STEP 1: Try normal extraction (PyMuPDF)
    # -------------------------------
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        text = ""

        for page in doc:
            page_text = page.get_text()
            if page_text:
                text += page_text

        doc.close()

    except Exception as e:
        print(f"[ERROR] Normal PDF extraction failed: {e}")

    # -------------------------------
    # STEP 2: Check if OCR needed
    # -------------------------------
    if len(text.strip()) > 50:
        return text   # ✅ Enough text → skip OCR

    print("⚠️ Low/No text found. Applying OCR...")

    # -------------------------------
    # STEP 3: Convert PDF → Images (LIMIT PAGES)
    # -------------------------------
    try:
        images = convert_from_path(
            file_path,
            first_page=1,
            last_page=3  # 🔥 limit for speed
        )
    except Exception as e:
        print(f"[ERROR] PDF to image conversion failed: {e}")
        return text

    # -------------------------------
    # STEP 4: Optimized OCR function
    # -------------------------------
    def process_image(img):
        try:
            # Convert to grayscale (faster + cleaner)
            img = img.convert("L")

            # Resize (reduce resolution → faster OCR)
            img = img.resize((img.width // 2, img.height // 2))

            return pytesseract.image_to_string(img)

        except Exception as e:
            print(f"[ERROR] OCR failed on image: {e}")
            return ""

    # -------------------------------
    # STEP 5: Parallel OCR
    # -------------------------------
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(process_image, images)

        ocr_text = " ".join(results)

        # If OCR gives better result, use it
        if len(ocr_text.strip()) > len(text.strip()):
            text = ocr_text

    except Exception as e:
        print(f"[ERROR] Parallel OCR failed: {e}")

    # -------------------------------
    # STEP 6: Return final text
    # -------------------------------
    return text