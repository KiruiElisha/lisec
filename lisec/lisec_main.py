import frappe
from frappe.utils import getdate, flt, cint , date_diff , nowdate , now 
import json


@frappe.whitelist()
def get_item_comp(item_code, price_list):
	doc = frappe.get_doc("Item", item_code)
	items = []
	for d in doc.item_component:
		d.sqm_pricing = 0
		d.qty_pricing = 0
		d.price_type = frappe.db.get_value("Item", d.item_code, "price_type")
		d.price = get_price(d.item_code, price_list) or d.price
		d.wastage_price = get_price(d.item_code, "Wastage Price List") or d.wastage_price
		items.append(d)
	return {"items": items, "item_doc": doc}

@frappe.whitelist()
def get_item_detail(item_code, price_list):
	data = {}
	if item_code and price_list:
		data["price_type"] = frappe.db.get_value("Item", item_code, "price_type")
		data["item_name"] = frappe.db.get_value("Item", item_code, "item_name")
		data["price"] = get_price(item_code, price_list) or 0
		data["wastage_price"] = get_price(item_code, "Wastage Price List") or 0
	return data

@frappe.whitelist()
def get_price(item,price_list):
	rate = 0
	r = frappe.db.sql("select price_list_rate from `tabItem Price` where price_list = %s and %s between valid_from and valid_upto and item_code = %s limit 1",(price_list, nowdate(), item))
	if r:
		if r[0][0]:
			rate = r[0][0]
	else:
		r = frappe.db.sql("select price_list_rate from `tabItem Price` where price_list = %s and (valid_from <= %s or valid_upto >= %s) and item_code = %s limit 1",(price_list, nowdate(), nowdate(), item))
		if r:
			if r[0][0]:
				rate = r[0][0]
		else:
			r = frappe.db.sql("select price_list_rate from `tabItem Price` where price_list = %s and valid_from IS NULL and valid_upto IS NULL and item_code = %s limit 1",(price_list, item))
			if r:
				if r[0][0]:
					rate = r[0][0]
	if not rate: rate = 0
	return rate

@frappe.whitelist()
def get_item_prices(items, price_list):
	items = json.loads(items)
	item_prices = {}
	for d in items:
		item_prices[d] = get_price(d, price_list)
	return item_prices