# -*- coding: utf-8 -*-
#
# Environment configurations for the Secondary Sales REST API module.
#
# Switch ACTIVE to LOCAL or TEST before starting the Odoo server.
#
#   Local  : odoo-bin -d s_sales ...
#   Test   : odoo-bin -d secondary_sales ...  (on 180.94.20.71)
#
# This file is the single source of truth for server URL and DB name.
# Keep it in sync with lib/core/constants.dart in the Flutter app.

_LOCAL = {
    "server_url": "http://127.0.0.1:8069",
    "db_name":    "s_sales",
}

_TEST = {
    "server_url": "http://180.94.20.71:8052",
    "db_name":    "secondary_sales",
}

# ← Change this line to switch environment
ACTIVE = _TEST

SERVER_URL = ACTIVE["server_url"]
DB_NAME    = ACTIVE["db_name"]
