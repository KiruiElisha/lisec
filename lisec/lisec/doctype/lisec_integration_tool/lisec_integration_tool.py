# Copyright (c) 2022, Codes Soft and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cstr, getdate, now
import json, requests
from frappe.utils.background_jobs import enqueue
from datetime import datetime, timedelta
from frappe import publish_realtime, get_user

default_company = frappe.db.get_single_value("Global Defaults", "default_company")


class LisecIntegrationTool(Document):
    pass


@frappe.whitelist(allow_guest=True)
def lisec_job_scheduler():
    enqueue("lisec.lisec.doctype.lisec_integration_tool.lisec_integration_tool.main")
    return "success in lisec background-job"


@frappe.whitelist(allow_guest=True)
def lisec_history_job_scheduler():
    # frappe.log_error("lisec_history_job_scheduler_Called")
    enqueue(
        "lisec.lisec.doctype.lisec_integration_tool.lisec_integration_tool.history_main"
    )
    frappe.log_error("lisec_history_job_scheduler_Done")
    return "success in lisec history background-job"

settings = frappe.get_single('Lisec Integration Settings')
host = settings.lisec_ip_address
port = settings.lisec_ip_port
site = settings.site
base_url = f"https://{host}:{port}/api/sites/{site}/versions/1"

api_access_token = ""
api_refresh_token = settings.api_refresh_token
api_user = settings.api_user
api_password_hash = settings.api_password_hash

# ------------------------------------------------


def init_module():
    requests.packages.urllib3.disable_warnings()


# ------------------------------------------------


def refresh_access_token():

    if api_refresh_token == "":
        # print("- api refresh token not set, can't authenticate using refresh token")
        return False

    url = base_url + "/authentication/tokens"
    req_header = {"refreshTokenHeader": api_refresh_token}

    resp = requests.put(url, headers=req_header, verify=False)

    if resp.status_code == 200:
        global api_access_token
        api_access_token = resp.text
        # print("- api access token refresh succesul, new access token set")
        return True
    else:
        # print("- api token refresh failed:")
        # print("  Status:", resp.status_code, "-", resp.reason)
        return False


# ------------------------------------------------


def get_new_access_token():
    if api_user == "" or api_password_hash == "":
        # print("- api_user and/or api_password_hash not set, can't authenticate using user and password")
        return False

    url = base_url + "/authentication/tokens"
    req_header = {"userHeader": api_user, "passwordHeader": api_password_hash}

    resp = requests.post(url, headers=req_header, verify=False)

    if resp.status_code == 200:
        result = resp.json()

        global api_access_token
        api_access_token = resp.json()["accessToken"]

        # print("- Authentication via user/password successful ")
        # print("  Please update/set 'api_refresh_token' field to authenticate via refresh token for improved security")
        # print("  New refresh token:", resp.json()["refreshToken"])
        # print("")
        # input( "Press Enter to continue..." )

        return True
    else:
        # print("- Authentication via user/password failed:")
        # print("  Status:", resp.status_code, "-", resp.reason)
        return False


# ------------------------------------------------


def get_access_token():

    if refresh_access_token() == False:
        if get_new_access_token() == False:
            # print("ERROR: all authentication methods failed, can't continue")
            return False

    return True


# ------------------------------------------------
def get_list_orders(today_date):
    # print("- Get list of orders")

    # url = f"/orders?limit={limit}&offset={offset}"
    # url = f"/orders?filter=header.creationDate>={start_date}"
    url = f"/orders?filter=header.creationDate=={today_date}"
    auth = "Bearer {}".format(api_access_token)
    req_header = {"Authorization": auth, "Content-Type": "application/json"}

    resp = requests.get(base_url + url, headers=req_header, verify=False)
    # frappe.log_error(str(base_url) + url + str(req_header))

    if resp.status_code == 200:
        # print("item details:")
        # print(json.dumps(resp.json(), indent=2))
        data = resp.json()
        # frappe.log_error(str(data))
        return data
    else:
        return []


# ------------------------------------------------


def get_order_details(order_id):

    url = "/orders/{}".format(order_id)

    auth = "Bearer {}".format(api_access_token)
    req_header = {"Authorization": auth, "Content-Type": "application/json"}

    resp = requests.get(base_url + url, headers=req_header, verify=False)

    if resp.status_code == 200:
        data = resp.json()
        frappe.log_error("Order Details Response", resp.text)
        return data


# ------------------------------------------------


def get_item_details(order_no, item_no):
    # print("- Get item details for Order/Item ", order_no, "/", item_no)

    url = "/orders/{}/items/{}".format(order_no, item_no)
    auth = "Bearer {}".format(api_access_token)
    req_header = {"Authorization": auth, "Content-Type": "application/json"}

    resp = requests.get(base_url + url, headers=req_header, verify=False)

    # print("  GET '{base_url}" + url + "':")
    # print("")
    # print("  Status:", resp.status_code, "-", resp.reason)
    # print("")

    # if resp.status_code == 200:
    # print("item details:")
    # print(json.dumps(resp.json(), indent=2))


# ---------------------------------------------------


def get_order_header_details(order_id):
    # print("Get order header details for Order ", order_id)

    url = "/orders/{}/header".format(order_id)

    auth = "Bearer {}".format(api_access_token)
    req_header = {"Authorization": auth, "Content-Type": "application/json"}

    resp = requests.get(base_url + url, headers=req_header, verify=False)

    # print("  GET '{base_url}" + url + "':")
    # print("")
    # print("  Status:", resp.status_code, "-", resp.reason)
    # print("")

    if resp.status_code == 200:
        # print("Order header details:")
        # print(json.dumps(resp.json(), indent=2))
        # data = resp.text
        # data = json.loads(data)
        data = resp.json()
        return data


# ---------------------------------------------------


