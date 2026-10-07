app_name = "telegram_connector"
app_title = "Telegram Connector"
app_publisher = "Your Company"
app_description = "Send ERPNext notifications to customers via Telegram"
app_email = "dev@example.com"
app_license = "MIT"
required_apps = ["frappe"]

after_install = "telegram_connector.install.after_install"
doctype_js = {
    "Customer": "public/js/customer.js",
    "Sales Invoice": "public/js/sales_invoice.js",
}

_h = "telegram_connector.events.handle"
doc_events = {"*": {"after_insert": _h, "on_update": _h, "on_submit": _h, "on_cancel": _h}}

scheduler_events = {
    "cron": {"* * * * *": ["telegram_connector.sender.poll_updates"]},
    "daily": ["telegram_connector.sender.cleanup_public_pdfs"],
}
