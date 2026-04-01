## steps to open this project

1. open virtual environment `pythonenv` in `git bash`
2. now activate the virtual environment using `source Scripts/activate`
3. navigate inside `MAJOR PROJECT` folder and open it in `VS Code`
4. run the project using `python -m backend.database.db` as `python -m module.module....`

## task completion status

1. Database Module
- It handles all the connections from the database.
- All the data written or read from the db using this module.

2. Indexer Module
- It scans through the local file system and stores the entire file and folders info in the database.
- These all information are stored in a table `Files` in the `sqlite3 db`.

3. Extractor Module
- It performs the content extraction of all the files in the LFS and stores the content in the table `FileContents`.
- I thas been implemented using `extractor.py` which call separate function according to the file extension.
- I am running `run_extractor` which reads each file from database and calls `extractor's` `extract_file()` function to extract the content of files based on the file extension.

4. Vectorization
