# Meta SS Route Management Flow Scenarios

This document maps common secondary-sales flows to the models used and the actions performed on each model.

## Core Model Roles

| Model | Role | Main Action |
| --- | --- | --- |
| `res.partner` | Distributor and outlet master data | Create/update contacts with `customer_type` |
| `hr.employee` | Sales employee master data | Assign distributor contact and routes |
| `sale.route` | Route master | Define route, distributor, employee |
| `sale.route.line` | Permanent route-outlet mapping | Add ordered outlets to route |
| `sale.route.visit.plan` | Optional management planning | Predefine employee route for a date |
| `sale.route.visit.plan.line` | Planned outlets for management plan | Store planned outlet list |
| `sale.route.visit` | Actual daily route execution/session | Employee starts/completes route visit |
| `sale.route.visit.line` | Actual outlet visit during execution | Mark outlet pending/visited/skipped |
| `sale.order` | Secondary sales order | Create sales order linked to route visit/outlet visit |

## Scenario 1: Master Data Setup

Goal: prepare distributor, outlets, employee, and route before any daily work.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `res.partner` | Create distributor | `name`, `customer_type = distributor` |
| 2 | `res.partner` | Create outlet | `name`, `customer_type = outlet` |
| 3 | `hr.employee` | Create/update employee | `name`, `distributor_contact_id` |
| 4 | `sale.route` | Create route | `name`, `code`, `ss_employee_id`, `distributor_contact_id` |
| 5 | `sale.route.line` | Add outlet under route | `route_id`, `outlet_id`, `sequence`, `expected_visit_time` |

Result:

```text
Employee -> Route -> Ordered Route Outlets
```

## Scenario 2: Employee Selects Route for Today

Goal: employee uses mobile app to select one of their assigned routes for the day.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `sale.route.visit` | Create route visit | `employee_id`, `route_id`, `visit_date`, `source = employee_selected` |
| 2 | `sale.route.visit.line` | Auto-created from route outlets | `visit_id`, `outlet_id`, `sequence`, `state = pending` |
| 3 | `sale.route.visit` | Start visit | `state = started` |

System behavior:

- `sale.route.visit` pulls active `sale.route.line` records into `sale.route.visit.line`.
- If the selected route has `ss_employee_id`, the visit employee must be one of them.

Result:

```text
Route Visit started for today's employee route execution
```

## Scenario 3: Employee Visits Existing Outlet and Sells

Goal: employee visits an existing outlet from the route and creates a secondary sales order.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `sale.route.visit.line` | Select outlet visit line | `visit_id`, `outlet_id`, `state = pending` |
| 2 | `sale.order` | Create secondary sale | `sale_type = secondary`, `route_visit_line_id` |
| 3 | `sale.order` | Auto-fill route context | `route_visit_id`, `so_employee_id`, `route_id`, `partner_id` |
| 4 | `sale.route.visit.line` | Auto-update after order | `state = visited` |

System behavior:

- Creating a sale order with `route_visit_line_id` forces the order to match that outlet visit.
- The order customer becomes the outlet from `sale.route.visit.line.outlet_id`.
- The outlet visit is marked `visited`.

Result:

```text
Outlet visit completed through a linked secondary sale order
```

## Scenario 4: Employee Visits Existing Outlet Without Sale

Goal: employee reaches an outlet but no order is created.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `sale.route.visit.line` | Update outlet visit line | `state = skipped` |
| 2 | `sale.route.visit.line` | Add reason if needed | `note` |

Result:

```text
Outlet is accounted for without creating a sale order
```

## Scenario 5: Employee Creates New Outlet During Visit

Goal: employee discovers a new outlet while working a route.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `res.partner` | Create outlet contact | `name`, `customer_type = outlet` |
| 2 | `sale.route.visit.line` | Add outlet to active route visit | `visit_id`, `outlet_id`, `state = pending` |
| 3 | `sale.route.line` | Auto-created if missing | `route_id`, `outlet_id`, `sequence`, `expected_visit_time` |
| 4 | `sale.order` | Optional sale from new outlet visit | `route_visit_line_id` |

System behavior:

- Adding a new outlet to `sale.route.visit.line` also ensures the outlet exists in the permanent route outlet mapping.
- If the outlet is already assigned to another route, the system raises a validation error.

Result:

```text
New outlet becomes part of the route master and can be used in future visits
```

## Scenario 6: Management Predefines a Visit Plan

Goal: management plans that an employee should visit a route on a specific date.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `sale.route.visit.plan` | Create plan | `employee_id`, `route_id`, `visit_date`, `state = draft` |
| 2 | `sale.route.visit.plan.line` | Auto-created from route outlets | `plan_id`, `outlet_id`, `sequence`, `state = pending` |
| 3 | `sale.route.visit.plan` | Confirm plan | `state = confirmed` |

System behavior:

- Management planning is optional.
- A plan does not create sales orders.
- A plan does not replace route master data.

Result:

```text
Confirmed route plan is ready for employee execution
```

## Scenario 7: Employee Executes Management Plan

Goal: employee starts work from a confirmed management plan.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `sale.route.visit` | Create visit from plan | `plan_id` |
| 2 | `sale.route.visit` | Auto-fill visit context | `employee_id`, `route_id`, `visit_date`, `source = management_plan` |
| 3 | `sale.route.visit.line` | Auto-created from plan lines | `visit_id`, `outlet_id`, `sequence`, `state = pending` |
| 4 | `sale.route.visit` | Start visit | `state = started` |
| 5 | `sale.order` | Create orders from outlet visits | `route_visit_line_id` |
| 6 | `sale.route.visit` | Complete visit | `state = done` |

Result:

```text
Management plan becomes an actual route visit session
```

## Scenario 8: Complete Route Visit

Goal: close the route visit at the end of the day.

| Step | Model | Action | Important Fields |
| --- | --- | --- | --- |
| 1 | `sale.route.visit.line` | Ensure every outlet is handled | `state in (visited, skipped)` |
| 2 | `sale.route.visit` | Complete route visit | `state = done` |

System behavior:

- A route visit cannot be completed while any outlet visit line is still `pending`.

Result:

```text
Daily route execution is closed
```

## Recommended Mobile API Flow

```text
1. Fetch employee assigned routes
   Model: sale.route
   Filter: ss_employee_id contains current employee

2. Employee selects route
   Create: sale.route.visit

3. Fetch outlet visit lines
   Model: sale.route.visit.line
   Filter: visit_id = active visit

4. Employee creates/chooses outlet
   Create: res.partner if new outlet
   Create: sale.route.visit.line if outlet is newly added to route visit

5. Employee creates sale
   Create: sale.order with route_visit_line_id

6. Employee closes visit
   Update: sale.route.visit state = done
```

## Key Rules

- `sale.route.line` is the single user-facing source for route outlets.
- `sale.route.visit.plan` is optional and only for management planning.
- `sale.route.visit` is the actual route execution record for mobile and daily work.
- `sale.order` should link to `route_visit_line_id` when created from a mobile outlet visit.
