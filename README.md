# Pipecat Quickstart

Build and deploy your first voice AI bot in under 10 minutes. Develop locally, then scale to production on Pipecat Cloud.

## Local Development

### Prerequisites

#### Environment

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager installed

#### AI Service API keys

You'll need API keys from three services:

- [ElevenLabs](https://elevenlabs.io/app/sign-up) for Speech-to-Text and Text-to-Speech
- [OpenAI](https://auth.openai.com/create-account) for LLM inference

### Setup

Navigate to the quickstart directory and set up your environment.

1. Clone this repository

   ```bash
   git clone https://github.com/pipecat-ai/pipecat-quickstart.git
   cd pipecat-quickstart
   ```

2. Configure your API keys:

   Create a `.env` file:

   ```bash
   cp env.example .env
   ```

   Then, add your API keys:

   ```ini
   ELEVENLABS_API_KEY=your_deepgram_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

3. Set up a virtual environment and install dependencies

   ```bash
   uv sync
   ```

### Run your bot locally

```bash
uv run bot.py
```

**Open http://localhost:7860 in your browser** and click `Connect` to start talking to your bot.

> 💡 First run note: The initial startup may take ~20 seconds as Pipecat downloads required models and imports.

🎉 **Success!** Your bot is running locally. Now let's deploy it to production so others can use it.

---


### Troubleshooting

- **Browser permissions**: Allow microphone access when prompted
- **Connection issues**: Try a different browser or check VPN/firewall settings
- **Audio issues**: Verify microphone and speakers are working and not muted
