// Copyright (c) 2022, Aqiq Solutions and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lisec Integration Tool', {
	refresh(frm) {
		frm.dashboard.clear_headline();
		
		frm.add_custom_button(__('Create MR'),
			function() {
				if (!frm.doc.order_id) {
					frappe.show_alert({
						message: __("Please enter an Order ID"),
						indicator: 'red'
					});
					return;
				}

				frappe.call({
					method: 'lisec.lisec.doctype.lisec_integration_tool.lisec_integration_tool.main_manual',
					args: {
						order_id: frm.doc.order_id,
					},
					freeze: true,
					freeze_message: "<h3 style='color: RoyalBlue;'>Creating Material Request...</h3>",
					callback: (r) => {
						if (r && r.message) {
							console.log("MR Creation Response:", r.message);
							
							// Parse the response if it's an object
							let message = typeof r.message === 'object' ? 
								JSON.stringify(r.message, null, 2) : r.message;
							
							frm.dashboard.set_headline_alert(
								`<div class="row">
									<div class="col-xs-12">
										<span class="indicator green">
											${message}
										</span>
									</div>
								</div>`
							);
							
							frappe.show_alert({
								message: __("Process Complete"),
								indicator: 'green'
							}, 5);
						}
					},
					error: (r) => {
						console.error("MR Creation Error:", r);
						
						frm.dashboard.set_headline_alert(
							`<div class="row">
								<div class="col-xs-12">
									<span class="indicator red">
										Error: ${r.message || "Unknown error"}
									</span>
								</div>
							</div>`
						);
						
						frappe.show_alert({
							message: __("Error in process"),
							indicator: 'red'
						});
					}
				});
			}
		);
	},
});
