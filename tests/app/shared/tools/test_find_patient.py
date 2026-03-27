"""Tests for the find_patient tool."""

import pytest

from app.shared.tools import find_patient


class TestFindPatient:
    @pytest.mark.asyncio
    async def test_dummy_always_returns_patient(self):
        result = await find_patient("Jane Doe", "1990-01-15")
        assert result is not None
        assert result["patient_id"] == "dummy-123"
        assert result["name"] == "Jane Doe"
        assert result["date_of_birth"] == "1990-01-15"
