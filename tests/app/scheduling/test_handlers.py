"""Tests for scheduling flow handler functions."""

from unittest.mock import AsyncMock, patch

import pytest

from app.scheduling.handlers import (
    handle_collect_name,
    handle_create_appointment,
    handle_find_patient,
)


class FakeFlowManager:
    def __init__(self):
        self.state = {}


class TestHandleCollectName:
    @pytest.mark.asyncio
    async def test_stores_name_and_transitions_to_dob_node(self):
        fm = FakeFlowManager()
        result_msg, next_node = await handle_collect_name({"name": "Jane Doe"}, fm)
        assert "Jane Doe" in result_msg
        assert fm.state["patient_name"] == "Jane Doe"
        assert next_node is not None
        assert len(next_node["functions"]) == 1
        assert next_node["functions"][0].name == "find_patient_playwright"


class TestHandleFindPatient:
    @pytest.mark.asyncio
    @patch("app.scheduling.handlers.find_patient_api", new_callable=AsyncMock)
    async def test_patient_found_transitions_to_appointment_node(self, mock_find):
        mock_find.return_value = {
            "patient_id": "dummy-123",
            "name": "Jane Doe",
            "date_of_birth": "1990-01-15",
        }
        fm = FakeFlowManager()
        fm.state["patient_name"] = "Jane Doe"
        result_msg, next_node = await handle_find_patient({"date_of_birth": "1990-01-15"}, fm)
        assert "Jane Doe" in result_msg
        assert next_node is not None
        assert len(next_node["functions"]) == 1
        assert next_node["functions"][0].name == "create_appointment_playwright"

    @pytest.mark.asyncio
    @patch("app.scheduling.handlers.find_patient_api", new_callable=AsyncMock)
    async def test_patient_found_updates_state(self, mock_find):
        mock_find.return_value = {
            "patient_id": "dummy-123",
            "name": "Jane Doe",
            "date_of_birth": "1990-01-15",
        }
        fm = FakeFlowManager()
        fm.state["patient_name"] = "Jane Doe"
        await handle_find_patient({"date_of_birth": "1990-01-15"}, fm)
        assert fm.state["patient_id"] == "dummy-123"
        assert fm.state["patient_name"] == "Jane Doe"

    @pytest.mark.asyncio
    @patch("app.scheduling.handlers.find_patient_api", new_callable=AsyncMock)
    async def test_patient_not_found_transitions_to_not_found_node(self, mock_find):
        mock_find.return_value = None
        fm = FakeFlowManager()
        fm.state["patient_name"] = "Nobody"
        result_msg, next_node = await handle_find_patient({"date_of_birth": "2000-01-01"}, fm)
        assert "not found" in result_msg.lower()
        assert next_node is not None
        assert next_node["functions"][0].name == "collect_name"


class TestHandleCreateAppointment:
    @pytest.mark.asyncio
    @patch("app.scheduling.handlers.create_appointment_api", new_callable=AsyncMock)
    async def test_appointment_created_transitions_to_confirmation(self, mock_create):
        mock_create.return_value = {
            "appointment_id": "appt-456",
            "patient_id": "dummy-123",
            "date": "2026-04-01",
            "time": "10:00",
        }
        fm = FakeFlowManager()
        fm.state["patient_id"] = "dummy-123"
        result_msg, next_node = await handle_create_appointment(
            {"date": "2026-04-01", "time": "10:00"}, fm
        )
        assert "2026-04-01" in result_msg
        assert "10:00" in result_msg
        assert next_node is not None
        assert next_node["functions"] == []
        assert next_node["post_actions"] == [{"type": "end_conversation"}]

    @pytest.mark.asyncio
    @patch("app.scheduling.handlers.create_appointment_api", new_callable=AsyncMock)
    async def test_appointment_created_updates_state(self, mock_create):
        mock_create.return_value = {
            "appointment_id": "appt-456",
            "patient_id": "dummy-123",
            "date": "2026-04-01",
            "time": "10:00",
        }
        fm = FakeFlowManager()
        fm.state["patient_id"] = "dummy-123"
        await handle_create_appointment({"date": "2026-04-01", "time": "10:00"}, fm)
        assert fm.state["appointment"]["appointment_id"] == "appt-456"
        assert fm.state["appointment"]["date"] == "2026-04-01"

    @pytest.mark.asyncio
    @patch("app.scheduling.handlers.create_appointment_api", new_callable=AsyncMock)
    async def test_appointment_failed_stays_on_same_node(self, mock_create):
        mock_create.return_value = None
        fm = FakeFlowManager()
        fm.state["patient_id"] = "dummy-123"
        result_msg, next_node = await handle_create_appointment(
            {"date": "2026-04-01", "time": "10:00"}, fm
        )
        assert "sorry" in result_msg.lower()
        assert next_node is None
