"""Patient lookup tool backed by Healthie via Playwright.

Uses the global search bar in Healthie's staging UI to find patients by name,
then verifies their date of birth on the client detail page.
"""

from __future__ import annotations

from loguru import logger

from app.integrations.healthie_api import get_client as get_api_client
from app.integrations.healthie_playwright import BASE_URL, get_client


async def find_patient_playwright(name: str, date_of_birth: str) -> dict | None:
    """Look up a patient by name and date of birth.

    Args:
        name: The patient's full name.
        date_of_birth: The patient's date of birth (YYYY-MM-DD).

    Returns:
        dict with patient_id, name, date_of_birth if found, or None.
    """
    client = await get_client()
    page = await client.ensure_browser()

    try:
        # Navigate to home page if not already there
        if BASE_URL not in page.url or "/users/" in page.url:
            logger.info("Navigating to Healthie home page...")
            await page.goto(BASE_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

        # Click on the search input and fill with patient name
        search_input = page.locator('input[name="keywords"]')
        await search_input.wait_for(state="visible", timeout=10000)
        await search_input.click()
        await search_input.fill(name)
        logger.info(f"Searching for patient: {name}")

        # Wait for search results dropdown to appear
        await page.wait_for_timeout(3000)

        # Check for "No results..." text
        no_results = page.locator('text="No results..."')
        if await no_results.count() > 0:
            logger.info(f"No results found for patient: {name}")
            await search_input.clear()
            return None

        # Find the first result link (class contains _userName_)
        result_link = page.locator("[class*='_userName_']").first
        try:
            await result_link.wait_for(state="visible", timeout=5000)
        except Exception:
            logger.warning(f"No search result links found for: {name}")
            await search_input.clear()
            return None

        # Extract patient name and ID from the result
        found_name = (await result_link.text_content() or "").strip()
        href = await result_link.get_attribute("href") or ""
        logger.info(f"Found result: {found_name} — href: {href}")

        # Extract patient ID from href like /users/5769986
        patient_id = None
        if "/users/" in href:
            patient_id = href.split("/users/")[-1].split("/")[0].split("?")[0]

        if not patient_id:
            logger.warning(f"Could not extract patient ID from href: {href}")
            await search_input.clear()
            return None

        # Clear the search input
        await search_input.clear()

        # Navigate to the client detail page to verify DOB
        detail_url = f"{BASE_URL}/users/{patient_id}"
        logger.info(f"Navigating to client detail page: {detail_url}")
        await page.goto(detail_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Look for the DOB on the detail page
        dob_value = None
        try:
            # Look for "Date of birth" label and its sibling value
            dob_element = page.locator("text='Date of birth'")
            if await dob_element.count() > 0:
                # The DOB value is typically near the label; look for a sibling/parent structure
                dob_container = dob_element.locator("xpath=..")
                container_text = await dob_container.text_content() or ""
                # Remove the label to get just the value
                dob_text = container_text.replace("Date of birth", "").strip()
                if dob_text and dob_text != "Not Set":
                    dob_value = dob_text
                    logger.info(f"Found DOB on detail page: {dob_value}")
                else:
                    logger.info(f"DOB is not set for patient {found_name}")
        except Exception as exc:
            logger.warning(f"Error reading DOB from detail page: {exc}")

        # Compare DOB if we have one from the page
        if dob_value is not None:
            # Normalize both DOBs for comparison (handle different formats)
            normalized_page_dob = _normalize_date(dob_value)
            normalized_input_dob = _normalize_date(date_of_birth)
            if normalized_page_dob and normalized_input_dob:
                if normalized_page_dob != normalized_input_dob:
                    logger.info(
                        f"DOB mismatch: page={normalized_page_dob}, input={normalized_input_dob}"
                    )
                    return None
            logger.info("DOB verified successfully")

        # Cache the patient
        client.patient_cache[patient_id] = found_name
        logger.info(f"Patient found and cached: {found_name} (ID: {patient_id})")

        return {
            "patient_id": patient_id,
            "name": found_name,
            "date_of_birth": dob_value or date_of_birth,
        }

    except Exception as exc:
        logger.error(f"Error during patient search: {exc}")
        return None


def _normalize_date(date_str: str) -> str | None:
    """Normalize a date string to YYYY-MM-DD format for comparison."""
    import re
    from datetime import datetime

    date_str = date_str.strip()

    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # Try common formats
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning(f"Could not normalize date: {date_str}")
    return None


async def find_patient_api(name: str, date_of_birth: str) -> dict | None:
    """Look up a patient by name and date of birth via the Healthie GraphQL API.

    Args:
        name: The patient's full name.
        date_of_birth: The patient's date of birth (YYYY-MM-DD).

    Returns:
        dict with patient_id, name, date_of_birth if found, or None.
    """
    client = await get_api_client()

    query = """
    query GetPatients($keywords: String) {
      users(keywords: $keywords, active_status: "Active") {
        id
        first_name
        last_name
        dob
      }
    }
    """

    try:
        data = await client.execute(query, {"keywords": name})
    except Exception as exc:
        logger.error(f"Error searching for patient: {exc}")
        return None

    users = data.get("users") or []
    if not users:
        logger.info(f"No patients found for: {name}")
        return None

    # Find the first user whose DOB matches
    normalized_input_dob = _normalize_date(date_of_birth)
    for user in users:
        user_dob = user.get("dob") or ""
        normalized_user_dob = _normalize_date(user_dob) if user_dob else None

        if (
            normalized_input_dob
            and normalized_user_dob
            and normalized_input_dob == normalized_user_dob
        ):
            patient_id = user["id"]
            found_name = f"{user['first_name']} {user['last_name']}"
            client.patient_cache[patient_id] = found_name
            logger.info(f"Patient found via API: {found_name} (ID: {patient_id})")
            return {
                "patient_id": patient_id,
                "name": found_name,
                "date_of_birth": normalized_user_dob,
            }

    logger.info(f"No patient matched DOB {date_of_birth} for name: {name}")
    return None


async def find_patient(name: str, date_of_birth: str) -> dict | None:
    """Look up a patient by name and date of birth.

    Args:
        name: The patient's full name.
        date_of_birth: The patient's date of birth (YYYY-MM-DD).

    Returns:
        dict with patient_id, name, date_of_birth if found, or None.
    """
    return await find_patient_api(name, date_of_birth)