def create_items(order):
    rtn_msg = "create_items_for_order called."
    try:
        if order:
            ccount = 0
            ucount = 0
            for d in order["items"]:
                if d["bom"]:
                    items = d["bom"]
                    for item in items:
                        if item["bomId"]:
                            item_code = str(item["id"])
                            item_name = str(item["userDescription"])
                        if item_code:
                            if not frappe.db.exists("Item", {"item_code": item_code}):
                                add_item = frappe.new_doc("Item")
                                add_item.item_code = item_code
                                add_item.item_name = item_name
                                add_item.item_group = "Lisec"
                                add_item.company = default_company
                                if item.get("itemGeometry"):
                                    add_item.height = item["itemGeometry"].get(
                                        "rectHeight"
                                    )
                                    add_item.width = item["itemGeometry"].get(
                                        "rectWidth"
                                    )
                                add_item.item_component = []
                                if len(d["bom"]) > 1:
                                    bom_list = d["bom"]
                                    if d["bom"][0].get("itemProcess"):
                                        processes_list = d["bom"][0]["itemProcess"]
                                        for process in processes_list:
                                            process_id = str(process["processId"])
                                            new_item_doc_name = ""
                                            if not frappe.db.exists(
                                                "Item", {"item_code": process_id}
                                            ):
                                                item_doc = frappe.new_doc("Item")
                                                item_doc.item_code = process_id
                                                item_doc.item_name = process_id
                                                item_doc.item_group = "Lisec"
                                                item_doc.company = default_company
                                                item_doc.flags.ignore_mandatory = True
                                                item_doc.save(ignore_permissions=True)
                                                new_item_doc_name = item_doc.name
                                                ccount += 1
                                            process_row = {}
                                            process_row["item_code"] = new_item_doc_name
                                            process_row["item_name"] = process_id
                                            process_row["qty"] = process["quantity"]
                                            process_row["item_width"] = process[
                                                "parameters"
                                            ]["width"]
                                            process_row["item_height"] = process[
                                                "parameters"
                                            ]["height"]
                                            add_item.append(
                                                "item_component", process_row
                                            )

                                    for idx in range(1, len(bom_list)):
                                        component_item = str(bom_list[idx]["id"])
                                        new_item_doc_name = ""
                                        if component_item:
                                            if not frappe.db.exists(
                                                "Item", {"item_code": component_item}
                                            ):
                                                item_doc = frappe.new_doc("Item")
                                                item_doc.item_code = component_item
                                                item_doc.item_name = bom_list[idx][
                                                    "userDescription"
                                                ]
                                                item_doc.company = default_company

                                                item_doc.item_group = "Lisec"
                                                item_doc.flags.ignore_mandatory = True
                                                item_doc.save(ignore_permissions=True)
                                                new_item_doc_name = item_doc.name
                                                ccount += 1
                                            component_row = {}
                                            if new_item_doc_name:
                                                component_row[
                                                    "item_code"
                                                ] = new_item_doc_name
                                            else:
                                                component_row[
                                                    "item_code"
                                                ] = component_item
                                            component_row["item_name"] = bom_list[idx][
                                                "userDescription"
                                            ]
                                            component_row["qty"] = bom_list[idx].get(
                                                "qty"
                                            )
                                            if bom_list[idx].get("itemGeometry"):
                                                component_row["item_width"] = bom_list[idx][
                                                    "itemGeometry"
                                                ].get("rectWidth")
                                                component_row["item_height"] = bom_list[idx][
                                                    "itemGeometry"
                                                ].get("rectHeight")
                                            add_item.append(
                                                "item_component", component_row
                                            )

                                        if bom_list[idx].get("itemProcess"):
                                            processes_list = bom_list[idx]["itemProcess"]
                                            for process in processes_list:
                                                process_id = str(process["processId"])
                                                if not frappe.db.exists(
                                                    "Item", {"item_code": process_id}
                                                ):
                                                    item_doc = frappe.new_doc("Item")
                                                    item_doc.item_code = process_id
                                                    item_doc.item_name = process_id
                                                    item_doc.item_group = "Lisec"
                                                    item_doc.company = default_company
                                                    item_doc.flags.ignore_mandatory = (
                                                        True
                                                    )
                                                    item_doc.save(
                                                        ignore_permissions=True
                                                    )
                                                    ccount += 1
                                                component_row = {}
                                                component_row["item_code"] = process_id
                                                component_row["item_name"] = process_id
                                                component_row["qty"] = process[
                                                    "quantity"
                                                ]
                                                component_row["item_width"] = process[
                                                    "parameters"
                                                ]["width"]
                                                component_row["item_height"] = process[
                                                    "parameters"
                                                ]["height"]
                                                add_item.append(
                                                    "item_component", component_row
                                                )
                                add_item.company = default_company
                                add_item.flags.ignore_mandatory = True
                                add_item.save(ignore_permissions=True)
                                ccount += 1

        rtn_msg = "Created {ccount} new items from LISEC API data Successfully."
        return rtn_msg

    except Exception as e:
        # error_message = frappe.get_traceback()+"Error\n"+str(e)
        # frappe.log_error(error_message, "create_items lisec error.")
        frappe.throw(
            f"Error occured while handling function of creation of items of order# {order['header']['orderNo']}"
        )


# -----------------------------------------------LISEC LOGS---------------------------------------------------------
def create_lisec_log(order, map_vars):
    try:
        log_msg = ""
        if order:
            # It checks if already records exists, if not then it will create a new log record.
            log_exists = frappe.db.exists(
                "Lisec Logs",
                {
                    "customer_id": order["header"]["custNo"],
                    "lisec_reference_no": order["header"]["orderNo"],
                    "creation_date": order["header"]["creationDate"],
                },
            )
            if not log_exists:
                log_doc = frappe.new_doc("Lisec Logs")
                log_doc.customer_id = str(order["header"]["custNo"])
                log_doc.customer_address = order["header"]["customerAddress"]["name"]
                log_doc.lisec_reference_no = str(order["header"]["orderNo"])
                log_doc.creation_date = order["header"]["creationDate"]

                log_doc.log_items = []
                log_doc.components = []
                count = 1

                # Iterates through lisec orders

                for d in order["items"]:
                    if d["bom"]:  # Checks if the item has bom or not
                        item_row = {}
                        item_row["item_code"] = d["bom"][0]["id"]
                        item_row["item_name"] = d["bom"][0]["userDescription"]
                        item_row["rate"] = 0.0
                        log_doc.append("log_items", item_row)

                        if d["bom"][0].get(
                            "itemProcess"
                        ):  # it checks the main item object has itemProces or not, it has will add item process in components table of Item
                            processes_list = d["bom"][0]["itemProcess"]
                            for process in processes_list:
                                process_id = str(process["processId"])
                                process_row = {}
                                process_row["parent_item"] = (
                                    str(count) + " - " + str(d["bom"][0]["id"])
                                )
                                process_row["item_code"] = process_id
                                process_row["item_detail"] = process_id
                                process_row["qty"] = process["quantity"]
                                process_row["item_width"] = process["parameters"][
                                    "width"
                                ]
                                process_row["item_height"] = process["parameters"][
                                    "height"
                                ]
                                log_doc.append("components", process_row)

                        # Checks for item components and if there are, will add them in item components of Item Master
                        if len(d["bom"]) > 1:
                            bom_list = d["bom"]
                            for idx in range(1, len(bom_list)):
                                component_row = {}
                                component_item = str(bom_list[idx]["id"])
                                if component_item:
                                    component_row["parent_item"] = (
                                        str(count) + " - " + str(d["bom"][0]["id"])
                                    )
                                    component_row["item_code"] = component_item
                                    component_row["item_detail"] = bom_list[idx][
                                        "userDescription"
                                    ]
                                    component_row["qty"] = bom_list[idx].get("qty")
                                    if bom_list[idx].get("itemGeometry"):
                                        component_row["item_width"] = bom_list[idx][
                                            "itemGeometry"
                                        ].get("rectWidth")
                                        component_row["item_height"] = bom_list[idx][
                                            "itemGeometry"
                                        ].get("rectHeight")
                                    log_doc.append("components", component_row)

                                    if bom_list[idx].get("itemProcess"):
                                        processes_list = bom_list[idx]["itemProcess"]
                                        for process in processes_list:
                                            process_id = str(process["processId"])
                                            process_row = {}
                                            process_row["parent_item"] = (
                                                str(count)
                                                + " - "
                                                + str(d["bom"][0]["id"])
                                            )
                                            process_row["item_code"] = process_id
                                            process_row["item_detail"] = process_id
                                            process_row["qty"] = process["quantity"]
                                            process_row["item_width"] = process[
                                                "parameters"
                                            ]["width"]
                                            process_row["item_height"] = process[
                                                "parameters"
                                            ]["height"]
                                            log_doc.append("components", process_row)
                        count += 1
                log_msg = "Created new LISEC LOG records."
                log_doc.flags.ignore_mandatory = True
                log_doc.save(ignore_permissions=True)
            # if the lisec log records is already existing in the ERP
            else:
                log_name = frappe.db.get_value("Lisec Logs", log_exists)
                # frappe.msgprint(cstr(log_name))
                log_doc = frappe.get_doc("Lisec Logs", log_name)
                log_doc.customer_id = str(order["header"]["custNo"])
                log_doc.customer_address = order["header"]["customerAddress"]["name"]
                log_doc.lisec_reference_no = str(order["header"]["orderNo"])
                log_doc.creation_date = order["header"]["creationDate"]

                log_doc.log_items = []
                log_doc.components = []
                count = 1
                for d in order["items"]:
                    if d["bom"]:
                        item_row = {}
                        item_row["item_code"] = d["bom"][0]["id"]
                        item_row["item_name"] = d["bom"][0]["userDescription"]
                        item_row["rate"] = 0.0
                        item_row["qty"] = d["qty"]
                        item_row["height_mm"] = d["bom"][0]["itemGeometry"][
                            "rectHeight"
                        ]
                        item_row["width_mm"] = d["bom"][0]["itemGeometry"]["rectWidth"]
                        item_row["pcs"] = d["bom"][0]["itemGeometry"]["area"]
                        log_doc.append("log_items", item_row)

                log_msg = "Overwrote LISEC LOG records."
                log_doc.flags.ignore_mandatory = True
                log_doc.save(ignore_permissions=True)
        return log_msg
    except:
        frappe.throw(
            f"Error occured while handling function of cration of Lisec Log for order# {order['header']['orderNo']}"
        )


