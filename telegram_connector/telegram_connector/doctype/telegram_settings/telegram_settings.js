function run(frm, method) {
	const go = () => frm.call({ doc: frm.doc, method }).then(r => {
		if (r.message) frappe.msgprint(r.message);
		frm.reload_doc();
	});
	return frm.is_dirty() ? frm.save().then(go) : go();
}
frappe.ui.form.on("Telegram Settings", {
	btn_test_connection: f => run(f, "test_connection"),
	btn_set_webhook: f => run(f, "set_webhook"),
	btn_send_code: f => run(f, "send_login_code"),
	btn_verify: f => run(f, "verify_login_code"),
	btn_send_test: f => run(f, "send_test_message"),
});
