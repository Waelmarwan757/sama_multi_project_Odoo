import logging
from datetime import datetime, time
from odoo import models, fields, api


_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    late_days = fields.Float(
        string='Late Days',
        compute='_compute_late_days',
        help='Total days of late attendance for the payslip period.',
    )

    def _compute_late_days(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)

            attendances = payslip.employee_id.attendance_ids.filtered(
                lambda att: 
                    from_date_midnight <= att.check_in <= end_of_to_date 
            )
            late_days = attendances.get_late_days()
            payslip.late_days = late_days
