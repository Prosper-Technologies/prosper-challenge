"""Tests for scheduling flow handler functions."""

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
        assert next_node["functions"][0].name == "find_patient"


class TestHandleFindPatient:
    @pytest.mark.asyncio
    async def test_patient_found_transitions_to_appointment_node(self):
        fm = FakeFlowManager()
        fm.state["patient_name"] = "Jane Doe"
        result_msg, next_node = await handle_find_patient(
            {"date_of_birth": "1990-01-15"}, fm
        )
        assert "Jane Doe" in result_msg
        assert next_node is not None
        assert len(next_node["functions"]) == 1
        assert next_node["functions"][0].name == "create_appointment"

    @pytest.mark.asyncio
    async def test_patient_found_updates_state(self):
        fm = FakeFlowManager()
        fm.state["patient_name"] = "Jane Doe"
        await handle_find_patient(
            {"date_of_birth": "1990-01-15"}, fm
        )
        assert fm.state["patient_id"] == "dummy-123"
        assert fm.state["patient_name"] == "Jane Doe"

    @pytest.mark.asyncio
    async def test_patient_not_found_transitions_to_not_found_node(self):
        import app.scheduling.handlers as handlers_module
        original = handlers_module.find_patient

        async def fake_not_found(name, dob):
            return None

        handlers_module.find_patient = fake_not_found
        try:
            fm = FakeFlowManager()
            fm.state["patient_name"] = "Nobody"
            result_msg, next_node = await handle_find_patient(
                {"date_of_birth": "2000-01-01"}, fm
            )
            assert "not found" in result_msg.lower()
            assert next_node is not None
            assert next_node["functions"][0].name == "collect_name"
        finally:
            handlers_module.find_patient = original


class TestHandleCreateAppointment:
    @pytest.mark.asyncio
    async def test_appointment_created_transitions_to_confirmation(self):
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
    async def test_appointment_created_updates_state(self):
        fm = FakeFlowManager()
        fm.state["patient_id"] = "dummy-123"
        await handle_create_appointment(
            {"date": "2026-04-01", "time": "10:00"}, fm
        )
        assert fm.state["appointment"]["appointment_id"] == "appt-456"
        assert fm.state["appointment"]["date"] == "2026-04-01"

    @pytest.mark.asyncio
    async def test_appointment_failed_stays_on_same_node(self):
        # Must patch the name in handlers module, not the source module,
        # because handlers.py binds create_appointment via `from ... import`.
        import app.scheduling.handlers as handlers_module
        original = handlers_module.create_appointment

        async def fake_fail(patient_id, date, time):
            return None

        handlers_module.create_appointment = fake_fail
        try:
            fm = FakeFlowManager()
            fm.state["patient_id"] = "dummy-123"
            result_msg, next_node = await handle_create_appointment(
                {"date": "2026-04-01", "time": "10:00"}, fm
            )
            assert "sorry" in result_msg.lower()
            assert next_node is None
        finally:
            handlers_module.create_appointment = original
