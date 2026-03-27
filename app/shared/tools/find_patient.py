"""Patient lookup tool.

Dummy implementation for now. Will be backed by Healthie (or another EHR)
in a future PR. The flow layer calls this function without knowing
which backend fulfills the request.
"""


async def find_patient(name: str, date_of_birth: str) -> dict | None:
    """Look up a patient by name and date of birth.

    Args:
        name: The patient's full name.
        date_of_birth: The patient's date of birth (YYYY-MM-DD).

    Returns:
        dict with patient_id, name, date_of_birth if found, or None.
    """
    # TODO: Replace with real Healthie lookup via healthie.py
    return {"patient_id": "dummy-123", "name": name, "date_of_birth": date_of_birth}
