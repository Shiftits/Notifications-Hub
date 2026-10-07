function show_results(results) {
	const failed = results.filter(r => r.status !== "Sent");
	if (!failed.length && !results.some(r => r.error)) {
		const where = results.map(r => r.channel).join(" + ");
		return frappe.show_alert({ message: __("Sent to customer via {0}", [where]), indicator: "green" });
	}
	const rows = results.map(r => {
		const color = r.status === "Sent" ? "green" : "red";
		const err = r.error ? ` — ${frappe.utils.escape_html(r.error).replace(/\n/g, "<br>")}` : "";
		return `<p><b>${r.channel}</b>: <span class="text-${color === "green" ? "success" : "danger"}">${r.status}</span>${err}</p>`;
	});
	frappe.msgprint({ title: __("Notify Customer"), message: rows.join(""), indicator: failed.length ? "red" : "orange" });
}

function send(frm, channel) {
	frappe.call({
		method: "telegram_connector.api.notify_customer",
		args: { doctype: frm.doc.doctype, name: frm.doc.name, channel },
		freeze: true,
		freeze_message: __("Sending..."),
	}).then(r => show_results((r.message || {}).results || []));
}

function notify(frm) {
	frappe.call({ method: "telegram_connector.api.get_enabled_channels" }).then(r => {
		const ch = r.message || [];
		if (!ch.length) {
			return frappe.msgprint(__("No channel is enabled. Enable Telegram or WhatsApp in Notification Hub."));
		}
		if (ch.length === 1) {
			return frappe.confirm(__("Send this invoice to the customer on {0}?", [ch[0]]), () => send(frm, ch[0]));
		}
		const d = new frappe.ui.Dialog({
			title: __("Notify Customer"),
			fields: [{
				fieldname: "channel", fieldtype: "Select", label: __("Send via"),
				options: [...ch, "Both"].join("\n"), default: "Both", reqd: 1,
			}],
			primary_action_label: __("Send"),
			primary_action(v) {
				d.hide();
				send(frm, v.channel);
			},
		});
		d.show();
	});
}

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus === 2) return;
		frm.add_custom_button(__("Notify Customer"), () => notify(frm));
	},
});
