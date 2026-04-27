"""Healthie EHR integration module.

This module provides functions to interact with Healthie for patient management
and appointment scheduling.
"""

import os

from playwright.async_api import async_playwright, Browser, Page
from loguru import logger

_browser: Browser | None = None
_page: Page | None = None


async def login_to_healthie() -> Page:
    """Log into Healthie and return an authenticated page instance.

    This function handles the login process using credentials from environment
    variables. The browser and page instances are stored for reuse by other
    functions in this module.

    Returns:
        Page: An authenticated Playwright Page instance ready for use.

    Raises:
        ValueError: If required environment variables are missing.
        Exception: If login fails for any reason.
    """
    global _browser, _page

    email = os.environ.get("HEALTHIE_EMAIL")
    password = os.environ.get("HEALTHIE_PASSWORD")

    if not email or not password:
        raise ValueError("HEALTHIE_EMAIL and HEALTHIE_PASSWORD must be set in environment variables")

    if _page is not None:
        logger.info("Using existing Healthie session")
        return _page

    logger.info("Logging into Healthie...")
    playwright = await async_playwright().start()
    _browser = await playwright.chromium.launch(headless=False)
    _page = await _browser.new_page()

    email_input = _page.locator(
        '[data-test-id="input-identifier"], input[name="email"], input[type="email"]'
    ).first
    await _page.goto("https://secure.gethealthie.com/account/login", wait_until="domcontentloaded")
    try:
        await email_input.wait_for(state="visible", timeout=10000)
    except Exception:
        if "/account/login" not in _page.url:
            logger.info("Healthie session already authenticated")
            return _page
        raise

    await email_input.wait_for(state="visible", timeout=30000)
    await email_input.fill(email)

    submit_button = _page.locator('[data-test-id="submit-btn"], button:has-text("Log In")').first
    await submit_button.wait_for(state="visible", timeout=30000)
    await submit_button.click()

    password_input = _page.locator(
        'input[type="password"], input[name="password"], [data-test-id="input-password"]'
    ).first
    await password_input.wait_for(state="visible", timeout=30000)
    await password_input.fill(password)
    await submit_button.click()

    try:
        continue_button = _page.get_by_role("button", name="Continue to App")
        await continue_button.wait_for(state="visible", timeout=5000)
        await continue_button.click()
    except Exception:
        pass

    try:
        await _page.wait_for_function(
            "() => window.location.pathname !== '/account/login'",
            timeout=30000,
        )
    except Exception as exc:
        error_text = ""
        error_locator = _page.locator('[role="alert"], [data-test-id*="error"], .error').first
        if await error_locator.count() > 0:
            error_text = (await error_locator.inner_text()).strip()
        raise Exception(f"Login failed on Healthie. {error_text}".strip()) from exc

    logger.info("Successfully logged into Healthie")
    return _page


async def find_patient(name: str, date_of_birth: str) -> dict | None:
    """Find a patient in Healthie by name and date of birth.

    Args:
        name: The patient's full name.
        date_of_birth: The patient's date of birth in a format that Healthie accepts.

    Returns:
        dict | None: A dictionary containing patient information if found,
            including at least a 'patient_id' field. Returns None if the patient
            is not found or if an error occurs.

    Example return value:
        {
            "patient_id": "12345",
            "name": "John Doe",
            "date_of_birth": "1990-01-15",
            ...
        }
    """
    # TODO: Implement patient search functionality using Playwright
    # 1. Ensure you're logged in by calling login_to_healthie()
    # 2. Enter the patient's name and date of birth into the search field
    # 3. Submit the search
    # 4. Parse the results and return patient information
    # 5. Handle cases where the patient is not found
    pass


async def create_appointment(patient_id: str, date: str, time: str) -> dict | None:
    """Create an appointment in Healthie for the specified patient.

    Args:
        patient_id: The unique identifier for the patient in Healthie.
        date: The desired appointment date in a format that Healthie accepts.
        time: The desired appointment time in a format that Healthie accepts.

    Returns:
        dict | None: A dictionary containing appointment information if created
            successfully, including at least an 'appointment_id' field.
            Returns None if appointment creation fails.

    Example return value:
        {
            "appointment_id": "67890",
            "patient_id": "12345",
            "date": "2026-02-15",
            "time": "10:00 AM",
            ...
        }
    """
    # TODO: Implement appointment creation functionality using Playwright
    # 1. Ensure you're logged in by calling login_to_healthie()
    # 2. Navigate to the appointment creation page for the patient
    # 3. Fill in the date and time fields
    # 4. Submit the appointment creation form
    # 5. Verify the appointment was created successfully
    # 6. Return appointment information
    # 7. Handle errors (e.g., time slot unavailable, invalid date/time)
    pass
