"""Handler functions for the scheduling conversation flow.

Each handler is called when the LLM invokes a tool. Handlers call
tools from the tools layer and return (message, next_node) tuples.
"""

from pipecat_flows import FlowArgs, FlowManager

from app.shared.tools import find_patient, create_appointment


async def handle_collect_name(args: FlowArgs, flow_manager: FlowManager):
    """Handle the collect_name tool call. Stores name and transitions to DOB node."""
    from .nodes import create_collect_dob_node

    name = args["name"]
    flow_manager.state["patient_name"] = name

    return (
        f"Got it, {name}.",
        create_collect_dob_node(),
    )


async def handle_find_patient(args: FlowArgs, flow_manager: FlowManager):
    """Handle the find_patient tool call. Transitions to appointment or not-found node."""
    from .nodes import create_appointment_node, create_patient_not_found_node

    name = flow_manager.state["patient_name"]
    date_of_birth = args["date_of_birth"]

    result = await find_patient(name, date_of_birth)

    if result:
        flow_manager.state["patient_id"] = result["patient_id"]
        flow_manager.state["patient_name"] = result["name"]
        return (
            f"Patient found: {result['name']}.",
            create_appointment_node(),
        )
    else:
        return (
            "Patient not found with that name and date of birth.",
            create_patient_not_found_node(),
        )


async def handle_create_appointment(args: FlowArgs, flow_manager: FlowManager):
    """Handle the create_appointment tool call. Transitions to confirmation node."""
    from .nodes import create_confirmation_node

    patient_id = flow_manager.state["patient_id"]
    date = args["date"]
    time = args["time"]

    result = await create_appointment(patient_id, date, time)

    if result:
        flow_manager.state["appointment"] = result
        return (
            f"Appointment created for {date} at {time}.",
            create_confirmation_node(),
        )
    else:
        return (
            "Sorry, there was an issue creating the appointment. Please try a different date or time.",
            None,  # Stay on appointment node to retry
        )
