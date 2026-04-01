#  It has to run only once to initialize the database,
#  so we can comment it out after the first run.

# from backend.database.db import initialize_database
# initialize_database()


import re

def clean_text(text):
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)

    return text.strip()