# -----------------------------------------------LISEC LOGS---------------------------------------------------------
def create_lisec_log(order, map_vars):
    try:
        log_msg = ""
        if order:
            # It checks if already records exists, if not then it will create a new log record.
            log_exists = frappe.db.exists(
                "Lisec Logs",
                {
                    "customer_id": order["header"]["custNo"],
                    "lisec_reference_no": order["header"]["orderNo"],
                    "creation_date": order["header"]["creationDate"],
                },
            )
            if not log_exists:
                log_doc = frappe.new_doc("Lisec Logs")
                log_doc.customer_id = str(order["header"]["custNo"])
                log_doc.customer_address = order["header"]["customerAddress"]["name"]
                log_doc.lisec_reference_no = str(order["header"]["orderNo"])
                log_doc.creation_date = order["header"]["creationDate"]

                log_doc.log_items = []
                log_doc.components = []
                count = 1

                # Iterates through lisec orders

                for d in order["items"]:
                    if d["bom"]:  # Checks if the item has bom or not
                        item_row = {}
                        item_row["item_code"] = d["bom"][0]["id"]
                        item_row["item_name"] = d["bom"][0]["userDescription"]
                        item_row["rate"] = 0.0
                        item_row["qty"] = d["qty"]
                        item_row["height_mm"] = d["bom"][0]["itemGeometry"][
                            "rectHeight"
                        ]
                        item_row["width_mm"] = d["bom"][0]["itemGeometry"]["rectWidth"]
                        item_row["pcs"] = d["bom"][0]["itemGeometry"]["area"]
                        log_doc.append("log_items", item_row)

                log_msg = "Created new LISEC LOG records."
                log_doc.flags.ignore_mandatory = True
                log_doc.save(ignore_permissions=True)

            # if the lisec log records is already existing in the ERP
            else:
                log_name = frappe.db.get_value("Lisec Logs", log_exists)
                log_doc = frappe.get_doc("Lisec Logs", log_name)
                log_doc.customer_id = str(order["header"]["custNo"])
                log_doc.customer_address = order["header"]["customerAddress"]["name"]
                log_doc.lisec_reference_no = str(order["header"]["orderNo"])
                log_doc.creation_date = order["header"]["creationDate"]

                log_doc.log_items = []
                log_doc.components = []

                for d in order["items"]:
                    if d["bom"]:
                        item_row = {}
                        item_row["item_code"] = d["bom"][0]["id"]
                        item_row["item_name"] = d["bom"][0]["userDescription"]
                        item_row["rate"] = 0.0
                        item_row["qty"] = d["qty"]
                        item_row["height_mm"] = d["bom"][0]["itemGeometry"][
                            "rectHeight"
                        ]
                        item_row["width_mm"] = d["bom"][0]["itemGeometry"]["rectWidth"]
                        item_row["pcs"] = d["bom"][0]["itemGeometry"]["area"]
                        log_doc.append("log_items", item_row)

                log_msg = "Overwrote LISEC LOG records."
                log_doc.flags.ignore_mandatory = True
                log_doc.save(ignore_permissions=True)
        return log_msg
    except:
        frappe.throw(
            f"Error occured while handling function of cration of Lisec Log for order# {order['header']['orderNo']}"
        )


