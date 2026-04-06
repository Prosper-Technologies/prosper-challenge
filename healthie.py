"""Healthie EHR integration module.

This module provides functions to interact with Healthie for patient management
and appointment scheduling.
"""

import os
from datetime import date, time as dt_time, datetime
from time import sleep

from openai import AsyncOpenAI
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

    await _page.goto("https://secure.gethealthie.com/users/sign_in", wait_until="domcontentloaded")
    
    # Wait for the email input to be visible
    email_input = _page.locator('input[name="identifier"]')
    await email_input.wait_for(state="visible", timeout=30000)
    await email_input.fill(email)

    first_login_button = _page.locator('button:has-text("Log In")')
    await first_login_button.wait_for(state="visible", timeout=30000)
    await first_login_button.click()

    
    # Wait for password input
    password_input = _page.locator('input[name="password"]')
    await password_input.wait_for(state="visible", timeout=30000)
    await password_input.fill(password)
    
    # Find and click the Log In button
    submit_button = _page.locator('button:has-text("Log In")')
    await submit_button.wait_for(state="visible", timeout=30000)
    await submit_button.click()
    
    # Wait for navigation after login
    await _page.wait_for_timeout(3000)
    
    # Check if we've navigated away from the sign-in page
    current_url = _page.url
    if "sign_in" in current_url:
        raise Exception("Login may have failed - still on sign-in page")

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
    await login_to_healthie()

    await _page.goto("https://secure.gethealthie.com/clients/active", wait_until="domcontentloaded")

    # Wait for search input
    search_input = _page.locator('input[data-testid="search-input"]')
    await search_input.wait_for(state="visible", timeout=30000)

    await _page.wait_for_timeout(1000)

    await search_input.fill(name)

    await _page.wait_for_timeout(5000)

    result_links = _page.locator("td.client-name-row a")
    count = await result_links.count()
    logger.info(f"Found {count} search results for '{name}'")

    if count == 0:
        raise ValueError(f"No patients found for {name}")

    patient_hrefs: list[str] = []
    for i in range(count):
        href = await result_links.nth(i).get_attribute("href")
        if href:
            patient_hrefs.append(href)

    client = AsyncOpenAI()

    for idx, href in enumerate(patient_hrefs):
        await _page.goto(f"https://secure.gethealthie.com{href}", wait_until="domcontentloaded")

        dob_el = _page.locator('[data-testid="client-dob"]')
        await dob_el.wait_for(state="attached", timeout=10000)
        dob_text = (await dob_el.text_content() or "").strip()

        if not dob_text:
            logger.info(f"Skipping result {idx + 1}/{len(patient_hrefs)}: no DOB on file")
            continue

        name_el = _page.locator('.sidebar-full-name')
        await name_el.wait_for(state="visible", timeout=10000)
        found_name = await name_el.text_content()

        logger.info(f"Checking result {idx + 1}/{len(patient_hrefs)}: {found_name}, DOB: {dob_text}")

        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Do these refer to the same person? Dates must coincide, and name has to be the same. Example: \"John Doe\" is the same as \"John R. doe\" but not the same as \"John\" or \"Doe\". Answer only 'yes' or 'no'.\n"
                        f"Input name: {name}\n"
                        f"Input DOB: {date_of_birth}\n"
                        f"Found name: {found_name}\n"
                        f"Found DOB: {dob_text}"
                    ),
                }
            ],
        )
        answer = resp.choices[0].message.content.strip().lower()
        verified = answer == "yes"
        logger.info(f"Patient verification for result {idx + 1}: {answer} (verified={verified})")

        if verified:
            return {
                "patient_id": _page.url.split("/")[-1],
                "name": found_name.strip() if found_name else name,
                "date_of_birth": dob_text.strip() if dob_text else None,
            }

    raise ValueError(f"No matching patient found for {name} with DOB {date_of_birth}")


async def create_appointment(patient_id: str, date: date, time: dt_time) -> dict | None:
    """Create an appointment in Healthie for the specified patient.

    Navigates to the patient's page, opens the appointment dialog, fills
    in the date, time, and appointment type fields, then submits the form.

    Args:
        patient_id: The unique identifier for the patient in Healthie.
        date: The desired appointment date.
        time: The desired appointment time.

    Returns:
        dict | None: A dictionary with patient_id, date, and time on success.
            Returns None if appointment creation fails.
    """
    page = await login_to_healthie()

    healthie_date = date.strftime("%B %-d, %Y")  # e.g. "April 6, 2026"
    healthie_time = time.strftime("%-I:%M %p")  # e.g. "12:00 PM"

    logger.info(f"Creating appointment for patient {patient_id} on {healthie_date} at {healthie_time}")

    await page.goto(
        f"https://secure.gethealthie.com/users/{patient_id}",
        wait_until="domcontentloaded",
    )

    add_btn = page.locator('[data-testid="add-appointment-button"]')
    await add_btn.wait_for(state="visible", timeout=30000)
    await add_btn.click()

    # Fill date (React datepicker — triple-click to select all, then type over)
    date_input = page.locator("input#date")
    await date_input.wait_for(state="visible", timeout=10000)
    await date_input.click(click_count=3)
    await date_input.fill(healthie_date)

    # Fill time (React datepicker — same approach)
    time_input = page.locator("input#time")
    await time_input.wait_for(state="visible", timeout=10000)
    await time_input.click(click_count=3)
    await time_input.fill(healthie_time)



    # Select appointment type from React Select dropdown
    type_input = page.locator("input#appointment_type_id")
    await type_input.wait_for(state="visible", timeout=10000)
    await type_input.click()
    await type_input.fill("Initial Consultation")
    option = page.get_by_role("option", name="Initial Consultation - 60 Minutes")
    await option.wait_for(state="visible", timeout=5000)
    await option.click()

    logger.info(f"Appointment fields filled for patient {patient_id}: {healthie_date} at {healthie_time}")

    submit_btn = page.get_by_test_id("appointment-form-modal").get_by_test_id("primaryButton")
    await submit_btn.wait_for(state="visible", timeout=10000)
    await submit_btn.click()

    logger.info(f"Appointment submitted for patient {patient_id}")

    return {
        "patient_id": patient_id,
        "date": date.isoformat(),
        "time": time.isoformat(),
    }
