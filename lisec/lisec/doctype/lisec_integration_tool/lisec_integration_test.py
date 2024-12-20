import json,requests

host     = "41.215.78.100"
port     = "17800"
site     = "IMPALA"
base_url = "https://{}:{}/api/sites/{}/versions/1".format( host, port, site )

api_access_token  = ""
api_refresh_token = "c6ad588b81104149a04addb0fb288e6f4bc731c1c5d24042a7b825afddc0de5d"
api_user          = "lisec"
api_password_hash = "DRAlTSFGd0vTlU7bn5uyIQrcOerXYjQ3jMQFlbkyouoG1Ek+aX5+wPKalYldOwjT9ABgCsXfTy375tQgo9Pe8w=="

# ------------------------------------------------

def init_module():
    requests.packages.urllib3.disable_warnings()

# ------------------------------------------------

def refresh_access_token():

    if api_refresh_token == "":
        print( "- api refresh token not set, can't authenticate using refresh token" )
        return False;

    url        = base_url + "/authentication/tokens"
    req_header = { 'refreshTokenHeader' : api_refresh_token };

    resp = requests.put( url, headers=req_header, verify=False )

    if resp.status_code == 200:
        global api_access_token 
        api_access_token = resp.text
        print( "- api access token refresh succesul, new access token set" )
        return True
    else:
        print( "- api token refresh failed:" )
        print( "  Status:", resp.status_code, '-', resp.reason )
        return False

# ------------------------------------------------

def get_new_access_token():
    if api_user == "" or api_password_hash == "":
        print( "- api_user and/or api_password_hash not set, can't authenticate using user and password" )
        return False

    url        = base_url + "/authentication/tokens"
    req_header = { 'userHeader' : api_user, 'passwordHeader' : api_password_hash };

    resp = requests.post( url, headers=req_header, verify=False )

    if resp.status_code == 200:
        result = resp.json()

        global api_access_token
        api_access_token  = resp.json()['accessToken']

        print( "- Authentication via user/password successful " )
        print( "  Please update/set 'api_refresh_token' field to authenticate via refresh token for improved security" )
        print( "  New refresh token:", resp.json()['refreshToken'] )
        print( "" )
        input( "Press Enter to continue..." )

        return True
    else:
        print( "- Authentication via user/password failed:" )
        print( "  Status:", resp.status_code, '-', resp.reason )
        return False

# ------------------------------------------------

def get_access_token():

    if refresh_access_token() == False:
        if get_new_access_token() == False:
            print( "ERROR: all authentication methods failed, can't continue" )
            return False

    return True
# ------------------------------------------------
def get_list_orders(limit=None):
    print( "- Get list of orders")
    url = "/orders?limit=1000&offset=1"
    auth       = "Bearer {}".format(api_access_token)
    req_header = { 'Authorization' : auth, 'Content-Type' : 'application/json' }

    resp = requests.get( base_url + url, headers=req_header, verify=False)

    if resp.status_code == 200:
        print( "Orders list:" )
        print( json.dumps(resp.json(),indent=2) )
    print(f"orders list api {resp.status_code}")
    orders = resp.json()
    customers = []
    ordertypes = []
    ordersList = []
    projects = []
    customer_address = []
    items = []
    qtys = []
    uoms = []
    for d in orders:
        ordersList.append(d['header']['orderNo'])
        customers.append(d['header']['custNo'])
        ordertypes.append(d['header']['orderType'])
        projects.append(d['header']['project'])
        customer_address.append(d['header']['customerAddress']['name'])
        for item in d['items']:
            items.append(item['itemNo'])
            uoms.append(item['qtyUom'])
            qtys.append(item['qty'])
    
    print(f"<h1>ORDERS: </h1> {ordersList}")
    # print(f"customers {customers}")
    # print(f"orderTypes: {ordertypes}")
    # print(f"projects {projects}")
    # print(f"customer addresses {customer_address}"  )
    # print(f"items {items}")
    # print(f"item qty {qtys}")
    # print(f"qtyuoms {uoms}")
# ------------------------------------------------

def get_item_details( order_no, item_no ):
    print( "- Get item details for Order/Item ", order_no, "/", item_no )

    url = "/orders/{}/items/{}".format( order_no, item_no )
    auth       = "Bearer {}".format(api_access_token)
    req_header = { 'Authorization' : auth, 'Content-Type' : 'application/json' }

    resp = requests.get( base_url + url, headers=req_header, verify=False)

    print( "  GET '{base_url}" + url + "':" )
    print( "" )
    print( "  Status:", resp.status_code, '-', resp.reason )
    print( "" )

    if resp.status_code == 200:
        print( "ITEM DETAILS:" )
        print( json.dumps(resp.json(),indent=2) )



# ---------------------------------------------------

def get_order_header_details(order_id):
    print("Get order header details for Order ", order_id)

    url = "/orders/{}/header".format(order_id)
    
    auth       = "Bearer {}".format(api_access_token)
    req_header = { 'Authorization' : auth, 'Content-Type' : 'application/json' }

    resp = requests.get( base_url + url, headers=req_header, verify=False)

    print( "  GET '{base_url}" + url + "':" )
    print( "" )
    print( "  Status:", resp.status_code, '-', resp.reason )
    print( "" )

    if resp.status_code == 200:
        print( "Order header details:" )
        # print( json.dumps(resp.json(),indent=2) )
        resp = resp.text
        print(resp)
        print(json.loads(resp))
        # print(resp.json())

def get_order_details(order_id):
    print("Get order details for Order ", order_id)

    url = "/orders/{}".format(order_id)
    
    auth       = "Bearer {}".format(api_access_token)
    req_header = { 'Authorization' : auth, 'Content-Type' : 'application/json' }

    resp = requests.get( base_url + url, headers=req_header, verify=False)

    print( "  GET '{base_url}" + url + "':" )
    print( "" )
    print( "  Status:", resp.status_code, '-', resp.reason )
    print( "" )

    if resp.status_code == 200:
        print( "Order details:" )
        # print( json.dumps(resp.json(),indent=2) )
        resp = resp.text
        print(resp)
        print(json.loads(resp))
        # print(resp.json())

# --- main() -------------------------------------

init_module()

if get_access_token():
    # get_list_orders()
    get_order_details(6002239) #other orders numbers are: 1087767, 195702, 195703, 195704
    # get_order_header_details(195699)
    # get_item_details( 195687, 1 )

