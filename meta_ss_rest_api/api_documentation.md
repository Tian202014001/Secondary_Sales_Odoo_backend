# Secondary Sales API Documentation

Detailed endpoint documentation for `meta_api_user` and `meta_ss_rest_api`.

For a short endpoint index, see [api_list.md](api_list.md).

## Common Format

Authentication APIs use plain HTTP JSON.

Business APIs in `meta_ss_rest_api` are Odoo JSON-RPC endpoints. The app should send request data inside `params`.

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {},
  "id": 1
}
```

Successful business API responses are returned inside Odoo's JSON-RPC `result`.

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "success": true,
    "api_version": "v1",
    "message": "Request completed successfully.",
    "data": {}
  }
}
```

Current security behavior:

- Auth APIs return access and refresh tokens.
- Business APIs are currently `auth="public"`.
- Business APIs currently scope data using `employee_id` from request `params`.
- Later, business APIs should validate `Authorization: Bearer <token>` and derive `employee_id` from the token.

## Endpoint Direction

The API uses resource-oriented endpoints:

- Contacts use `/api/v1/contacts` with `customer_type`.
- Sales use `/api/v1/sale-orders` with `sale_type`.
- Sale, delivery, and virtual transfer state changes use resource-specific `/action` endpoints.

## meta_api_user

### Login

`POST /api/v1/auth/login`

Request:

```json
{
  "login": "test@gmail.com",
  "password": "1234",
  "device_id": "pixel-5",
  "device_name": "Pixel 5"
}
```

Response:

```json
{
  "access_token": "jwt-access-token",
  "refresh_token": "plain-refresh-token",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": 4,
    "name": "test",
    "role": "Territory Sales Manager",
    "group": {
      "id": 3,
      "code": "tsm",
      "name": "Territory Sales Manager"
    },
    "permissions": [
      "dealer.view",
      "dealer.create",
      "primary_sale.create"
    ],
    "employee_id": 7,
    "employee_name": "Anita Oliver"
  }
}
```

### Refresh

`POST /api/v1/auth/refresh`

Request:

```json
{
  "refresh_token": "plain-refresh-token"
}
```

Response:

```json
{
  "success": true,
  "message": "Token refreshed successfully.",
  "data": {
    "access_token": "new-jwt-access-token",
    "refresh_token": "new-refresh-token",
    "token_type": "Bearer",
    "expires_in": 3600
  }
}
```

### Logout

`POST /api/v1/auth/logout`

Headers:

```http
Authorization: Bearer jwt-access-token
```

Request:

```json
{}
```

Response:

```json
{
  "success": true,
  "message": "Logout successful."
}
```

## Contacts, Dealers, Outlets

### Employee List

`POST /api/v1/employees`

