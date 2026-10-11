import frappe
from frappe.utils import escape_html

from telegram_connector import sender

DRIVER_DOCTYPE = "Driver"
STOP_DOCTYPE = "Delivery Stop"

DOCTYPE_CONFIG = {
    "Delivery Trip": {
        "fields": ["company", "vehicle", "departure_time", "total_estimated_distance"],
        "stops": True,
    },
    "Transportation Request": {
        "fields": ["customer", "route", "departure_time", "note"],
        "stops": False,
    },
}
STOP_FIELDS = ["customer", "address", "delivery_note", "estimated_arrival"]


def on_update(doc, method=None):
    f = frappe.flags
    if f.in_import or f.in_patch or f.in_install or f.in_migrate:
        return
    if doc.doctype not in DOCTYPE_CONFIG:
        return
    channels = _driver_channels()
    if not channels:
        return

    before = doc.get_doc_before_save()
    driver = doc.get("driver")
    old_driver = before.get("driver") if before else None

    if old_driver and old_driver != driver:
        _enqueue(doc.doctype, doc.name, old_driver, reassigned_message(doc), channels, "Reassignment notice")

    if not driver:
        return

    if not before or old_driver != driver or not _sent_before(doc.doctype, doc.name, driver):
        text = full_message(doc, f"{doc.doctype} assigned to you")
        kind = "Details"
    else:
        changes = describe_changes(doc, before)
        if not changes:
            return
        text = update_message(doc, changes)
        kind = "Update"

    _enqueue(doc.doctype, doc.name, driver, text, channels, kind)


# ---------------- Delivery ----------------
def _driver_channels():
    """Driver messages go out on Telegram only for now.
    WhatsApp is commented out on purpose; to enable it later, use: return sender.enabled_channels()
    """
    # return sender.enabled_channels()  # WhatsApp: disabled for now
    return ["Telegram"] if sender.channel_enabled("Telegram") else []


def _enqueue(doctype, name, driver, text, channels, kind):
    frappe.enqueue(
        "telegram_connector.driver_notifications.send_to_driver",
        queue="short",
        enqueue_after_commit=True,
        doctype=doctype,
        name=name,
        driver=driver,
        text=text,
        channels=channels,
        kind=kind,
        sent_by=frappe.session.user,
    )


def _driver_phone(driver):
    """Driver's cell_number; if empty, the linked Employee's cell_number; if still empty, the linked User's mobile_no."""
    d = frappe.db.get_value(DRIVER_DOCTYPE, driver, ["cell_number", "employee", "user"], as_dict=True) or {}
    cell = d.get("cell_number")
    if not cell and d.get("employee") and frappe.db.exists("Employee", d.employee):
        cell = frappe.db.get_value("Employee", d.employee, "cell_number")
    if not cell and d.get("user") and frappe.db.exists("User", d.user):
        cell = frappe.db.get_value("User", d.user, "mobile_no")
    return sender.normalize_phone(cell, sender.settings().default_country_code)


