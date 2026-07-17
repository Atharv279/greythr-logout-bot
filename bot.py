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
    # weekday() returns 0 for Monday, 6 for Sunday
    weekday = dt.weekday()
    day = dt.day

    if weekday == 6:  # Sunday
        return False
    
    if weekday == 5:  # Saturday
        # 1st Saturday: day 1 to 7
        # 3rd Saturday: day 15 to 21
        if 1 <= day <= 7 or 15 <= day <= 21:
            return False
        return True
    
    # Monday to Friday
    return True

async def find_button(page, text_type):
    # Try role first
    button = page.get_by_role("button", name=re.compile(rf"^{text_type}$", re.IGNORECASE))
    count = await button.count()
    
    # Try tag-based selector with text
    if count == 0:
        button = page.locator('gt-button button').filter(has_text=re.compile(rf"{text_type.replace(' ', '[- ]')}", re.IGNORECASE))
        count = await button.count()
        
    # Try any button with text
    if count == 0:
        button = page.locator('button').filter(has_text=re.compile(rf"{text_type.replace(' ', '[- ]')}", re.IGNORECASE))
        count = await button.count()
        
    return button if count > 0 else None

async def process_account(page, username, password):
    try:
        print(f"Starting process for {username}...")
        await page.goto(GREYTHR_URL)
        print(f"Navigated to {GREYTHR_URL}. Current URL: {page.url}")

        if "/v3/portal/ess/home" in page.url:
            print("Already logged in, logging out first...")
            await logout(page)
            await page.goto(GREYTHR_URL)
            print(f"Navigated back to {GREYTHR_URL} after logout. Current URL: {page.url}")

        print("Waiting for login fields...")
        await page.wait_for_selector('input[name="username"]', timeout=20000)
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)
        print("Fields filled, submitting login...")
        await page.click('button[type="submit"]')

        print("Waiting for dashboard to load...")
        await page.wait_for_url("**/v3/portal/ess/home", timeout=30000)
        print(f"Dashboard loaded. Current URL: {page.url}")
        
        # Give it a moment for the Sign Out/In button to render
        await asyncio.sleep(5)

        # 1. Try to find the Sign Out button
        print("Checking for Sign Out button...")
        sign_out_btn = await find_button(page, "Sign Out")
        
        if sign_out_btn:
            print("Found Sign Out button. Clicking it to check out...")
            await sign_out_btn.first.click()
            print("Successfully clicked Sign Out.")
            await asyncio.sleep(3)
        else:
            print("Sign Out button not found. Checking for Sign In button...")
            sign_in_btn = await find_button(page, "Sign In")
            if sign_in_btn:
                print("Found Sign In button. User forgot to check-in. Clicking Sign In first...")
                await sign_in_btn.first.click()
                print("Successfully clicked Sign In. Waiting for page to update...")
                await asyncio.sleep(7) # Wait for page state/action to update
                
                # Check for Sign Out button again (either directly or via page reload)
                print("Checking for Sign Out button after checking in...")
                sign_out_btn = await find_button(page, "Sign Out")
                if not sign_out_btn:
                    print("Sign Out button not visible yet. Reloading dashboard...")
                    await page.reload()
                    await asyncio.sleep(5)
                    sign_out_btn = await find_button(page, "Sign Out")
                
                if sign_out_btn:
                    print("Found Sign Out button after reload/update. Clicking it to check out...")
                    await sign_out_btn.first.click()
                    print("Successfully clicked Sign Out.")
                    await asyncio.sleep(3)
                else:
                    print("Sign Out button STILL NOT FOUND after clicking Sign In.")
            else:
                print("Neither Sign Out nor Sign In buttons were found. User might be on a different page or button selectors changed.")
        
        await logout(page)
        return True
    except Exception as e:
        print(f"Error processing {username}: {str(e)}")
        # Print URL if it failed
        print(f"Failed at URL: {page.url}")
        return False

async def logout(page):
    try:
        logout_button = page.locator('a:has-text("Logout"), button:has-text("Logout"), .icon-logout')
        if await logout_button.count() > 0:
            await logout_button.first.click()
        else:
            profile = page.locator('.profile-image, .user-name, gt-profile-image')
            if await profile.count() > 0:
                await profile.first.click()
                await page.locator('a:has-text("Logout"), button:has-text("Logout")').first.click()
        await page.wait_for_url("**/auth/login**", timeout=10000)
    except:
        await page.context.clear_cookies()

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

    # Only process the first account
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
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        for acc in accounts:
            await process_account(page, acc["user"], acc["pass"])
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_bot())
