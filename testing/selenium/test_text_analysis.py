"""
Selenium Test Case 2: Text Analysis Page
Tests that text input and analysis workflow functions correctly.
"""

import unittest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "http://localhost:5173"

# A valid test account — update these with real credentials for your app
TEST_EMAIL = "junaidamalik01@gmail.com"
TEST_PASSWORD = "hello1234"

# Sample text long enough to pass the 50-character minimum
SAMPLE_TEXT = (
    "The sun rose slowly over the mountains, casting long shadows across the valley. "
    "Birds began to sing in the tall trees near the river. A gentle breeze carried "
    "the scent of wildflowers through the cool morning air. Children ran along the "
    "dirt path laughing and playing, enjoying the start of a beautiful summer day. "
    "The farmers were already working in the golden fields of wheat."
)


class TestTextAnalysis(unittest.TestCase):
    """Test cases for the ClarityWorks text analysis page."""

    def setUp(self):
        """Set up Chrome WebDriver and log in before each test."""
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        self.wait = WebDriverWait(self.driver, 15)

        # Log in first so we can access protected pages
        self._login()

    def tearDown(self):
        """Close browser after each test."""
        time.sleep(1)
        self.driver.quit()

    def _login(self):
        """Helper: log in with test credentials."""
        self.driver.get(f"{BASE_URL}/login")
        time.sleep(2)  # Pause: see login page

        email_input = self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='email']")
            )
        )
        email_input.send_keys(TEST_EMAIL)
        time.sleep(1)  # Pause: see email typed

        password_input = self.driver.find_element(
            By.CSS_SELECTOR, "input[type='password']"
        )
        password_input.send_keys(TEST_PASSWORD)
        time.sleep(1)  # Pause: see password typed

        sign_in_btn = self.driver.find_element(
            By.XPATH, "//button[contains(text(), 'Sign In')]"
        )
        sign_in_btn.click()

        # Wait until we leave the login page (redirected after successful login)
        self.wait.until(
            lambda driver: "/login" not in driver.current_url
        )
        time.sleep(2)  # Pause: see dashboard after login

    # ------------------------------------------------------------------
    # Test 1: Analyze page loads with all expected elements
    # ------------------------------------------------------------------
    def test_analyze_page_loads(self):
        """Verify the analyze page renders with title, textarea, and tabs."""
        self.driver.get(f"{BASE_URL}/analyze")
        time.sleep(2)  # Pause: see the analyze page load

        # Page heading
        heading = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//h1[contains(text(), 'New Analysis')]")
            )
        )
        self.assertTrue(heading.is_displayed(), "Page heading should be visible")
        time.sleep(1)  # Pause: heading verified

        # Textarea for text input
        textarea = self.driver.find_element(By.TAG_NAME, "textarea")
        self.assertTrue(textarea.is_displayed(), "Text area should be visible")

        # Analyze button should exist but be disabled (no text entered)
        analyze_btn = self.driver.find_element(
            By.XPATH, "//button[contains(text(), 'Analyze')]"
        )
        self.assertTrue(
            analyze_btn.is_displayed(), "Analyze button should be visible"
        )

        # Word count display should show 0
        word_count = self.driver.find_element(
            By.XPATH, "//p[contains(text(), 'Current Word Count')]"
        )
        self.assertTrue(
            word_count.is_displayed(), "Word count label should be visible"
        )

        time.sleep(3)  # Pause: all elements verified on screen
        print("PASS - Analyze page loads with all expected elements")

    # ------------------------------------------------------------------
    # Test 2: Enter text and verify word count updates
    # ------------------------------------------------------------------
    def test_text_input_updates_word_count(self):
        """Verify that typing text updates the word count display."""
        self.driver.get(f"{BASE_URL}/analyze")
        time.sleep(2)  # Pause: see the analyze page

        # Wait for textarea
        textarea = self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "textarea"))
        )

        # Type sample text
        textarea.send_keys(SAMPLE_TEXT)
        time.sleep(3)  # Pause: see the text appear and word count update

        # The word count number should be greater than 0
        # Find the bold number element near the word count label
        word_count_el = self.driver.find_element(
            By.XPATH,
            "//p[contains(@class, 'text-3xl') and contains(@class, 'font-bold')]",
        )
        word_count_text = word_count_el.text.strip()
        word_count_value = int(word_count_text)

        self.assertGreater(
            word_count_value, 0, "Word count should update after typing text"
        )
        time.sleep(2)  # Pause: see the updated word count

        # The analyze button should now be enabled (text > 50 chars)
        analyze_btn = self.driver.find_element(
            By.XPATH, "//button[contains(text(), 'Analyze')]"
        )
        self.assertTrue(
            analyze_btn.is_enabled(),
            "Analyze button should be enabled when text is long enough",
        )

        time.sleep(3)  # Pause: see the enabled Analyze button
        print(
            f"PASS - Word count updated to {word_count_value} after entering text"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
