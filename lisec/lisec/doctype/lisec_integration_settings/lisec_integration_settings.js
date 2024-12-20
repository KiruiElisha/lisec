// Copyright (c) 2024, Codes Soft and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lisec Integration Settings', {
	refresh: function(frm) {
		// Add custom button for testing connection
		frm.add_custom_button(__('Test Connection'), function() {
			frappe.call({
				method: 'lisec.lisec.doctype.lisec_integration_settings.lisec_integration_settings.test_connection',
				callback: function(r) {
					if (r.message) {
						if (r.message.success) {
							frm.dashboard.set_headline_alert(
								'<div class="alert alert-success">Connection Successful!</div>'
							);
						} else {
							frm.dashboard.set_headline_alert(
								`<div class="alert alert-danger">Connection Failed: ${r.message.error}</div>`
							);
						}
					}
				}
			});
		});
	}
});