Used by assignment screens. For Van Loading Location creation, `employee_id` is the logged-in/acting employee, while the selected employee from this endpoint is sent as `assigned_employee_id`.

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "distributor_id": 3,
    "search": "Audrey",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Employees fetched successfully.",
  "data": [
    {
      "id": 12,
      "name": "Audrey Peterson",
      "work_phone": "01700000000",
      "mobile_phone": "01700000000",
      "work_email": "audrey@example.com",
      "job_title": "Sales Officer",
      "distributor": {
        "id": 3,
        "name": "Distributor A"
      },
      "assigned_routes": [
        {
          "id": 10,
          "name": "Route A",
          "code": "R-A"
        }
      ]
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Create Employee

`POST /api/v1/employees/create`

Creates a new employee (Sales Officer) with distributor tagging and optional assigned routes.

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "name": "Sales Officer A",
    "email": "so_a@example.com",
    "phone": "01700000001",
    "job_title": "Sales Officer",
    "distributor_id": 3,
    "assigned_route_ids": [10, 11]
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Employee created successfully.",
  "data": {
    "id": 15,
    "name": "Sales Officer A",
    "work_phone": null,
    "mobile_phone": "01700000001",
    "work_email": "so_a@example.com",
    "job_title": "Sales Officer",
    "distributor": {
      "id": 3,
      "name": "Distributor A"
    },
    "assigned_routes": [
      {
        "id": 10,
        "name": "Route A",
        "code": "R-A"
      },
      {
        "id": 11,
        "name": "Route B",
        "code": "R-B"
      }
    ]
  }
}
```

### Employee Detail

`POST /api/v1/employees/<employee_id>`

Fetches the details of a specific employee, including assigned distributor and route mappings.

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {},
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Employee details fetched successfully.",
  "data": {
    "id": 15,
    "name": "Sales Officer A",
    "work_phone": null,
    "mobile_phone": "01700000001",
    "work_email": "so_a@example.com",
    "job_title": "Sales Officer",
    "distributor": {
      "id": 3,
      "name": "Distributor A"
    },
    "assigned_routes": [
      {
        "id": 10,
        "name": "Route A",
        "code": "R-A"
      },
      {
        "id": 11,
        "name": "Route B",
        "code": "R-B"
      }
    ]
  }
}
```

### Update Employee

`POST /api/v1/employees/<employee_id>/update`

Updates an existing employee's name, contact information, distributor tagging, or assigned route mappings.

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "name": "Sales Officer A Updated",
    "assigned_route_ids": [10]
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Employee updated successfully.",
  "data": {
    "id": 15,
    "name": "Sales Officer A Updated",
    "work_phone": null,
    "mobile_phone": "01700000001",
    "work_email": "so_a@example.com",
    "job_title": "Sales Officer",
    "distributor": {
      "id": 3,
      "name": "Distributor A"
    },
    "assigned_routes": [
      {
        "id": 10,
        "name": "Route A",
        "code": "R-A"
      }
    ]
  }
}
```

### Contact List

`POST /api/v1/contacts`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "customer_type": "distributor",
    "search": "DB",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Contacts fetched successfully.",
  "data": [
    {
      "id": 65,
      "name": "Distributor B",
      "customer_type": "distributor",
      "phone": "01711-123456",
      "email": "db@example.com",
      "street": "Road 1",
      "city": "Dhaka",
      "active": true,
      "customer_stock_location": {
        "id": 5,
        "name": "Customers"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

For outlet filters, pass `customer_type: "outlet"`. Optional filters include `employee_id`, `route_id`, `distributor_id`, `assigned`, `search`, `active`, `page`, and `page_size`.

### Create Contact

`POST /api/v1/contacts/create`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "name": "Hasan Store",
    "customer_type": "distributor",
    "phone": "01711-123456",
    "email": "hasan@example.com",
    "street": "Mirpur-10",
    "city": "Dhaka"
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Contact created successfully.",
  "data": {
    "id": 70,
    "name": "Hasan Store",
    "customer_type": "distributor",
    "phone": "01711-123456"
  }
}
```

Use `customer_type: "outlet"` to create outlet contacts.

### Contact Detail

`POST /api/v1/contacts/<contact_id>`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "customer_type": "distributor"
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Contact fetched successfully.",
  "data": {
    "id": 70,
    "name": "Hasan Store",
    "customer_type": "distributor",
    "phone": "01711-123456",
    "street": "Mirpur-10",
    "city": "Dhaka"
  }
}
```

## Products and Stock

### Product List

`POST /api/v1/products`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "search": "Milk",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Products fetched successfully.",
  "data": [
    {
      "id": 25,
      "name": "Fresh Milk",
      "default_code": "MLK001",
      "list_price": 65.0,
      "tracking": "lot",
      "uom": {
        "id": 1,
        "name": "Ltr"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Warehouse List

`POST /api/v1/warehouses`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "search": "WH",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Warehouses fetched successfully.",
  "data": [
    {
      "id": 1,
      "name": "My Company Warehouse",
      "code": "WH",
      "stock_location": {
        "id": 8,
        "name": "WH/Stock",
        "usage": "internal"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Product Available Lots

`POST /api/v1/products/<product_id>/available-lots`

Request by warehouse:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "warehouse_id": 1
  },
  "id": 1
}
```

