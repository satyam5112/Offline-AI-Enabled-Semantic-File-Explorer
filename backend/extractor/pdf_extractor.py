import fitz  # PyMuPDF


def extract_pdf(file_path):
    text = ""

    try:
        doc = fitz.open(file_path)

        for page in doc:
            text += page.get_text()

    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")

    return text