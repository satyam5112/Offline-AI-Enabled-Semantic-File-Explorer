from backend.database.db import get_all_files
from backend.extractor.extractor import extract_file


def run_extractor():
    files = get_all_files()

    # count = 0
    for file in files:
        # count += 1
        # if count == 12:
            # break
        extract_file(file["id"], file["file_path"])
        print(f"Extracted: {file['file_path']}")

if __name__ == "__main__":
    run_extractor()