# -----------------------------------------------SALES ORDER---------------------------------------------------------
def create_sales_order(order, map_vars):
    try:
        rtn_msg = "Just entered in sales order creation function"
        log_msg = "Log msg initial."
        if order:
            # Calls function to create LISEC Log record
            log_msg = create_lisec_log(order, map_vars)

            order_name = f"{order['header']['custNo']}-{order['header']['orderNo']}-{order['header']['creationDate']}"  # Unique sales order no
            lisec_order_exist = frappe.db.exists(
                "Sales Order", {"order_from_lisec": order_name}
            )

            # It checks if already records exists, if not then it will create a new Sales Order in ERP.

            if not lisec_order_exist:
                doc = frappe.new_doc("Sales Order")
                order_dict = frappe._dict()
                hd_map = map_vars.header_mapping
                items_map = map_vars.items_mapping
                for h in range(0, len(hd_map)):
                    erp_field = hd_map[h].erp_field
                    lisec_field = hd_map[h].lisec_field

                    if erp_field == "department":
                        order_dict[f"{erp_field}"] = "Test Department - IG"
                    elif erp_field == "cost_center":
                        order_dict[f"{erp_field}"] = "Archi - IG"
                    elif erp_field == "customer_address":
                        order_dict[
                            f"{erp_field}"
                        ] = f"{order['header']['customerAddress']['name']}-Billing"
                    elif erp_field == "set_warehouse":
                        order_dict[f"{erp_field}"] = "Automobile - IG"
                    elif erp_field == "grand_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "base_grand_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "rounded_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "base_rounded_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "delivery_date":
                        order_dict[f"{erp_field}"] = order["header"]["deliveryInfo"][
                            "deliveryDate"
                        ]
                    else:
                        order_dict[f"{erp_field}"] = order["header"][f"{lisec_field}"]

                doc.update(order_dict)

                doc.items = []
                doc.components = []
                count = 1
                for d in order["items"]:
                    if d["bom"]:
                        item_row = {}

                        # items_map is for fields mapping, specified in LISEC INTEGRATION TOOL single doctype cdt

                        for item in range(0, len(items_map)):
                            item_erp = items_map[item].erp_field  # fieldname in erp
                            item_lisec = items_map[
                                item
                            ].lisec_item  # fieldname in lisec api data

                            if item_erp == "warehouse":
                                item_row[f"{item_erp}"] = "Automobile - IG"
                            elif item_erp == "conversion_factor":
                                item_row[f"{item_erp}"] = 1.0
                            else:
                                item_row[f"{item_erp}"] = d["bom"][0][f"{item_lisec}"]
                        doc.append("items", item_row)

                        if d["bom"][0].get("itemProcess"):
                            processes_list = d["bom"][0]["itemProcess"]
                            for process in processes_list:
                                process_row = {}
                                process_row["parent_item"] = (
                                    str(count) + " - " + str(d["bom"][0]["id"])
                                )
                                process_row["item_code"] = process["processId"]
                                process_row["item_detail"] = process["processId"]
                                process_row["qty"] = process["quantity"]
                                process_row["item_width"] = process["parameters"][
                                    "width"
                                ]
                                process_row["item_height"] = process["parameters"][
                                    "height"
                                ]
                                doc.append("components", process_row)

                        if len(d["bom"]) > 1:
                            bom_list = d["bom"]
                            for idx in range(1, len(bom_list)):
                                component_row = {}
                                component_item = str(bom_list[idx]["id"])
                                if component_item:
                                    component_row["parent_item"] = (
                                        str(count) + " - " + str(d["bom"][0]["id"])
                                    )
                                    component_row["item_code"] = component_item
                                    component_row["item_detail"] = bom_list[idx][
                                        "userDescription"
                                    ]
                                    component_row["qty"] = bom_list[idx].get("qty")
                                    if bom_list[idx].get("itemGeometry"):
                                        component_row["item_width"] = bom_list[idx][
                                            "itemGeometry"
                                        ].get("rectWidth")
                                        component_row["item_height"] = bom_list[idx][
                                            "itemGeometry"
                                        ].get("rectHeight")
                                    doc.append("components", component_row)

                                    if bom_list[idx].get("itemProcess"):
                                        processes_list = bom_list[idx]["itemProcess"]
                                        for process in processes_list:
                                            process_row = {}
                                            process_row["parent_item"] = (
                                                str(count)
                                                + " - "
                                                + str(d["bom"][0]["id"])
                                            )
                                            process_row["item_code"] = process[
                                                "processId"
                                            ]
                                            process_row["item_detail"] = process[
                                                "processId"
                                            ]
                                            process_row["qty"] = process["quantity"]
                                            process_row["item_width"] = process[
                                                "parameters"
                                            ]["width"]
                                            process_row["item_height"] = process[
                                                "parameters"
                                            ]["height"]
                                            doc.append("components", process_row)
                    count += 1
                doc.order_from_lisec = order_name
                doc.flags.ignore_mandatory = True
                doc.save(ignore_permissions=True)

                rtn_msg = f"Created {count} new Sales Order from LISEC API Data!"

            else:
                record_name = frappe.db.get_value(
                    "Sales Order", {"order_from_lisec": order_name}, "name"
                )
                doc = frappe.get_doc("Sales Order", record_name)
                order_dict = frappe._dict()
                hd_map = map_vars.header_mapping
                items_map = map_vars.items_mapping
                for h in range(0, len(hd_map)):
                    erp_field = hd_map[h].erp_field
                    lisec_field = hd_map[h].lisec_field

                    if erp_field == "department":
                        order_dict[f"{erp_field}"] = "Test Department - IG"
                    elif erp_field == "cost_center":
                        order_dict[f"{erp_field}"] = "Archi - IG"
                    elif erp_field == "customer_address":
                        order_dict[
                            f"{erp_field}"
                        ] = f"{order['header']['customerAddress']['name']}-Billing"
                    elif erp_field == "set_warehouse":
                        order_dict[f"{erp_field}"] = "Automobile - IG"
                    elif erp_field == "grand_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "base_grand_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "rounded_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "base_rounded_total":
                        order_dict[f"{erp_field}"] = 99
                    elif erp_field == "delivery_date":
                        order_dict[f"{erp_field}"] = order["header"]["deliveryInfo"][
                            "deliveryDate"
                        ]
                    else:
                        order_dict[f"{erp_field}"] = order["header"][f"{lisec_field}"]

                doc.update(order_dict)

                doc.items = []
                doc.components = []
                count = 1
                for d in order["items"]:
                    if d["bom"]:
                        item_row = {}
                        for item in range(0, len(items_map)):
                            item_erp = items_map[item].erp_field
                            item_lisec = items_map[item].lisec_item

                            if item_erp == "warehouse":
                                item_row[f"{item_erp}"] = "Automobile - IG"
                            elif item_erp == "conversion_factor":
                                item_row[f"{item_erp}"] = 1.0
                            else:
                                item_row[f"{item_erp}"] = d["bom"][0][f"{item_lisec}"]
                        doc.append("items", item_row)

                        if d["bom"][0].get("itemProcess"):
                            processes_list = d["bom"][0]["itemProcess"]
                            for process in processes_list:
                                process_row = {}
                                process_row["parent_item"] = (
                                    str(count) + " - " + str(d["bom"][0]["id"])
                                )
                                process_row["item_code"] = process["processId"]
                                process_row["item_detail"] = process["processId"]
                                process_row["qty"] = process["quantity"]
                                process_row["item_width"] = process["parameters"][
                                    "width"
                                ]
                                process_row["item_height"] = process["parameters"][
                                    "height"
                                ]
                                doc.append("components", process_row)

                        if len(d["bom"]) > 1:
                            bom_list = d["bom"]
                            for idx in range(1, len(bom_list)):
                                component_row = {}
                                component_item = str(bom_list[idx]["id"])
                                if component_item:
                                    component_row["parent_item"] = (
                                        str(count) + " - " + str(d["bom"][0]["id"])
                                    )
                                    component_row["item_code"] = component_item
                                    component_row["item_detail"] = bom_list[idx][
                                        "userDescription"
                                    ]
                                    component_row["qty"] = bom_list[idx].get("qty")
                                    if bom_list[idx].get("itemGeometry"):
                                        component_row["item_width"] = bom_list[idx][
                                            "itemGeometry"
                                        ].get("rectWidth")
                                        component_row["item_height"] = bom_list[idx][
                                            "itemGeometry"
                                        ].get("rectHeight")
                                    doc.append("components", component_row)

                                    if bom_list[idx].get("itemProcess"):
                                        processes_list = bom_list[idx]["itemProcess"]
                                        for process in processes_list:
                                            process_row = {}
                                            process_row["parent_item"] = (
                                                str(count)
                                                + " - "
                                                + str(d["bom"][0]["id"])
                                            )
                                            process_row["item_code"] = process[
                                                "processId"
                                            ]
                                            process_row["item_detail"] = process[
                                                "processId"
                                            ]
                                            process_row["qty"] = process["quantity"]
                                            process_row["item_width"] = process[
                                                "parameters"
                                            ]["width"]
                                            process_row["item_height"] = process[
                                                "parameters"
                                            ]["height"]
                                            doc.append("components", process_row)
                    count += 1
                doc.order_from_lisec = order_name
                doc.flags.ignore_mandatory = True
                doc.save(ignore_permissions=True)
                rtn_msg = f"Updated an existing Sales Order from LISEC API Data!"
        return f"Msg from Create Sales Order: {rtn_msg}, Msg from Create Lisec Log: {log_msg} "
    except:
        frappe.throw(
            f"Error occured while handling function of cration of sales order# {order['header']['orderNo']}"
        )


