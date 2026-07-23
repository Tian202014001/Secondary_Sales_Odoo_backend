# -*- coding: utf-8 -*-
{
    "name": "Secondary Sales - Expense API",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    "summary": "API and Custom Logic for Mobile App Expense Submission and Approval",
    "description": "Provides expense API endpoints for the mobile application.",
    "author": "Abrar Ahmed Tian",
    "depends": [
        "base",
        "hr",
        "hr_expense",
        "meta_api_user",
        "meta_ss_rest_api",
        "meta_ss_employee",
    ],
    "data": [
        "views/hr_expense_sheet_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
