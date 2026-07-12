{
    'name': 'Meta Secondary Sales - Attendance',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Attendance',
    'summary': 'Geo-fenced attendance tracking for Secondary Sales app.',
    'description': """
        This module provides API endpoints and logic for mobile app users to check in/out.
        It adds geo-fencing logic based on distributor location radius.
    """,
    'author': 'Meta',
    'depends': [
        'base',
        'hr_attendance',
        'meta_ss_employee',
        'meta_ss_rest_api',
        'meta_ss_route_management',
        'meta_barikoi_base',
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/hr_attendance_views.xml',
        'views/res_mobile_user_group_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
