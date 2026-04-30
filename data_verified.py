import os
import re
import time
import logging
import pandas as pd
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TARGET_BASE_URL = os.getenv("TARGET_BASE_URL")
API_KEY = os.getenv("LLM_API_KEY")
API_BASE = os.getenv("LLM_API_BASE", "https://api.perplexity.ai")
PATTERN_MAIN_TEXT = os.getenv("PATTERN_MAIN_TEXT", "")
PATTERN_METRIC = os.getenv("PATTERN_METRIC", "")


class EntityVerifier:
    """
    Verifies entity data against a target web database.
    Uses Selenium to scrape the page and an LLM to confirm the entity name matches.
    """

    def __init__(self, input_file: str, output_file: str):
        self.input_file = input_file
        self.output_file = output_file
        self.driver: Optional[webdriver.Chrome] = None
        self.llm_client = self._init_llm_client()

    def _init_llm_client(self) -> Optional[OpenAI]:
        try:
            return OpenAI(api_key=API_KEY, base_url=API_BASE)
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            return None

    def _setup_driver(self):
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)

    def _clean_text(self, text: str) -> str:
        """Removes special characters and normalizes whitespace."""
        if not text:
            return ""
        text = re.sub(r'[^\w\s]', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _extract_page_title(self) -> str:
        """Extracts the main entity name from the loaded page."""
        try:
            self.driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(1)
            body_text = self.driver.find_element(By.TAG_NAME, "body").text

            if PATTERN_MAIN_TEXT:
                match = re.search(PATTERN_MAIN_TEXT, body_text, re.DOTALL)
                if match:
                    return match.group(1).strip()

            for tag in ['h1', 'h2']:
                for el in self.driver.find_elements(By.TAG_NAME, tag):
                    text = el.text.strip()
                    if 5 < len(text) < 100:
                        return text

        except Exception:
            pass
        return "Not Found"

    def _extract_metric(self) -> str:
        """Extracts the target numeric metric from the loaded page."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if PATTERN_METRIC:
                match = re.search(PATTERN_METRIC, body_text, re.DOTALL)
                if match and match.group(1).isdigit():
                    return match.group(1)
        except Exception:
            pass
        return "N/A"

    def _verify_with_llm(self, expected: str, actual: str) -> bool:
        """Uses the LLM to confirm two strings refer to the same entity."""
        if not self.llm_client or not actual:
            return False
        prompt = (
            f"Are '{expected}' and '{actual}' the same entity/organization? "
            f"Ignore minor differences. Reply 'Yes' or 'No'."
        )
        try:
            response = self.llm_client.chat.completions.create(
                model="sonar",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
            )
            return 'yes' in response.choices[0].message.content.lower()
        except Exception:
            return False

    def _process_row(self, entity_id: str, entity_name: str) -> dict:
        result = {"status": "Error", "found_name": "", "metric": ""}

        if not TARGET_BASE_URL:
            logger.error("TARGET_BASE_URL not set in environment.")
            return result

        try:
            self.driver.get(f"{TARGET_BASE_URL}/{entity_id}")

            if "404" in self.driver.title:
                result["status"] = "Not Found"
                return result

            found_name = self._extract_page_title()
            result["found_name"] = found_name

            if self._verify_with_llm(entity_name, found_name):
                result["status"] = "Match"
                result["metric"] = self._extract_metric()
            else:
                result["status"] = "Mismatch"

        except Exception as e:
            result["status"] = f"Exception: {str(e)[:30]}"

        return result

    def run(self):
        """Main loop: reads input, verifies each row, saves output."""
        logger.info("Starting verification process...")
        self._setup_driver()

        try:
            df = pd.read_excel(self.input_file)
            results = []

            for idx, row in df.iterrows():
                e_id = str(row.iloc[0])
                e_name = str(row.iloc[1])
                logger.info(f"[{idx + 1}/{len(df)}] Verifying: {e_name}")
                results.append(self._process_row(e_id, e_name))

            result_df = pd.DataFrame(results)
            final_df = pd.concat([df, result_df], axis=1)
            final_df.to_excel(self.output_file, index=False)
            logger.info(f"Done. Results saved to '{self.output_file}'")

        finally:
            if self.driver:
                self.driver.quit()


if __name__ == "__main__":
    verifier = EntityVerifier("input_data.xlsx", "output_data.xlsx")
    verifier.run()
