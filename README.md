# greytHR Auto Check-out Bot

This bot automatically performs a **Sign Out** (Check-out) operation on greytHR in the evening. It is designed to run automatically via GitHub Actions after **6:30 PM IST** on working days.

## How It Works
1. **Working Day Validation**: It checks if today is a working day (skips Sundays, and 1st/3rd Saturdays).
2. **Auto-Login**: Logs into the portal using the credentials provided in the environment variables.
3. **Smart Button Locator**: Looks for the **Sign Out** button on the dashboard:
   - Uses role-based selectors for high accuracy.
   - Falls back to `gt-button` container filters and tag filters if needed.
   - **Fail-safe**: It checks if the button text is actually "Sign Out" (or "Sign-Out") before clicking. If only a "Sign In" button is found, it logs it and exits safely to prevent double check-ins or accidental re-sign-ins.
4. **Auto-Session-Logout**: Logs out of the session profile once the attendance action is finished.
5. **Anti-Detection Delay**: If `RANDOM_DELAY` is enabled, the bot pauses for a random interval (up to 4 minutes) before logging in to mimic human behavior.

## Timezone & Scheduling (After 6:30 PM IST)
- GitHub Actions runs schedules in **UTC**.
- **6:30 PM IST** is equal to **13:00 UTC** (IST is UTC + 5:30).
- The scheduled cron jobs are set as:
  - `35 13 * * 1-5`: Runs at **07:05 PM IST** (Monday through Friday).
  - `45 13 * * 1-5`: Runs at **07:15 PM IST** (Backup run).
- These are staggered to run after 6:30 PM IST and acts as safety nets in case one run fails or is delayed.

## Deployment Setup

### 1. Create a GitHub Repository
Create a new GitHub repository under your account (e.g. `greythr-checkout-bot`) and push the contents of this folder into it.

### 2. Configure GitHub Repository Secrets
Go to your repository **Settings > Secrets and variables > Actions** and add the following repository secrets:
* `GREYTHR_USERNAME`: Your greytHR username/login ID.
* `GREYTHR_PASSWORD`: Your greytHR password.

### 3. Verify Workflow Permissions
Under **Settings > Actions > General > Workflow permissions**, ensure **"Read and write permissions"** is selected. This is required for the keepalive workflow to commit and push changes twice a month to prevent GitHub from automatically disabling scheduled runs.

## Running Locally

To run the bot locally for testing:

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Run the script with your credentials:
   ```bash
   export GREYTHR_USERNAME="your_username"
   export GREYTHR_PASSWORD="your_password"
   export GREYTHR_URL="https://nio-stars.greythr.com/"
   python bot.py
   ```
