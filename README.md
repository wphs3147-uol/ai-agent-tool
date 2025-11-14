# AI Agent Tool for Mac

An AI powered automation agent for macOS that performs OS level tasks using natural language input. Designed to simplify and accelerate repetitive desktop actions using OpenAI’s GPT models, AppleScript, and local OCR tools.

---

## Features

- Sorts and organises files in your Downloads folder by file type
- Daily Briefing Agent:
  - Opens WhatsApp, Outlook and iMessage on macOS
  - Takes full screen local screenshots of each app
  - Uses OCR to extract recent messages
  - Summarises communication threads with GPT-4
- Modular design for easy extension and new agents

---

## Tech Stack

- Python 3.12
- OpenAI GPT (via API)
- AppleScript (`osascript`)
- Tesseract OCR (`pytesseract`)
- macOS Automator / local scripting

---

## Instructions for your own use

### 1. Clone the repo
```bash
git clone https://github.com/wphs3147-uol/ai-agent-tool
```

### 2. Create a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
brew install tesseract  # macOS only
```

### 4. Add your OpenAI API key
Create a `.env` file in the root folder with:
```env
OPENAI_API_KEY=your_key_here
```

### 5. Run an agent
```bash
python agents/daily_briefing.py
```

---


## 🔒 .gitignore Note

This project ignores personal screenshots, `.env` files, and cached artefacts all of which I used for testing this tool:
```
.venv/
__pycache__/
.env
*.png
*.jpg
briefing_screen.png
```

---