Request by location:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "location_id": 8
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Available lots fetched successfully.",
  "product": {
    "id": 25,
    "name": "Eggs",
    "tracking": "lot"
  },
  "location": {
    "id": 8,
    "name": "WH/Stock"
  },
  "data": [
    {
      "lot_id": 7,
      "lot_name": "LOT-001",
      "product_id": 25,
      "available_qty": 10.0,
      "quantity": 10.0,
      "reserved_quantity": 0.0,
      "uom": {
        "id": 1,
        "name": "Dzn"
      },
      "location": {
        "id": 8,
        "name": "WH/Stock"
      }
    }
  ]
}
```

## Sales

### Sale Order List

`POST /api/v1/sale-orders`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "sale_type": "primary",
    "search": "Hasan",
    "state": "sale",
    "date": "2026-06-08",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Sale orders fetched successfully.",
  "data": [
    {
      "id": 20,
      "name": "S00020",
      "sale_type": "primary",
      "state": "sale",
      "date_order": "2026-06-08 11:29:00",
      "distributor": {
        "id": 3,
        "name": "Hasan Store"
      },
      "amount_total": 137.2,
      "lines": []
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Create Sale Order

`POST /api/v1/sale-orders/create`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "sale_type": "primary",
    "distributor_id": 3,
    "client_order_ref": "APP-PO-001",
    "confirm": false,
    "expected_delivery_date": "2026-06-08",
    "order_lines": [
      {
        "product_id": 25,
        "product_uom_qty": 10,
        "price_unit": 120.0,
        "discount": 5.0
      },
      {
        "product_id": 26,
        "product_uom_qty": 2,
        "price_unit": 65.0
      }
    ]
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Sale order created successfully.",
  "data": {
    "id": 20,
    "name": "S00020",
    "sale_type": "primary",
    "state": "draft",
    "distributor": {
      "id": 3,
      "name": "Distributor A"
    },
    "amount_total": 1200.0,
    "lines": []
  }
}
```

### Sale Order Detail

`POST /api/v1/sale-orders/<order_id>`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "sale_type": "primary"
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Sale order fetched successfully.",
  "data": {
    "id": 20,
    "name": "S00020",
    "state": "sale",
    "date_order": "2026-06-08 11:29:00",
    "expected_delivery_date": "2026-06-08 00:00:00",
    "can_cancel": true,
    "can_validate_delivery": true,
    "distributor": {
      "id": 3,
      "name": "Hasan Store",
      "phone": "01711-123456",
      "address": "Mirpur-10, Dhaka"
    },
    "amounts": {
      "amount_untaxed": 140.0,
      "amount_tax": 0.0,
      "amount_total": 137.2,
      "discount": 2.8,
      "receivable": 0.0
    },
    "lines": [
      {
        "id": 55,
        "product": {
          "id": 25,
          "name": "Eggs",
          "tracking": "lot"
        },
        "product_uom_qty": 1.0,
        "qty_delivered": 0.0,
        "balance_qty": 1.0,
        "price_total": 137.2
      }
    ],
    "delivery_orders": [
      {
        "id": 12,
        "name": "WH/OUT/00012",
        "state": "assigned"
      }
    ]
  }
}
```

### Sale Order Action

`POST /api/v1/sale-orders/<order_id>/action`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "sale_type": "primary",
    "action": "cancel"
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Sale order action completed successfully.",
  "data": {
    "id": 20,
    "name": "S00020",
    "state": "cancel",
    "can_cancel": false,
    "can_validate_delivery": false
  }
}
```

### Print Sale Order

`POST /api/v1/sale-orders/<order_id>/print`

