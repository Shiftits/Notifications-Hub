"""Send Transportation Request details to the assigned Driver on Telegram.

- Driver set (or changed) and saved      -> full request details are sent to the driver.
- Driver changed                         -> previous driver gets a "reassigned" notice.
- Any later save / update-after-submit   -> only the changes are sent to the current driver.
- If nothing has ever been delivered to the current driver yet (e.g. they were not linked
  on Telegram at the time), the full details are sent again on the next save.
Every send is also written to the request's Activity timeline (who, to whom, by whom).
"""

import frappe
from frappe.utils import escape_html

from telegram_connector import sender

DOCTYPE = "Transportation Request"
DRIVER_DOCTYPE = "Driver"
TRACKED_FIELDS = ["customer", "route", "departure_time", "note"]


def on_update(doc, method=None):
    f = frappe.flags
    if f.in_import or f.in_patch or f.in_install or f.in_migrate:
        return
    channels = _driver_channels()
    if not channels:
        return

    before = doc.get_doc_before_save()
    driver = doc.get("driver")
    old_driver = before.get("driver") if before else None

    if old_driver and old_driver != driver:
        _enqueue(doc.name, old_driver, reassigned_message(doc), channels, "Reassignment notice")

    if not driver:
        return

    if not before or old_driver != driver or not _sent_before(doc.name, driver):
        text = full_message(doc, "Transportation Request assigned to you")
        kind = "Request details"
    else:
        changes = describe_changes(doc, before)
        if not changes:
            return
        text = update_message(doc, changes)
        kind = "Request update"

    _enqueue(doc.name, driver, text, channels, kind)


# ---------------- Delivery ----------------
def _driver_channels():
    """Driver messages go out on Telegram only for now.
    WhatsApp is commented out on purpose; to enable it later, use: return sender.enabled_channels()
    """
    # return sender.enabled_channels()  # WhatsApp: disabled for now
    return ["Telegram"] if sender.channel_enabled("Telegram") else []


def _enqueue(name, driver, text, channels, kind):
    frappe.enqueue(
        "telegram_connector.transportation_request.send_to_driver",
        queue="short",
        enqueue_after_commit=True,
        trip=name,
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


def send_to_driver(trip, driver, text, channels, kind="Request details", sent_by=None):
    phone = _driver_phone(driver)
    for ch in channels:
        log = frappe.get_doc({
            "doctype": "Hub Message Log",
            "status": "Queued",
            "channel": ch,
            "reference_doctype": DOCTYPE,
            "reference_name": trip,
            "party_type": DRIVER_DOCTYPE,
            "party": driver,
            "mobile_no": phone,
            "message": text,
            "attach_print": 0,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
        sender.deliver(log.name, notify=False)
        status, error = frappe.db.get_value("Hub Message Log", log.name, ["status", "error"])
        _log_activity(trip, driver, phone, ch, kind, status, error, text, sent_by)


def _log_activity(trip, driver, phone, channel, kind, status, error, text, sent_by):
    """Write a line in the request's activity timeline: what was sent, to whom, by whom."""
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
        frappe.get_doc(DOCTYPE, trip).add_comment("Info", f"{head}<br><br>{body}")
    except Exception:
        frappe.log_error(title="Telegram: transportation request activity", message=frappe.get_traceback())


def _sent_before(name, driver):
    return bool(frappe.db.exists("Hub Message Log", {
        "reference_doctype": DOCTYPE, "reference_name": name,
        "party_type": DRIVER_DOCTYPE, "party": driver, "status": "Sent",
    }))


# ---------------- Messages ----------------
def _fmt(fieldname, value, meta=None):
    meta = meta or frappe.get_meta(DOCTYPE)
    if value in (None, ""):
        return "-"
    df = meta.get_field(fieldname)
    return frappe.format_value(value, df=df) if df else str(value)


def full_message(doc, title):
    meta = frappe.get_meta(DOCTYPE)
    lines = [
        title,
        f"Request: {doc.name}",
        f"Customer: {doc.get('customer_name') or doc.get('customer') or '-'}",
        f"Route: {doc.get('route') or '-'}",
        f"Departure: {_fmt('departure_time', doc.get('departure_time'), meta)}",
    ]
    if doc.get("note"):
        lines.append(f"Note: {doc.note}")
    return "\n".join(lines)


def update_message(doc, changes):
    head = [f"Transportation Request {doc.name} was updated:"]
    body = [f"- {c}" for c in changes]
    return "\n".join(head + body + ["", full_message(doc, "Current request details")])


def reassigned_message(doc):
    return (
        f"Transportation Request {doc.name} has been reassigned to another driver.\n"
        "You are no longer assigned to this request."
    )


def describe_changes(doc, before):
    meta = frappe.get_meta(DOCTYPE)
    changes = []
    for f in TRACKED_FIELDS:
        if not meta.has_field(f):
            continue
        old, new = before.get(f), doc.get(f)
        if _norm(old) != _norm(new):
            label = meta.get_label(f)
            changes.append(f"{label}: {_fmt(f, old, meta)} -> {_fmt(f, new, meta)}")
    return changes


def _norm(value):
    return "" if value is None else str(value)
