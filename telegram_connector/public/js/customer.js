frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Telegram Link"), () =>
			frappe.call({ method: "telegram_connector.api.get_or_create_link",
				args: { party_type: "Customer", party: frm.doc.name } })
				.then(r => frappe.set_route("Form", "Telegram Link", r.message)));
	},
});
