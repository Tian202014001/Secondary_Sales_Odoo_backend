# -*- coding: utf-8 -*-


class AccessKey:
    """Canonical mobile UI resource keys used for API endpoint authorization.

    Values must match the Flutter access catalog synced through
    ``/api/v1/access/catalog/sync``. Keep endpoint code importing these
    constants instead of hardcoding raw strings in controllers.
    """

    # Primary sales.
    PRIMARY_ORDERS_LIST = "screen.primary_sale.orders.list"
    PRIMARY_ORDERS_DETAIL = "screen.primary_sale.orders.detail"
    PRIMARY_ORDERS_CREATE_SCREEN = "screen.primary_sale.orders.create"
    PRIMARY_ORDERS_CREATE = "action.primary_sale.orders.create"
    PRIMARY_ORDERS_CONFIRM = "action.primary_sale.orders.confirm"
    PRIMARY_ORDERS_CANCEL = "action.primary_sale.orders.cancel"

    PRIMARY_DELIVERIES_LIST = "screen.primary_sale.deliveries.list"
    PRIMARY_DELIVERIES_VALIDATE = "action.primary_sale.deliveries.validate"

    PRIMARY_RETURNS_LIST = "screen.primary_sale.returns.list"
    PRIMARY_RETURNS_CREATE_SCREEN = "screen.primary_sale.returns.create"
    PRIMARY_RETURNS_CREATE = "action.primary_sale.returns.create"
    PRIMARY_RETURNS_SAVE = "action.primary_sale.returns.save"
    PRIMARY_RETURNS_CANCEL = "action.primary_sale.returns.cancel"
    PRIMARY_RETURNS_VALIDATE = "action.primary_sale.returns.validate"

    PRIMARY_SCRAPS_LIST = "screen.primary_sale.scraps.list"
    PRIMARY_SCRAPS_CREATE_SCREEN = "screen.primary_sale.scraps.create"
    PRIMARY_SCRAPS_CREATE = "action.primary_sale.scraps.create"
    PRIMARY_SCRAPS_SAVE = "action.primary_sale.scraps.save"
    PRIMARY_SCRAPS_CANCEL = "action.primary_sale.scraps.cancel"
    PRIMARY_SCRAPS_VALIDATE = "action.primary_sale.scraps.validate"

    PRIMARY_DISTRIBUTORS_LIST = "screen.primary_sale.distributors.list"
    PRIMARY_DISTRIBUTORS_DETAIL = "screen.primary_sale.distributors.detail"
    PRIMARY_DISTRIBUTORS_CREATE_SCREEN = "screen.primary_sale.distributors.create"
    PRIMARY_DISTRIBUTORS_CREATE = "action.primary_sale.distributors.create"

    # Secondary sales.
    SECONDARY_ORDERS_LIST = "screen.secondary_sale.orders.list"
    SECONDARY_ORDERS_CREATE_SCREEN = "screen.secondary_sale.orders.create"
    SECONDARY_ORDERS_CREATE = "action.secondary_sale.orders.create"
    SECONDARY_ORDERS_CONFIRM = "action.secondary_sale.orders.confirm"
    SECONDARY_ORDERS_CANCEL = "action.secondary_sale.orders.cancel"

    SECONDARY_DELIVERIES_LIST = "screen.secondary_sale.deliveries.list"
    SECONDARY_DELIVERIES_VALIDATE = "action.secondary_sale.deliveries.validate"

    SECONDARY_RETURNS_LIST = "screen.secondary_sale.returns.list"
    SECONDARY_RETURNS_CREATE_SCREEN = "screen.secondary_sale.returns.create"
    SECONDARY_RETURNS_CREATE = "action.secondary_sale.returns.create"
    SECONDARY_RETURNS_SAVE = "action.secondary_sale.returns.save"
    SECONDARY_RETURNS_CANCEL = "action.secondary_sale.returns.cancel"
    SECONDARY_RETURNS_VALIDATE = "action.secondary_sale.returns.validate"

    SECONDARY_SCRAPS_LIST = "screen.secondary_sale.scraps.list"
    SECONDARY_SCRAPS_CREATE_SCREEN = "screen.secondary_sale.scraps.create"
    SECONDARY_SCRAPS_CREATE = "action.secondary_sale.scraps.create"
    SECONDARY_SCRAPS_SAVE = "action.secondary_sale.scraps.save"
    SECONDARY_SCRAPS_CANCEL = "action.secondary_sale.scraps.cancel"
    SECONDARY_SCRAPS_VALIDATE = "action.secondary_sale.scraps.validate"

    SECONDARY_ROUTES_LIST = "screen.secondary_sale.routes.list"
    SECONDARY_ROUTES_DETAIL = "screen.secondary_sale.routes.detail"
    SECONDARY_ROUTES_CREATE_SCREEN = "screen.secondary_sale.routes.create"
    SECONDARY_ROUTES_CREATE = "action.secondary_sale.routes.create"
    SECONDARY_ROUTES_ADD_OUTLET = "action.secondary_sale.routes.add_outlet"

    SECONDARY_VISITS_LIST = "screen.secondary_sale.visits.list"
    SECONDARY_VISITS_CHECK_IN = "action.secondary_sale.visits.check_in"
    SECONDARY_VISITS_CHECK_OUT = "action.secondary_sale.visits.check_out"

    SECONDARY_TRANSFERS_LIST = "screen.secondary_sale.transfers.list"
    SECONDARY_TRANSFERS_DETAIL = "screen.secondary_sale.transfers.detail"
    SECONDARY_TRANSFERS_CREATE_SCREEN = "screen.secondary_sale.transfers.create"
    SECONDARY_TRANSFERS_CREATE = "action.secondary_sale.transfers.create"
    SECONDARY_TRANSFERS_VALIDATE = "action.secondary_sale.transfers.validate"
    SECONDARY_TRANSFERS_CANCEL = "action.secondary_sale.transfers.cancel"

    SECONDARY_VAN_LOADING_LIST = "screen.secondary_sale.van_loading.list"
    SECONDARY_VAN_LOADING_FORM = "screen.secondary_sale.van_loading.form"
    SECONDARY_VAN_LOADING_LOCATION_DETAIL = (
        "screen.secondary_sale.van_loading.location_detail"
    )

    SECONDARY_OUTLETS_LIST = "screen.secondary_sale.outlets.list"
    SECONDARY_OUTLETS_EDIT = "screen.secondary_sale.outlets.edit"
    SECONDARY_OUTLETS_CREATE = "action.secondary_sale.outlets.create"

    # HR / accounts / dashboard.
    HR_ATTENDANCE = "screen.hr.attendance"
    HR_ATTENDANCE_SKIP_GEO = "action.hr.attendance.skip_geo_fence"
    HR_LEAVE = "screen.hr.leave"
    HR_LEAVE_CREATE = "action.hr.leave.create"

    ACCOUNTS_EXPENSE = "screen.accounts.expense"
    ACCOUNTS_EXPENSE_CREATE = "action.accounts.expense.create"

    DASHBOARD_MODULE = "screen.module.dashboard"
    DASHBOARD_HOME = "screen.dashboard.home"
    DASHBOARD_SETTINGS = "screen.dashboard.settings"
    DASHBOARD_SALES_OFFICERS_LIST = "screen.dashboard.sales_officers.list"
    DASHBOARD_SALES_OFFICERS_DETAIL = "screen.dashboard.sales_officers.detail"
    DASHBOARD_SALES_OFFICERS_CREATE_SCREEN = (
        "screen.dashboard.sales_officers.create"
    )
    DASHBOARD_SALES_OFFICERS_CREATE = "action.dashboard.sales_officers.create"
