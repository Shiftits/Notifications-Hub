import frappe

INTERNAL = {"Notification Hub", "Hub Notification Rule", "Hub Message Log", "Telegram Link"}
EVENTS = {"after_insert": "New", "on_update": "Save", "on_submit": "Submit", "on_cancel": "Cancel"}


def handle(doc, method=None):
    f = frappe.flags
    if f.in_import or f.in_patch or f.in_install or f.in_migrate:
        return
    event = EVENTS.get(method)
    if not event or doc.doctype in INTERNAL:
        return
    if not (
        frappe.db.get_single_value("Notification Hub", "enabled")
        or frappe.db.get_single_value("Notification Hub", "whatsapp_enabled")
    ):
        return
    rules = frappe.get_all(
        "Hub Notification Rule",
        filters={"enabled": 1, "document_type": doc.doctype, "event": event},
        pluck="name",
    )
    for r in rules:
        frappe.enqueue(
            "telegram_connector.sender.process_rule",
            queue="short",
            enqueue_after_commit=True,
            rule=r,
            ref_doctype=doc.doctype,
            ref_name=doc.name,
        )
