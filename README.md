<div align="center">

# 🔍 Web Rate Searcher

**Automatically find and verify ratings for a list of institutions — no manual browsing needed.**

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![Selenium](https://img.shields.io/badge/Selenium-Headless%20Chrome-green?logo=selenium&logoColor=white)
![AI Powered](https://img.shields.io/badge/AI-Perplexity%20Sonar-purple)

</div>

---

## Overview

This tool automates collecting ratings from a target website for a large list of institutions.

You give it an Excel file with names and locations. It:
1. Uses **Perplexity AI** to find each institution's unique ID on the target site
2. Uses a **headless Chrome browser** to scrape the rating from each page
3. Uses **AI again** to verify the result is actually the right institution

No more copy-pasting URLs or searching one by one.

---

## How It Works

```
📄 input_data.xlsx
        │
        ▼
┌───────────────────┐
│   main.py         │  ← Ask AI for the 6-digit ID
│   (Step 1: Enrich)│  ← Scrape the rating from the website
└───────────────────┘
        │
        ▼
📄 enriched_data.xlsx
        │
        ▼
┌───────────────────────┐
│   data_verified.py    │  ← Re-open each page
│   (Step 2: Verify)    │  ← AI confirms it's the right institution
└───────────────────────┘
        │
        ▼
📄 output_data.xlsx  ✅
```

---

## Project Structure

```
search_rate_in_web/
├── main.py              # Step 1 — find IDs and scrape ratings
├── data_verified.py     # Step 2 — verify matches and confirm ratings
├── .env.example         # configuration template
├── requirements.txt     # Python dependencies
└── input_data.xlsx      # your input (you create this)
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Google Chrome

The tool drives a headless Chrome browser. `webdriver-manager` handles downloading the right ChromeDriver automatically — you just need Chrome installed.

### 3. Create your `.env` file

```bash
cp .env.example .env
```

Then open `.env` and fill in:

| Variable | Required | Description |
|:---|:---:|:---|
| `LLM_API_KEY` | ✅ | Your [Perplexity API key](https://www.perplexity.ai/settings/api) |
| `TARGET_BASE_URL` | ✅ | Base URL of the target site |
| `INPUT_FILENAME` | — | Input file name (default: `input_data.xlsx`) |
| `OUTPUT_FILENAME` | — | Output file name (default: `enriched_data.xlsx`) |
| `COL_ENTITY_NAME` | — | Column name for institution names (default: `name`) |
| `COL_LOCATION` | — | Column name for locations (default: `location`) |
| `SEARCH_KEYWORD` | — | Text on the page that appears just before the rating number |
| `PATTERN_MAIN_TEXT` | — | Regex to extract the institution name (Step 2) |
| `PATTERN_METRIC` | — | Regex to extract the rating (Step 2) |

### 4. Prepare your input file

Create `input_data.xlsx` with at least these two columns:

| name | location |
|:---|:---|
| Example University | Tel Aviv |
| Another College | Jerusalem |

Column names must match `COL_ENTITY_NAME` and `COL_LOCATION` in your `.env`.

---

## Usage

### Step 1 — Enrich

```bash
python main.py
```

Reads your input file, finds the ID and rating for each institution, and saves:

| Column | Description |
|:---|:---|
| `found_id` | 6-digit ID found by AI |
| `extracted_metric` | Rating scraped from the website |

Output: `enriched_data.xlsx`

---

### Step 2 — Verify

```bash
python data_verified.py
```

Re-checks each result to confirm the ID is actually correct, then saves:

| Column | Description |
|:---|:---|
| `found_name` | Name shown on the institution's page |
| `status` | `Match`, `Mismatch`, or `Not Found` |
| `metric` | Rating — only filled for confirmed matches |

Output: `output_data.xlsx`

---

## Tech Stack

| Tool | Role |
|:---|:---|
| [Selenium](https://selenium-python.readthedocs.io/) | Headless Chrome browser automation |
| [Perplexity Sonar](https://www.perplexity.ai/) | AI-powered ID lookup and name verification |
| [pandas](https://pandas.pydata.org/) | Reading and writing Excel files |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | Keeping secrets out of the code |

---

## Requirements

- Python 3.9+
- Google Chrome
- A Perplexity API key
