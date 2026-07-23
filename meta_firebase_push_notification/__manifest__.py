# -*- coding: utf-8 -*-
{
    'name': "Meta Firebase Push Notification",
    'summary': "Firebase Push Notifications for Secondary Sales Mobile App",
    'description': """
        Sends push notifications to Flutter mobile app users via Firebase Cloud Messaging (FCM).
        Tracks devices, tokens, and sends a push notification when a Sale Order is confirmed.
    """,
    'author': "Abrar Ahmed Tian",
    'category': 'Sales',
    'version': '18.0.1.0.0',
    'depends': ['base', 'sale', 'mail', 'hr', 'hr_holidays', 'hr_expense', 'meta_ss_rest_api'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/mail_template_data.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
