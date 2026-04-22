# AI Agent Tool for Mac

An AI-powered automation system that takes natural language input and executes tasks locally on macOS. It integrates OCR to read visual input, SQLite for persistent memory (so it learns from past interactions), and LLM-based reasoning to structure decisions.

---

## Architecture

```
User Input → LLM Router → Agent Execution → Memory Store (SQLite)
                  ↑                              │
                  └──── past context ─────────────┘
```

The system operates as a feedback loop: every task—successful or failed—is recorded in a SQLite database. When a new request arrives, the LLM router retrieves relevant history (similar past tasks, known failure patterns) and uses it to make better routing and planning decisions.

---

## Features

- **Natural language task input** — describe what you want in plain English
- **LLM-based intent routing** — GPT classifies your request and selects the right agent (no brittle keyword matching)
- **Persistent memory (SQLite)** — stores task history, outcomes, and errors so the system improves over time
- **OCR integration** — reads visual input from macOS apps via Tesseract
- **Structured logging & monitoring** — JSON-formatted logs, error classification, and a `--health` command for system diagnostics
- **Graceful failure handling** — retry logic with exponential backoff, per-operation error recovery, and degraded-mode execution
- **Modular agent design** — easy to add new agents without touching the core pipeline

### Agents

- **File Sorter** — organises files in your Downloads folder by type (documents, images, videos, etc.) with collision handling and per-file error recovery
- **Daily Briefing** — opens WhatsApp, Outlook, and iMessage; captures screenshots; runs OCR; and summarises your messages via GPT-4

---

## Tech Stack

- Python 3.12
- OpenAI GPT-4 / GPT-4-Turbo (via API)
- SQLite 3 (persistent memory — no external database needed)
- Tesseract OCR (`pytesseract`)
- AppleScript (`osascript`) for macOS automation
- Structured JSON logging

---

## Project Structure

```
ai-agent-tool/
├── main.py                  # Entry point — orchestrates the full pipeline
├── core/
│   ├── router.py            # LLM-based intent classification and task routing
│   └── logger.py            # Structured logging, retry logic, error classification
├── agents/
│   ├── file_sorter.py       # File organisation agent
│   └── daily_briefing.py    # Message capture and summarisation agent
├── memory/
│   ├── memory_store.py      # SQLite-backed persistent memory and learning
│   └── agent_memory.db      # Auto-created database (git-ignored)
├── logs/
│   └── agent.log            # Structured JSON log file (git-ignored)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/wphs3147-uol/ai-agent-tool
cd ai-agent-tool
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
Create a `.env` file in the root folder:
```env
OPENAI_API_KEY=your_key_here
```

---

## Usage

### Run a task
```bash
python main.py
```
You'll be prompted to describe a task in natural language. The system will route it to the appropriate agent, show you a plan, and ask for confirmation before executing.

### Run the daily briefing directly
```bash
python agents/daily_briefing.py
```

### Check system health
```bash
python main.py --health
```
Displays success rates, failure patterns, average execution times, and unresolved errors.

---

## Design Principles

This system was built with production constraints in mind:

- **What breaks?** — every agent handles errors at the individual operation level (per-file, per-app) so a single failure doesn't take down the whole pipeline
- **How do we monitor it?** — structured JSON logs, error classification, and a health dashboard backed by SQLite give visibility into system behaviour
- **What's the simplest way to improve reliability?** — the memory loop means the system learns from failures; retry logic with exponential backoff handles transient issues; graceful degradation keeps partial results when full execution isn't possible

---

## .gitignore Note

This project ignores personal screenshots, `.env` files, database files, logs, and cached artefacts:
```
venv/
__pycache__/
.env
*.png
*.jpg
*.db
logs/
```
