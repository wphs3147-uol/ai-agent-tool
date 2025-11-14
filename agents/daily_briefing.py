import os
import time
import pytesseract
from PIL import Image, ImageGrab
import subprocess
from dotenv import load_dotenv
from openai import OpenAI

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def open_app(app_name):
    print(f"[DEBUG] Launching {app_name}...")
    subprocess.run(["open", "-a", app_name])

def take_screenshot(save_path):
    print(f"[DEBUG] Waiting 5 seconds before screenshot...")
    time.sleep(5)
    img = ImageGrab.grab()
    img.save(save_path)
    return save_path

def extract_text(image_path):
    print(f"[DEBUG] Extracting text from {image_path}...")
    return pytesseract.image_to_string(Image.open(image_path))

def summarize_text(text):
    if not text.strip():
        return "[WARNING] No text detected."

    print("[DEBUG] Sending extracted text to GPT for summarisation...")
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You summarise WhatsApp, iMessage and Outlook messages."},
            {"role": "user", "content": f"Summarise these:\n\n{text}"}
        ]
    )
    return response.choices[0].message.content.strip()

def run_daily_briefing():
    print("[DEBUG] Starting Daily Briefing Agent...")

    apps = {
        "WhatsApp": "briefing_whatsapp.png",
        "Microsoft Outlook": "briefing_outlook.png",
        "Messages": "briefing_messages.png"
    }

    extracted_texts = []

    for app_name, screenshot_path in apps.items():
        print(f"\n[DEBUG] → Opening {app_name}")
        open_app(app_name)
        time.sleep(3)

        print(f"[DEBUG] → Attempting fullscreen...")
        result = subprocess.run([
            "osascript", "-e",
            f'''
            tell application "{app_name}"
                activate
            end tell
            tell application "System Events"
                keystroke "f" using {{control down, command down}}
            end tell
            '''
        ], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"[ERROR] Failed to fullscreen {app_name}: {result.stderr.strip()}")
        else:
            print(f"[DEBUG] {app_name} should now be fullscreen.")

        screenshot = take_screenshot(screenshot_path)
        text = extract_text(screenshot)
        extracted_texts.append(f"[{app_name}]\n{text.strip()}\n")

    full_text = "\n\n".join(extracted_texts)
    summary = summarize_text(full_text)

    print("\n--- Daily Briefing Summary ---")
    print(summary)
    print("------------------------------")

if __name__ == "__main__":
    run_daily_briefing()
