"""Healthie EHR integration module.

This module provides functions to interact with Healthie for patient management
and appointment scheduling.
"""

from datetime import datetime
import time


import json
import os
import re

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, Browser, Page
from loguru import logger
from dotenv import load_dotenv
from pathlib import Path


_browser: Browser | None = None
_page: Page | None = None

DEFAULT_APPOINTMENT_TYPE = "Initial Consultation"
DEFAULT_CONTACT_TYPE = "Video Call"
DEFAULT_VIDEO_CALL_METHOD = "Healthie Video Call"
DEFAULT_TIMEZONE = "Europe/Madrid"
DEFAULT_APPOINTMENT_NOTES = ""
DEFAULT_REPEATING_APPOINTMENT = False
# Playwright browser mode toggle for local debugging.
PLAYWRIGHT_HEADLESS = True

load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)


def _parse_date_value(value: str) -> datetime | None:
    """Parse a date string using the formats we expect from callers and Healthie."""
    normalized = value.strip()
    if not normalized:
        return None

    # Normalize ordinal day suffixes (e.g. "31st May 2019" -> "31 May 2019").
    normalized = re.sub(r"\b(\d{1,2})(st|nd|rd|th)\b", r"\1", normalized, flags=re.IGNORECASE)

    for fmt in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    return None


def _candidate_dob_formats(date_of_birth: str) -> list[str]:
    """Return normalized DOB strings that may appear in Healthie search results."""
    value = date_of_birth.strip()
    if not value:
        return []

    candidates = {value}
    parsed = _parse_date_value(value)
    if parsed is not None:
        candidates.update(
            {
                parsed.strftime("%-m/%-d/%Y"),
                parsed.strftime("%m/%d/%Y"),
                parsed.strftime("%Y-%m-%d"),
                parsed.strftime("%d/%m/%Y"),
                parsed.strftime("%d-%m-%Y"),
                parsed.strftime("%m-%d-%Y"),
                parsed.strftime("%B %d, %Y"),
                parsed.strftime("%b %d, %Y"),
            }
        )

    return sorted(candidate for candidate in candidates if candidate)


def _extract_result_dob(result_text: str) -> str | None:
    """Extract the DOB displayed in a Healthie patient search result."""
    match = re.search(r"\((\d{1,2}/\d{1,2}/\d{4})\)", result_text)
    if not match:
        return None
    return match.group(1)


def _clean_result_name(result_text: str) -> str:
    """Strip the DOB suffix that Healthie appends in search results."""
    return re.sub(r"\s*\(\d{1,2}/\d{1,2}/\d{4}\)\s*$", "", result_text).strip()





