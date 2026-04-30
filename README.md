# Web Rate Searcher

A two-step Python automation tool that takes a list of institutions from an Excel file, finds their IDs on a target website using AI, scrapes a numeric rating from each page, and then verifies the results.

Built for a friend who needed to collect ratings for a large list of institutions without doing it manually one by one.

---

## What It Does

**Step 1 — Enrich (`main.py`)**

- Reads an Excel file with institution names and locations.
- Asks [Perplexity AI](https://www.perplexity.ai/) to find the unique 6-digit ID for each institution.
- Opens that institution's page on the target website using a headless Chrome browser.
- Scrapes the numeric rating from the page.
- Saves everything to a new Excel file.

**Step 2 — Verify (`data_verified.py`)**

- Reads the enriched Excel file (output of Step 1).
- Re-opens each institution's page and extracts the name shown on that page.
- Uses AI to confirm the scraped name actually matches the institution you searched for (catches wrong IDs).
- Re-extracts the rating for confirmed matches and flags mismatches.
- Saves a final verified Excel file.

---

## Project Structure

```
search_rate_in_web/
├── main.py              # Step 1: Find IDs and scrape ratings
├── data_verified.py     # Step 2: Verify matches and confirm ratings
├── .env.example         # Template for your configuration
├── requirements.txt     # Python dependencies
└── input_data.xlsx      # Your input file (you create this)
```

---

## Setup

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Google Chrome

The tool uses a headless Chrome browser. Make sure Chrome is installed on your machine.
`webdriver-manager` will automatically download the matching ChromeDriver.

### 3. Configure your environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and set:

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | Yes | Your Perplexity API key |
| `TARGET_BASE_URL` | Yes | Base URL of the target site (e.g. `https://example.com/institution`) |
| `INPUT_FILENAME` | No | Name of your input Excel file (default: `input_data.xlsx`) |
| `OUTPUT_FILENAME` | No | Name of the output Excel file (default: `enriched_data.xlsx`) |
| `COL_ENTITY_NAME` | No | Column name for institution names (default: `name`) |
| `COL_LOCATION` | No | Column name for locations (default: `location`) |
| `SEARCH_KEYWORD` | No | Text on the page that appears just before the rating number |
| `PATTERN_MAIN_TEXT` | No | Regex to extract the institution name from the page (for Step 2) |
| `PATTERN_METRIC` | No | Regex to extract the rating from the page (for Step 2) |

### 4. Prepare your input file

Create `input_data.xlsx` with at least two columns:

| name | location |
|---|---|
| Example University | Tel Aviv |
| Another College | Jerusalem |

The column names must match `COL_ENTITY_NAME` and `COL_LOCATION` in your `.env`.

---

## Running

### Step 1 — Enrich

```bash
python main.py
```

This produces `enriched_data.xlsx` (or whatever you set `OUTPUT_FILENAME` to) with two new columns:
- `found_id` — the 6-digit ID found by AI
- `extracted_metric` — the rating scraped from the website

### Step 2 — Verify

```bash
python data_verified.py
```

This reads `input_data.xlsx` (column 0 = ID, column 1 = Name) and produces `output_data.xlsx` with three new columns:
- `found_name` — the name found on the institution's page
- `status` — `Match`, `Mismatch`, or `Not Found`
- `metric` — the rating (only filled in for confirmed matches)

---

## How the AI Part Works

The tool uses the **Perplexity Sonar** model (accessed via the OpenAI-compatible API).

- In Step 1, it asks Perplexity to look up the institution's ID.
- In Step 2, it asks Perplexity to compare two names and decide if they refer to the same place — this catches cases where the ID lookup returned the wrong institution.

All sensitive configuration (API keys, target URLs, regex patterns) lives in `.env` and is never committed to the repository.

---

## Requirements

- Python 3.9+
- Google Chrome
- A [Perplexity API key](https://www.perplexity.ai/settings/api)