# -----------------------------------------------LISEC MATERIAL REQUEST LOGS---------------------------------------------------------
def create_mrq_log(order, map_vars):
    try:
        log_msg = ""
        if order:
            # It checks if already records exists, if not then it will create a new log record.
            log_exists = frappe.db.exists(
                "Lisec Logs",
                {
                    "customer_id": str(order["header"]["custNo"]),
                    "lisec_reference_no": str(order["header"]["orderNo"]),
                    "creation_date": order["header"]["creationDate"],
                },
            )
            if not log_exists:
                log_doc = frappe.new_doc("Lisec Logs")
                log_doc.customer_id = str(order["header"]["custNo"])
                log_doc.customer_address = order["header"]["customerAddress"]["name"]
                log_doc.lisec_reference_no = str(order["header"]["orderNo"])
                log_doc.creation_date = order["header"]["creationDate"]
                log_doc.project = order["header"]["project"]

                log_doc.log_items = []
                log_doc.components = []
                count = 1

                # Iterates through lisec orders

                for d in order["items"]:
                    if d["bom"]:  # Checks if the item has bom or not
                        item_row = {}
                        item_row["item_code"] = d["bom"][0]["id"]
                        item_row["item_name"] = d["bom"][0]["userDescription"]
                        item_row["rate"] = 0.0
                        item_row["qty"] = d["qty"]
                        item_row["height_mm"] = d["bom"][0]["itemGeometry"][
                            "rectHeight"
                        ]
                        item_row["width_mm"] = d["bom"][0]["itemGeometry"]["rectWidth"]
                        item_row["pcs"] = d["bom"][0]["itemGeometry"]["area"]
                        log_doc.append("log_items", item_row)

                log_msg = "Created new LISEC LOG records."
                log_doc.flags.ignore_mandatory = True
                log_doc.save(ignore_permissions=True)

            # if the lisec log records is already existing in the ERP
            else:
                log_name = frappe.db.get_value("Lisec Logs", log_exists)
                log_doc = frappe.get_doc("Lisec Logs", log_name)
                log_doc.customer_id = str(order["header"]["custNo"])
                log_doc.customer_address = order["header"]["customerAddress"]["name"]
                log_doc.lisec_reference_no = str(order["header"]["orderNo"])
                log_doc.creation_date = order["header"]["creationDate"]
                log_doc.project = order["header"]["project"]

                log_doc.log_items = []
                log_doc.components = []

                for d in order["items"]:
                    if d["bom"]:
                        item_row = {}
                        item_row["item_code"] = d["bom"][0]["id"]
                        item_row["item_name"] = d["bom"][0]["userDescription"]
                        item_row["rate"] = 0.0
                        item_row["qty"] = d["qty"]
                        item_row["height_mm"] = d["bom"][0]["itemGeometry"][
                            "rectHeight"
                        ]
                        item_row["width_mm"] = d["bom"][0]["itemGeometry"]["rectWidth"]
                        item_row["pcs"] = d["bom"][0]["itemGeometry"]["area"]
                        log_doc.append("log_items", item_row)

                log_msg = "Overwrote LISEC LOG records."
                log_doc.flags.ignore_mandatory = True
                log_doc.save(ignore_permissions=True)
        return log_msg
    except:
        frappe.throw(
            f"Error occured while handling function of cration of Lisec Log for order# {order['header']['orderNo']}"
        )


# -----------------------------------------------MATERIAL REQUEST---------------------------------------------------------
def check_sales_order_approval(sales_doc):
    """Check if sales order is approved based on workflow state or document status"""
    try:
        # First check if workflow state field exists
        if hasattr(sales_doc, 'workflow_state'):
            return sales_doc.docstatus == 1 and sales_doc.workflow_state == 'Approve Order'
        
        # If no workflow state, just check if submitted
        return sales_doc.docstatus == 1
        
    except Exception as e:
        frappe.log_error(
            message=f"Error checking sales order approval: {str(e)}\n{frappe.get_traceback()}",
            title=f"LISEC Sales Order Check Error - {sales_doc.name}"
        )
        return False