async def _select_react_option(
    page: Page,
    input_selector: str,
    *,
    option_text: str | None = None,
    match_mode: str = "contains",
) -> str:
    """Select an option from a Healthie react-select input and return its label."""
    field_id = input_selector[1:] if input_selector.startswith("#") else None
    opener_locator = None
    if field_id:
        opener_locator = page.locator(
            f'[data-testid="{field_id}"], [data-input-for="{field_id}"]'
        ).first

    input_locator = page.locator(input_selector).first
    await input_locator.wait_for(state="visible", timeout=10000)
    if opener_locator is not None and await opener_locator.count() > 0:
        try:
            await opener_locator.click(force=True)
        except Exception:
            await opener_locator.evaluate("(element) => element.click()")
    else:
        await input_locator.click(force=True)

    options = page.locator('[id^="react-select-"][id*="-option-"]')
    await options.first.wait_for(state="visible", timeout=10000)
    option_count = await options.count()

    chosen_option = None
    chosen_label = None
    normalized_target = option_text.lower().strip() if option_text else None

    for index in range(option_count):
        option = options.nth(index)
        label = " ".join((await option.inner_text()).split())
        if not label:
            continue

        if normalized_target is None:
            chosen_option = option
            chosen_label = label
            break

        candidate = label.lower()
        is_match = candidate == normalized_target if match_mode == "exact" else normalized_target in candidate
        if is_match:
            chosen_option = option
            chosen_label = label
            break

    if chosen_option is None:
        raise RuntimeError(f"Unable to find Healthie dropdown option for {option_text!r}")

    await chosen_option.click()
    return chosen_label or ""



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

    started_at = time.monotonic()
    logger.info("Logging into Healthie...")
    playwright = await async_playwright().start()
    _browser = await playwright.chromium.launch(
        headless=PLAYWRIGHT_HEADLESS,
        args=["--disable-blink-features=AutomationControlled"] if PLAYWRIGHT_HEADLESS else None,
    )
    _page = await _browser.new_page(
        viewport={"width": 1366, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )

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
        logger.exception("Healthie login: email input did not appear on login page")
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
    password_submit = _page.locator('[data-test-id="submit-btn"], button:has-text("Log In")').first
    await password_submit.wait_for(state="visible", timeout=10000)
    await password_submit.click()

    # Healthie may show a passkey interstitial with "Continue to app" after password submit.
    # In headless mode this can appear slightly later and sometimes as a link-like control.
    continue_clicked = False
    try:
        continue_button = _page.get_by_role("button", name=re.compile(r"continue to app", re.I))
        await continue_button.wait_for(state="visible", timeout=12000)
        await continue_button.click()
        continue_clicked = True
        logger.info("Healthie login: clicked passkey interstitial continue button")
    except Exception:
        try:
            continue_link = _page.get_by_role("link", name=re.compile(r"continue to app", re.I))
            await continue_link.wait_for(state="visible", timeout=12000)
            await continue_link.click()
            continue_clicked = True
            logger.info("Healthie login: clicked passkey interstitial continue link")
        except Exception:
            try:
                continue_text = _page.locator("text=/continue to app/i").first
                await continue_text.wait_for(state="visible", timeout=12000)
                await continue_text.click()
                continue_clicked = True
                logger.info("Healthie login: clicked passkey interstitial continue text fallback")
            except Exception:
                pass

    try:
        await _page.wait_for_function(
            "() => window.location.pathname !== '/account/login'",
            timeout=30000,
        )
    except PlaywrightTimeoutError:
        # One extra late interstitial pass for headless timing differences.
        logger.warning("Healthie login: initial navigation wait timed out, trying late continue fallback")
        try:
            continue_text = _page.locator("text=/continue to app/i").first
            await continue_text.wait_for(state="visible", timeout=5000)
            await continue_text.click()
            await _page.wait_for_function(
                "() => window.location.pathname !== '/account/login'",
                timeout=15000,
            )
            logger.info("Healthie login: late continue click succeeded")
        except Exception as exc:
            error_text = ""
            error_locator = _page.locator('[role="alert"], [data-test-id*="error"], .error').first
            if await error_locator.count() > 0:
                error_text = (await error_locator.inner_text()).strip()
            logger.error(
                "Healthie login failed after timeout fallback. current_url='{}' error_text='{}'",
                _page.url,
                error_text,
            )
            raise Exception(f"Login failed on Healthie. {error_text}".strip()) from exc
    except Exception as exc:
        error_text = ""
        error_locator = _page.locator('[role="alert"], [data-test-id*="error"], .error').first
        if await error_locator.count() > 0:
            error_text = (await error_locator.inner_text()).strip()
        logger.error(
            "Healthie login failed after password submit. current_url='{}' error_text='{}'",
            _page.url,
            error_text,
        )
        raise Exception(f"Login failed on Healthie. {error_text}".strip()) from exc

    logger.info("Successfully logged into Healthie in {:.2f}s", time.monotonic() - started_at)
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

    page = await login_to_healthie()
    dob_candidates = _candidate_dob_formats(date_of_birth)
    requested_dob = _parse_date_value(date_of_birth)

    search_input = page.locator(
        'input[data-testid="header-client-search-form"], '
        'input[placeholder="Search Clients..."], '
        'input[aria-label="Search Clients"]'
    ).first
    await search_input.wait_for(state="visible", timeout=30000)
    await search_input.click()
    await search_input.fill("")
    # Headless mode can miss reactive search handlers when value is set all at once.
    # Type with key events first, then fall back to fill if needed.
    try:
        await search_input.type(name, delay=30)
    except Exception:
        await search_input.fill(name)
        logger.warning("find_patient search input type() failed; fell back to fill() name='{}'", name)

    results = page.locator('[data-testid="header-client-result"]')
    try:
        await results.first.wait_for(state="visible", timeout=10000)
    except Exception:
        logger.info("No Healthie patient search results appeared for {}", name)
        return None

    result_count = await results.count()
    target_result = None
    target_name = None
    target_profile_url = None
    matched_dob = None

    for index in range(result_count):
        result = results.nth(index)
        text = " ".join((await result.inner_text()).split())
        if name.lower() not in text.lower():
            continue

        result_dob = _extract_result_dob(text)
        parsed_result_dob = _parse_date_value(result_dob or "")
        matched_candidate = next((candidate for candidate in dob_candidates if candidate in text), None)
        dob_matches = bool(matched_candidate)

        if not dob_matches and requested_dob is not None and parsed_result_dob is not None:
            dob_matches = requested_dob.date() == parsed_result_dob.date()
            if dob_matches:
                matched_candidate = result_dob
                pass

        if not dob_matches:
            continue

        name_link = result.locator('[data-testid="header-client-result-name"]').first
        target_name = _clean_result_name(" ".join((await name_link.inner_text()).split()))
        target_profile_url = await name_link.get_attribute("href")
        target_result = name_link
        matched_dob = matched_candidate
        break

    if target_result is None:
        logger.info("No Healthie patient matched name={} dob={}", name, date_of_birth)
        return None

    await target_result.click()
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_url(re.compile(r".*/users/\d+$"), timeout=15000)

    patient_id_match = re.search(r"/users/(\d+)", page.url)
    if not patient_id_match:
        raise RuntimeError(f"Unable to determine patient id from Healthie URL: {page.url}")

    return {
        "patient_id": patient_id_match.group(1),
        "name": target_name or name,
        "date_of_birth": matched_dob or date_of_birth,
        "profile_url": target_profile_url or page.url,
    }


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
    page = await login_to_healthie()
    await page.goto(f"https://secure.gethealthie.com/users/{patient_id}", wait_until="domcontentloaded")
    await page.wait_for_load_state("domcontentloaded")

    add_appointment_button = page.locator('[data-testid="add-appointment-button"]').first
    await add_appointment_button.wait_for(state="visible", timeout=15000)
    await add_appointment_button.click()

    appointment_type = await _select_react_option(
        page,
        "#appointment_type_id",
        option_text=DEFAULT_APPOINTMENT_TYPE,
    )
    await _select_react_option(page, "#contact_type", option_text=DEFAULT_CONTACT_TYPE)
    await _select_react_option(page, "#video_service", option_text=DEFAULT_VIDEO_CALL_METHOD)

    timezone_display = page.locator(".timezone-select__single-value .selected-option-title").first
    await timezone_display.wait_for(state="visible", timeout=10000)
    current_timezone = " ".join((await timezone_display.inner_text()).split())
    if DEFAULT_TIMEZONE not in current_timezone:
        await _select_react_option(page, "#timezone", option_text=DEFAULT_TIMEZONE)

    date_input = page.locator('input[name="date"]').first
    await date_input.wait_for(state="visible", timeout=10000)
    await date_input.fill(date)

    time_input = page.locator('input[name="time"]').first
    await time_input.wait_for(state="visible", timeout=10000)
    await time_input.fill(time)
    await time_input.press("Enter")

    await page.locator('textarea[name="notes"]').first.fill(DEFAULT_APPOINTMENT_NOTES)

    repeating_checkbox = page.locator('input[name="is_repeating"]').first
    if DEFAULT_REPEATING_APPOINTMENT:
        await repeating_checkbox.check()
    else:
        await repeating_checkbox.uncheck()

    submit_button = page.locator('button[data-testid="primaryButton"]:has-text("Add appointment")').first
    await submit_button.wait_for(state="visible", timeout=10000)

    async with page.expect_response(
        lambda response: (
            response.url == "https://app.gethealthie.com/graphql"
            and response.request.method == "POST"
            and "createAppointment" in (response.request.post_data or "")
        ),
        timeout=30000,
    ) as response_info:
        await submit_button.click()
    response = await response_info.value

    payload = await response.text()
    response_data = json.loads(payload)
    appointment = response_data[0]["data"]["createAppointment"]["appointment"]

    if not appointment or not appointment.get("id"):
        raise RuntimeError(f"Healthie appointment creation did not return an appointment id: {payload}")

    return {
        "appointment_id": appointment["id"],
        "patient_id": patient_id,
        "appointment_type": appointment.get("appointment_type", {}).get("name") or appointment_type,
        "contact_type": appointment.get("contact_type"),
        "date": appointment.get("date"),
        "time": time,
        "end": appointment.get("end"),
        "timezone": appointment.get("timezone_abbr") or current_timezone,
    }
