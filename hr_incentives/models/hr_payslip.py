import logging
from datetime import datetime, time
from odoo import models, fields, api


_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    bonus_amount = fields.Float(
        string='Bonus Amount',
        compute='_compute_incentives_amount',
        help='Total bonus amount for the payslip period.',
    )
    penalty_amount = fields.Float(
        string='Penalty Amount',
        compute='_compute_incentives_amount',
        help='Total penalty amount for the payslip period.',
    )

    def _compute_incentives_amount(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            incentives = self.env['hr.incentive'].sudo().search([
                ('employee_id', '=', payslip.employee_id.id),
                ('date', '>=', from_date_midnight),
                ('date', '<=', end_of_to_date),
                ('state', '=', 'approved'),
            ])
            payslip.bonus_amount = sum(incentives.filtered(lambda i: i.type == 'bonus').mapped('amount'))
            payslip.penalty_amount = sum(incentives.filtered(lambda i: i.type == 'penalty').mapped('amount'))