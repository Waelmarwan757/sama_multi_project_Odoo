{
    'name': 'Samalink Security Groups',
    'version': '1.0.0',
    'summary': 'Manage security groups for Samalink',
    'description': 'Module to manage security groups and permissions in Samalink.',
    'author': '46-d-006',
    'website': 'https://edara.digital',
    'category': 'Tools',
    'depends': ['base', 'hr', 'hr_attendance', 'hr_holidays', 'menuitems_whitelist'],
    'data': [
        'views/hr_attendance.xml',
        'security/res_groups.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}