"""Tests for the find_patient_api tool."""

from unittest.mock import AsyncMock, patch

import pytest

from app.shared.tools.find_patient import find_patient_api


class TestFindPatient:
    @pytest.mark.asyncio
    @patch("app.shared.tools.find_patient.get_api_client", new_callable=AsyncMock)
    async def test_returns_patient_when_dob_matches(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.execute.return_value = {
            "users": [
                {
                    "id": "123",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "dob": "1990-01-15",
                }
            ]
        }
        mock_client.patient_cache = {}
        mock_get_client.return_value = mock_client

        result = await find_patient_api("Jane Doe", "1990-01-15")
        assert result is not None
        assert result["patient_id"] == "123"
        assert result["name"] == "Jane Doe"
        assert result["date_of_birth"] == "1990-01-15"

    @pytest.mark.asyncio
    @patch("app.shared.tools.find_patient.get_api_client", new_callable=AsyncMock)
    async def test_returns_none_when_no_users(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.execute.return_value = {"users": []}
        mock_get_client.return_value = mock_client

        result = await find_patient_api("Nobody", "2000-01-01")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.shared.tools.find_patient.get_api_client", new_callable=AsyncMock)
    async def test_returns_none_when_dob_mismatch(self, mock_get_client):
        mock_client = AsyncMock()
        mock_client.execute.return_value = {
            "users": [
                {
                    "id": "123",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "dob": "1995-06-20",
                }
            ]
        }
        mock_get_client.return_value = mock_client

        result = await find_patient_api("Jane Doe", "1990-01-15")
        assert result is None
