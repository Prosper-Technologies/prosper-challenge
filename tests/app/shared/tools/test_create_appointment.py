"""Tests for the create_appointment_api tool."""

from unittest.mock import AsyncMock, patch

import pytest

from app.shared.tools.create_appointment import create_appointment_api


class TestCreateAppointment:
    @pytest.mark.asyncio
    @patch("app.shared.tools.create_appointment.get_api_client", new_callable=AsyncMock)
    async def test_returns_appointment_on_success(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.execute.side_effect = [
            # First call: get appointment types
            {"appointmentTypes": [{"id": "type-1", "name": "Consultation"}]},
            # Second call: create appointment
            {
                "createAppointment": {
                    "appointment": {"id": "appt-456", "date": "2026-04-01"},
                    "messages": None,
                }
            },
        ]
        mock_get_client.return_value = mock_client

        result = await create_appointment_api("patient-123", "2026-04-01", "10:00")
        assert result is not None
        assert result["appointment_id"] == "appt-456"
        assert result["patient_id"] == "patient-123"
        assert result["date"] == "2026-04-01"
        assert result["time"] == "10:00"

    @pytest.mark.asyncio
    @patch("app.shared.tools.create_appointment.get_api_client", new_callable=AsyncMock)
    async def test_returns_none_when_no_appointment_types(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.execute.return_value = {"appointmentTypes": []}
        mock_get_client.return_value = mock_client

        result = await create_appointment_api("patient-123", "2026-04-01", "10:00")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.shared.tools.create_appointment.get_api_client", new_callable=AsyncMock)
    async def test_returns_none_on_api_error(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.execute.side_effect = [
            {"appointmentTypes": [{"id": "type-1", "name": "Consultation"}]},
            {
                "createAppointment": {
                    "appointment": None,
                    "messages": [{"field": "datetime", "message": "is invalid"}],
                }
            },
        ]
        mock_get_client.return_value = mock_client

        result = await create_appointment_api("patient-123", "2026-04-01", "10:00")
        assert result is None
