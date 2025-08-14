import logging
from datetime import datetime, time
from odoo import models, fields, api


_logger = logging.getLogger(__name__)

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    work_entry_id = fields.Many2one(
        'hr.work.entry',
        compute='_compute_work_entry_id',
        store=True,
        string='Work Entry',
        help='Link to the work entry associated with this attendance record.',
    )
    late_check_in = fields.Float(
        string='Late Check-in',
        compute='_compute_late_check_in',
        store=True,
        help='Time in hours that the employee checked in late.',
    )
    early_check_out = fields.Float(
        string='Early Check-out',
        compute='_compute_early_check_out',
        store=True,
        help='Time in hours that the employee checked out early.',
    )

    @api.depends('check_in', 'check_out')
    def _compute_work_entry_id(self):
        attendance_type = self.env.ref('hr_work_entry.work_entry_type_attendance')
        for attendance in self:
            date_midnight = datetime.combine(attendance.check_in.date(), time.min)
            end_of_date = datetime.combine(attendance.check_in.date(), time.max)
            work_entries = self.env['hr.work.entry'].search([
                ('employee_id', '=', attendance.employee_id.id),
                ('date_start', '>=', date_midnight),
                ('date_stop', '<=', end_of_date),
                ('work_entry_type_id', '=', attendance_type.id)
            ], limit=1)
            attendance.work_entry_id = work_entries.id

    @api.depends('check_in', 'work_entry_id.date_start')
    def _compute_late_check_in(self):
        for attendance in self:
            if attendance.check_in and attendance.work_entry_id:
                late_minutes = (attendance.check_in - attendance.work_entry_id.date_start).total_seconds() / 60.0 / 60.0
                attendance.late_check_in = max(late_minutes, 0)

    @api.depends('check_out', 'work_entry_id.date_stop')
    def _compute_early_check_out(self):
        for attendance in self:
            if attendance.check_out and attendance.work_entry_id:
                early_minutes = (attendance.work_entry_id.date_stop - attendance.check_out).total_seconds() / 60.0 / 60.0
                attendance.early_check_out = max(early_minutes, 0)

    def get_attendance_deviation(self):
        """
        Returns a dictionary with the late check-in and early check-out times.
        """
        return sum(self.mapped('late_check_in'))

    