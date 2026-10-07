import frappe
from frappe.model.document import Document
from jinja2 import Environment, TemplateSyntaxError


class HubNotificationRule(Document):
    def before_insert(self):
        # Auto title so the user does not have to invent one
        if not self.title:
            base = f"{self.document_type} - {self.event} - {self.channel or 'Telegram'}"
            title, n = base, 1
            while frappe.db.exists("Hub Notification Rule", title):
                n += 1
                title = f"{base} ({n})"
            self.title = title

    def validate(self):
        try:
            Environment().parse(self.message or "")
        except TemplateSyntaxError as e:
            frappe.throw(f"Error in message template: {e}")