def send_to_driver(doctype, name, driver, text, channels, kind="Details", sent_by=None):
    phone = _driver_phone(driver)
    for ch in channels:
        log = frappe.get_doc({
            "doctype": "Hub Message Log",
            "status": "Queued",
            "channel": ch,
            "reference_doctype": doctype,
            "reference_name": name,
            "party_type": DRIVER_DOCTYPE,
            "party": driver,
            "mobile_no": phone,
            "message": text,
            "attach_print": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        sender.deliver(log.name, notify=False)
        status, error = frappe.db.get_value("Hub Message Log", log.name, ["status", "error"])
        _log_activity(doctype, name, driver, phone, ch, kind, status, error, text, sent_by)


def _log_activity(doctype, name, driver, phone, channel, kind, status, error, text, sent_by):
    """Write a line in the document's activity timeline: what was sent, to whom, by whom."""
    try:
        driver_name = frappe.db.get_value(DRIVER_DOCTYPE, driver, "full_name") or driver
        sender_name = frappe.db.get_value("User", sent_by, "full_name") or sent_by or "System"
        to = f"{driver_name} ({driver})" + (f", {phone}" if phone else "")
        icon = {"Sent": "✅", "Not Linked": "⚠️"}.get(status, "❌")
        head = f"{icon} <b>{escape_html(kind)}</b> sent to Driver <b>{escape_html(to)}</b> " \
               f"via <b>{channel}</b>: <b>{escape_html(status or '-')}</b><br>" \
               f"By: {escape_html(sender_name)}"
        if error:
            head += f"<br>Reason: {escape_html(error).replace(chr(10), '<br>')}"
        body = escape_html(text).replace("\n", "<br>")
        frappe.get_doc(doctype, name).add_comment("Info", f"{head}<br><br>{body}")
    except Exception:
        frappe.log_error(title="Telegram: driver notification activity", message=frappe.get_traceback())


def _sent_before(doctype, name, driver):
    return bool(frappe.db.exists("Hub Message Log", {
        "reference_doctype": doctype, "reference_name": name,
        "party_type": DRIVER_DOCTYPE, "party": driver, "status": "Sent",
    }))


# ---------------- Messages ----------------
def _fmt(doctype, fieldname, value):
    if value in (None, ""):
        return "-"
    df = frappe.get_meta(doctype).get_field(fieldname)
    return frappe.format_value(value, df=df) if df else str(value)


def _stop_label(row):
    parts = [row.get("customer_name") or row.get("customer") or "Stop"]
    if row.get("address"):
        parts.append(row.address)
    if row.get("delivery_note"):
        parts.append(f"DN: {row.delivery_note}")
    return " - ".join(parts)


def full_message(doc, title):
    cfg = DOCTYPE_CONFIG[doc.doctype]
    meta = frappe.get_meta(doc.doctype)
    lines = [title, f"{doc.doctype}: {doc.name}"]
    for f in cfg["fields"]:
        if not meta.has_field(f):
            continue
        value = doc.get(f)
        if f == "customer":
            value = doc.get("customer_name") or value
        if value in (None, ""):
            continue
        lines.append(f"{meta.get_label(f)}: {_fmt(doc.doctype, f, doc.get(f)) if f != 'customer' else value}")
    if cfg["stops"]:
        stops = doc.get("delivery_stops") or []
        if stops:
            lines.append("")
            lines.append("Stops:")
            for i, row in enumerate(stops, 1):
                lines.append(f"{i}. {_stop_label(row)}")
        else:
            lines.append("No stops yet.")
    return "\n".join(lines)


def update_message(doc, changes):
    head = [f"{doc.doctype} {doc.name} was updated:"]
    body = [f"- {c}" for c in changes]
    return "\n".join(head + body + ["", full_message(doc, "Current details")])


def reassigned_message(doc):
    return (
        f"{doc.doctype} {doc.name} has been reassigned to another driver.\n"
        "You are no longer assigned to this one."
    )


def describe_changes(doc, before):
    cfg = DOCTYPE_CONFIG[doc.doctype]
    meta = frappe.get_meta(doc.doctype)
    changes = []
    for f in cfg["fields"]:
        if not meta.has_field(f):
            continue
        old, new = before.get(f), doc.get(f)
        if _norm(old) != _norm(new):
            changes.append(f"{meta.get_label(f)}: {_fmt(doc.doctype, f, old)} -> {_fmt(doc.doctype, f, new)}")

    if cfg["stops"]:
        child_meta = frappe.get_meta(STOP_DOCTYPE)
        old_rows = {r.name: r for r in before.get("delivery_stops") or []}
        new_rows = {r.name: r for r in doc.get("delivery_stops") or []}
        for name, row in new_rows.items():
            if name not in old_rows:
                changes.append(f"Stop added: {_stop_label(row)}")
                continue
            old_row = old_rows[name]
            for f in STOP_FIELDS:
                if not child_meta.has_field(f):
                    continue
                if _norm(old_row.get(f)) != _norm(row.get(f)):
                    changes.append(
                        f"Stop {_stop_label(old_row)}: {child_meta.get_label(f)} "
                        f"{_fmt(STOP_DOCTYPE, f, old_row.get(f))} -> {_fmt(STOP_DOCTYPE, f, row.get(f))}"
                    )
        for name, row in old_rows.items():
            if name not in new_rows:
                changes.append(f"Stop removed: {_stop_label(row)}")
    return changes


def _norm(value):
    return "" if value is None else str(value)