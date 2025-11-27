import os
import re
import time
import logging
import pandas as pd
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI
from dotenv import load_dotenv

# --- Configuration & Setup ---
load_dotenv()  # Load variables from .env file

# Logger Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Environment Variables
API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("TARGET_BASE_URL")
INPUT_FILE = os.getenv("INPUT_FILENAME", "input_data.xlsx")
OUTPUT_FILE = os.getenv("OUTPUT_FILENAME", "enriched_data.xlsx")
COL_NAME = os.getenv("COL_ENTITY_NAME", "name")
COL_LOC = os.getenv("COL_LOCATION", "location")
METRIC_KEYWORD = os.getenv("SEARCH_KEYWORD")  # The text to look for on the page


class DataEnricher:
    """
    A generic tool to enrich a dataset of entities by:
    1. Finding an ID via LLM (Perplexity).
    2. Scraping a specific metric from a target website using that ID.
    """

    def __init__(self):
        self._validate_config()
        self.llm_client = OpenAI(api_key=API_KEY, base_url="https://api.perplexity.ai")
        self.driver = self._setup_driver()

    def _validate_config(self):
        if not API_KEY:
            raise ValueError("Missing LLM_API_KEY in .env file")
        if not BASE_URL:
            raise ValueError("Missing TARGET_BASE_URL in .env file")

    def _setup_driver(self):
        """Initializes a headless Chrome browser."""
        logger.info("Initializing Headless Browser...")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        # Optimize performance by blocking images
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

        try:
            return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except Exception as e:
            logger.warning(f"Webdriver Manager failed, trying default: {e}")
            return webdriver.Chrome(options=options)

    def get_entity_id(self, name: str, location: str) -> Optional[str]:
        """Queries the LLM to find the unique ID for the entity."""
        try:
            # The prompt template is generic; the specific phrasing is injected here
            prompt = (
                f"Find the unique 6-digit ID code for the institution '{name}' "
                f"located in '{location}' (Country: Israel). "
                f"Return ONLY the 6-digit number."
            )

            response = self.llm_client.chat.completions.create(
                model="sonar",
                messages=[
                    {"role": "system", "content": "Return only a 6-digit number."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50
            )
            content = response.choices[0].message.content
            match = re.search(r'\b(\d{6})\b', content)
            return match.group(1) if match else None
        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            return None

    def scrape_metric(self, entity_id: str) -> str:
        """Navigates to the URL and scrapes the target metric."""
        try:
            url = f"{BASE_URL}/{entity_id}"
            self.driver.get(url)
            time.sleep(2)  # Allow JS to load

            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)

            body_text = self.driver.find_element(By.TAG_NAME, "body").text

            # Logic to find the number after the keyword
            if METRIC_KEYWORD and METRIC_KEYWORD in body_text:
                # Regex: Find the keyword, look ahead for a number between 1-10
                # Note: Adjust regex in .env if the format changes
                pattern = re.escape(METRIC_KEYWORD) + r'[^\d]*(\d{1,2})'
                match = re.search(pattern, body_text)

                if match:
                    val = match.group(1)
                    if val.isdigit() and 1 <= int(val) <= 10:
                        return val

            return "N/A"
        except Exception as e:
            logger.debug(f"Scraping failed for ID {entity_id}: {e}")
            return "N/A"

    def process_file(self):
        """Main execution loop."""
        logger.info(f"Loading data from {INPUT_FILE}...")
        try:
            df = pd.read_excel(INPUT_FILE, engine='openpyxl')
        except FileNotFoundError:
            logger.error("Input file not found.")
            return

        # Initialize columns
        df['found_id'] = ""
        df['extracted_metric'] = ""

        total = len(df)
        for index, row in df.iterrows():
            name = str(row.get(COL_NAME, ""))
            loc = str(row.get(COL_LOC, ""))

            logger.info(f"[{index + 1}/{total}] Processing: {name}")

            # 1. Get ID
            entity_id = self.get_entity_id(name, loc)

            if entity_id:
                logger.info(f"    -> Found ID: {entity_id}")
                df.at[index, 'found_id'] = entity_id

                # 2. Scrape Metric
                metric = self.scrape_metric(entity_id)
                logger.info(f"    -> Metric: {metric}")
                df.at[index, 'extracted_metric'] = metric
            else:
                logger.warning("    -> ID not found.")
                df.at[index, 'found_id'] = "Not Found"
                df.at[index, 'extracted_metric'] = "N/A"

            time.sleep(0.5)  # Rate limiting

        self.driver.quit()

        logger.info(f"Saving to {OUTPUT_FILE}...")
        df.to_excel(OUTPUT_FILE, index=False)
        logger.info("Done.")


if __name__ == "__main__":
    enricher = DataEnricher()
    enricher.process_file()