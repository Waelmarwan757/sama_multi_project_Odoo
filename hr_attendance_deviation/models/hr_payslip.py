import logging
from datetime import datetime, time
from odoo import models, fields, api


_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    attendance_deviation = fields.Float(
        string='Attendance Deviation',
        compute='_compute_attendance_deviation',
        help='Total hours of attendance deviation for the payslip period.',
    )

    def _compute_attendance_deviation(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)

            attendances = payslip.employee_id.attendance_ids.filtered(
                lambda att: 
                    from_date_midnight <= att.check_in <= end_of_to_date 
            )
            attendance_deviation = attendances.get_attendance_deviation()
            payslip.attendance_deviation = attendance_deviation
