import unittest
from unittest.mock import AsyncMock, patch

import healthie


class FakeLocator:
    def __init__(self, *, text="", href=None, count=1):
        self.text = text
        self.href = href
        self.count_value = count
        self.nth_items = []
        self.selector_map = {}
        self.fill_calls = []
        self.click_calls = 0
        self.wait_for_calls = []
        self.press_calls = []
        self.type_calls = []
        self.check_calls = 0
        self.uncheck_calls = 0

    @property
    def first(self):
        return self

    def nth(self, index):
        return self.nth_items[index]

    def locator(self, selector):
        return self.selector_map[selector]

    async def wait_for(self, **kwargs):
        self.wait_for_calls.append(kwargs)

    async def fill(self, value):
        self.fill_calls.append(value)

    async def click(self, **_kwargs):
        self.click_calls += 1

    async def evaluate(self, _expression):
        self.click_calls += 1

    async def press(self, key):
        self.press_calls.append(key)

    async def type(self, value, delay=None):
        self.type_calls.append((value, delay))

    async def check(self):
        self.check_calls += 1

    async def uncheck(self):
        self.uncheck_calls += 1

    async def count(self):
        return self.count_value

    async def inner_text(self):
        return self.text

    async def get_attribute(self, name):
        if name == "href":
            return self.href
        return None


class FakePage:
    def __init__(self):
        self.url = "https://secure.gethealthie.com/"
        self.locators = {}
        self.goto = AsyncMock()
        self.wait_for_function = AsyncMock()
        self.wait_for_load_state = AsyncMock()
        self.wait_for_url = AsyncMock(side_effect=self._set_user_url)
        self.wait_for_timeout = AsyncMock()
        self.role_locators = {}
        self.expected_response = None
        self.expect_response_predicate = None
        self.expect_response_timeout = None

    def locator(self, selector):
        if selector not in self.locators:
            raise AssertionError(f"Unexpected selector: {selector}")
        return self.locators[selector]

    def get_by_role(self, role, name=None):
        key = (role, name)
        if key not in self.role_locators:
            raise AssertionError(f"Unexpected role lookup: {key}")
        return self.role_locators[key]

    async def _set_user_url(self, *_args, **_kwargs):
        self.url = "https://secure.gethealthie.com/users/15502020"

    def expect_response(self, predicate, timeout=None):
        self.expect_response_predicate = predicate
        self.expect_response_timeout = timeout
        return FakeExpectResponse(self.expected_response)


class FakeExpectResponse:
    def __init__(self, response):
        self.value = AsyncMock(return_value=response)()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeRequest:
    def __init__(self, *, method="POST", post_data=""):
        self.method = method
        self.post_data = post_data


class FakeResponse:
    def __init__(self, *, url, body, method="POST", post_data=""):
        self.url = url
        self._body = body
        self.request = FakeRequest(method=method, post_data=post_data)

    async def text(self):
        return self._body


class FakeBrowser:
    def __init__(self, page):
        self.page = page
        self.new_page = AsyncMock(return_value=page)


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.launch = AsyncMock(return_value=browser)


class FakePlaywright:
    def __init__(self, browser):
        self.chromium = FakeChromium(browser)


class LoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        healthie._browser = None
        healthie._page = None

    async def test_login_requires_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "HEALTHIE_EMAIL and HEALTHIE_PASSWORD"):
                await healthie.login_to_healthie()

    async def test_login_reuses_existing_page(self):
        existing_page = object()
        healthie._page = existing_page

        with patch.dict(
            "os.environ",
            {"HEALTHIE_EMAIL": "user@example.com", "HEALTHIE_PASSWORD": "secret"},
            clear=True,
        ):
            result = await healthie.login_to_healthie()

        self.assertIs(result, existing_page)

    async def test_login_submits_credentials_and_returns_page(self):
        page = FakePage()
        browser = FakeBrowser(page)
        playwright = FakePlaywright(browser)

        email_input = FakeLocator()
        password_input = FakeLocator()
        submit_button = FakeLocator()
        error_locator = FakeLocator(count=0)
        continue_button = FakeLocator()
        continue_button.wait_for = AsyncMock(side_effect=RuntimeError("no continue button"))

        page.locators = {
            '[data-test-id="input-identifier"], input[name="email"], input[type="email"]': email_input,
            '[data-test-id="submit-btn"], button:has-text("Log In")': submit_button,
            'input[type="password"], input[name="password"], [data-test-id="input-password"]': password_input,
            '[role="alert"], [data-test-id*="error"], .error': error_locator,
        }
        page.role_locators = {("button", "Continue to App"): continue_button}

        with patch.dict(
            "os.environ",
            {"HEALTHIE_EMAIL": "user@example.com", "HEALTHIE_PASSWORD": "secret"},
            clear=True,
        ):
            with patch("healthie.async_playwright") as async_playwright_mock:
                async_playwright_mock.return_value.start = AsyncMock(return_value=playwright)
                result = await healthie.login_to_healthie()

        self.assertIs(result, page)
        page.goto.assert_awaited_once_with(
            "https://secure.gethealthie.com/account/login", wait_until="domcontentloaded"
        )
        self.assertEqual(email_input.fill_calls, ["user@example.com"])
        self.assertEqual(password_input.fill_calls, ["secret"])
        self.assertEqual(submit_button.click_calls, 2)
        page.wait_for_function.assert_awaited_once()


class FindPatientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        healthie._browser = None
        healthie._page = None

    async def test_find_patient_returns_none_when_no_results_appear(self):
        page = FakePage()
        search_input = FakeLocator()
        results = FakeLocator()
        results.wait_for = AsyncMock(side_effect=RuntimeError("not found"))
        page.locators = {
            'input[data-testid="header-client-search-form"], input[placeholder="Search Clients..."], input[aria-label="Search Clients"]': search_input,
            '[data-testid="header-client-result"]': results,
        }

        with patch("healthie.login_to_healthie", AsyncMock(return_value=page)):
            result = await healthie.find_patient("Missing Patient", "31/05/2019")

        self.assertIsNone(result)
        self.assertEqual(search_input.fill_calls, [""])
        self.assertEqual(search_input.type_calls, [("Missing Patient", 30)])

    async def test_find_patient_returns_none_when_dob_does_not_match(self):
        page = FakePage()
        search_input = FakeLocator()
        name_link = FakeLocator(text="Marc Vernet (5/31/2019)", href="/users/15502020")
        result_item = FakeLocator(text="Marc Vernet (5/31/2019) View Profile Chart Note")
        result_item.selector_map = {'[data-testid="header-client-result-name"]': name_link}
        results = FakeLocator(count=1)
        results.nth_items = [result_item]

        page.locators = {
            'input[data-testid="header-client-search-form"], input[placeholder="Search Clients..."], input[aria-label="Search Clients"]': search_input,
            '[data-testid="header-client-result"]': results,
        }

        with patch("healthie.login_to_healthie", AsyncMock(return_value=page)):
            result = await healthie.find_patient("Marc Vernet", "01/01/2000")

        self.assertIsNone(result)
        self.assertEqual(name_link.click_calls, 0)

    async def test_find_patient_clicks_matching_result_and_returns_patient_data(self):
        page = FakePage()
        search_input = FakeLocator()
        wrong_name_link = FakeLocator(text="Other Patient (5/31/2019)", href="/users/999")
        wrong_result = FakeLocator(text="Other Patient (5/31/2019) View Profile")
        wrong_result.selector_map = {'[data-testid="header-client-result-name"]': wrong_name_link}

        matched_name_link = FakeLocator(text="Marc Vernet (5/31/2019)", href="/users/15502020")
        matched_result = FakeLocator(text="Marc Vernet (5/31/2019) View Profile Chart Note")
        matched_result.selector_map = {'[data-testid="header-client-result-name"]': matched_name_link}

        results = FakeLocator(count=2)
        results.nth_items = [wrong_result, matched_result]

        page.locators = {
            'input[data-testid="header-client-search-form"], input[placeholder="Search Clients..."], input[aria-label="Search Clients"]': search_input,
            '[data-testid="header-client-result"]': results,
        }

        with patch("healthie.login_to_healthie", AsyncMock(return_value=page)):
            result = await healthie.find_patient("Marc Vernet", "31/05/2019")

        self.assertEqual(search_input.fill_calls, [""])
        self.assertEqual(search_input.type_calls, [("Marc Vernet", 30)])
        self.assertEqual(matched_name_link.click_calls, 1)
        page.wait_for_load_state.assert_awaited_once_with("domcontentloaded")
        page.wait_for_url.assert_awaited_once()
        self.assertEqual(
            result,
            {
                "patient_id": "15502020",
                "name": "Marc Vernet",
                "date_of_birth": "5/31/2019",
                "profile_url": "/users/15502020",
            },
        )

    async def test_find_patient_matches_when_requested_dob_has_ordinal_suffix(self):
        page = FakePage()
        search_input = FakeLocator()
        matched_name_link = FakeLocator(text="Marc Vernet (5/31/2019)", href="/users/15502020")
        matched_result = FakeLocator(text="MV Marc Vernet (5/31/2019) View Profile Chart Note")
        matched_result.selector_map = {'[data-testid="header-client-result-name"]': matched_name_link}

        results = FakeLocator(count=1)
        results.nth_items = [matched_result]

        page.locators = {
            'input[data-testid="header-client-search-form"], input[placeholder="Search Clients..."], input[aria-label="Search Clients"]': search_input,
            '[data-testid="header-client-result"]': results,
        }

        with patch("healthie.login_to_healthie", AsyncMock(return_value=page)):
            result = await healthie.find_patient("Marc Vernet", "31st May 2019")

        self.assertEqual(matched_name_link.click_calls, 1)
        self.assertEqual(
            result,
            {
                "patient_id": "15502020",
                "name": "Marc Vernet",
                "date_of_birth": "5/31/2019",
                "profile_url": "/users/15502020",
            },
        )


class CreateAppointmentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        healthie._browser = None
        healthie._page = None

    async def test_create_appointment_fills_form_and_returns_graphql_data(self):
        page = FakePage()
        add_button = FakeLocator()
        appointment_type_input = FakeLocator()
        contact_type_input = FakeLocator()
        video_service_input = FakeLocator()
        timezone_input = FakeLocator()
        date_input = FakeLocator()
        time_input = FakeLocator()
        notes_input = FakeLocator()
        repeating_checkbox = FakeLocator()
        submit_button = FakeLocator()
        timezone_display = FakeLocator(text="Europe/Madrid")

        appointment_options = FakeLocator(count=2)
        appointment_options.nth_items = [
            FakeLocator(text="Initial Consultation - 60 Minutes"),
            FakeLocator(text="Follow-up Session - 45 Minutes"),
        ]
        contact_options = FakeLocator(count=2)
        contact_options.nth_items = [
            FakeLocator(text="Phone Call"),
            FakeLocator(text="Video Call"),
        ]
        video_options = FakeLocator(count=2)
        video_options.nth_items = [
            FakeLocator(text="Zoom"),
            FakeLocator(text="Healthie Video Call"),
        ]
        timezone_options = FakeLocator(count=2)
        timezone_options.nth_items = [
            FakeLocator(text="America/New_York"),
            FakeLocator(text="Europe/Madrid - Your Timezone"),
        ]

        page.locators = {
            '[data-testid="add-appointment-button"]': add_button,
            "#appointment_type_id": appointment_type_input,
            '[data-testid="appointment_type_id"], [data-input-for="appointment_type_id"]': appointment_type_input,
            "#contact_type": contact_type_input,
            '[data-testid="contact_type"], [data-input-for="contact_type"]': contact_type_input,
            "#video_service": video_service_input,
            '[data-testid="video_service"], [data-input-for="video_service"]': video_service_input,
            "#timezone": timezone_input,
            '[data-testid="timezone"], [data-input-for="timezone"]': timezone_input,
            ".timezone-select__single-value .selected-option-title": timezone_display,
            '[id^="react-select-"][id*="-option-"]': appointment_options,
            'input[name="date"]': date_input,
            'input[name="time"]': time_input,
            'textarea[name="notes"]': notes_input,
            'input[name="is_repeating"]': repeating_checkbox,
            'button[data-testid="primaryButton"]:has-text("Add appointment")': submit_button,
        }

        def locator_side_effect(selector):
            if selector == '[id^="react-select-"][id*="-option-"]':
                if appointment_type_input.click_calls > 0 and contact_type_input.click_calls == 0:
                    return appointment_options
                if contact_type_input.click_calls > 0 and video_service_input.click_calls == 0:
                    return contact_options
                if video_service_input.click_calls > 0 and timezone_input.click_calls == 0:
                    return video_options
                return timezone_options
            return page.locators[selector]

        page.locator = locator_side_effect
        page.expected_response = FakeResponse(
            url="https://app.gethealthie.com/graphql",
            method="POST",
            post_data="mutation createAppointment { createAppointment { appointment { id } } }",
            body=(
                '[{"data":{"createAppointment":{"appointment":{"id":"1519949000",'
                '"contact_type":"Healthie Video Call",'
                '"date":"2027-01-02 17:00:00 +0100",'
                '"end":"2027-01-02 18:00:00 +0100",'
                '"timezone_abbr":"CET",'
                '"appointment_type":{"name":"Initial Consultation"}}}}}]'
            ),
        )

        with patch("healthie.login_to_healthie", AsyncMock(return_value=page)):
            result = await healthie.create_appointment("15502020", "January 2, 2027", "5:00 PM")

        page.goto.assert_awaited_once_with(
            "https://secure.gethealthie.com/users/15502020", wait_until="domcontentloaded"
        )
        page.wait_for_load_state.assert_awaited_once_with("domcontentloaded")
        self.assertEqual(date_input.fill_calls, ["January 2, 2027"])
        self.assertEqual(time_input.fill_calls, ["5:00 PM"])
        self.assertEqual(time_input.press_calls, ["Enter"])
        self.assertEqual(notes_input.fill_calls, [healthie.DEFAULT_APPOINTMENT_NOTES])
        self.assertEqual(repeating_checkbox.uncheck_calls, 1)
        self.assertEqual(submit_button.click_calls, 1)
        self.assertEqual(page.expect_response_timeout, 30000)
        self.assertTrue(page.expect_response_predicate(page.expected_response))
        self.assertEqual(
            result,
            {
                "appointment_id": "1519949000",
                "patient_id": "15502020",
                "appointment_type": "Initial Consultation",
                "contact_type": "Healthie Video Call",
                "date": "2027-01-02 17:00:00 +0100",
                "time": "5:00 PM",
                "end": "2027-01-02 18:00:00 +0100",
                "timezone": "CET",
            },
        )

    async def test_create_appointment_raises_when_graphql_response_has_no_id(self):
        page = FakePage()
        add_button = FakeLocator()
        appointment_type_input = FakeLocator()
        contact_type_input = FakeLocator()
        video_service_input = FakeLocator()
        timezone_input = FakeLocator()
        date_input = FakeLocator()
        time_input = FakeLocator()
        notes_input = FakeLocator()
        repeating_checkbox = FakeLocator()
        submit_button = FakeLocator()
        timezone_display = FakeLocator(text="Europe/Madrid")

        appointment_options = FakeLocator(count=1)
        appointment_options.nth_items = [FakeLocator(text="Initial Consultation - 60 Minutes")]
        contact_options = FakeLocator(count=1)
        contact_options.nth_items = [FakeLocator(text="Video Call")]
        video_options = FakeLocator(count=1)
        video_options.nth_items = [FakeLocator(text="Healthie Video Call")]
        timezone_options = FakeLocator(count=1)
        timezone_options.nth_items = [FakeLocator(text="Europe/Madrid - Your Timezone")]

        page.locators = {
            '[data-testid="add-appointment-button"]': add_button,
            "#appointment_type_id": appointment_type_input,
            '[data-testid="appointment_type_id"], [data-input-for="appointment_type_id"]': appointment_type_input,
            "#contact_type": contact_type_input,
            '[data-testid="contact_type"], [data-input-for="contact_type"]': contact_type_input,
            "#video_service": video_service_input,
            '[data-testid="video_service"], [data-input-for="video_service"]': video_service_input,
            "#timezone": timezone_input,
            '[data-testid="timezone"], [data-input-for="timezone"]': timezone_input,
            ".timezone-select__single-value .selected-option-title": timezone_display,
            '[id^="react-select-"][id*="-option-"]': appointment_options,
            'input[name="date"]': date_input,
            'input[name="time"]': time_input,
            'textarea[name="notes"]': notes_input,
            'input[name="is_repeating"]': repeating_checkbox,
            'button[data-testid="primaryButton"]:has-text("Add appointment")': submit_button,
        }
        def locator_side_effect(selector):
            if selector == '[id^="react-select-"][id*="-option-"]':
                if appointment_type_input.click_calls > 0 and contact_type_input.click_calls == 0:
                    return appointment_options
                if contact_type_input.click_calls > 0 and video_service_input.click_calls == 0:
                    return contact_options
                if video_service_input.click_calls > 0 and timezone_input.click_calls == 0:
                    return video_options
                return timezone_options
            return page.locators[selector]

        page.locator = locator_side_effect
        page.expected_response = FakeResponse(
            url="https://app.gethealthie.com/graphql",
            method="POST",
            post_data="createAppointment",
            body='[{"data":{"createAppointment":{"appointment":{}}}}]',
        )

        with patch("healthie.login_to_healthie", AsyncMock(return_value=page)):
            with self.assertRaisesRegex(RuntimeError, "did not return an appointment id"):
                await healthie.create_appointment("15502020", "January 2, 2027", "5:00 PM")


if __name__ == "__main__":
    unittest.main()
