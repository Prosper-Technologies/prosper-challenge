"""Tests for scheduling flow node definitions."""

from app.scheduling.nodes import (
    create_appointment_node,
    create_collect_dob_node,
    create_confirmation_node,
    create_greeting_node,
    create_patient_not_found_node,
)
from app.scheduling.prompts import ROLE_MESSAGES


class TestNodeDefinitions:
    def test_greeting_node_has_role_and_task_messages(self):
        node = create_greeting_node()
        assert node["role_messages"] == ROLE_MESSAGES
        assert len(node["task_messages"]) == 1
        assert node["task_messages"][0]["role"] == "system"

    def test_greeting_node_has_collect_name_function(self):
        node = create_greeting_node()
        assert len(node["functions"]) == 1
        assert node["functions"][0].name == "collect_name"

    def test_collect_dob_node_has_find_patient_function(self):
        node = create_collect_dob_node()
        assert len(node["functions"]) == 1
        assert node["functions"][0].name == "find_patient"

    def test_collect_dob_node_has_no_role_messages(self):
        node = create_collect_dob_node()
        assert "role_messages" not in node

    def test_appointment_node_has_create_appointment_function(self):
        node = create_appointment_node()
        assert len(node["functions"]) == 1
        assert node["functions"][0].name == "create_appointment"

    def test_confirmation_node_has_no_functions(self):
        node = create_confirmation_node()
        assert node["functions"] == []

    def test_confirmation_node_has_end_conversation_post_action(self):
        node = create_confirmation_node()
        assert node["post_actions"] == [{"type": "end_conversation"}]

    def test_patient_not_found_node_has_collect_name_function(self):
        node = create_patient_not_found_node()
        assert len(node["functions"]) == 1
        assert node["functions"][0].name == "collect_name"
