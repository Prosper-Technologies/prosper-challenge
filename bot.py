#
# Copyright (c) 2024-2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Pipecat Quickstart Example.

The example runs a simple voice AI bot that you can connect to using your
browser and speak with it. You can also deploy this bot to Pipecat Cloud.

Required AI services:
- ElevenLabs (Speech-to-Text and Text-to-Speech)
- OpenAI (LLM)

Run the bot using::

    uv run bot.py
"""

import os
from dataclasses import dataclass
from typing import Awaitable, Callable

from dotenv import load_dotenv
from loguru import logger

print("🚀 Starting Pipecat bot...")
print("⏳ Loading models and imports (20 seconds, first run only)\n")

logger.info("Loading Local Smart Turn Analyzer V3...")
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3

logger.info("✅ Local Smart Turn Analyzer V3 loaded")
logger.info("Loading Silero VAD model...")
from pipecat.audio.vad.silero import SileroVADAnalyzer

logger.info("✅ Silero VAD model loaded")

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame

logger.info("Loading pipeline components...")
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.elevenlabs.stt import ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import (
    TurnAnalyzerUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from healthie import create_appointment, find_patient

logger.info("✅ All components loaded successfully!")

load_dotenv(override=True)


SCHEDULING_SYSTEM_PROMPT = """
You are the digital scheduling assistant for Prosper Health clinic.

Your job is to help callers schedule an appointment in this exact order:
1. Ask for the patient's full name.
2. Ask for the patient's date of birth.
3. Once you have both, call `lookup_patient_record`.
4. Only after the patient is found, ask for the desired appointment date.
5. Then ask for the desired appointment time.
6. Once you have both, call `book_appointment`.
7. Confirm the final outcome clearly.

