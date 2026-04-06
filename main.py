import asyncio
from datetime import date, time
from dotenv import load_dotenv
load_dotenv(override=True)
from healthie import login_to_healthie, find_patient, create_appointment
from time import sleep

async def main():
    # patient_info_result = await find_patient("Eric Smith", "April 14, 2026")
    # print(f'Patient found: {patient_info_result}')

    await create_appointment("14794809", date(2026, 4, 25), time(15, 0))
    sleep(100000)

asyncio.run(main())