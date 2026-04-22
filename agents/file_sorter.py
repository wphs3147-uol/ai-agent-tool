"""
File Sorter Agent — organises files in a directory by type.

Includes graceful failure handling, per-file error recovery,
and structured logging for production reliability.
"""

import os
import shutil
from pathlib import Path
from core.logger import get_logger

logger = get_logger("agents.file_sorter")

FILE_TYPES = {
    "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".csv"],
    "Images":    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"],
    "Videos":    [".mp4", ".mov", ".avi", ".mkv", ".webm"],
    "Audio":     [".mp3", ".wav", ".aac", ".flac", ".ogg"],
    "Archives":  [".zip", ".rar", ".tar", ".gz", ".7z"],
    "Applications": [".dmg", ".pkg", ".exe", ".app"],
    "Code":      [".py", ".js", ".html", ".css", ".java", ".c", ".cpp", ".ts", ".go", ".rs"],
}


def _resolve_category(extension):
    """Map a file extension to its category, or 'Other' if unrecognised."""
    for folder, extensions in FILE_TYPES.items():
        if extension in extensions:
            return folder
    return "Other"


def sort_downloads_by_type(download_path=None):
    """
    Sort files in the target directory into categorised sub-folders.

    Returns a summary dict: {moved: int, skipped: int, errors: int, details: [...]}
    """
    if download_path is None:
        download_path = str(Path.home() / "Downloads")

    summary = {"moved": 0, "skipped": 0, "errors": 0, "details": []}

    # --- Validate path ---
    if not os.path.exists(download_path):
        logger.error("Target path does not exist: %s", download_path)
        raise FileNotFoundError(f"Path does not exist: {download_path}")

    if not os.path.isdir(download_path):
        logger.error("Target path is not a directory: %s", download_path)
        raise NotADirectoryError(f"Not a directory: {download_path}")

    logger.info("Starting file sort in: %s", download_path)

    for file in os.listdir(download_path):
        full_path = os.path.join(download_path, file)

        # Skip directories and hidden files
        if not os.path.isfile(full_path) or file.startswith("."):
            summary["skipped"] += 1
            continue

        ext = os.path.splitext(file)[1].lower()
        category = _resolve_category(ext)
        target_folder = os.path.join(download_path, category)

        try:
            os.makedirs(target_folder, exist_ok=True)
            dest = os.path.join(target_folder, file)

            # Handle name collisions
            if os.path.exists(dest):
                base, extension = os.path.splitext(file)
                counter = 1
                while os.path.exists(dest):
                    dest = os.path.join(target_folder, f"{base}_{counter}{extension}")
                    counter += 1
                logger.info("Name collision for '%s', renamed to avoid overwrite", file)

            shutil.move(full_path, dest)
            logger.info("Moved: %s → %s", file, category)
            summary["moved"] += 1
            summary["details"].append({"file": file, "category": category, "status": "moved"})

        except PermissionError as e:
            logger.warning("Permission denied for '%s': %s", file, e)
            summary["errors"] += 1
            summary["details"].append({"file": file, "status": "permission_denied"})
        except OSError as e:
            logger.warning("OS error moving '%s': %s", file, e)
            summary["errors"] += 1
            summary["details"].append({"file": file, "status": "os_error", "error": str(e)})

    logger.info(
        "Sort complete — moved: %d, skipped: %d, errors: %d",
        summary["moved"], summary["skipped"], summary["errors"],
    )
    return summary
