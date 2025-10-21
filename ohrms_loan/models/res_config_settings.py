from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    loan_after_month_day = fields.Integer(
        string='Allowed Loan After Month Day',
        help='Set the day of the month after which employees are allowed to apply for loans.',
        config_parameter='ohrms_loan.loan_after_month_day',
        default=10
    )
    loan_before_month_day = fields.Integer(
        string='Allowed Loan Before Month Day',
        help='Set the day of the month before which employees are allowed to apply for loans.',
        config_parameter='ohrms_loan.loan_before_month_day',
        default=20
    )