def create_material_requests(order, map_vars):
    try:
        rtn_msg = "Just entered in material requests creation function"
        log_msg = "Log msg initial."
        pending_sales_order = None

        if order:
            # Calls function to create LISEC Log record
            log_msg = create_mrq_log(order, map_vars)

            order_name = f"{order['header']['custNo']}-{order['header']['orderNo']}-{order['header']['creationDate']}"  # Unique sales order no
            lisec_order_exist = frappe.db.exists(
                "Material Request",
                {"order_from_lisec": order_name, "docstatus": ["!=", 2]},
            )

            # It checks if already records exists, if not then it will create a new Sales Order in ERP.
            department = frappe.db.get_list(
                "Department",
                pluck="name",
            )
            cost_center = frappe.db.get_list(
                "Cost Center",
                pluck="name",
            )
            sales_order = frappe.db.get_list(
                "Sales Order",
                pluck="name",
            )
            project = frappe.db.get_list(
                "Project",
                pluck="name",
            )

        
            warehouse = frappe.db.get_value('Warehouse', {'custom_lisec_warehouse_id': order["header"]["delivStockId"]}, "name") if order["header"]["delivStockId"] else None 

            if not lisec_order_exist:
                if order["header"]["custOrdNo"] and (order["header"]["custOrdNo"] in sales_order):
                    sales_doc =  frappe.get_doc('Sales Order', order["header"]["custOrdNo"])
                    if check_sales_order_approval(sales_doc):
                        doc = frappe.new_doc("Material Request")
                        doc.material_request_type = "Manufacture"
                        doc.transaction_date = order["header"]["creationDate"]
                        doc.customer = str(order["header"]["custNo"])
                        doc.customer_order_no = str(order["header"]["custOrdNo"])
                        doc.schedule_date = order["header"]["deliveryInfo"]["deliveryDate"]
                        doc.sales_order_id = str(order["header"]["custOrdNo"])
                        if (order["header"]["project"]) and (
                            order["header"]["project"] in project
                        ):
                            doc.project = order["header"]["project"]
                        if (order["header"]["origin"]["externalReference"]) and (
                            order["header"]["origin"]["externalReference"] in cost_center
                        ):
                            doc.cost_center = order["header"]["origin"]["externalReference"]
                        else:
                            doc.cost_center = "Archi - IG"

                        if (order["header"]["origin"]["additionalInfo"]) and (
                            order["header"]["origin"]["additionalInfo"] in department
                        ):
                            doc.department = order["header"]["origin"]["additionalInfo"]
                        else:
                            doc.department = "HQ-ARCHI - IG"
                        doc.set_warehouse = warehouse

                        doc.lisec_order_id = order["header"]["orderNo"]
                        doc.items = []
                        for d in order["items"]:
                            if d["bom"]:
                                item_row = {
                                    "item_code": str(d["bom"][0]["id"]),
                                    "item_name": d["bom"][0]["userDescription"],
                                    "qty": (
                                        d["bom"][0]["itemGeometry"]["rectHeight"]
                                        * d["bom"][0]["itemGeometry"]["rectWidth"]
                                    )
                                    * d["qty"]
                                    / 1000000,
                                    "uom": "Square Meter",
                                    "stock_uom": "Square Meter",
                                    "height": d["bom"][0]["itemGeometry"]["rectHeight"],
                                    "width": d["bom"][0]["itemGeometry"]["rectWidth"],
                                    "pcs": d["qty"],
                                    "warehouse": warehouse,
                                    "schedule_date": order["header"]["deliveryInfo"][
                                        "deliveryDate"
                                    ],
                                    "project_unit": str(d["origin"]["externalReference"])
                                    or "None",
                                    "project_activity": "Glass",
                                    "unit_secession": str(d["origin"]["additionalInfo"])
                                    or "None",
                                }
                                doc.append("items", item_row)
                        doc.order_from_lisec = order_name
                        doc.flags.ignore_mandatory = True
                        doc.save(ignore_permissions=True)
                        
                        log_doc_name = frappe.db.get_value(
                            "Lisec Logs",
                            {
                                "customer_id": str(order["header"]["custNo"]),
                                "lisec_reference_no": str(order["header"]["orderNo"]),
                                "creation_date": order["header"]["creationDate"],
                            },
                            "name",
                        )
                        if log_doc_name:
                            log_doc = frappe.get_doc("Lisec Logs", log_doc_name)
                            log_doc.mr_no = doc.name
                            log_doc.mr_status = doc.status
                            log_doc.flags.ignore_mandatory = True
                            log_doc.save(ignore_permissions=True)
                        

                        """ Call this script for auto submission of material request if it has BOM else send email"""
                        all_has_bom = []
                        for item in doc.items:
                            if item.bom_no is not None:
                                all_has_bom.append(True)
                            else:
                                all_has_bom.append(False)

                        if doc.material_request_type=='Manufacture':
                            if False in all_has_bom:
                                frappe.sendmail(
                                        recipients = [frappe.db.get_value('Lisec Integration Tool', 'Lisec Integration Tool', 'no_bom_email_recipient')],
                                        subject = f'Material Request with Lisec Order ID {doc.lisec_order_id} has no BOM.',
                                        message = f'The Material Request with LISEC Order No. {doc.lisec_order_id} against Sales Order ID. {doc.sales_order_id} could not be created because of no BOM defined for any or some of the items.'
                                    )
                            else:
                                try:
                                    doc.submit()
                                except Exception as e:
                                    error_message = frappe.get_traceback()+"\n"+str(e)
                                    error_title = f"Material Request {doc.name} creation/submission error!"
                                    frappe.log_error(error_message, error_title)


                        rtn_msg = f"Created new Material Requests from LISEC API Data!"

                    else:
                        pending_sales_order = str(order["header"]["custOrdNo"])
                else:
                    doc = frappe.new_doc("Material Request")
                    doc.material_request_type = "Manufacture"
                    doc.transaction_date = order["header"]["creationDate"]
                    doc.customer = str(order["header"]["custNo"])
                    doc.customer_order_no = str(order["header"]["custOrdNo"])
                    doc.schedule_date = order["header"]["deliveryInfo"]["deliveryDate"]
                    
                    if (order["header"]["project"]) and (
                        order["header"]["project"] in project
                    ):
                        doc.project = order["header"]["project"]
                    if (order["header"]["origin"]["externalReference"]) and (
                        order["header"]["origin"]["externalReference"] in cost_center
                    ):
                        doc.cost_center = order["header"]["origin"]["externalReference"]
                    else:
                        doc.cost_center = "Archi - IG"

                    if (order["header"]["origin"]["additionalInfo"]) and (
                        order["header"]["origin"]["additionalInfo"] in department
                    ):
                        doc.department = order["header"]["origin"]["additionalInfo"]
                    else:
                        doc.department = "HQ-ARCHI - IG"
                    doc.set_warehouse = warehouse

                    doc.lisec_order_id = order["header"]["orderNo"]
                    doc.items = []
                    for d in order["items"]:
                        if d["bom"]:
                            item_row = {
                                "item_code": str(d["bom"][0]["id"]),
                                "item_name": d["bom"][0]["userDescription"],
                                "qty": (
                                    d["bom"][0]["itemGeometry"]["rectHeight"]
                                    * d["bom"][0]["itemGeometry"]["rectWidth"]
                                )
                                * d["qty"]
                                / 1000000,
                                "uom": "Square Meter",
                                "stock_uom": "Square Meter",
                                "height": d["bom"][0]["itemGeometry"]["rectHeight"],
                                "width": d["bom"][0]["itemGeometry"]["rectWidth"],
                                "pcs": d["qty"],
                                "warehouse": warehouse,
                                "schedule_date": order["header"]["deliveryInfo"][
                                    "deliveryDate"
                                ],
                                "project_unit": str(d["origin"]["externalReference"])
                                or "None",
                                "project_activity": "Glass",
                                "unit_secession": str(d["origin"]["additionalInfo"])
                                or "None",
                            }
                            doc.append("items", item_row)
                    doc.order_from_lisec = order_name
                    doc.flags.ignore_mandatory = True
                    doc.save(ignore_permissions=True)
                    
                    log_doc_name = frappe.db.get_value(
                        "Lisec Logs",
                        {
                            "customer_id": str(order["header"]["custNo"]),
                            "lisec_reference_no": str(order["header"]["orderNo"]),
                            "creation_date": order["header"]["creationDate"],
                        },
                        "name",
                    )
                    if log_doc_name:
                        log_doc = frappe.get_doc("Lisec Logs", log_doc_name)
                        log_doc.mr_no = doc.name
                        log_doc.mr_status = doc.status
                        log_doc.flags.ignore_mandatory = True
                        log_doc.save(ignore_permissions=True)
                    

                    """ Call this script for auto submission of material request if it has BOM else send email"""
                    all_has_bom = []
                    for item in doc.items:
                        if item.bom_no is not None:
                            all_has_bom.append(True)
                        else:
                            all_has_bom.append(False)

                    if doc.material_request_type=='Manufacture':
                        if False in all_has_bom:
                            frappe.sendmail(
                                    recipients = [frappe.db.get_value('Lisec Integration Tool', 'Lisec Integration Tool', 'no_bom_email_recipient')],
                                    subject = f'Material Request with Lisec Order ID {doc.lisec_order_id} has no BOM.',
                                    message = f'The Material Request with LISEC Order No. {doc.lisec_order_id} against Sales Order ID. {doc.sales_order_id} could not be created because of no BOM defined for any or some of the items.'
                                )
                        else:
                            try:
                                doc.submit()
                            except Exception as e:
                                error_message = frappe.get_traceback()+"\n"+str(e)
                                error_title = f"Material Request {doc.name} creation/submission error!"
                                frappe.log_error(error_message, error_title)


                    rtn_msg = f"Created new Material Requests from LISEC API Data!"


            else:
                record_name = frappe.db.get_value(
                    "Material Request",
                    {"order_from_lisec": order_name, "docstatus": ["!=", 2]},
                    "name",
                )

                if order["header"]["custOrdNo"] and (order["header"]["custOrdNo"] in sales_order):
                    sales_doc =  frappe.get_doc('Sales Order', order["header"]["custOrdNo"])
                    if check_sales_order_approval(sales_doc):
                        doc = frappe.get_doc("Material Request", record_name)

                        doc.material_request_type = "Manufacture"
                        doc.transaction_date = order["header"]["creationDate"]
                        doc.customer = str(order["header"]["custNo"])
                        doc.customer_order_no = str(order["header"]["custOrdNo"])
                        doc.schedule_date = order["header"]["deliveryInfo"]["deliveryDate"]
                        if (order["header"]["project"]) and (
                            order["header"]["project"] in project
                        ):
                            doc.project = order["header"]["project"]
                        if (order["header"]["origin"]["externalReference"]) and (
                            order["header"]["origin"]["externalReference"] in cost_center
                        ):
                            doc.cost_center = order["header"]["origin"]["externalReference"]
                        else:
                            doc.cost_center = "Archi - IG"

                        if (order["header"]["origin"]["additionalInfo"]) and (
                            order["header"]["origin"]["additionalInfo"] in department
                        ):
                            doc.department = order["header"]["origin"]["additionalInfo"]
                        else:
                            doc.department = "HQ-ARCHI - IG"

                        doc.warehouse = warehouse
                        doc.lisec_order_id = order["header"]["orderNo"]
                        doc.items = []
                        for d in order["items"]:
                            if d["bom"]:
                                item_row = {
                                    "item_code": str(d["bom"][0]["id"]),
                                    "item_name": d["bom"][0]["userDescription"],
                                    "qty": (
                                        d["bom"][0]["itemGeometry"]["rectHeight"]
                                        * d["bom"][0]["itemGeometry"]["rectWidth"]
                                    )
                                    * d["qty"]
                                    / 1000000,
                                    "uom": "Square Meter",
                                    "stock_uom": "Square Meter",
                                    "height": d["bom"][0]["itemGeometry"]["rectHeight"],
                                    "width": d["bom"][0]["itemGeometry"]["rectWidth"],
                                    "pcs": d["qty"],
                                    "warehouse": warehouse,
                                    "schedule_date": order["header"]["deliveryInfo"][
                                        "deliveryDate"
                                    ],
                                    "project_unit": str(d["origin"]["externalReference"])
                                    or "None",
                                    "project_activity": "Glass",
                                    "unit_secession": str(d["origin"]["additionalInfo"])
                                    or "None",
                                }
                                doc.append("items", item_row)
                        doc.order_from_lisec = order_name
                        doc.flags.ignore_mandatory = True
                        doc.save(ignore_permissions=True)
                        
                        log_doc_name = frappe.db.get_value(
                            "Lisec Logs",
                            {
                                "customer_id": str(order["header"]["custNo"]),
                                "lisec_reference_no": str(order["header"]["orderNo"]),
                                "creation_date": order["header"]["creationDate"],
                            },
                            "name",
                        )
                        if log_doc_name:
                            log_doc = frappe.get_doc("Lisec Logs", log_doc_name)
                            log_doc.mr_no = doc.name
                            log_doc.mr_status = doc.status
                            log_doc.flags.ignore_mandatory = True
                            log_doc.save(ignore_permissions=True)


                        """ Call this script for auto submission of material request if it has BOM else send email"""
                        all_has_bom = []
                        for item in doc.items:
                            if item.bom_no is not None:
                                all_has_bom.append(True)
                            else:
                                all_has_bom.append(False)

                        if doc.material_request_type=='Manufacture':
                            if False in all_has_bom:
                                frappe.sendmail(
                                        recipients = [frappe.db.get_value('Lisec Integration Tool', 'Lisec Integration Tool', 'no_bom_email_recipient')],
                                        subject = f'Material Request with Lisec Order ID {doc.lisec_order_id} has no BOM.',
                                        message = f'The Material Request with LISEC Order No. {doc.lisec_order_id} against Sales Order ID. {doc.sales_order_id} could not be created because of no BOM defined for any or some of the items.'
                                    )
                            else:
                                try:
                                    doc.submit()
                                except Exception as e:
                                    error_message = frappe.get_traceback()+"\n"+str(e)
                                    error_title = f"Material Request {doc.name} creation/submission error!"
                                    frappe.log_error(error_message, error_title)
                        
                        rtn_msg = f"Updated an existing Sales Order from LISEC API Data!"
                    else:
                        pending_sales_order = str(order["header"]["custOrdNo"])
                
                else:
                    doc = frappe.get_doc("Material Request", record_name)
                    doc.material_request_type = "Manufacture"
                    doc.transaction_date = order["header"]["creationDate"]
                    doc.customer = str(order["header"]["custNo"])
                    doc.customer_order_no = str(order["header"]["custOrdNo"])
                    doc.schedule_date = order["header"]["deliveryInfo"]["deliveryDate"]
                    if (order["header"]["project"]) and (
                        order["header"]["project"] in project
                    ):
                        doc.project = order["header"]["project"]
                    if (order["header"]["origin"]["externalReference"]) and (
                        order["header"]["origin"]["externalReference"] in cost_center
                    ):
                        doc.cost_center = order["header"]["origin"]["externalReference"]
                    else:
                        doc.cost_center = "Archi - IG"

                    if (order["header"]["origin"]["additionalInfo"]) and (
                        order["header"]["origin"]["additionalInfo"] in department
                    ):
                        doc.department = order["header"]["origin"]["additionalInfo"]
                    else:
                        doc.department = "HQ-ARCHI - IG"

                    doc.warehouse = warehouse
                    doc.lisec_order_id = order["header"]["orderNo"]
                    doc.items = []
                    for d in order["items"]:
                        if d["bom"]:
                            item_row = {
                                "item_code": str(d["bom"][0]["id"]),
                                "item_name": d["bom"][0]["userDescription"],
                                "qty": (
                                    d["bom"][0]["itemGeometry"]["rectHeight"]
                                    * d["bom"][0]["itemGeometry"]["rectWidth"]
                                )
                                * d["qty"]
                                / 1000000,
                                "uom": "Square Meter",
                                "stock_uom": "Square Meter",
                                "height": d["bom"][0]["itemGeometry"]["rectHeight"],
                                "width": d["bom"][0]["itemGeometry"]["rectWidth"],
                                "pcs": d["qty"],
                                "warehouse": warehouse,
                                "schedule_date": order["header"]["deliveryInfo"][
                                    "deliveryDate"
                                ],
                                "project_unit": str(d["origin"]["externalReference"])
                                or "None",
                                "project_activity": "Glass",
                                "unit_secession": str(d["origin"]["additionalInfo"])
                                or "None",
                            }
                            doc.append("items", item_row)
                    doc.order_from_lisec = order_name
                    doc.flags.ignore_mandatory = True
                    doc.save(ignore_permissions=True)
                    
                    log_doc_name = frappe.db.get_value(
                        "Lisec Logs",
                        {
                            "customer_id": str(order["header"]["custNo"]),
                            "lisec_reference_no": str(order["header"]["orderNo"]),
                            "creation_date": order["header"]["creationDate"],
                        },
                        "name",
                    )
                    if log_doc_name:
                        log_doc = frappe.get_doc("Lisec Logs", log_doc_name)
                        log_doc.mr_no = doc.name
                        log_doc.mr_status = doc.status
                        log_doc.flags.ignore_mandatory = True
                        log_doc.save(ignore_permissions=True)


                    """ Call this script for auto submission of material request if it has BOM else send email"""
                    all_has_bom = []
                    for item in doc.items:
                        if item.bom_no is not None:
                            all_has_bom.append(True)
                        else:
                            all_has_bom.append(False)

                    if doc.material_request_type=='Manufacture':
                        if False in all_has_bom:
                            frappe.sendmail(
                                    recipients = [frappe.db.get_value('Lisec Integration Tool', 'Lisec Integration Tool', 'no_bom_email_recipient')],
                                    subject = f'Material Request with Lisec Order ID {doc.lisec_order_id} has no BOM.',
                                    message = f'The Material Request with LISEC Order No. {doc.lisec_order_id} against Sales Order ID. {doc.sales_order_id} could not be created because of no BOM defined for any or some of the items.'
                                )
                        else:
                            try:
                                doc.submit()
                            except Exception as e:
                                error_message = frappe.get_traceback()+"\n"+str(e)
                                error_title = f"Material Request {doc.name} creation/submission error!"
                                frappe.log_error(error_message, error_title)
                    
                    rtn_msg = f"Updated an existing Sales Order from LISEC API Data!"      
        # return f"Msg from Create Material Requests: {rtn_msg}, Msg from Create Lisec Log: {log_msg} "
        return rtn_msg, pending_sales_order

    except Exception as e:
        error_msg = f"Error in create_material_requests: {str(e)}\n{frappe.get_traceback()}"
        frappe.log_error(message=error_msg, title=f"LISEC MR Creation Error")
        return f"Error: {str(e)}", None


