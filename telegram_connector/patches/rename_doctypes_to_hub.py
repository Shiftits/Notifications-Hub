import frappe

# old name -> new name
RENAMES = [
    ("Telegram Settings", "Notification Hub"),
    ("Telegram Notification", "Hub Notification Rule"),
    ("Telegram Message", "Hub Message Log"),
]


def execute():
    """Rename the old doctypes in place so existing settings, rules, logs and secrets are kept."""
    dev_mode = frappe.conf.get("developer_mode")
    frappe.conf.developer_mode = 1  # standard doctypes can only be renamed in developer mode
    try:
        for old, new in RENAMES:
            if not frappe.db.exists("DocType", old) or frappe.db.exists("DocType", new):
                continue
            is_single = frappe.db.get_value("DocType", old, "issingle")
            frappe.rename_doc("DocType", old, new, force=True)
            if is_single:
                # values of a Single live in tabSingles, secrets (tokens, session) in __Auth
                frappe.db.sql("update `tabSingles` set doctype=%s where doctype=%s", (new, old))
                frappe.db.sql(
                    "update `__Auth` set doctype=%s, name=%s where doctype=%s and name=%s",
                    (new, new, old, old),
                )
            frappe.db.sql("update `tabFile` set attached_to_doctype=%s where attached_to_doctype=%s", (new, old))
            frappe.db.commit()
    finally:
        frappe.conf.developer_mode = dev_mode
