function run(frm, method) {
	const go = () => frm.call({ doc: frm.doc, method }).then(r => {
		if (r.message) frappe.msgprint(r.message);
		frm.reload_doc();
	});
	return frm.is_new() || frm.is_dirty() ? frm.save().then(go) : go();
}
frappe.ui.form.on("Telegram Link", {
	refresh(frm) {
		if (frm.doc.deep_link) {
			frm.add_custom_button(__("Copy Link"), () => frappe.utils.copy_to_clipboard(frm.doc.deep_link));
		}
	},
	party(frm) {
		if (!frm.doc.party_type || !frm.doc.party || frm.doc.mobile_no) return;
		frappe.call({ method: "telegram_connector.api.get_party_mobile",
			args: { party_type: frm.doc.party_type, party: frm.doc.party } })
			.then(r => r.message && frm.set_value("mobile_no", r.message));
	},
	btn_link_now: f => run(f, "link_now"),
	btn_send_test: f => run(f, "send_test"),
});
