# PikPak Cloud Manager

A local web app to manage your PikPak cloud storage — browse files, extract download links from shared URLs, and transfer files to Dropbox.

## Features

- **My Cloud** – Login with your PikPak account (email/password or access token), browse folders with breadcrumb navigation, select files and transfer to Dropbox
- **Shared Link** – Paste any `mypikpak.com/s/...` URL to list files and extract direct download links
- **Auto-login** – Persists `refresh_token` so you stay logged in across sessions
- **Dropbox Transfer** – Bulk transfer selected files directly from PikPak to Dropbox

## Requirements

- Python 3.x
- Flask
- requests

```bash
pip install flask requests
```

## Usage

```bash
python pikpak_extractor.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

## Login

**Option 1 – Email/Password:** Enter your PikPak credentials. On new devices, PikPak may require captcha verification.

**Option 2 – Access Token (recommended if captcha blocks):**
1. Open [mypikpak.com](https://mypikpak.com) and log in normally
2. Press **F12** → **Network** tab
3. Click any folder in PikPak (triggers API requests)
4. Find any request to `api-drive.mypikpak.net`
5. In **Headers**, find `Authorization: Bearer eyJ...`
6. Right-click the value → **Copy value**
7. Paste in the Access Token field

## Dropbox Setup

1. Go to [dropbox.com/developers](https://www.dropbox.com/developers)
2. Create an app with `files.content.read` and `files.content.write` scopes
3. Generate an access token and paste it in the Dropbox field

## Notes

- Download links from shared URLs expire in ~24 hours
- Tokens are stored locally in `pikpak_tokens.json` and `pikpak_device.json`