Rules:
- Ask for only one missing piece of information at a time.
- Keep replies short, natural, and conversational for voice.
- Do not ask for appointment date or time before the patient has been found.
- Never ask the caller for a patient ID.
- Never say a booking is confirmed until `book_appointment` succeeds.
- If a tool reports failure, explain that simply and ask for the next corrective detail.
- If the caller gives multiple details at once, acknowledge them and continue with the next missing item.
- If the date of birth, appointment date, or appointment time sounds ambiguous, ask a brief clarifying question before using a tool.
- Begin the conversation by greeting the caller and asking for their full name.
""".strip()


@dataclass
class SchedulingSession:
    patient_name: str | None = None
    date_of_birth: str | None = None
    patient_id: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None

    def reset(self) -> None:
        self.patient_name = None
        self.date_of_birth = None
        self.patient_id = None
        self.appointment_date = None
        self.appointment_time = None

    def clear_patient(self) -> None:
        self.patient_id = None
        self.appointment_date = None
        self.appointment_time = None


def build_scheduling_tools() -> ToolsSchema:
    return ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="lookup_patient_record",
                description=(
                    "Find a patient in Healthie after you have collected the full name "
                    "and date of birth."
                ),
                properties={
                    "name": {
                        "type": "string",
                        "description": "The patient's full name.",
                    },
                    "date_of_birth": {
                        "type": "string",
                        "description": (
                            "The patient's date of birth as provided by the caller."
                        ),
                    },
                },
                required=["name", "date_of_birth"],
            ),
            FunctionSchema(
                name="book_appointment",
                description=(
                    "Book an appointment for the patient already found in the system."
                ),
                properties={
                    "date": {
                        "type": "string",
                        "description": "The requested appointment date.",
                    },
                    "time": {
                        "type": "string",
                        "description": "The requested appointment time.",
                    },
                },
                required=["date", "time"],
            ),
        ]
    )


def _normalize_tool_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


async def _handle_patient_lookup(
    params: FunctionCallParams,
    session: SchedulingSession,
) -> None:
    name = _normalize_tool_value(params.arguments.get("name"))
    date_of_birth = _normalize_tool_value(params.arguments.get("date_of_birth"))

    session.patient_name = name or None
    session.date_of_birth = date_of_birth or None
    session.clear_patient()

    if not name or not date_of_birth:
        await params.result_callback(
            {
                "status": "missing_required_fields",
                "message": "Both patient name and date of birth are required.",
            }
        )
        return

    try:
        patient = await find_patient(name=name, date_of_birth=date_of_birth)
    except Exception as exc:
        logger.exception("Patient lookup failed")
        await params.result_callback(
            {
                "status": "lookup_error",
                "message": f"Patient lookup failed: {exc}",
            }
        )
        return

    if not patient or not patient.get("patient_id"):
        await params.result_callback(
            {
                "status": "not_found",
                "message": "No matching patient record was found.",
                "name": name,
                "date_of_birth": date_of_birth,
            }
        )
        return

    session.patient_id = str(patient["patient_id"])

    await params.result_callback(
        {
            "status": "found",
            "message": "Patient record found.",
            "patient_id": session.patient_id,
            "name": patient.get("name", name),
            "date_of_birth": patient.get("date_of_birth", date_of_birth),
        }
    )


async def _handle_appointment_booking(
    params: FunctionCallParams,
    session: SchedulingSession,
) -> None:
    date = _normalize_tool_value(params.arguments.get("date"))
    time = _normalize_tool_value(params.arguments.get("time"))

    session.appointment_date = date or None
    session.appointment_time = time or None

    if not session.patient_id:
        await params.result_callback(
            {
                "status": "patient_not_selected",
                "message": "A patient must be found before booking an appointment.",
            }
        )
        return

    if not date or not time:
        await params.result_callback(
            {
                "status": "missing_required_fields",
                "message": "Both appointment date and time are required.",
            }
        )
        return

    try:
        appointment = await create_appointment(
            patient_id=session.patient_id,
            date=date,
            time=time,
        )
    except Exception as exc:
        logger.exception("Appointment booking failed")
        await params.result_callback(
            {
                "status": "booking_error",
                "message": f"Appointment booking failed: {exc}",
                "patient_id": session.patient_id,
                "date": date,
                "time": time,
            }
        )
        return

    if not appointment or not appointment.get("appointment_id"):
        await params.result_callback(
            {
                "status": "booking_failed",
                "message": "The appointment could not be created.",
                "patient_id": session.patient_id,
                "date": date,
                "time": time,
            }
        )
        return

    await params.result_callback(
        {
            "status": "booked",
            "message": "Appointment created successfully.",
            "appointment_id": str(appointment["appointment_id"]),
            "patient_id": session.patient_id,
            "date": appointment.get("date", date),
            "time": appointment.get("time", time),
            "appointment_type": appointment.get("appointment_type"),
            "contact_type": appointment.get("contact_type"),
            "timezone": appointment.get("timezone"),
        }
    )


def build_scheduling_function_handlers(
    session: SchedulingSession,
) -> dict[str, Callable[[FunctionCallParams], Awaitable[None]]]:
    return {
        "lookup_patient_record": lambda params: _handle_patient_lookup(params, session),
        "book_appointment": lambda params: _handle_appointment_booking(params, session),
    }


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info(f"Starting bot")

    session = SchedulingSession()
    elevenlabs_key = os.environ["ELEVENLABS_API_KEY"]
    stt = ElevenLabsRealtimeSTTService(api_key=elevenlabs_key)
    tts = ElevenLabsTTSService(
        api_key=elevenlabs_key,
        voice_id="SAz9YHcvj6GT2YYXdXww",
    )

    llm = OpenAILLMService(api_key=os.environ["OPENAI_API_KEY"])

    messages = [
        {
            "role": "system",
            "content": SCHEDULING_SYSTEM_PROMPT,
        },
    ]

    context = LLMContext(messages, tools=build_scheduling_tools(), tool_choice="auto")
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
            ),
        ),
    )

    rtvi = RTVIProcessor()

    for function_name, handler in build_scheduling_function_handlers(session).items():
        llm.register_function(function_name, handler)

    pipeline = Pipeline(
        [
            transport.input(),  # Transport user input
            rtvi,  # RTVI processor
            stt,
            user_aggregator,  # User responses
            llm,  # LLM
            tts,  # TTS
            transport.output(),  # Transport bot output
            assistant_aggregator,  # Assistant spoken responses
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        session.reset()
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)

    await runner.run(task)


async def bot(runner_args: RunnerArguments):
    """Main bot entry point for the bot starter."""

    transport_params = {
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
        ),
    }

    transport = await create_transport(runner_args, transport_params)

    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