# ---------------------------------------------------


@frappe.whitelist(allow_guest=True)
def get_lisec_data(limit, offset, start_date, end_date):
    init_module()
    lisec_history_job_scheduler()
    if get_access_token():
        orders = get_list_orders(start_date)
        orders_list = ""
        for d in orders:
            orders_list += f"""OrderNo: {cstr(d['header']['orderNo'])} , orderType: {cstr(d['header']['orderType'])}, custNo: {cstr(d['header']['custNo'])}, custOrdNo: {d["header"]["custOrdNo"]}\n"""
        doc = frappe.get_doc("Lisec Integration Tool")
        doc.lisec_response = str(orders_list)
        doc.flags.ignore_mandatory = True
        doc.save(ignore_permissions=True)
        doc.reload()
        return "Success in getting orders list."
    else:
        return "Could not get the response. May be authentication trouble."


# --- main() -------------------------------------
@frappe.whitelist(allow_guest=True)
def main():
    init_module()

    if get_access_token():
        orders = get_list_orders(getdate())
        map_vars = frappe.get_doc(
            "Lisec Integration Tool"
        )  # This gets all field values of LISEC INTEGRATION TOOL single doc
        
        return_msg = ""
        pending_sales_orders = ""
        sales_orders_are_pending =  False
        for order in orders:
            if order:
                # create_items(order)
                try:
                    resp = create_material_requests(order, map_vars)
                    if resp[1] is not None:
                        pending_sales_orders += str(resp[1])+"\n"
                except:
                    frappe.log_error(frappe.get_traceback(), "LISEC Error")
                    frappe.throw(f"Error occured while creating material request.")
        if pending_sales_orders not in (None, ""):
            sales_orders_are_pending = True
        if sales_orders_are_pending:
            generate_notification_for_pending_orders(pending_sales_orders=pending_sales_orders)
        return "Successful access"
    else:
        return "access failed!"


