"""Tests for the create_appointment_playwright tool."""

import pytest

from app.shared.tools import create_appointment_playwright


class TestCreateAppointment:
    @pytest.mark.asyncio
    async def test_dummy_always_returns_appointment(self):
        result = await create_appointment_playwright("patient-123", "2026-04-01", "10:00")
        assert result is not None
        assert result["appointment_id"] == "appt-456"
        assert result["patient_id"] == "patient-123"
        assert result["date"] == "2026-04-01"
        assert result["time"] == "10:00"
