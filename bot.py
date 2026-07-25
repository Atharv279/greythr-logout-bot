import asyncio
import os
import random
import re
import json
from datetime import datetime
from playwright.async_api import async_playwright

GREYTHR_URL = os.environ.get("GREYTHR_URL", "https://nio-stars.greythr.com/")

def is_working_day(dt):
    """
    Checks if a given date is a working day.
    Rules:
    - Sunday: Holiday
    - 1st Saturday: Holiday
    - 3rd Saturday: Holiday
    - 2nd, 4th, 5th Saturday: Working
    - Monday to Friday: Working
    """
    weekday = dt.weekday()
    day = dt.day

    if weekday == 6:  # Sunday
        return False
    
    if weekday == 5:  # Saturday
        if 1 <= day <= 7 or 15 <= day <= 21:
            return False
        return True
    
    return True

async def find_button(page, text_type):
    """Find Sign Out / Sign In button with multiple selector strategies."""
    is_out = "out" in text_type.lower()
    
    if is_out:
        patterns = [
            re.compile(r"^\s*Sign[-\s]?Out\s*$", re.IGNORECASE),
            re.compile(r"^\s*Swipe[-\s]?Out\s*$", re.IGNORECASE),
            re.compile(r"^\s*Check[-\s]?Out\s*$", re.IGNORECASE),
            re.compile(r"Sign[-\s]?Out", re.IGNORECASE),
            re.compile(r"Swipe[-\s]?Out", re.IGNORECASE),
        ]
        sel_regex = r"(Sign|Swipe|Check)[-\s]?Out"
    else:
        patterns = [
            re.compile(r"^\s*Sign[-\s]?In\s*$", re.IGNORECASE),
            re.compile(r"^\s*Swipe[-\s]?In\s*$", re.IGNORECASE),
            re.compile(r"^\s*Check[-\s]?In\s*$", re.IGNORECASE),
            re.compile(r"Sign[-\s]?In", re.IGNORECASE),
            re.compile(r"Swipe[-\s]?In", re.IGNORECASE),
        ]
        sel_regex = r"(Sign|Swipe|Check)[-\s]?In"

    for pat in patterns:
        btn = page.get_by_role("button", name=pat)
        if await btn.count() > 0:
            return btn

    selectors = [
        'gt-button[shade="primary"] button',
        'gt-button button',
        'button.btn-swipe',
        'button',
        'a.btn'
    ]
    for sel in selectors:
        loc = page.locator(sel).filter(has_text=re.compile(sel_regex, re.IGNORECASE))
        if await loc.count() > 0:
            return loc

    return None

async def handle_confirmation_modal(page):
    """Click confirm/yes/submit if a sign-in or sign-out confirmation popup appears."""
    await asyncio.sleep(2)
    confirm_btn = page.locator("button, gt-button").filter(
        has_text=re.compile(r"^\s*(Confirm|Yes|Submit|Save|Ok)\s*$", re.IGNORECASE)
    )
    if await confirm_btn.count() > 0 and await confirm_btn.first.is_visible():
        print("Confirmation modal detected. Clicking confirm...")
        await confirm_btn.first.click()
        await asyncio.sleep(2)

async def logout(page):
    try:
        logout_button = page.locator('a:has-text("Logout"), button:has-text("Logout"), .icon-logout')
        if await logout_button.count() > 0:
            await logout_button.first.click()
        else:
            profile = page.locator('.profile-image, .user-name, gt-profile-image, .avatar')
            if await profile.count() > 0:
                await profile.first.click()
                await page.locator('a:has-text("Logout"), button:has-text("Logout")').first.click()
        await asyncio.sleep(3)
    except Exception as e:
        print(f"Logout warning: {e}")
        await page.context.clear_cookies()

async def process_account(page, username, password):
    try:
        print(f"Starting process for {username}...")
        await page.goto(GREYTHR_URL, wait_until="domcontentloaded")
        print(f"Navigated to {GREYTHR_URL}. Current URL: {page.url}")

        if "/portal/" in page.url or "/ess/" in page.url:
            print("Already logged in, logging out first...")
            await logout(page)
            await page.goto(GREYTHR_URL, wait_until="domcontentloaded")

        print("Waiting for login input fields...")
        await page.wait_for_selector('input[name="username"], input#username', timeout=20000)
        await page.fill('input[name="username"], input#username', username)
        await page.fill('input[name="password"], input#password', password)
        print("Fields filled, submitting login...")
        await page.click('button[type="submit"]')

        print("Waiting for dashboard page to load...")
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        await asyncio.sleep(5)
        print(f"Dashboard loaded. Current URL: {page.url}")

        print("Checking for Sign Out / Swipe Out button...")
        sign_out_btn = await find_button(page, "Sign Out")

        if sign_out_btn:
            print("Found Sign Out button. Clicking it to check out...")
            await sign_out_btn.first.click()
            print("Successfully clicked Sign Out.")
            await handle_confirmation_modal(page)
        else:
            print("Sign Out button not found. Checking for Sign In button...")
            sign_in_btn = await find_button(page, "Sign In")
            if sign_in_btn:
                print("Found Sign In button. User forgot to check-in. Clicking Sign In first...")
                await sign_in_btn.first.click()
                await handle_confirmation_modal(page)
                print("Successfully clicked Sign In. Waiting for page to update...")
                await asyncio.sleep(7)

                print("Checking for Sign Out button after checking in...")
                sign_out_btn = await find_button(page, "Sign Out")
                if not sign_out_btn:
                    print("Sign Out button not visible yet. Reloading dashboard...")
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(5)
                    sign_out_btn = await find_button(page, "Sign Out")

                if sign_out_btn:
                    print("Found Sign Out button after reload/update. Clicking it to check out...")
                    await sign_out_btn.first.click()
                    print("Successfully clicked Sign Out.")
                    await handle_confirmation_modal(page)
                else:
                    print("Sign Out button STILL NOT FOUND after clicking Sign In.")
            else:
                print("Neither Sign Out nor Sign In buttons were found. User might be on a different page or button selectors changed.")

        await logout(page)
        return True
    except Exception as e:
        print(f"Error processing {username}: {str(e)}")
        print(f"Failed at URL: {page.url}")
        return False

async def run_bot():
    now = datetime.now()
    if not is_working_day(now):
        print(f"Today ({now.strftime('%Y-%m-%d, %A')}) is a holiday. Skipping...")
        return

    if os.environ.get("RANDOM_DELAY", "false").lower() == "true":
        delay = random.randint(0, 240)
        print(f"Waiting for {delay} seconds...")
        await asyncio.sleep(delay)

    accounts_json = os.environ.get("GREYTHR_ACCOUNTS")
    accounts = json.loads(accounts_json) if accounts_json else []
    if not accounts:
        u, p = os.environ.get("GREYTHR_USERNAME"), os.environ.get("GREYTHR_PASSWORD")
        if u and p: accounts = [{"user": u, "pass": p}]

    if not accounts:
        print("No accounts configured.")
        return

    accounts = accounts[:1]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--no-first-run",
                "--no-zygote",
                "--single-process"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        for acc in accounts:
            await process_account(page, acc["user"], acc["pass"])
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
