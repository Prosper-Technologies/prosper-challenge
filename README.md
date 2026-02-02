# Prosper Challenge

This is a template repository for an AI voice agent that is meant to schedule appointments for a health clinic. The foundations are already set:

- Pipecat is configured with sensible defaults and the bot already introduces itself when initialized
- Playwright is set up so that you can programmatically log into Healthie, the EHR we'll use for this challenge

However, for the agent to be fully functional you'll need to implement the following missig pieces:

- Expand the agent's configuration so that it asks for the patient's name and date of birth
- Once it finds the patient it should ask for the desired date and time of the appointment and create it
- Implement the find patient and create appointment functionalities using Playwright

## Setup

To get started, fork this repository so that you can start commiting and pushing changes to your own copy.

### Prerequisites

#### Environment

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager installed

#### Healthie Account

You'll need a Healthie account for testing, you can create one [here](https://secure.gethealthie.com/users/sign_up/provider).

### Installation

1. Clone this repository

   ```bash
   git clone <repository-url>
   cd prosper-challenge
   ```

2. Copy the API keys we've shared with you, as well as your Healthie credentials:

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

### Running the Bot

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

## Expectations & Deliverable

We encourage you to use AI tools (Claude Code, Cursor, etc.) to help you with this challenge. We don't mind if you fully "vibe code" the solution, that means you probably have good prompting skills. What we do care about is whether you understand the decisions and trade-offs behind your solutuion, as well as the opportunities to improve it in the future. This is what we'll evaluate during our review session.

Once you are done, please share share with us the link to your fork so that we can get familiar with it before our chat.
