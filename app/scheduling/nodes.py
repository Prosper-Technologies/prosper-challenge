"""Node definitions for the scheduling conversation flow.

Each function returns a NodeConfig dict that pipecat-flows uses
to configure a conversation state.
"""

from pipecat_flows import FlowsFunctionSchema, NodeConfig

from .prompts import (
    APPOINTMENT_TASK,
    COLLECT_DOB_TASK,
    CONFIRMATION_TASK,
    GREETING_TASK,
    PATIENT_NOT_FOUND_TASK,
    ROLE_MESSAGES,
)
from .handlers import handle_collect_name, handle_create_appointment, handle_find_patient


FIND_PATIENT_SCHEMA = {
    "date_of_birth": {
        "type": "string",
        "description": "The patient's date of birth in YYYY-MM-DD format",
    },
}


def create_greeting_node() -> NodeConfig:
    """Initial node: greet patient and ask for their name."""
    return {
        "role_messages": ROLE_MESSAGES,
        "task_messages": [{"role": "system", "content": GREETING_TASK}],
        "functions": [
            FlowsFunctionSchema(
                name="collect_name",
                description="Record the patient's full name",
                properties={
                    "name": {
                        "type": "string",
                        "description": "The patient's full name",
                    },
                },
                required=["name"],
                handler=handle_collect_name,
            )
        ],
    }


def create_collect_dob_node() -> NodeConfig:
    """Second node: ask for date of birth, then look up the patient."""
    return {
        "task_messages": [{"role": "system", "content": COLLECT_DOB_TASK}],
        "functions": [
            FlowsFunctionSchema(
                name="find_patient",
                description="Look up a patient by name and date of birth",
                properties=FIND_PATIENT_SCHEMA,
                required=["date_of_birth"],
                handler=handle_find_patient,
            )
        ],
    }


def create_appointment_node() -> NodeConfig:
    """Second node: ask for appointment date and time."""
    return {
        "task_messages": [{"role": "system", "content": APPOINTMENT_TASK}],
        "functions": [
            FlowsFunctionSchema(
                name="create_appointment",
                description="Create an appointment for the patient",
                properties={
                    "date": {
                        "type": "string",
                        "description": "The appointment date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "The appointment time in HH:MM format (24-hour)",
                    },
                },
                required=["date", "time"],
                handler=handle_create_appointment,
            )
        ],
    }


def create_confirmation_node() -> NodeConfig:
    """Final node: confirm booking and say goodbye."""
    return {
        "task_messages": [{"role": "system", "content": CONFIRMATION_TASK}],
        "functions": [],
        "post_actions": [{"type": "end_conversation"}],
    }


def create_patient_not_found_node() -> NodeConfig:
    """Error node: patient not found, offer to retry from name collection."""
    return {
        "task_messages": [{"role": "system", "content": PATIENT_NOT_FOUND_TASK}],
        "functions": [
            FlowsFunctionSchema(
                name="collect_name",
                description="Record the patient's full name",
                properties={
                    "name": {
                        "type": "string",
                        "description": "The patient's full name",
                    },
                },
                required=["name"],
                handler=handle_collect_name,
            )
        ],
    }
