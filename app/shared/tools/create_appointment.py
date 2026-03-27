"""Appointment creation tool.

Dummy implementation for now. Will be backed by Healthie (or another EHR)
in a future PR. The flow layer calls this function without knowing
which backend fulfills the request.
"""


async def create_appointment(patient_id: str, date: str, time: str) -> dict | None:
    """Create an appointment for a patient.

    Args:
        patient_id: The patient's ID from find_patient.
        date: The appointment date (YYYY-MM-DD).
        time: The appointment time (HH:MM, 24-hour).

    Returns:
        dict with appointment_id, patient_id, date, time if created, or None.
    """
    # TODO: Replace with real Healthie appointment creation via healthie.py
    return {"appointment_id": "appt-456", "patient_id": patient_id, "date": date, "time": time}
