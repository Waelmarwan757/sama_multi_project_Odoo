import logging
from datetime import datetime, time
from odoo import models, fields, api


_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    late_days = fields.Float(
        string='Late Days',
        compute='_compute_partial_shift_days_hours',
        help='Total days of late attendance for the payslip period.',
    )
    late_hours = fields.Float(
        string='Late Hours',
        compute='_compute_partial_shift_days_hours',
        help='Total hours of late attendance for the payslip period.',
    )
    late_permission_count = fields.Integer(
        string='Late Permissions',
        compute='_compute_late_permission_count',
        help='Number of late permissions granted during the payslip period.',
    )
    early_leaving_days = fields.Float(
        string='Early Leaving Days',
        compute='_compute_partial_shift_days_hours',
        help='Total days of early leaving for the payslip period.',
    )
    early_leaving_hours = fields.Float(
        string='Early Leaving Hours',
        compute='_compute_partial_shift_days_hours',
        help='Total hours of early leaving for the payslip period.',
    )
    overtime_hours = fields.Float(
        string='Overtime Hours (Approved)',
        compute='_compute_overtime_hours',
        help='Total overtime hours for the payslip period.',
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

    def _compute_overtime_hours(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            overtime_attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('check_in', '>=', from_date_midnight),
                ('check_in', '<=', end_of_to_date),
                ('overtime_status', '=', 'approved')
            ])
            payslip.overtime_hours = sum(overtime_attendances.mapped('validated_overtime_hours'))

    def _compute_late_permission_count(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            late_permissions = self.env['hr.work.entry'].search_count([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_start', '>=', from_date_midnight),
                ('date_stop', '<=', end_of_to_date),
                ('work_entry_type_id.code', '=', 'LATE')
            ])
            payslip.late_permission_count = late_permissions

    def _compute_weekend_days(self):
        attendance_type = self.env.ref('hr_work_entry.work_entry_type_attendance')
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            weekend_days = self.env['hr.work.entry'].search_count([
                ('employee_id', '=', payslip.employee_id.id),
                ('date_start', '>=', from_date_midnight),
                ('date_stop', '<=', end_of_to_date),
                ('work_entry_type_id.code', '=', 'REST100')
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

    def _compute_partial_shift_days_hours(self):
        for payslip in self:
            from_date_midnight = datetime.combine(payslip.date_from, time.min)
            end_of_to_date = datetime.combine(payslip.date_to, time.max)
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('check_in', '>=', from_date_midnight),
                ('check_in', '<=', end_of_to_date)
            ])
            late_days_hours = attendances.get_late_days_hours()
            payslip.late_days = late_days_hours['late_days']
            payslip.late_hours = late_days_hours['late_hours']
            early_leaving_days_hours = attendances.get_early_leaving_days_hours()
            payslip.early_leaving_days = early_leaving_days_hours['early_leaving_days']
            payslip.early_leaving_hours = early_leaving_days_hours['early_leaving_hours']
