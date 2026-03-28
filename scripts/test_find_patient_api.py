"""Quick smoke test for find_patient_api."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from app.shared.tools.find_patient import find_patient_api  # noqa: E402


async def main():
    result = await find_patient_api("Jeff Mills", "1990-01-01")
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
