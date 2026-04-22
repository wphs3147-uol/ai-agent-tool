"""
Daily Briefing Agent — captures and summarises messages from macOS apps.

Uses OCR (pytesseract) to extract text from screenshots and GPT to
produce a unified briefing. Includes retry logic, graceful degradation
per-app, and structured logging.
"""

import os
import time
import subprocess
from core.logger import get_logger, retry
from dotenv import load_dotenv
from openai import OpenAI

logger = get_logger("agents.daily_briefing")

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Apps to capture — order determines briefing order
BRIEFING_APPS = {
    "WhatsApp":          "briefing_whatsapp.png",
    "Microsoft Outlook": "briefing_outlook.png",
    "Messages":          "briefing_messages.png",
}

SCREENSHOT_DIR = os.path.dirname(os.path.dirname(__file__))


def _open_app(app_name):
    """Launch a macOS application, with error handling for missing apps."""
    logger.info("Launching %s...", app_name)
    result = subprocess.run(["open", "-a", app_name], capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("Could not launch %s: %s", app_name, result.stderr.strip())
        return False
    return True


def _activate_fullscreen(app_name):
    """Attempt to put an app into fullscreen via AppleScript."""
    try:
        result = subprocess.run(
            [
                "osascript", "-e",
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events" to keystroke "f" '
                f'using {{control down, command down}}',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.warning("Fullscreen failed for %s: %s", app_name, result.stderr.strip())
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.warning("Fullscreen command timed out for %s", app_name)
        return False


def _take_screenshot(save_path, wait_seconds=5):
    """Capture the screen after a delay, returning the path or None on failure."""
    logger.info("Waiting %ds before screenshot...", wait_seconds)
    time.sleep(wait_seconds)

    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(save_path)
        logger.info("Screenshot saved: %s", save_path)
        return save_path
    except ImportError:
        logger.error("Pillow/ImageGrab not available — cannot take screenshot")
        return None
    except Exception as e:
        logger.error("Screenshot failed: %s", e)
        return None


def _extract_text(image_path):
    """Run OCR on an image, returning extracted text or an empty string on failure."""
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(image_path))
        char_count = len(text.strip())
        logger.info("OCR extracted %d characters from %s", char_count, image_path)
        return text.strip()
    except ImportError:
        logger.error("pytesseract not installed — OCR unavailable")
        return ""
    except Exception as e:
        logger.error("OCR failed for %s: %s", image_path, e)
        return ""


@retry(max_attempts=2, base_delay=2.0)
def _summarise_text(text):
    """Send extracted text to GPT for summarisation, with retry on API errors."""
    if not text.strip():
        return "[No text detected — nothing to summarise.]"

    logger.info("Sending %d characters to GPT for summarisation...", len(text))
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": (
                    "You summarise WhatsApp, iMessage and Outlook messages into a "
                    "concise daily briefing. Group by app, highlight action items, "
                    "and flag anything urgent."
                ),
            },
            {"role": "user", "content": f"Summarise these messages:\n\n{text}"},
        ],
    )
    return response.choices[0].message.content.strip()


def run_daily_briefing():
    """
    Execute the full daily briefing pipeline.

    Returns a dict: {summary: str, apps_captured: int, apps_failed: int, errors: []}
    """
    logger.info("Starting Daily Briefing Agent")
    result = {"summary": "", "apps_captured": 0, "apps_failed": 0, "errors": []}

    extracted_texts = []

    for app_name, screenshot_file in BRIEFING_APPS.items():
        screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_file)

        # Try to open the app — skip gracefully if it's not installed
        if not _open_app(app_name):
            result["apps_failed"] += 1
            result["errors"].append(f"{app_name}: could not launch")
            logger.warning("Skipping %s — could not launch", app_name)
            continue

        time.sleep(3)
        _activate_fullscreen(app_name)

        # Take screenshot
        path = _take_screenshot(screenshot_path)
        if not path:
            result["apps_failed"] += 1
            result["errors"].append(f"{app_name}: screenshot failed")
            continue

        # Extract text via OCR
        text = _extract_text(path)
        if text:
            extracted_texts.append(f"[{app_name}]\n{text}")
            result["apps_captured"] += 1
        else:
            result["apps_failed"] += 1
            result["errors"].append(f"{app_name}: OCR returned no text")
            logger.warning("No text extracted from %s", app_name)

    # Summarise whatever we managed to collect
    if extracted_texts:
        full_text = "\n\n".join(extracted_texts)
        try:
            result["summary"] = _summarise_text(full_text)
        except Exception as e:
            logger.error("Summarisation failed: %s", e)
            result["summary"] = f"[Summarisation failed: {e}]\n\nRaw text:\n{full_text}"
    else:
        result["summary"] = "[No text captured from any app — briefing empty.]"
        logger.warning("No text captured from any app")

    # Print the briefing
    print("\n--- Daily Briefing Summary ---")
    print(result["summary"])
    print("------------------------------")
    print(f"Apps captured: {result['apps_captured']}/{len(BRIEFING_APPS)}")
    if result["errors"]:
        print(f"Issues: {', '.join(result['errors'])}")

    logger.info(
        "Briefing complete — captured: %d, failed: %d",
        result["apps_captured"], result["apps_failed"],
    )
    return result


if __name__ == "__main__":
    run_daily_briefing()
