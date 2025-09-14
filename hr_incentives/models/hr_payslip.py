import logging
from datetime import datetime, time
from odoo import models, fields, api


_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    incetives_amount = fields.Float(
        string='Incentives Amount',
        compute='_compute_incentives_amount',
        help='Total incentives amount for the payslip period.',
    )

    def _compute_incentives_amount(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            incentives = self.env['hr.incentive'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('date', '>=', from_date_midnight),
                ('date', '<=', end_of_to_date),
                ('state', '=', 'approved')
            ])
            payslip.incentives_amount = sum(incentives.mapped('amount'))