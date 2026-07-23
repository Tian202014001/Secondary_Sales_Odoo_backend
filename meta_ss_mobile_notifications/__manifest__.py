# -*- coding: utf-8 -*-
{
    'name': "Meta SS Mobile Notifications",
    'summary': "In-app notification center (read state, list API, deep-link reference) for the mobile app",
    'description': """
        Consumer side of the mobile push notification system. Extends
        meta_firebase_push_notification (without modifying it) by adding read/unread
        tracking and a generic record reference to mobile.push.notification, and exposes
        REST endpoints for the Flutter app to list notifications, fetch the unread count,
        and mark notifications read.
    """,
    'author': "Abrar Ahmed Tian",
    'category': 'Sales',
    'version': '18.0.1.0.0',
    'depends': ['meta_firebase_push_notification', 'meta_ss_rest_api'],
    'data': [
        'views/notification_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
