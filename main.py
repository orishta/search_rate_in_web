import os
import re
import time
import logging
import pandas as pd
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("TARGET_BASE_URL")
INPUT_FILE = os.getenv("INPUT_FILENAME", "input_data.xlsx")
OUTPUT_FILE = os.getenv("OUTPUT_FILENAME", "enriched_data.xlsx")
COL_NAME = os.getenv("COL_ENTITY_NAME", "name")
COL_LOC = os.getenv("COL_LOCATION", "location")
METRIC_KEYWORD = os.getenv("SEARCH_KEYWORD")


class DataEnricher:
    """
    Enriches an Excel dataset by:
    1. Using an LLM (Perplexity) to find a 6-digit ID for each entity.
    2. Scraping a numeric metric from a target website using that ID.
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

    def _setup_driver(self) -> webdriver.Chrome:
        logger.info("Initializing headless browser...")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

        try:
            return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except Exception as e:
            logger.warning(f"WebdriverManager failed, falling back to system driver: {e}")
            return webdriver.Chrome(options=options)

    def get_entity_id(self, name: str, location: str) -> Optional[str]:
        """Queries the LLM to find the unique 6-digit ID for the entity."""
        prompt = (
            f"Find the unique 6-digit ID code for the institution '{name}' "
            f"located in '{location}' (Country: Israel). "
            f"Return ONLY the 6-digit number."
        )
        try:
            response = self.llm_client.chat.completions.create(
                model="sonar",
                messages=[
                    {"role": "system", "content": "Return only a 6-digit number."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=50,
            )
            content = response.choices[0].message.content
            match = re.search(r'\b(\d{6})\b', content)
            return match.group(1) if match else None
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return None

    def scrape_metric(self, entity_id: str) -> str:
        """Navigates to the entity page and scrapes the target metric."""
        try:
            self.driver.get(f"{BASE_URL}/{entity_id}")
            time.sleep(2)
            self.driver.execute_script("window.scrollBy(0, 300);")
            time.sleep(1)

            body_text = self.driver.find_element(By.TAG_NAME, "body").text

            if METRIC_KEYWORD and METRIC_KEYWORD in body_text:
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
        """Main loop: reads input, enriches each row, saves output."""
        logger.info(f"Loading data from '{INPUT_FILE}'...")
        try:
            df = pd.read_excel(INPUT_FILE, engine='openpyxl')
        except FileNotFoundError:
            logger.error(f"Input file '{INPUT_FILE}' not found.")
            return

        df['found_id'] = ""
        df['extracted_metric'] = ""
        total = len(df)

        for index, row in df.iterrows():
            name = str(row.get(COL_NAME, ""))
            loc = str(row.get(COL_LOC, ""))
            logger.info(f"[{index + 1}/{total}] Processing: {name}")

            entity_id = self.get_entity_id(name, loc)

            if entity_id:
                logger.info(f"    -> ID: {entity_id}")
                df.at[index, 'found_id'] = entity_id
                metric = self.scrape_metric(entity_id)
                logger.info(f"    -> Metric: {metric}")
                df.at[index, 'extracted_metric'] = metric
            else:
                logger.warning("    -> ID not found.")
                df.at[index, 'found_id'] = "Not Found"
                df.at[index, 'extracted_metric'] = "N/A"

            time.sleep(0.5)

        self.driver.quit()
        logger.info(f"Saving results to '{OUTPUT_FILE}'...")
        df.to_excel(OUTPUT_FILE, index=False)
        logger.info("Done.")


if __name__ == "__main__":
    enricher = DataEnricher()
    enricher.process_file()
