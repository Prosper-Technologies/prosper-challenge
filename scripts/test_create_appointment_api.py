"""Test script for create_appointment_api via GraphQL API."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from app.shared.tools.create_appointment import create_appointment_api  # noqa: E402
from app.shared.tools.find_patient import find_patient_api  # noqa: E402


async def main() -> None:
    # First, find the patient to populate the cache
    patient = await find_patient_api("Jeff Mills", "1990-01-01")
    if not patient:
        print("ERROR: Could not find patient Jeff Mills")
        return

    print(f"Found patient: {patient}")
    patient_id = patient["patient_id"]

    # Now create an appointment
    result = await create_appointment_api(patient_id, "2026-04-01", "14:30")
    if result:
        print(f"Appointment created: {result}")
    else:
        print("ERROR: Failed to create appointment")


if __name__ == "__main__":
    asyncio.run(main())
