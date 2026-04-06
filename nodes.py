

from pipecat_flows import FlowsFunctionSchema, NodeConfig
from pipecat_flows import FlowArgs, FlowResult

from dateutil import parser as dateutil_parser

from healthie import find_patient, create_appointment

# Node configurations
def create_initial_node() -> NodeConfig:
    """Create initial node for party size collection."""
    return {
        "name": "initial",
        "role_message": "You are a digital assistant from the Prosper Health clinic. Be casual and friendly. This is a voice conversation, so avoid special characters and emojis.",
        "task_messages": [
            {
                "role": "user",
                "content": "Say hello and briefly introduce yourself as a digital assistant from the Prosper Health clinic. Ask for the patient's name and date of birth. This is your only job for now; if the customer asks for something else, politely remind them you can't do it.",
            }
        ],
        "functions": [collect_patient_info_schema],
        "respond_immediately": True,
    }

class PatientInfoResult(FlowResult):
    name: str
    date_of_birth: str

async def collect_patient_info(args: FlowArgs) -> tuple[PatientInfoResult, NodeConfig]:
    """Collect the patient's name and date of birth, then look them up in Healthie."""
    name = args["name"]
    date_of_birth = args["date_of_birth"]
    patient = await find_patient(name, date_of_birth)
    patient_id = patient["patient_id"]
    result = PatientInfoResult(name=name, date_of_birth=date_of_birth)
    return result, create_schedule_node(patient_id)

collect_patient_info_schema = FlowsFunctionSchema(
    name="collect_patient_info",
    description="Collect the patient's name and date of birth",
    properties={
        "name": {"type": "string"},
        "date_of_birth": {"type": "string"},
    },
    required=["name", "date_of_birth"],
    handler=collect_patient_info,
)



def create_schedule_node(patient_id: str) -> NodeConfig:
    """Create the scheduling node that collects a date and time for the appointment."""

    async def schedule_appointment(args: FlowArgs) -> tuple[None, NodeConfig]:
        parsed_dt = dateutil_parser.parse(f"{args['date']} {args['time']}")
        result = await create_appointment(
            patient_id,
            parsed_dt.date(),
            parsed_dt.time(),
        )
        return None, create_end_node(
            appointment_date=result["date"],
            appointment_time=result["time"],
        )

    schedule_appointment_schema = FlowsFunctionSchema(
        name="schedule_appointment",
        description="Schedule an appointment once the patient provides a date and time",
        properties={
            "date": {"type": "string", "description": "Appointment date, e.g. 'April 10, 2026'"},
            "time": {"type": "string", "description": "Appointment time, e.g. '2:30 PM'"},
        },
        required=["date", "time"],
        handler=schedule_appointment,
    )

    return {
        "name": "schedule",
        "task_messages": [
            {
                "role": "user",
                "content": "Great news — the patient's record was found. Now ask them what date and time they'd like to schedule an appointment. Once they provide both, call schedule_appointment.",
            }
        ],
        "functions": [schedule_appointment_schema],
    }


def create_end_node(appointment_date: str, appointment_time: str) -> NodeConfig:
    """Create the final node that confirms the booking and ends."""
    return {
        "name": "end_node",
        "task_messages": [
            {
                "role": "user",
                "content": f"Tell the patient their appointment has been booked for {appointment_date} at {appointment_time}. Thank them and end the conversation.",
            }
        ],
        "post_actions": [{"type": "end_conversation"}],
    }