Renders the sale order QWeb PDF report (`sale.action_report_saleorder`) and returns it as a base64 encoded string along with the correct filename matching the sale order name.

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Sale order PDF generated successfully.",
  "data": {
    "filename": "S00020.pdf",
    "file_content": "JVBERi0xLjQKJ..."
  }
}
```

## Delivery

### Prepare Delivery Validation

`POST /api/v1/deliveries/prepare`

Prepares the data required by the mobile app's delivery validation/details view. If `picking_id` is supplied, Odoo fetches the details of that specific picking (supporting done/cancel states for historical view). If `picking_id` is omitted, the API automatically finds the first active delivery for the given sales order.

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "sale_order_id": 20,
    "picking_id": 12
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Delivery validation data fetched successfully.",
  "data": {
    "order": {
      "id": 20,
      "name": "S00020",
      "state": "sale",
      "distributor": {
        "id": 3,
        "name": "Hasan Store"
      }
    },
    "picking": {
      "id": 12,
      "name": "WH/OUT/00012",
      "state": "assigned",
      "lines": [
        {
          "move_id": 50,
          "sale_line_id": 55,
          "product": {
            "id": 25,
            "name": "Eggs",
            "tracking": "lot"
          },
          "product_uom_qty": 1.0,
          "quantity_done": 0.0,
          "remaining_qty": 1.0,
          "default_delivery_qty": 1.0,
          "product_uom": {
            "id": 1,
            "name": "Dzn"
          },
          "lot_lines": []
        }
      ]
    },
    "warehouses": [
      {
        "id": 1,
        "name": "My Company Warehouse",
        "code": "WH",
        "stock_location": {
          "id": 8,
          "name": "WH/Stock"
        }
      }
    ]
  }
}
```

### Validate Delivery

`POST /api/v1/deliveries/<picking_id>/action`

Validates or cancels the delivery matching `<picking_id>`. 
- `action`: `'validate'` or `'cancel'`.
- `create_backorder`: a boolean (default `true`) used during `'validate'`. If the processed quantities are less than the initial demand, setting `create_backorder` to `true` creates a backorder picking in Odoo; setting it to `false` processes the quantities without creating a backorder.

Request without lots:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "sale_order_id": 20,
    "action": "validate",
    "warehouse_id": 1,
    "create_backorder": true,
    "lines": [
      {
        "move_id": 24,
        "quantity_done": 1.0
      }
    ]
  },
  "id": 1
}
```

Request with lots:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "sale_order_id": 20,
    "action": "validate",
    "warehouse_id": 1,
    "create_backorder": true,
    "lines": [
      {
        "move_id": 24,
        "quantity_done": 1.0,
        "lot_lines": [
          {
            "lot_id": 7,
            "quantity": 1.0
          }
        ]
      }
    ]
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Delivery validated successfully.",
  "data": {
    "validation_result": true,
    "order": {
      "id": 20,
      "name": "S00020",
      "state": "sale",
      "lines": [
        {
          "id": 55,
          "product_uom_qty": 1.0,
          "qty_delivered": 1.0,
          "balance_qty": 0.0
        }
      ],
      "delivery_orders": [
        {
          "id": 12,
          "name": "WH/OUT/00012",
          "state": "done"
        }
      ]
    }
  }
}
```

## Routes and Secondary Outlets

### Employee Route List

