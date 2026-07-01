{
    "name": "Secondary Sales - Leave Request API",
    "version": "1.0",
    "category": "Human Resources",
    "summary": "API and Custom Logic for Mobile App Leave Requests",
    "description": "Provides leave request API for the mobile application and strict manager approval logic.",
    "author": "Metamorphosis",
    "depends": [
        "base",
        "hr",
        "hr_holidays",
        "meta_api_user",
        "meta_ss_rest_api",
        "meta_ss_employee",
    ],
    "data": [
        "views/hr_leave_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
