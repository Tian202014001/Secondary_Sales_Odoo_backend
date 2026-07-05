# API Endpoints List

**Total Endpoints:** 77

| Endpoint | Methods | Auth | Description | File |
|----------|---------|------|-------------|------|
| `/api/v1/contacts` | POST | user | List/search contacts using customer_type and optional filters. | `contacts.py` |
| `/api/v1/contacts/<int:contact_id>` | POST | user | Return one contact by id, optionally validating customer_type. | `contacts.py` |
| `/api/v1/contacts/<int:contact_id>/update` | POST | user | Update an existing distributor or outlet contact using customer_type. | `contacts.py` |
| `/api/v1/contacts/<int:contact_id>/visits` | POST | user | Fetch past check-in/out logs and sales orders for a specific contact/outlet. | `contacts.py` |
| `/api/v1/contacts/create` | POST | user | Create a distributor or outlet contact using customer_type. | `contacts.py` |
| `/api/v1/deliveries` | POST | user | No description. | `deliveries.py` |
| `/api/v1/deliveries/<int:picking_id>/action` | POST | user | Run a delivery action such as validate or cancel. | `deliveries.py` |
| `/api/v1/deliveries/prepare` | POST | user | Return data needed by the mobile delivery validation screen. | `deliveries.py` |
| `/api/v1/deliveries/products/<int:product_id>/auto-assign-lots` | POST | user | Return auto-assigned (FIFO) lot lines for a given quantity. | `deliveries.py` |
| `/api/v1/deliveries/products/<int:product_id>/lots` | POST | user | Return lot-wise available stock in the delivery's source location. | `deliveries.py` |
| `/api/v1/employees` | POST | user | Return employees for assignment dropdowns. | `employees.py` |
| `/api/v1/employees/<int:employee_id>` | POST | user | Return one employee detail by id. | `employees.py` |
| `/api/v1/employees/<int:employee_id>/update` | POST | user | Update an existing employee details and route mappings. | `employees.py` |
| `/api/v1/employees/create` | POST | user | Create a new employee (Sales Officer) with distributor tagging and optional routes. | `employees.py` |
| `/api/v1/hr/attendance/action` | POST | user | Handle check_in and check_out with strict Geo-fencing. | `attendance.py` |
| `/api/v1/hr/attendance/history` | POST | user | Fetch paginated attendance logs for the employee. | `attendance.py` |
| `/api/v1/hr/attendance/status` | POST | user | Fetch current active attendance status. | `attendance.py` |
| `/api/v1/hr/expense/approve` | POST | user | Approve an expense sheet. | `expense.py` |
| `/api/v1/hr/expense/categories` | POST | user | Fetch categories/products that can be expensed. | `expense.py` |
| `/api/v1/hr/expense/drafts` | POST | user | Fetch draft/unsubmitted expenses for the employee. | `expense.py` |
| `/api/v1/hr/expense/list` | POST | user | Fetch own or pending approval expenses. | `expense.py` |
| `/api/v1/hr/expense/refuse` | POST | user | Refuse/Reject an expense sheet. | `expense.py` |
| `/api/v1/hr/expense/sheet/create` | POST | user | Create an expense sheet, link/update/create expenses, and submit it. | `expense.py` |
| `/api/v1/hr/expense/sheet/details` | POST | user | Fetch details and line items of a specific expense sheet. | `expense.py` |
| `/api/v1/hr/expense/sheet/list` | POST | user | Fetch own or pending approval expense sheets/reports. | `expense.py` |
| `/api/v1/hr/leave/action` | POST | user | Approve or Reject a leave (For Managers) | `leave_api.py` |
| `/api/v1/hr/leave/list` | POST | user | Unified endpoint for listing leaves (Own, Pending, Approved, Rejected, All) | `leave_api.py` |
| `/api/v1/hr/leave/request` | POST | user | Submit a new leave request with optional attachment | `leave_api.py` |
| `/api/v1/hr/leave/types` | POST | user | Fetch leave types with allocation balances | `leave_api.py` |
| `/api/v1/locations` | POST | user | List and search stock locations. | `locations.py` |
| `/api/v1/products` | POST | user | Return saleable products for the mobile primary sale flow. | `products.py` |
| `/api/v1/products/<int:product_id>/available-lots` | POST | user | Return available lots for a product under a warehouse/location. | `warehouses.py` |
| `/api/v1/returns` | POST | user | Get list of return deliveries. | `returns.py` |
| `/api/v1/returns/<int:picking_id>` | POST | user | Get details of a specific return delivery. | `returns.py` |
| `/api/v1/returns/<int:picking_id>/update` | POST | user | Update lines of an existing draft/assigned return delivery. | `returns.py` |
| `/api/v1/returns/create` | POST | user | Create a return picking from distributor customer location to warehouse. | `returns.py` |
| `/api/v1/returns/prepare` | POST | user | Fetch distributor location, destination warehouse, and available stock. | `returns.py` |
| `/api/v1/returns/products` | POST | user | Get available products for return from distributor customer location. | `returns.py` |
| `/api/v1/returns/products/<int:product_id>/lots` | POST | user | Get available lots for a product in distributor customer location. | `returns.py` |
| `/api/v1/sale-orders` | POST | user | Return sale orders filtered by sale_type and common dashboard filters. | `sales.py` |
| `/api/v1/sale-orders/<int:order_id>` | POST | user | Return one sale order detail, optionally filtered by sale_type. | `sale_order_details.py` |
| `/api/v1/sale-orders/<int:order_id>/action` | POST | user | Run a sale order action such as confirm or cancel. | `sale_order_details.py` |
| `/api/v1/sale-orders/<int:order_id>/print` | POST | user | Render the invoice PDF for a sale order and return it in base64 format. | `sale_order_details.py` |
| `/api/v1/sale-orders/<int:order_id>/update` | POST | user | Update a sale order with draft/sale restrictions. | `sales.py` |
| `/api/v1/sale-orders/create` | POST | user | Create a sale order using sale_type. | `sales.py` |
| `/api/v1/sales/mediums` | POST | user | Fetch available order mediums from utm.medium. | `sales.py` |
| `/api/v1/scraps` | POST | user | Get list of scrap deliveries. | `scraps.py` |
| `/api/v1/scraps/<int:picking_id>` | POST | user | Get details of a specific scrap delivery. | `scraps.py` |
| `/api/v1/scraps/<int:picking_id>/update` | POST | user | Update lines of an existing draft/assigned scrap delivery. | `scraps.py` |
| `/api/v1/scraps/create` | POST | user | Create a scrap picking from distributor scrap location to virtual scrap location. | `scraps.py` |
| `/api/v1/scraps/prepare` | POST | user | Fetch distributor scrap location, destination scrap location, and available stock. | `scraps.py` |
| `/api/v1/scraps/products` | POST | user | Get available products for scrap from distributor scrap location. | `scraps.py` |
| `/api/v1/scraps/products/<int:product_id>/lots` | POST | user | Get available lots for a product in distributor scrap location. | `scraps.py` |
| `/api/v1/ss/routes` | POST | user | Return routes assigned to a requested employee. | `routes.py` |
| `/api/v1/ss/routes/<int:route_id>` | POST | user | Return one route detail by route id for a requested employee. | `routes.py` |
| `/api/v1/ss/routes/<int:route_id>/outlets/<int:outlet_id>/remove` | POST | user | Remove an outlet from a route. | `routes.py` |
| `/api/v1/ss/routes/<int:route_id>/outlets/add` | POST | user | Add an existing or newly created outlet to a selected route. | `routes.py` |
| `/api/v1/ss/routes/<int:route_id>/update` | POST | user | Update a route assigned to the requested employee. | `routes.py` |
| `/api/v1/ss/routes/create` | POST | user | Create a route assigned to the requested employee. | `routes.py` |
| `/api/v1/van_loading/targets` | POST | user | Fetch monthly target products for van loading with current distributor stock. | `van_loading.py` |
| `/api/v1/virtual-locations` | POST | user | List van loading virtual locations. | `virtual_locations.py` |
| `/api/v1/virtual-locations/<int:location_id>` | POST | user | Virtual location detail. | `virtual_locations.py` |
| `/api/v1/virtual-locations/create` | POST | user | Create a van loading location and assign employee/distributor. | `virtual_locations.py` |
| `/api/v1/virtual-transfers` | POST | user | List virtual transfers for the employee's assigned distributor. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/<int:transfer_id>` | POST | user | Return one virtual transfer detail. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/<int:transfer_id>/action` | POST | user | Run a virtual transfer action such as validate or cancel. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/<int:transfer_id>/update` | POST | user | Update lines of an existing draft/assigned virtual transfer. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/create` | POST | user | Create a Virtual Location Transfer into an assigned Van Loading Location. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/prepare` | POST | user | Prepare distributor source and employee Van Loading destinations. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/products` | POST | user | Search products available in the employee distributor customer location. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/products/<int:product_id>/auto-assign-lots` | POST | user | Return auto-assigned (FIFO) lot lines for a given quantity in the distributor location. | `virtual_transfers.py` |
| `/api/v1/virtual-transfers/products/<int:product_id>/lots` | POST | user | Return lot-wise available stock in the distributor customer location. | `virtual_transfers.py` |
| `/api/v1/visits` | POST | user | Get paginated list of visits. | `routes.py` |
| `/api/v1/visits/<int:visit_id>/update` | POST | user | Update an existing outlet.visit record (e.g., set check_out_time). | `routes.py` |
| `/api/v1/visits/create` | POST | user | Create a new outlet.visit record. | `routes.py` |
| `/api/v1/visits/today` | POST | user | Get today's visits (active and checked out) for the employee. | `routes.py` |
| `/api/v1/warehouses` | POST | user | Return warehouses for delivery source selection. | `warehouses.py` |
