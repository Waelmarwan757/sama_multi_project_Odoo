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
    days_attended = fields.Float(
        string='Days Attended',
        compute='_compute_days_attended',
        help='Total days of attendance for the payslip period.',
    )
    weekend_days = fields.Float(
        string='Weekend Off Days',
        compute='_compute_weekend_days',
        help='Total weekend days for the payslip period.',
    )

    def _compute_weekend_days(self):
        attendance_type = self.env.ref('hr_work_entry.work_entry_type_attendance')
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            weekend_days = self.env['hr.work.entry'].search_count([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_start', '>=', from_date_midnight),
                ('date_stop', '<=', end_of_to_date),
                ('work_entry_type_id.code', '=', 'REST_ALLOW')
            ])
            payslip.weekend_days = weekend_days

    def _compute_days_attended(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            days_attended = self.env['hr.attendance'].search_count([
                ('employee_id', '=', payslip.employee_id.id),
                ('check_in', '>=', from_date_midnight),
                ('check_in', '<=', end_of_to_date)
            ])
            payslip.days_attended = days_attended

    def _compute_late_days(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('check_in', '>=', from_date_midnight),
                ('check_in', '<=', end_of_to_date)
            ])
            late_days = attendances.get_late_days()
            payslip.late_days = late_days