`POST /api/v1/ss/routes`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "search": "Dhaka",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Routes fetched successfully.",
  "data": [
    {
      "id": 10,
      "name": "Dhaka North",
      "code": "DN",
      "active": true,
      "outlet_count": 4
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Create Employee Route

`POST /api/v1/ss/routes/create`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "name": "Dhaka North",
    "code": "DN",
    "outlet_ids": [80, 81]
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Route created successfully.",
  "data": {
    "id": 10,
    "name": "Dhaka North",
    "code": "DN",
    "outlet_count": 2
  }
}
```

### Add Outlet To Route

`POST /api/v1/ss/routes/<route_id>/outlets/add`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "outlet_id": 80,
    "expected_visit_time": "10:30"
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Outlet added to route successfully.",
  "data": {
    "id": 10,
    "name": "Dhaka North",
    "outlets": [
      {
        "id": 80,
        "name": "City Mart"
      }
    ]
  }
}
```

### Route Detail

`POST /api/v1/ss/routes/<route_id>`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Route fetched successfully.",
  "data": {
    "id": 10,
    "name": "Dhaka North",
    "code": "DN",
    "active": true,
    "outlets": [
      {
        "id": 80,
        "name": "City Mart",
        "phone": "01711-567890",
        "address": "Dhanmondi-15, Dhaka"
      }
    ]
  }
}
```

### Update Route

`POST /api/v1/ss/routes/<route_id>/update`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "name": "Dhaka North Updated",
    "active": true,
    "outlet_ids": [80, 81, 82]
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Route updated successfully.",
  "data": {
    "id": 10,
    "name": "Dhaka North Updated",
    "outlet_count": 3
  }
}
```

Outlet list/search is handled by `POST /api/v1/contacts` with
`customer_type: "outlet"` and optional `employee_id`, `route_id`,
`distributor_id`, `assigned`, and `search` filters.

## Virtual Locations

### Virtual Location List

