import frappe
from frappe.model.document import Document

from telegram_connector import sender


class TelegramLink(Document):
    def validate(self):
        cc = sender.settings().default_country_code
        if self.mobile_no:
            self.mobile_no = sender.normalize_phone(self.mobile_no, cc)
        if not (self.mobile_no or (self.party_type and self.party)):
            frappe.throw("Select a Party or enter a mobile number")
        if not self.token:
            self.token = frappe.generate_hash(length=10)
        self.deep_link = sender.make_deep_link(self.token)

    @frappe.whitelist()
    def link_now(self):
        if sender.settings().mode == "Bot":
            if not self.deep_link:
                frappe.throw("Click Test Connection in Notification Hub first to detect the bot username")
            return f"Send this link to the customer so they can press Start:<br><b>{self.deep_link}</b>"
        try:
            info = sender.resolve_user(self.mobile_no)
            self.db_set({"chat_id": str(info["id"]), "telegram_username": info["username"],
                         "status": "Linked", "last_error": ""})
            return "✅ Linked"
        except Exception as e:
            self.db_set({"status": "Failed", "last_error": str(e)})
            frappe.db.commit()
            return f"❌ {e}"

    @frappe.whitelist()
    def send_test(self):
        try:
            sender.send_text(self.chat_id, self.mobile_no, "Test message from ERPNext")
            return "✅ Sent"
        except Exception as e:
            return f"❌ {e}"
