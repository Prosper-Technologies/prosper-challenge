import unittest
from datetime import datetime, timedelta

import healthie


class HealthieIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        healthie._browser = None
        healthie._page = None

    async def asyncTearDown(self):
        if healthie._page is not None:
            await healthie._page.close()
            healthie._page = None

        if healthie._browser is not None:
            await healthie._browser.close()
            healthie._browser = None

    async def test_login_to_healthie_returns_authenticated_page(self):
        page = await healthie.login_to_healthie()

        self.assertIsNotNone(page)
        self.assertTrue(page.url.startswith("https://secure.gethealthie.com/"))
        self.assertNotIn("/account/login", page.url)

    async def test_find_patient_finds_known_patient(self):
        patient = await healthie.find_patient("Marc Vernet", "31/05/2019")

        self.assertIsNotNone(patient)
        self.assertEqual(patient["patient_id"], "15502020")
        self.assertEqual(patient["name"], "Marc Vernet")
        self.assertIn(patient["date_of_birth"], {"5/31/2019", "05/31/2019"})

    async def test_create_appointment_books_future_slot(self):
        future = datetime.now() + timedelta(days=30, hours=2)
        date = future.strftime("%B %d, %Y")
        time = future.strftime("%I:00 %p").lstrip("0")

        appointment = await healthie.create_appointment("15502020", date, time)

        self.assertIsNotNone(appointment)
        self.assertEqual(appointment["patient_id"], "15502020")
        self.assertTrue(appointment["appointment_id"].isdigit())
        self.assertEqual(appointment["time"], time)
        self.assertEqual(appointment["appointment_type"], healthie.DEFAULT_APPOINTMENT_TYPE)
        self.assertEqual(appointment["contact_type"], healthie.DEFAULT_VIDEO_CALL_METHOD)


if __name__ == "__main__":
    unittest.main()
