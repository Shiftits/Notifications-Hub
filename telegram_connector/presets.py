import frappe

SEP = "------------------------------"


def _items(prices=True):
    if prices:
        line = (
            '{{ loop.index }}. {{ i.item_name }}\\n'
            '   {{ "%g"|format(i.qty) }} {{ i.uom or "" }} x {{ i.get_formatted("rate", doc) }}'
            ' = {{ i.get_formatted("amount", doc) }}\\n'
        )
    else:
        line = '{{ loop.index }}. {{ i.item_name }}\\n   Quantity: {{ "%g"|format(i.qty) }} {{ i.uom or "" }}\\n'
    return "Items\\n{% for i in doc.items %}" + line + "{% endfor %}"


_TOTALS = (
    'Subtotal: {{ doc.get_formatted("total") }}\\n'
    '{% if doc.discount_amount %}Discount: {{ doc.get_formatted("discount_amount") }}\\n{% endif %}'
    '{% for t in doc.taxes %}{% if t.tax_amount %}{{ t.description }}: {{ t.get_formatted("tax_amount", doc) }}\\n{% endif %}{% endfor %}'
    'Grand Total: {{ doc.get_formatted("grand_total") }}\\n'
)

_PAYMENT_STATUS = (
    '{% if doc.paid_amount %}Amount Paid: {{ doc.get_formatted("paid_amount") }}\\n{% endif %}'
    '{% if doc.outstanding_amount %}Amount Due: {{ doc.get_formatted("outstanding_amount") }}\\n'
    '{% else %}Status: Paid in full\\n{% endif %}'
)


def _msg(title, date_label, date_field, extra="", prices=True, payment=False):
    s = (
        "{{ doc.company }}\\n"
        + title + ": {{ doc.name }}\\n\\n"
        "Dear {{ doc.customer_name }},\\n\\n"
        "Please find the details of your " + title.lower() + " below.\\n\\n"
        + date_label + ': {{ doc.get_formatted("' + date_field + '") }}\\n'
        + extra + "\\n"
        + _items(prices) + SEP + "\\n"
    )
    if prices:
        s += _TOTALS
        if payment:
            s += _PAYMENT_STATUS
    s += "\\nThank you for your business.\\n{{ doc.company }}"
    return s.replace("\\n", "\n")


_PARTY = dict(
    party_field="customer", party_doctype="Customer", mobile_field="contact_mobile",
    party_mobile_field="mobile_no", prefer_party_mobile=1, condition="",
)

_DUE = '{% if doc.due_date %}Due Date: {{ doc.get_formatted("due_date") }}\\n{% endif %}'
_DELIVERY = '{% if doc.delivery_date %}Delivery Date: {{ doc.get_formatted("delivery_date") }}\\n{% endif %}'
_VALID = '{% if doc.valid_till %}Valid Until: {{ doc.get_formatted("valid_till") }}\\n{% endif %}'

PRESETS = {
    "Sales Invoice": dict(_PARTY, message=_msg("Invoice", "Invoice Date", "posting_date", _DUE, payment=True), attach_print=1),
    "Sales Order": dict(_PARTY, message=_msg("Sales Order", "Order Date", "transaction_date", _DELIVERY), attach_print=1),
    "Delivery Note": dict(_PARTY, message=_msg("Delivery Note", "Delivery Date", "posting_date", prices=False), attach_print=0),
    "Quotation": dict(
        _PARTY, party_field="party_name", condition='doc.quotation_to == "Customer"',
        message=_msg("Quotation", "Quotation Date", "transaction_date", _VALID), attach_print=1,
    ),
    "Payment Entry": dict(
        _PARTY, party_field="party", mobile_field="", condition='doc.payment_type == "Receive"',
        message=(
            "{{ doc.company }}\n"
            "Payment Receipt: {{ doc.name }}\n\n"
            "Dear {{ doc.party_name }},\n\n"
            "We confirm receipt of your payment. Details are below.\n\n"
            'Date: {{ doc.get_formatted("posting_date") }}\n'
            "{% if doc.mode_of_payment %}Payment Method: {{ doc.mode_of_payment }}\n{% endif %}"
            "{% if doc.reference_no %}Reference No: {{ doc.reference_no }}\n{% endif %}"
            'Amount Received: {{ "{:,.2f}".format(doc.paid_amount) }} {{ doc.paid_to_account_currency }}\n'
            "{% if doc.references %}\nApplied To\n"
            '{% for r in doc.references %}- {{ r.reference_name }}: {{ "{:,.2f}".format(r.allocated_amount) }}\n{% endfor %}'
            "{% endif %}\nThank you for your payment.\n{{ doc.company }}"
        ),
        attach_print=0,
    ),
}


def get_preset(doctype):
    """Ready-made recipient fields + message for a DocType (smart defaults for unknown ones)."""
    if doctype in PRESETS:
        return dict(PRESETS[doctype])
    meta = frappe.get_meta(doctype)
    p = dict(message="", party_field="", party_doctype="", mobile_field="", party_mobile_field="",
             prefer_party_mobile=0, attach_print=0, condition="")
    if meta.has_field("customer"):
        p.update(party_field="customer", party_doctype="Customer", party_mobile_field="mobile_no", prefer_party_mobile=1)
    for f in ("contact_mobile", "mobile_no", "mobile"):
        if meta.has_field(f):
            p["mobile_field"] = f
            break
    lines = [doctype + ": {{ doc.name }}"]
    if meta.has_field("customer_name"):
        lines.append("Customer: {{ doc.customer_name }}")
    for f in ("posting_date", "transaction_date"):
        if meta.has_field(f):
            lines.append('Date: {{ doc.get_formatted("' + f + '") }}')
            break
    if meta.has_field("grand_total"):
        lines.append('Total: {{ doc.get_formatted("grand_total") }}')
    p["message"] = "\n".join(lines)
    return p
