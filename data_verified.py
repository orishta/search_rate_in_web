import os
import re
import time
import logging
import pandas as pd
from typing import Optional, Tuple, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from openai import OpenAI
from dotenv import load_dotenv

# Load sensitive configuration from .env file
load_dotenv()

# --- Configuration ---
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Load secrets from environment variables (Invisible to GitHub)
TARGET_BASE_URL = os.getenv("TARGET_BASE_URL")
API_KEY = os.getenv("LLM_API_KEY")
API_BASE = os.getenv("LLM_API_BASE", "https://api.perplexity.ai")

# Load regex patterns from environment (to hide language/specifics)
PATTERN_MAIN_TEXT = os.getenv("PATTERN_MAIN_TEXT", "")
PATTERN_METRIC = os.getenv("PATTERN_METRIC", "")


class EntityVerifier:
    """
    A generic tool to verify entity data against a target web database
    using Selenium for scraping and an LLM for fuzzy string matching.
    """

    def __init__(self, input_file: str, output_file: str):
        self.input_file = input_file
        self.output_file = output_file
        self.driver = None
        self.llm_client = self._init_llm_client()

    def _init_llm_client(self) -> Optional[OpenAI]:
        try:
            return OpenAI(api_key=API_KEY, base_url=API_BASE)
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            return None

    def setup_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)

    def clean_text(self, text: str) -> str:
        """Standardizes text for comparison."""
        if not text: return ""
        # Remove common special characters and normalize whitespace
        text = re.sub(r'[^\w\s]', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def extract_page_title(self) -> str:
        """Extracts the main entity name from the page using configured strategies."""
        try:
            self.driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(1)

            body_text = self.driver.find_element(By.TAG_NAME, "body").text

            # Strategy 1: Regex pattern from config
            if PATTERN_MAIN_TEXT:
                match = re.search(PATTERN_MAIN_TEXT, body_text, re.DOTALL)
                if match:
                    return match.group(1).strip()

            # Strategy 2: Header tags
            for tag in ['h1', 'h2']:
                for el in self.driver.find_elements(By.TAG_NAME, tag):
                    text = el.text.strip()
                    if 5 < len(text) < 100:
                        return text

        except Exception:
            pass
        return "Not Found"

    def extract_target_metric(self) -> str:
        """Extracts a specific numeric value based on the environment pattern."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text

            if PATTERN_METRIC:
                match = re.search(PATTERN_METRIC, body_text, re.DOTALL)
                if match:
                    val = match.group(1)
                    if val.isdigit(): return val

            return "N/A"
        except Exception:
            return "N/A"

    def verify_with_llm(self, expected: str, actual: str) -> bool:
        """Uses LLM to check if two strings refer to the same entity."""
        if not self.llm_client or not actual: return False

        prompt = (f"Are '{expected}' and '{actual}' the same entity/organization? "
                  f"Ignore minor differences. Reply 'Yes' or 'No'.")

        try:
            response = self.llm_client.chat.completions.create(
                model="sonar",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5
            )
            return 'yes' in response.choices[0].message.content.lower()
        except Exception:
            return False

    def process_row(self, entity_id: str, entity_name: str) -> dict:
        result = {"status": "Error", "found_name": "", "metric": ""}

        if not TARGET_BASE_URL:
            logger.error("Target URL not set in environment.")
            return result

        try:
            # Construct URL dynamically
            url = f"{TARGET_BASE_URL}/{entity_id}"
            self.driver.get(url)

            if "404" in self.driver.title:
                result["status"] = "Not Found"
                return result

            found_name = self.extract_page_title()
            result["found_name"] = found_name

            if self.verify_with_llm(entity_name, found_name):
                result["status"] = "Match"
                result["metric"] = self.extract_target_metric()
            else:
                result["status"] = "Mismatch"

        except Exception as e:
            result["status"] = f"Exception: {str(e)[:20]}"

        return result

    def run(self):
        logger.info("Starting verification process...")
        self.setup_driver()

        try:
            df = pd.read_excel(self.input_file)
            # Assuming standard column names, map them if necessary
            # For privacy, the code assumes column 0 is ID, column 1 is Name

            results = []
            for idx, row in df.iterrows():
                # Generic column access
                e_id = str(row.iloc[0])
                e_name = str(row.iloc[1])

                logger.info(f"Processing: {e_name}")
                data = self.process_row(e_id, e_name)

                # Append results to row
                results.append(data)

            # Convert results to dataframe and save
            result_df = pd.DataFrame(results)
            final_df = pd.concat([df, result_df], axis=1)
            final_df.to_excel(self.output_file, index=False)
            logger.info(f"Done. Saved to {self.output_file}")

        finally:
            if self.driver: self.driver.quit()


if __name__ == "__main__":
    verifier = EntityVerifier("input_data.xlsx", "output_data.xlsx")
    verifier.run()