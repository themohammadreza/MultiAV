import os

STORAGE_PATH = "storage/files"

os.makedirs(STORAGE_PATH, exist_ok=True)

def save_file(file_id: str, content: bytes) -> str:
    path = os.path.join(STORAGE_PATH, file_id)
    with open(path, "wb") as f:
        f.write(content)
    return path

