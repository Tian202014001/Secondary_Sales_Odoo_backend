import sys
import json
import requests
sys.path.append('/home/abrar/odoo/odoo_18/odoo')
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', '/home/abrar/odoo/odoo_18/odoo.conf'])
db_name = "ss"
registry = odoo.modules.registry.Registry(db_name)

mobile_user_login = ""

# 1. Reset password of mobile user associated with Abigail Peterson
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    employee = env["hr.employee"].browse(6) # Abigail Peterson
    
    mobile_user = env["res.mobile.user"].search([("employee_id", "=", employee.id)], limit=1)
    if not mobile_user:
        mobile_user = env["res.mobile.user"].create({
            "name": "Abigail Peterson Test User",
            "phone": "1234567890",
            "email": "abigail@test.com",
            "password": "password123",
            "employee_id": employee.id,
        })
        cr.commit()
        print(f"Created mobile user: {mobile_user.name}")
    else:
        print(f"Found mobile user: {mobile_user.name}")
        mobile_user.password = "password123"
        cr.commit()
        print(f"Reset password for mobile user {mobile_user.name} to 'password123'")
        
    mobile_user_login = mobile_user.phone or mobile_user.email
    print(f"Using login: {mobile_user_login}")

# 2. Authenticate and call business APIs via HTTP Session
BASE_URL = "http://localhost:8069"
s = requests.Session()

print("\n=== AUTHENTICATING ===")
login_payload = {
    "db": db_name,
    "login": mobile_user_login,
    "password": "password123",
    "device_id": "test-device-python"
}
res_login = s.post(f"{BASE_URL}/api/v1/auth/login", json=login_payload)
print("Login Status:", res_login.status_code)
login_data = res_login.json()
print("Login Response:", json.dumps(login_data, indent=2))

access_token = login_data.get("access_token")
if not access_token:
    print("Authentication failed!")
    sys.exit(1)

# Add authorization header to session
s.headers.update({
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
})

# --- A. Product List API ---
print("\n=== A. TESTING PRODUCT LIST API ===")
product_list_payload = {
    "jsonrpc": "2.0",
    "params": {
        "van_operation_type": "unload",
        "destination_location_id": 38
    }
}
res = s.post(f"{BASE_URL}/api/v1/virtual-transfers/products", json=product_list_payload)
print("Status Code:", res.status_code)
print("Response:", json.dumps(res.json(), indent=2))

# Let's parse products from response
res_data = res.json().get("result", {})
products = res_data.get("products", [])
desk_product = next((p for p in products if p["id"] == 46), None)
cable_product = next((p for p in products if p["id"] == 44), None)

print(f"\nDesk Product Info: {desk_product}")
print(f"Cable Product Info: {cable_product}")

# --- B. Lot List API ---
print("\n=== B. TESTING LOT LIST API ===")
lot_list_payload = {
    "jsonrpc": "2.0",
    "params": {
        "van_operation_type": "unload",
        "destination_location_id": 38
    }
}
res_lot = s.post(f"{BASE_URL}/api/v1/virtual-transfers/products/44/lots", json=lot_list_payload)
print("Status Code:", res_lot.status_code)
print("Response:", json.dumps(res_lot.json(), indent=2))

# --- C. Create Virtual Unload Transfer ---
print("\n=== C. TESTING CREATE VIRTUAL UNLOAD TRANSFER ===")
create_payload = {
    "jsonrpc": "2.0",
    "params": {
        "van_operation_type": "unload",
        "destination_location_id": 38,
        "lines": [
            {
                "product_id": 46, # Customizable Desk (untracked)
                "fresh_qty": 3.0,
                "scrap_qty": 1.0
            },
            {
                "product_id": 44, # Cable Management Box (tracked by lot)
                "fresh_qty": 4.0,
                "scrap_qty": 2.0,
                "lot_lines": [
                    {
                        "lot_id": 3, # CM-BOX-00001
                        "fresh_qty": 4.0,
                        "scrap_qty": 2.0
                    }
                ]
            }
        ]
    }
}
res_create = s.post(f"{BASE_URL}/api/v1/virtual-transfers/create", json=create_payload)
print("Status Code:", res_create.status_code)
print("Response:", json.dumps(res_create.json(), indent=2))

created_transfer = res_create.json().get("result", {}).get("data", {})
transfer_id = created_transfer.get("id")

if transfer_id:
    # --- D. Validate Virtual Unload Transfer ---
    print(f"\n=== D. TESTING VALIDATE VIRTUAL UNLOAD TRANSFER (ID: {transfer_id}) ===")
    action_payload = {
        "jsonrpc": "2.0",
        "params": {
            "action": "validate"
        }
    }
    res_validate = s.post(f"{BASE_URL}/api/v1/virtual-transfers/{transfer_id}/action", json=action_payload)
    print("Status Code:", res_validate.status_code)
    print("Response:", json.dumps(res_validate.json(), indent=2))
    
    # Let's inspect the database states of the created pickings
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        picking = env["stock.picking"].browse(transfer_id)
        print(f"\n=== POST-VALIDATION CHECK ===")
        print(f"Unload Picking: {picking.name}")
        print(f"  State: {picking.state}")
        print(f"  Source Location: {picking.location_id.name}")
        print(f"  Dest Location: {picking.location_dest_id.name}")
        
        # Check moves
        for move in picking.move_ids:
            print(f"  Move Product: {move.product_id.display_name}")
            print(f"    State: {move.state}")
            print(f"    Demand: {move.product_uom_qty}")
            print(f"    Scrap Qty field: {move.ss_scrap_qty}")
            for ml in move.move_line_ids:
                print(f"    Move Line Lot: {ml.lot_id.name if ml.lot_id else 'None'}")
                print(f"      Qty Done: {ml.quantity}")
                print(f"      Scrap Qty Done: {ml.ss_scrap_qty}")
                
        # Find auto scrap picking
        scrap_picking = env["stock.picking"].search([
            ("origin", "=", f"Auto Scrap for {picking.name}")
        ])
        if scrap_picking:
            print(f"\nAuto Scrap Picking found: {scrap_picking.name}")
            print(f"  State: {scrap_picking.state}")
            print(f"  Source Location: {scrap_picking.location_id.name}")
            print(f"  Dest Location: {scrap_picking.location_dest_id.name}")
            for move in scrap_picking.move_ids:
                print(f"  Move Product: {move.product_id.display_name}")
                print(f"    State: {move.state}")
                print(f"    Demand: {move.product_uom_qty}")
                for ml in move.move_line_ids:
                    print(f"    Move Line Lot: {ml.lot_id.name if ml.lot_id else 'None'}")
                    print(f"      Qty Done: {ml.quantity}")
        else:
            print("\nError: Auto Scrap Picking not found!")
