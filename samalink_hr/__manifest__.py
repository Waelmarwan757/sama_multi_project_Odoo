{
    'name': 'Samalink HR',
    'version': '1.0',
    'summary': 'HR Module for Samalink',
    'description': 'Custom HR functionalities for Samalink.',
    'author': '46-d-006',
    'website': 'https://edara.digital',
    'category': 'Human Resources',
    'depends': ['base', 'hr', 'samalink_security_groups', 'hr_contract'],
    'data': [
        'views/hr_employee.xml',
        'views/hr_contract.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}