# Prosper Challenge

You've been given a template repository for an AI voice agent that is meant to schedule appointments for a clinic. The foundations are already set:

- Pipecat is configured with sensible defaults and the bot already introduces itself when initialized
- Playwright is set up so that you can programmatically log into Healthie, the EHR we'll use for this challenge

In order for the voice agent to be fully functional you'll need to implement the following missing parts:

- Expand the agent's configuration so that it asks for the patient's name and date of birth
- Once it finds the patient it should ask for the desired date and time of the appointment and create it
- Implement the find patient and create appointment functionalities using Playwright

## Setup

### Prerequisites

#### Environment

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager installed

#### AI Service API keys

You'll need API keys from the following services:

- [ElevenLabs](https://elevenlabs.io/app/sign-up) for Speech-to-Text and Text-to-Speech
- [OpenAI](https://auth.openai.com/create-account) for LLM inference

#### Healthie Account

You'll need a Healthie account for testing, you can create one [here](https://secure.gethealthie.com/users/sign_up/provider).

### Installation

1. Clone this repository

   ```bash
   git clone <repository-url>
   cd prosper-challenge
   ```

2. Configure your API keys and Healthie credentials:

   Create a `.env` file:

   ```bash
   cp env.example .env
   ```

   Then, add your API keys and credentials:

   ```ini
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   OPENAI_API_KEY=your_openai_api_key
   HEALTHIE_EMAIL=your_healthie_email
   HEALTHIE_PASSWORD=your_healthie_password
   ```

3. Set up a virtual environment and install dependencies

   ```bash
   uv sync
   ```

4. Install Playwright browsers

   ```bash
   uv run playwright install chromium
   ```

## Running the Bot

```bash
uv run bot.py
```

**Open http://localhost:7860 in your browser** and click `Connect` to start talking to your bot.

> 💡 First run note: The initial startup may take ~20 seconds as Pipecat downloads required models and imports.

## What You Need to Implement

1. **Agent Configuration**: Modify the agent's behavior to ask for patient name and date of birth, then appointment date and time. (This guide)[https://docs.pipecat.ai/guides/learn/function-calling] on function calling from Pipecat is probably a good start.

2. **Find Patient Function**: Implement `healthie.find_patient(name, date_of_birth)` in `healthie.py` to search for patients in Healthie using Playwright.

3. **Create Appointment Function**: Implement `healthie.create_appointment(patient_id, date, time)` in `healthie.py` to create appointments in Healthie using Playwright.

4. **Integration**: Connect the voice agent to these functions so it can actually schedule appointments during conversations.

## Testing

You can test your implementation by:

1. Running the bot and having a conversation where you provide:
   - A patient name and date of birth
   - A desired appointment date and time

2. Verifying in Healthie that the appointment was created successfully

3. Testing error cases (e.g., patient not found, invalid date/time, unavailable time slot)

## Troubleshooting

- **Browser permissions**: Allow microphone access when prompted
- **Connection issues**: Try a different browser or check VPN/firewall settings
- **Audio issues**: Verify microphone and speakers are working and not muted
- **Playwright issues**: Make sure you've run `uv run playwright install chromium`
- **Healthie login issues**: Verify your credentials are correct in the `.env` file
