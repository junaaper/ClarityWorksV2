"""
Selenium Test Case 1: Login Page
Tests that the login page loads correctly and handles user authentication.
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


class TestLoginPage(unittest.TestCase):
    """Test cases for the ClarityWorks login page."""

    def setUp(self):
        """Set up Chrome WebDriver before each test."""
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options,
        )
        self.wait = WebDriverWait(self.driver, 10)

    def tearDown(self):
        """Close browser after each test."""
        time.sleep(1)
        self.driver.quit()

    # ------------------------------------------------------------------
    # Test 1: Login page loads with all expected elements
    # ------------------------------------------------------------------
    def test_login_page_loads(self):
        """Verify the login page renders with title, form fields, and buttons."""
        self.driver.get(f"{BASE_URL}/login")
        time.sleep(2)  # Pause: see the login page load

        # Page title / branding
        brand = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//h1[contains(text(), 'ClarityWorks')]")
            )
        )
        self.assertTrue(brand.is_displayed(), "ClarityWorks title should be visible")
        time.sleep(1)  # Pause: title verified

        # Email input
        email_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='email']")
        self.assertTrue(email_input.is_displayed(), "Email input should be visible")

        # Password input
        password_input = self.driver.find_element(
            By.CSS_SELECTOR, "input[type='password']"
        )
        self.assertTrue(
            password_input.is_displayed(), "Password input should be visible"
        )

        # Sign In button
        sign_in_btn = self.driver.find_element(
            By.XPATH, "//button[contains(text(), 'Sign In')]"
        )
        self.assertTrue(
            sign_in_btn.is_displayed(), "Sign In button should be visible"
        )

        # Register link
        register_link = self.driver.find_element(
            By.XPATH, "//a[contains(text(), 'Sign up')]"
        )
        self.assertTrue(
            register_link.is_displayed(), "Sign up link should be visible"
        )

        time.sleep(2)  # Pause: all elements verified
        print("PASS - Login page loads with all expected elements")

    # ------------------------------------------------------------------
    # Test 2: Invalid login shows error message
    # ------------------------------------------------------------------
    def test_invalid_login_shows_error(self):
        """Verify that submitting wrong credentials shows an error message."""
        self.driver.get(f"{BASE_URL}/login")
        time.sleep(2)  # Pause: see the login page

        # Wait for form to load
        email_input = self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='email']")
            )
        )

        # Type invalid credentials
        email_input.send_keys("wrong@example.com")
        time.sleep(1)  # Pause: see email typed

        password_input = self.driver.find_element(
            By.CSS_SELECTOR, "input[type='password']"
        )
        password_input.send_keys("wrongpassword123")
        time.sleep(1)  # Pause: see password typed

        # Click Sign In
        sign_in_btn = self.driver.find_element(
            By.XPATH, "//button[contains(text(), 'Sign In')]"
        )
        sign_in_btn.click()
        time.sleep(2)  # Pause: see the error appear

        # Wait for error message to appear (red alert box)
        error_alert = self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[class*='bg-red']")
            )
        )
        self.assertTrue(
            error_alert.is_displayed(),
            "Error message should appear for invalid credentials",
        )

        # Should still be on the login page (not redirected)
        self.assertIn("/login", self.driver.current_url)

        time.sleep(3)  # Pause: see the error message displayed
        print("PASS - Invalid login shows error message correctly")


if __name__ == "__main__":
    unittest.main(verbosity=2)
