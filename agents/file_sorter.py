import os
import shutil
from pathlib import Path

def sort_downloads_by_type(download_path=None):
    if download_path is None:
        download_path = str(Path.home() / "Downloads")

    if not os.path.exists(download_path):
        print(f"This path does not exist: {download_path}")
        return

    # Create destination folders
    file_types = {
        "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".csv"],
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"],
        "Videos": [".mp4", ".mov", ".avi", ".mkv"],
        "Audio": [".mp3", ".wav", ".aac"],
        "Archives": [".zip", ".rar", ".tar", ".gz", ".7z"],
        "Applications": [".dmg", ".pkg", ".exe"],
        "Code": [".py", ".js", ".html", ".css", ".java", ".c", ".cpp"]
    }

    for file in os.listdir(download_path):
        full_path = os.path.join(download_path, file)

        if os.path.isfile(full_path):
            ext = os.path.splitext(file)[1].lower()
            moved = False

            for folder, extensions in file_types.items():
                if ext in extensions:
                    target_folder = os.path.join(download_path, folder)
                    os.makedirs(target_folder, exist_ok=True)
                    shutil.move(full_path, os.path.join(target_folder, file))
                    print(f"I've moved: {file} → {folder}")
                    moved = True
                    break

            if not moved:
                other_folder = os.path.join(download_path, "Other")
                os.makedirs(other_folder, exist_ok=True)
                shutil.move(full_path, os.path.join(other_folder, file))
                print(f"I've moved: {file} → Other")

    print("Downloads folder is now sorted by file type.")
