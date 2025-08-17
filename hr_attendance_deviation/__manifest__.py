{
    'name': 'HR Attendance Deviation',
    'version': '1.0.0',
    'summary': 'Module to track attendance deviations in HR',
    'description': 'This module helps in monitoring and managing attendance deviations for employees.',
    'author': '46-d-006',
    'website': 'https://edara.digital',
    'category': 'Human Resources',
    'depends': ['hr_attendance', 'hr_work_entry', 'hr_payroll_community'],
    'data': [
        'data/hr_salary_rule.xml',
        'views/hr_attendance.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}