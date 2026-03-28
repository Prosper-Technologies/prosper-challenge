"""End-to-end integration test: find patient then create appointment."""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv()

from app.shared.tools import create_appointment_playwright, find_patient_playwright  # noqa: E402


async def main() -> None:
    print("=" * 60)
    print("E2E Integration Test: Find Patient + Create Appointment")
    print("=" * 60)

    # Step 1: Find patient
    patient_name = "Jeff Mills"
    date_of_birth = "1990-01-01"
    print(f"\n[1/2] Finding patient: {patient_name} (DOB: {date_of_birth})")

    try:
        patient = await find_patient_playwright(patient_name, date_of_birth)
    except Exception as e:
        print(f"  FAIL: find_patient_playwright raised {type(e).__name__}: {e}")
        sys.exit(1)

    if not patient:
        print("  FAIL: Patient not found.")
        sys.exit(1)

    patient_id = patient.get("patient_id") or patient.get("id")
    print(f"  OK: Found patient — id={patient_id}, name={patient.get('name')}")

    # Step 2: Create appointment
    appt_date = "2026-04-15"
    appt_time = "10:00"
    print(f"\n[2/2] Creating appointment for {appt_date} at {appt_time}")

    try:
        result = await create_appointment_playwright(patient_id, appt_date, appt_time)
    except Exception as e:
        print(f"  FAIL: create_appointment_playwright raised {type(e).__name__}: {e}")
        sys.exit(1)

    if not result:
        print("  FAIL: Appointment creation returned falsy result.")
        sys.exit(1)

    print(f"  OK: Appointment created — {result}")

    print("\n" + "=" * 60)
    print("ALL STEPS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
