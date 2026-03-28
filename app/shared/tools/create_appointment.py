"""Appointment creation tool backed by Healthie via Playwright."""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from app.integrations.healthie_api import get_client as get_api_client
from app.integrations.healthie_playwright import BASE_URL, get_client


def _format_date(date_str: str) -> str:
    """Convert 'YYYY-MM-DD' to 'Month DD, YYYY' (e.g. 'April 1, 2026')."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    # %-d gives day without leading zero on Unix; %#d on Windows
    return dt.strftime("%B %-d, %Y")


def _format_time(time_str: str) -> str:
    """Convert 'HH:MM' 24-hour to 'H:MM AM/PM' (e.g. '2:30 PM')."""
    dt = datetime.strptime(time_str, "%H:%M")
    return dt.strftime("%-I:%M %p")


async def create_appointment_playwright(patient_id: str, date: str, time: str) -> dict | None:
    """Create an appointment for a patient.

    Args:
        patient_id: The patient's ID from find_patient_playwright.
        date: The appointment date (YYYY-MM-DD).
        time: The appointment time (HH:MM, 24-hour).

    Returns:
        dict with appointment_id, patient_id, date, time if created, or None.
    """
    try:
        client = await get_client()
        page = await client.ensure_browser()

        # --- Resolve patient name from cache or by visiting profile ---
        patient_name = client.patient_cache.get(patient_id)
        if not patient_name:
            logger.info(f"Patient {patient_id} not in cache — fetching from profile")
            await page.goto(f"{BASE_URL}/users/{patient_id}", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            # Try to grab the name from the page header
            name_el = page.locator("h1").first
            patient_name = (await name_el.text_content() or "").strip()
            if not patient_name:
                logger.error("Could not resolve patient name from profile page")
                return None
            client.patient_cache[patient_id] = patient_name
            logger.info(f"Resolved patient name: {patient_name}")

        # --- Navigate to home page and open appointment modal ---
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        add_btn = page.locator('button:has-text("Add New Appointment")')
        await add_btn.wait_for(state="visible", timeout=15000)
        await add_btn.click()
        logger.info("Clicked 'Add New Appointment'")

        # Wait for modal to appear
        await page.wait_for_selector("text=Add to Calendar", timeout=15000)
        logger.info("Appointment modal is open")

        # --- Fill Invitee field ---
        user_input = page.locator("#user")
        await user_input.wait_for(state="visible", timeout=10000)
        await user_input.click()
        await user_input.fill("")
        await user_input.type(patient_name, delay=80)
        await page.wait_for_timeout(1500)

        # Select the first matching dropdown option
        dropdown_option = page.locator(f'text="{patient_name}"').first
        try:
            await dropdown_option.wait_for(state="visible", timeout=5000)
            await dropdown_option.click()
        except Exception:
            # Fallback: click the first option in the dropdown list
            first_option = page.locator('[class*="option"], [role="option"]').first
            await first_option.wait_for(state="visible", timeout=5000)
            await first_option.click()
        logger.info(f"Selected invitee: {patient_name}")

        # --- Select first Appointment type ---
        appt_type = page.locator("#appointment_type_id")
        await appt_type.wait_for(state="visible", timeout=10000)
        await appt_type.click()
        await page.wait_for_timeout(500)
        first_type_option = page.locator('[class*="option"], [role="option"]').first
        await first_type_option.wait_for(state="visible", timeout=5000)
        await first_type_option.click()
        logger.info("Selected first appointment type")

        # --- Fill Start date ---
        formatted_date = _format_date(date)
        date_input = page.locator("#date")
        await date_input.wait_for(state="visible", timeout=10000)
        await date_input.click(click_count=3)  # Select all existing text
        await date_input.fill(formatted_date)
        logger.info(f"Set date to: {formatted_date}")

        # --- Fill Start time ---
        formatted_time = _format_time(time)
        time_input = page.locator("#time")
        await time_input.wait_for(state="visible", timeout=10000)
        await time_input.click(click_count=3)
        await time_input.fill(formatted_time)
        logger.info(f"Set time to: {formatted_time}")

        # --- Submit ---
        submit_btn = page.locator('button:has-text("Add Individual Session")')
        await submit_btn.wait_for(state="visible", timeout=10000)
        await submit_btn.click()
        logger.info("Clicked 'Add Individual Session'")

        # Wait for confirmation (modal closes)
        await page.wait_for_timeout(3000)
        logger.info("Appointment creation submitted")

        return {
            "appointment_id": "created",
            "patient_id": patient_id,
            "date": date,
            "time": time,
        }

    except Exception as exc:
        logger.error(f"Failed to create appointment: {exc}")
        return None


async def create_appointment_api(patient_id: str, date: str, time: str) -> dict | None:
    """Create an appointment for a patient via the Healthie GraphQL API.

    Args:
        patient_id: The patient's ID from find_patient_api.
        date: The appointment date (YYYY-MM-DD).
        time: The appointment time (HH:MM, 24-hour).

    Returns:
        dict with appointment_id, patient_id, date, time if created, or None.
    """
    client = await get_api_client()

    # First, get the first available appointment type
    types_query = """
    query GetAppointmentTypes {
      appointmentTypes {
        id
        name
      }
    }
    """

    try:
        types_data = await client.execute(types_query)
    except Exception as exc:
        logger.error(f"Error fetching appointment types: {exc}")
        return None

    appointment_types = types_data.get("appointmentTypes") or []
    if not appointment_types:
        logger.error("No appointment types available")
        return None

    appointment_type_id = appointment_types[0]["id"]
    logger.info(
        f"Using appointment type: {appointment_types[0]['name']} (ID: {appointment_type_id})"
    )

    # Combine date and time into datetime string
    dt_string = f"{date} {time}:00"

    # Create the appointment
    mutation = """
    mutation CreateAppointment(
      $appointment_type_id: String
      $datetime: String
      $attendee_ids: String
    ) {
      createAppointment(input: {
        appointment_type_id: $appointment_type_id
        datetime: $datetime
        attendee_ids: $attendee_ids
      }) {
        appointment {
          id
          date
        }
        messages {
          field
          message
        }
      }
    }
    """

    variables = {
        "appointment_type_id": appointment_type_id,
        "datetime": dt_string,
        "attendee_ids": patient_id,
    }

    try:
        data = await client.execute(mutation, variables)
    except Exception as exc:
        logger.error(f"Error creating appointment: {exc}")
        return None

    result = data.get("createAppointment", {})
    messages = result.get("messages") or []
    if messages:
        for msg in messages:
            logger.error(f"Appointment error - {msg['field']}: {msg['message']}")
        return None

    appointment = result.get("appointment")
    if not appointment:
        logger.error("No appointment returned from mutation")
        return None

    logger.info(f"Appointment created via API: ID={appointment['id']}")
    return {
        "appointment_id": appointment["id"],
        "patient_id": patient_id,
        "date": date,
        "time": time,
    }
