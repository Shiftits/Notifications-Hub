# Telegram Connector
Frappe/ERPNext app that sends document notifications (such as invoices) to customers on **Telegram** and **WhatsApp (Wapilot)**.

- **Notification Hub**: enable Telegram and/or WhatsApp, credentials, account login, test message.
- **Telegram Link**: links a customer to Telegram (Start link in Bot mode, or phone-number link in User Account mode). Not needed for WhatsApp.
- **Hub Notification Rule**: sending rules. Pick DocType + Event + Channel (Telegram / WhatsApp / Both); recipient fields and a ready message are filled in automatically. Template buttons: Insert Field, Preview, Load Default Template.
- **Hub Message Log**: log of every message with its channel and status, with a Retry button.
- **Notify Customer** button on Sales Invoice: sends the invoice immediately via the enabled channel(s).
- **Transportation Request to Driver** (automatic): when a Transportation Request gets a Driver and is saved, the request details (customer, route, departure) are sent to the driver. Later saves send only what changed. Each send is logged in the request's Activity. If the driver is changed, the previous driver is notified. The driver must be linked once (Driver's Telegram link), like customers.

## Setup guides
Open **Notification Hub**: the top section has four buttons (WhatsApp Guide, Telegram Bot Guide, Telegram User Account Guide, Troubleshooting) that show step-by-step instructions.

## WhatsApp (Wapilot)
Two Wapilot APIs are supported. The app picks one automatically from **Wapilot Base URL**:

| API | Base URL | Needs |
|---|---|---|
| API v2 | `https://api.wapilot.net/api/v2/<INSTANCE_ID>/send-message` | nothing extra |
| Classic SDK | `https://app.wapilot.io` | `./env/bin/pip install wapilot-sdk`, then `bench restart` |

1. Tick **Enable WhatsApp**, paste the Wapilot API token, set the Base URL, Save.
2. Click **WhatsApp Diagnostics** (never sends a message).
3. Use **Test Channel = WhatsApp** + a mobile number and click Send Test Message.

API v2 payloads can be changed in **Advanced (API v2 payloads)** (placeholders `{phone}`, `{message}`, `{media_url}`, `{file_name}`).

PDF attachments on WhatsApp are sent by URL, so the site must be reachable from the internet
(set `host_name` in site_config.json). The temporary public PDF is deleted after 2 days.

After updating the app run `bench --site <site> migrate` and `bench build --app telegram_connector`, then restart.