# --- on manual call from LISEC Integration Tool UI -------------------------------------
@frappe.whitelist(allow_guest=True)
def main_manual(order_id):
    init_module()
    if get_access_token():
        order = get_order_details(order_id)
        map_vars = frappe.get_doc(
            "Lisec Integration Tool"
        )  # This gets all field values of LISEC INTEGRATION TOOL single doc
        
        return_msg = ""
        pending_sales_orders = ""
        sales_orders_are_pending =  False
        if order:
            # create_items(order) 
            try:
                resp = create_material_requests(order, map_vars)
                if resp[1] is not None:
                    pending_sales_orders += str(resp[1])+"\n"
            except:
                frappe.log_error(frappe.get_traceback(), "LISEC Error")
                frappe.throw(f"Error occured while creating material request.")

        if pending_sales_orders not in (None, ""):
            sales_orders_are_pending = True

        if sales_orders_are_pending:
            generate_notification_for_pending_orders(pending_sales_orders=pending_sales_orders)
        return "Successful access"
    else:
        return "access failed!"






def generate_notification_for_pending_orders(pending_sales_orders=None):
    manufacturing_users = frappe.db.sql("""
        SELECT 
            u.email, u.name
            FROM `tabUser` u
            INNER JOIN `tabHas Role` hr ON u.name = hr.parent
            WHERE u.enabled=1 and hr.role in ('Manufacturing Notifications')
        """, as_dict=True)

    recipients = []
    message = frappe._(f"Following orders are not yet approved so LISEC wasn't allowed create MRs:\n{pending_sales_orders}")
    
    for d in manufacturing_users:
        doc = frappe.get_doc({
            'doctype': 'Notification Log',
            'subject': f'LISEC Pending Material Requests for orders: {pending_sales_orders}',
            'email_content': message,
            'from_user': 'noman.maimoon@impala.co.ke',
            'for_user': d.email,
            'read': 0,
            'document_type': "Lisec Integration Tool",
            'document_name': "Lisec Integration Tool"
            })

        doc.insert(ignore_permissions=True)
        # publish_realtime('notification', message=message, user=d.email)
        publish_realtime('msgprint', message=message, user=d.name)
    return 'notification published.'
# ------------------------------------------------


def get_history_list_orders(limit=None, status_code=53, mins=5):
    # print("- Get history list of orders")
    currentTimeDate = datetime.strptime(str(now()), "%Y-%m-%d %H:%M:%S.%f") - timedelta(
        minutes=mins
    )
    currentTime = str(datetime.strptime(str(currentTimeDate), "%Y-%m-%d %H:%M:%S.%f"))
    currentTime = currentTime.split(".")
    currentTime = currentTime[0].replace(" ", "T")
    # frappe.msgprint(str(currentTime))
    url = (
        f"/orders/status?filter=statusCodeId=={status_code};modified=ge='{currentTime}'"
    )
    auth = "Bearer {}".format(api_access_token)
    req_header = {"Authorization": auth, "Content-Type": "application/json"}
    resp = requests.get(base_url + url, headers=req_header, verify=False)
    if resp.status_code == 200:
        history = resp.json()
        # Create a shorter log message
        log_msg = f"History retrieved for status {status_code}"
        frappe.log_error(message=f"{log_msg}\nFull URL: {base_url}{url}\nResponse: {str(history)}", title="LISEC History Response")
    else:
        history = []
        frappe.log_error(message="No history found in LISEC response", title="LISEC Empty History")

    return history


# ------------------------------------------------


@frappe.whitelist(allow_guest=True)
def history_main():
    init_module()
    try:
        if get_access_token():
            status_code_from_doc = frappe.db.get_single_value(
                "Lisec Integration Tool", "lisec_get_past_order_statuscodeid"
            )
            mins_from_doc = frappe.db.get_single_value(
                "Lisec Integration Tool", "lisec_get_past_order_mins"
            )

            details = get_history_list_orders(
                status_code=status_code_from_doc, mins=mins_from_doc
            )

            for det in details:
                if det.get("orderNo"):
                    order = get_order_details(det.get("orderNo"))
                    if order:
                        map_vars = frappe.get_doc("Lisec Integration Tool")
                        try:
                            create_material_requests(order, map_vars)
                        except Exception as e:
                            # Create a more concise error log
                            error_msg = f"MR Creation Failed - Order {det.get('orderNo')}"
                            frappe.log_error(
                                message=f"Error details: {str(e)}",
                                title=error_msg
                            )
            return "Successful access"
        else:
            return "access failed!"
    except Exception as e:
        # Create a concise error log for the main function
        frappe.log_error(
            message=f"History main function error: {str(e)}",
            title="LISEC History Main Error"
        )
        frappe.throw("Error occurred while handling history_main function.")


""" 
LISEC POSTMAN URLS
GET A LIST OF ORDERS:

{{baseUrl}}/orders

with filters upto 5 orders limit

{{baseUrl}}/orders?limit=5&offset=5&filter=header.orderNo==1&sort_by==header.orderNo

"""
