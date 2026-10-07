import frappe
from frappe.model.document import Document
from frappe.utils.password import set_encrypted_password

from telegram_connector import sender

DT = "Telegram Settings"


def _tmp_key():
    return f"telegram_login:{frappe.session.user}"


def _cache():
    c = frappe.cache
    return c if hasattr(c, "set_value") else c()


def _run(coro):
    """Run Telethon code and turn any error into a readable message instead of a Server Error."""
    try:
        return sender.run_async(coro)
    except frappe.ValidationError:
        raise
    except Exception as e:
        frappe.throw(f"{type(e).__name__}: {e}")


def _set(field, value):
    frappe.db.set_single_value(DT, field, value)


SECRET_FIELDS = ("session_string", "webhook_secret")


def _set_secret(field, value):
    """Store a secret encrypted AND leave a dummy '*****' in the Single table.

    Frappe deletes a Password value from __Auth when the form is saved with an empty
    value. Because these fields are never typed into the form, the form would always
    send them empty and wipe the secret on the next Save. The dummy value prevents that.
    """
    set_encrypted_password(DT, DT, value, field)
    _set(field, "*" * 10)


class TelegramSettings(Document):
    def validate(self):
        for f in SECRET_FIELDS:
            if not self.get(f) and self.get_password(f, raise_exception=False):
                self.set(f, "*" * 10)

    @frappe.whitelist()
    def test_connection(self):
        frappe.only_for("System Manager")
        if self.mode == "Bot":
            me = sender.bot_call("getMe")
            _set("bot_username", me.get("username"))
            if self.link_method == "Polling":
                sender.bot_call("deleteWebhook")
            return f"✅ Bot: @{me.get('username')}"
        a, h = sender._creds(self)
        who = _run(sender._user_me(a, h, sender._session(self)))
        _set("account_status", who)
        return f"✅ Account: {who}"

    @frappe.whitelist()
    def set_webhook(self):
        frappe.only_for("System Manager")
        url = frappe.utils.get_url() + "/api/method/telegram_connector.api.webhook"
        if not url.startswith("https://"):
            frappe.throw("Webhook requires a public HTTPS URL. Use Polling if the server is internal.")
        secret = self.get_password("webhook_secret", raise_exception=False)
        if not secret:
            secret = frappe.generate_hash(length=32)
            _set_secret("webhook_secret", secret)
        sender.bot_call("setWebhook", {"url": url, "secret_token": secret, "allowed_updates": '["message"]'})
        return "✅ Webhook has been set"

    @frappe.whitelist()
    def send_login_code(self):
        frappe.only_for("System Manager")
        phone = sender.normalize_phone(self.login_phone, self.default_country_code)
        if not phone:
            frappe.throw("Enter the account phone number (Login Phone)")
        a, h = sender._creds(self)
        sess, code_hash = _run(sender._send_code(a, h, phone))
        # Keep the temporary state in the cache, not in the Single doctype,
        # because saving the form rewrites the Single values and loses the hash
        _cache().set_value(_tmp_key(), {"sess": sess, "hash": code_hash}, expires_in_sec=600)
        return "The code was sent to your Telegram app. Enter it in Login Code, then click Verify & Login."

    @frappe.whitelist()
    def verify_login_code(self):
        frappe.only_for("System Manager")
        phone = sender.normalize_phone(self.login_phone, self.default_country_code)
        state = _cache().get_value(_tmp_key()) or {}
        tmp, code_hash = state.get("sess"), state.get("hash")
        if not (tmp and code_hash):
            frappe.throw("Click Send Code first (the code stays valid for 10 minutes)")
        if not (self.login_code or "").strip():
            frappe.throw("Enter the code in the Login Code field")
        a, h = sender._creds(self)
        pw = self.get_password("two_fa_password", raise_exception=False)
        sess, who = _run(sender._verify(a, h, tmp, phone, self.login_code.strip(), code_hash, pw))
        _set_secret("session_string", sess)
        _cache().delete_value(_tmp_key())
        _set("account_status", who)
        _set("login_code", "")
        return f"✅ Logged in: {who}"

    @frappe.whitelist()
    def send_test_message(self):
        frappe.only_for("System Manager")
        r = (self.test_recipient or "").strip()
        if not r:
            frappe.throw("Enter a Test Recipient (chat id in Bot mode, or a mobile number in User Account mode)")
        text = self.test_text or "Test message from ERPNext ✅"
        if self.mode == "Bot":
            sender.send_text(r, None, text)
        else:
            sender.send_text(None, sender.normalize_phone(r, self.default_country_code), text)
        return "✅ Sent"
        