# SocialPilot AI Desktop — Phase 1 (Offline-first)

## Run on Windows
1. Install Python 3.11+ from https://python.org (enable "Add Python to PATH").
2. Extract this folder.
3. Double-click `run_windows.bat`.
4. First run installs PySide6; then the app launches.

## Build a Windows executable
Double-click `build_windows.bat`. The packaged app will be created in:
`dist\SocialPilot AI\SocialPilot AI.exe`

For a single-file build, replace the PyInstaller command with:
`pyinstaller --noconfirm --clean --windowed --onefile --name "SocialPilot AI" main.py`

## Local data
Database is stored in `%USERPROFILE%\SocialPilotAI\socialpilot.db`.
Back it up before moving or reinstalling Windows.

## Offline support
Workspaces, content drafts, campaign preparation, and CRM data are local/offline.
AI generation and Instagram/WhatsApp sending, publishing, synchronization, and live analytics need internet and official platform APIs. These integrations are not implemented in Phase 1.

## Safety
This version stores data on the current Windows user profile. It does not send data to a server.


## Phase 3.1: Secure token vault foundation

The Integrations page now includes a credential-vault section. Install dependencies with `pip install -r requirements.txt`. Tokens are stored using Python `keyring` in the OS credential store (Windows Credential Manager when running on Windows), not in the SQLite app database. This does not yet perform OAuth or call Meta APIs. Do not use production tokens until the OAuth flow, permissions, and token lifecycle handling are implemented and reviewed.
\n## Phase 3.5 OAuth code exchange\nThe OAuth Setup page can parse a redirect URL, extract the authorization code, and exchange it with Meta. Requires internet, a configured Meta App ID/Secret, and an exact redirect URI. App Secret and code are not saved to SQLite. Tokens are masked and not auto-persisted; store them using Secure Credential Vault.\n\n## Phase 3.6 token lifecycle helpers\nAdded token expiry display based on Meta expires_in and Instagram-eligible long-lived token exchange. Meta policies vary by product; this is not an automatic refresh scheduler. Token values remain masked and are not automatically persisted.\n\n## Phase 3.7 Meta asset discovery\nOAuth Setup includes Discover Connected Meta Assets. It queries /me/accounts with linked Instagram professional accounts and /me/businesses plus owned WhatsApp Business Accounts and phone numbers. Results are display-only; permissions and assigned assets determine returned data. Requires internet and suitable token scopes.\n
## Phase 4: WhatsApp Bulk Messaging (Python)

1. Install the app dependencies with `pip install -r requirements.txt`.
2. In Meta Developer dashboard, configure WhatsApp Business Cloud API and obtain a Phone Number ID and access token.
3. In SocialPilot AI → Integrations, choose the workspace and WhatsApp Business Platform (Meta), then save the token to Windows Credential Manager.
4. In Audience & CRM, contact records must have `marketing_opt_in=1`. Existing contacts default to **not opted in**.
5. Open WhatsApp Bulk, enter Phone Number ID, approved template name exactly as registered in Meta, and language code (usually `en_US`).
6. Build the queue, review it, then press Send queued messages and confirm.

**Compliance / limitations:** sends only official Cloud API template messages; no WhatsApp Web scraping or unofficial automation. Keep opt-in records and honor opt-outs. API acceptance is not proof of delivery. This build sends template messages with up to one body variable; richer template components need extension. Do not send to purchased/scraped lists.
