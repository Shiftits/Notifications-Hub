import frappe
from frappe.model.document import Document

from telegram_connector import sender


class HubMessageLog(Document):
    @frappe.whitelist()
    def retry(self):
        frappe.only_for("System Manager")
        sender.deliver(self.name)
        return frappe.db.get_value("Hub Message Log", self.name, "status")
