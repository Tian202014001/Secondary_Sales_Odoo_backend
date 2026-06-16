# Secondary Sales API Index

Quick endpoint list for `meta_api_user` and `meta_ss_rest_api`.

Full request and response examples are in [api_documentation.md](api_documentation.md).

## 1. Common Notes

- `meta_api_user` authentication endpoints use plain HTTP JSON.
- `meta_ss_rest_api` business endpoints use Odoo JSON-RPC `type="json"`.
- Business endpoints currently use `employee_id` in request `params`.
- Later, business endpoints should derive `employee_id` from `Authorization: Bearer <token>`.

## 2. meta_api_user

**Authentication**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login with phone/email and password. |
| `POST` | `/api/v1/auth/refresh` | Refresh access token. |
| `POST` | `/api/v1/auth/logout` | Logout current session. |

## 3. meta_ss_rest_api

### 3.1 Contacts, Dealers, Outlets

**Unified contact master data**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/employees` | Employee (Sales Officer) list/search. |
| `POST` | `/api/v1/employees/create` | Create a new employee (Sales Officer) with distributor and route tagging. |
| `POST` | `/api/v1/employees/<employee_id>` | Employee (Sales Officer) detail view. |
| `POST` | `/api/v1/employees/<employee_id>/update` | Update employee (Sales Officer) details and route mappings. |
| `POST` | `/api/v1/contacts` | Contact list/search using `customer_type`, `employee_id`, `route_id`, `distributor_id`, `search`. |
| `POST` | `/api/v1/contacts/create` | Create contact using `customer_type` (`distributor` or `outlet`). |
| `POST` | `/api/v1/contacts/<contact_id>` | Contact detail, optionally validating `customer_type`. |
| `POST` | `/api/v1/contacts/<contact_id>/update` | Update contact details. |
| `POST` | `/api/v1/contacts/<contact_id>/visits` | Contact visit history and past orders. |

### 3.2 Products and Stock

**Products, warehouses, and lot availability**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/products` | Product list/search. |
| `POST` | `/api/v1/warehouses` | Warehouse list. |
| `POST` | `/api/v1/products/<product_id>/available-lots` | Lot-wise available stock. |

### 3.3 Primary Sales

**Sale order creation and tracking**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/sale-orders` | Sale order list/dashboard using `sale_type` (`primary` currently used by app). |
| `POST` | `/api/v1/sale-orders/create` | Create sale order using `sale_type` (`primary` creation currently supported). |
| `POST` | `/api/v1/sale-orders/<order_id>` | Sale order detail. |
| `POST` | `/api/v1/sale-orders/<order_id>/update` | Update draft sale order. |
| `POST` | `/api/v1/sale-orders/<order_id>/action` | Run sale order action: `confirm`, `cancel`. |
| `POST` | `/api/v1/sale-orders/<order_id>/print` | Render the sale order QWeb PDF and return it in base64 format. |

### 3.4 Delivery

**Primary sale delivery validation**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/deliveries/prepare` | Prepare delivery validation data using `sale_order_id` and optional `picking_id`. |
| `POST` | `/api/v1/deliveries/<picking_id>/action` | Run delivery action: `validate`, `cancel`. |

### 3.5 Routes and Secondary Outlets

**Employee route and outlet assignment**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/ss/routes` | Employee route list. |
| `POST` | `/api/v1/ss/routes/create` | Create route. |
| `POST` | `/api/v1/ss/routes/<route_id>/outlets/add` | Add outlet to route. |
| `POST` | `/api/v1/ss/routes/<route_id>` | Route detail. |
| `POST` | `/api/v1/ss/routes/<route_id>/update` | Update route. |
| `POST` | `/api/v1/ss/routes/<route_id>/outlets/<outlet_id>/remove` | Remove outlet from route. |
| `POST` | `/api/v1/routes/<route_id>/visits` | Get/Initialize daily route visits tracking. |
| `POST` | `/api/v1/route-visits` | List route visits. |
| `POST` | `/api/v1/route-visits/<visit_id>` | Route visit detail. |
| `POST` | `/api/v1/route-visits/<visit_id>/action` | Route visit actions (`check_in`, `check_out`, `cancel`). |

### 4.1 Virtual Locations

**Create and manage Van Loading Locations**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/virtual-locations` | List Van Loading Locations. |
| `POST` | `/api/v1/virtual-locations/create` | Create Van Loading Location and assign employee/distributor. |
| `POST` | `/api/v1/virtual-locations/<location_id>` | Van Loading Location detail. |

### 4.2 Stock Locations

**List and search generic stock locations**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/locations` | List and search generic stock locations. |

## 5. Virtual Inventory Transfer

**Move stock from distributor customer location to employee Van Loading Location**

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/virtual-transfers` | List virtual transfers. |
| `POST` | `/api/v1/virtual-transfers/prepare` | Prepare transfer creation data. |
| `POST` | `/api/v1/virtual-transfers/products` | Search products available in distributor customer location. |
| `POST` | `/api/v1/virtual-transfers/products/<product_id>/lots` | Lot-wise available stock for transfer product. |
| `POST` | `/api/v1/virtual-transfers/create` | Create draft virtual transfer. |
| `POST` | `/api/v1/virtual-transfers/<transfer_id>` | Virtual transfer detail. |
| `POST` | `/api/v1/virtual-transfers/<transfer_id>/action` | Run virtual transfer action: `validate`, `cancel`. |
