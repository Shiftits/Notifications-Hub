import frappe

from telegram_connector.presets import PRESETS

DEFAULT_MESSAGE = PRESETS["Sales Invoice"]["message"]


def after_install():
    if frappe.db.exists("DocType", "Sales Invoice") and not frappe.db.exists(
        "Hub Notification Rule", "Sales Invoice - Submit"
    ):
        frappe.get_doc({
            "doctype": "Hub Notification Rule",
            "title": "Sales Invoice - Submit",
            "enabled": 1,
            "document_type": "Sales Invoice",
            "event": "Submit",
            "mobile_field": "contact_mobile",
            "party_field": "customer",
            "party_doctype": "Customer",
            "party_mobile_field": "mobile_no",
            "prefer_party_mobile": 1,
            "message": DEFAULT_MESSAGE,
        }).insert(ignore_permissions=True)
