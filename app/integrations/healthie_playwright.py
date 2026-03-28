"""Healthie Playwright client with login, session persistence, and browser lifecycle management."""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger
from playwright.async_api import Page, async_playwright

BASE_URL = "https://securestaging.gethealthie.com"
AUTH_DIR = Path(__file__).resolve().parents[2] / "auth"
STATE_FILE = AUTH_DIR / "healthie_state.json"


class HealthiePlaywrightClient:
    """Manages a Playwright browser session authenticated against Healthie."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._context = None
        self._page: Page | None = None
        self.patient_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ensure_browser(self) -> Page:
        """Return an authenticated page, restoring session or logging in as needed."""
        if self._page is not None:
            logger.info("Using existing Healthie session")
            return self._page

        # Try restoring a saved session first
        page = await self._try_restore_session()
        if page is not None:
            self._page = page
            return self._page

        # Fall back to a fresh login
        logger.info("No valid saved session — performing fresh login")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._context = await self._browser.new_context()
        self._page = await self._login(self._context)
        return self._page

    async def close(self) -> None:
        """Clean up browser and Playwright instances."""
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _login(self, context) -> Page:
        """Execute the full multi-step Healthie login flow and save session state."""
        email = os.environ.get("HEALTHIE_EMAIL")
        password = os.environ.get("HEALTHIE_PASSWORD")

        if not email or not password:
            raise ValueError(
                "HEALTHIE_EMAIL and HEALTHIE_PASSWORD must be set in environment variables"
            )

        page = await context.new_page()
        logger.info("Navigating to Healthie sign-in page...")
        await page.goto(f"{BASE_URL}/users/sign_in", wait_until="domcontentloaded")

        # Step 1 — enter email / identifier
        identifier_input = page.locator('input[name="identifier"]')
        await identifier_input.wait_for(state="visible", timeout=30000)
        await identifier_input.fill(email)

        submit_button = page.locator('[data-test-id="submit-btn"]')
        await submit_button.wait_for(state="visible", timeout=30000)
        await submit_button.click()

        # Step 2 — enter password
        password_input = page.locator('input[name="password"]')
        await password_input.wait_for(state="visible", timeout=30000)
        await password_input.fill(password)

        log_in_button = page.locator('button:has-text("Log In")')
        await log_in_button.wait_for(state="visible", timeout=30000)
        await log_in_button.click()

        # Step 3 — handle passkey / MFA prompt ("Continue to app")
        try:
            continue_button = page.locator('button:has-text("Continue to app")')
            await continue_button.wait_for(state="visible", timeout=10000)
            await continue_button.click()
            logger.info("Dismissed passkey prompt")
        except Exception:
            logger.debug("No passkey prompt detected — continuing")

        # Step 4 — wait for navigation away from login pages
        await page.wait_for_url(
            lambda url: "sign_in" not in url and "/account/login" not in url,
            timeout=30000,
        )

        # Persist session state
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(STATE_FILE))
        logger.info(f"Session state saved to {STATE_FILE}")

        logger.info("Successfully logged into Healthie")
        return page

    async def _try_restore_session(self) -> Page | None:
        """Attempt to restore a session from saved storage state."""
        if not STATE_FILE.exists():
            logger.debug("No saved session state file found")
            return None

        logger.info("Attempting to restore saved Healthie session...")
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                storage_state=str(STATE_FILE)
            )
            page = await self._context.new_page()
            await page.goto(BASE_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            if "sign_in" in page.url or "/account/login" in page.url:
                logger.warning("Saved session expired — will perform fresh login")
                await self.close()
                return None

            logger.info("Successfully restored Healthie session from saved state")
            return page
        except Exception as exc:
            logger.warning(f"Failed to restore session: {exc}")
            await self.close()
            return None


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_client: HealthiePlaywrightClient | None = None


async def get_client() -> HealthiePlaywrightClient:
    """Return the module-level singleton client, creating it if needed."""
    global _client
    if _client is None:
        _client = HealthiePlaywrightClient()
    return _client