`POST /api/v1/virtual-locations`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "location_type": "van_loading",
    "search": "Anita",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Virtual locations fetched successfully.",
  "data": [
    {
      "id": 48,
      "name": "Anita Oliver - Distributor A Van Loading",
      "usage": "customer",
      "location_type": "van_loading",
      "employee": {
        "id": 7,
        "name": "Anita Oliver"
      },
      "distributor": {
        "id": 3,
        "name": "Distributor A"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Create Virtual Location

`POST /api/v1/virtual-locations/create`

`employee_id` is the acting/logged-in employee for API context. `assigned_employee_id` is the employee saved on `stock.location.ss_employee_id`.

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "name": "Anita Oliver - Distributor A Van Loading",
    "location_type": "van_loading",
    "assigned_employee_id": 12,
    "assigned_distributor_id": 3
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Virtual location created successfully.",
  "data": {
    "id": 48,
    "name": "Anita Oliver - Distributor A Van Loading",
    "usage": "customer",
    "location_type": "van_loading",
    "employee": {
      "id": 12,
      "name": "Audrey Peterson"
    },
    "distributor": {
        "id": 3,
        "name": "Distributor A"
    }
  }
}
```

### Virtual Location Detail

`POST /api/v1/virtual-locations/<location_id>`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {},
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Virtual location fetched successfully.",
  "data": {
    "id": 48,
    "name": "Anita Oliver - Distributor A Van Loading",
    "usage": "customer",
    "location_type": "van_loading",
    "employee": {
      "id": 7,
      "name": "Anita Oliver"
    },
    "distributor": {
      "id": 3,
      "name": "Distributor A"
    }
  }
}
```

### Stock Location List

`POST /api/v1/locations`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "usage": "internal",
    "ss_location_type": "van_loading",
    "employee_id": 7,
    "search": "Van",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Locations fetched successfully.",
  "data": [
    {
      "id": 48,
      "name": "Van Loading 1",
      "complete_name": "Physical Locations/WH/Stock/Van Loading 1",
      "display_name": "WH/Stock/Van Loading 1",
      "usage": "internal",
      "active": true,
      "ss_location_type": "van_loading",
      "employee": {
        "id": 7,
        "name": "Sales Officer 1"
      },
      "distributor": {
        "id": 3,
        "name": "Distributor A"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

## Virtual Inventory Transfer

Virtual transfer moves stock from the employee's assigned distributor customer location into one of the employee's assigned Van Loading Locations.

Backend derives the source location from:

```text
hr.employee.distributor_contact_id.property_stock_customer
```

The app sends only `employee_id`, `destination_location_id`, and product lines.

### Virtual Transfer Prepare

`POST /api/v1/virtual-transfers/prepare`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Virtual transfer data fetched successfully.",
  "data": {
    "employee": {
      "id": 7,
      "name": "Audrey Peterson"
    },
    "distributor": {
      "id": 3,
      "name": "Distributor A"
    },
    "source_location": {
      "id": 35,
      "name": "Partners/Customers",
      "usage": "customer"
    },
    "destination_locations": [
      {
        "id": 48,
        "name": "Van Loading 1",
        "usage": "customer",
        "location_type": "van_loading",
        "employee": {
          "id": 7,
          "name": "Audrey Peterson"
        },
        "distributor": {
          "id": 3,
          "name": "Distributor A"
        }
      }
    ]
  }
}
```

### Transfer Product Search

`POST /api/v1/virtual-transfers/products`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "search": "Eggs",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Transfer products fetched successfully.",
  "source_location": {
    "id": 35,
    "name": "Partners/Customers",
    "usage": "customer"
  },
  "data": [
    {
      "id": 25,
      "name": "Eggs",
      "default_code": "EGG001",
      "tracking": "lot",
      "available_qty": 10.0,
      "uom": {
        "id": 1,
        "name": "Dzn"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Transfer Product Lots

`POST /api/v1/virtual-transfers/products/<product_id>/lots`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Transfer product lots fetched successfully.",
  "product": {
    "id": 25,
    "name": "Eggs",
    "tracking": "lot"
  },
  "source_location": {
    "id": 35,
    "name": "Partners/Customers",
    "usage": "customer"
  },
  "data": [
    {
      "lot_id": 7,
      "lot_name": "LOT-001",
      "available_qty": 5.0,
      "quantity": 5.0,
      "reserved_quantity": 0.0
    }
  ]
}
```

### Create Virtual Transfer

`POST /api/v1/virtual-transfers/create`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "destination_location_id": 48,
    "lines": [
      {
        "product_id": 25,
        "quantity": 2.0,
        "lot_lines": [
          {
            "lot_id": 7,
            "quantity": 2.0
          }
        ]
      }
    ]
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Virtual transfer created successfully.",
  "data": {
    "id": 90,
    "name": "VLT/00090",
    "state": "confirmed",
    "distributor": {
      "id": 3,
      "name": "Distributor A"
    },
    "source_location": {
      "id": 35,
      "name": "Partners/Customers",
      "usage": "customer"
    },
    "destination_location": {
      "id": 48,
      "name": "Van Loading 1",
      "location_type": "van_loading"
    },
    "lines": [
      {
        "move_id": 100,
        "product": {
          "id": 25,
          "name": "Eggs",
          "tracking": "lot"
        },
        "demand_qty": 2.0,
        "quantity": 2.0
      }
    ]
  }
}
```

### Virtual Transfer List

`POST /api/v1/virtual-transfers`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "state": "confirmed",
    "search": "VLT",
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Virtual transfers fetched successfully.",
  "data": [
    {
      "id": 90,
      "name": "VLT/00090",
      "state": "confirmed",
      "source_location": {
        "id": 35,
        "name": "Partners/Customers",
        "usage": "customer"
      },
      "destination_location": {
        "id": 48,
        "name": "Van Loading 1",
        "location_type": "van_loading"
      },
      "lines": []
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

### Virtual Transfer Detail

`POST /api/v1/virtual-transfers/<transfer_id>`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7
  },
  "id": 1
}
```

Response shape is one serialized transfer object, same as the list item but with full product and lot lines.

### Virtual Transfer Action

`POST /api/v1/virtual-transfers/<transfer_id>/action`

Request:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "employee_id": 7,
    "action": "validate"
  },
  "id": 1
}
```

Response:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Virtual transfer validated successfully.",
  "data": {
    "validation_result": true,
    "transfer": {
      "id": 90,
      "name": "VLT/00090",
      "state": "done"
    }
  }
}
```

Use `action: "cancel"` to cancel an eligible virtual transfer.
