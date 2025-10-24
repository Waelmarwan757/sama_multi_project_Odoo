import logging
from datetime import datetime
import pytz
from odoo import models, fields, api, Command

_logger = logging.getLogger(__name__)

class HrAttendanceMiddleware(models.Model):
    _name = 'hr.attendance.middleware'
    _description = 'HR Attendance Middleware'

    # General Information fields
    employee_id = fields.Many2one('hr.employee', string='Employee')
    date = fields.Date(string='Attendance Date')

    # Computed fields
    hr_attendance_id = fields.Many2one('hr.attendance', string='HR Attendance', compute='_compute_hr_attendance')
    working_time_ids = fields.Many2many('resource.calendar.attendance', string='Working Times', compute='_compute_working_times')
    work_entry_ids = fields.Many2many('hr.work.entry', string='Work Entries', compute='_compute_work_entries')
    zk_attendance_ids = fields.Many2many('zk.attendance', string='ZK Attendances', compute='_compute_zk_attendances')
    check_in_computed = fields.Datetime(string='Check In (result)', compute='_compute_checkings')
    check_out_computed = fields.Datetime(string='Check Out (result)', compute='_compute_checkings')

    @api.depends('employee_id', 'date')
    def _compute_hr_attendance(self):
        for record in self:
            if record.employee_id and record.date:
                hr_attendance = self.env['hr.attendance'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('check_in', '>=', datetime.combine(record.date, datetime.min.time())),
                    ('check_in', '<=', datetime.combine(record.date, datetime.max.time())),
                ], limit=1)
                record.hr_attendance_id = hr_attendance.id
            else:
                record.hr_attendance_id = False

    @api.depends('employee_id', 'date')
    def _compute_working_times(self):
        attendance_type = self.env.ref("hr_work_entry.work_entry_type_attendance")
        for record in self:
            if record.employee_id and record.date:
                time_ids = []
                contract = record.employee_id.contract_id
                dayofweek = str(record.date.weekday())
                if contract and contract.resource_calendar_id:
                    working_times = contract.resource_calendar_id.attendance_ids.filtered(lambda at: str(at.dayofweek) == dayofweek and at.work_entry_type_id == attendance_type)
                    time_ids.extend([Command.link(at.id) for at in working_times])
                if contract and contract.multi_shifts and contract.resource_calendar_ids:
                    for rc in contract.resource_calendar_ids:
                        working_times = rc.attendance_ids.filtered(lambda at: str(at.dayofweek) == dayofweek and at.work_entry_type_id == attendance_type)
                        time_ids.extend([Command.link(at.id) for at in working_times])
                record.working_time_ids = time_ids
            else:
                record.working_time_ids = False

    @api.depends('employee_id', 'date')
    def _compute_work_entries(self):
        for record in self:
            if record.employee_id and record.date:
                work_entry_ids = self.env['hr.work.entry'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('date_start', '<=', record.date),
                    ('date_stop', '>=', record.date),
                ])
                record.work_entry_ids = [Command.set(work_entry_ids.ids)]
            else:
                record.work_entry_ids = False

    @api.depends('employee_id', 'date')
    def _compute_zk_attendances(self):
        for record in self:
            if record.employee_id and record.date:
                zk_attendance_ids = self.env['zk.attendance'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('att_date', '=', record.date),
                ])
                record.zk_attendance_ids = [Command.set(zk_attendance_ids.ids)]
            else:
                record.zk_attendance_ids = False

    @api.depends('employee_id', 'zk_attendance_ids', 'hr_attendance_id.check_in', 'hr_attendance_id.check_out')
    def _compute_checkings(self):
        for record in self:
            check_in = False
            check_out = False
            punch_datetimes = []
            if record.employee_id and record.zk_attendance_ids:
                punch_datetimes.extend(record._get_zk_api_datetimes())
            if record.hr_attendance_id:
                if record.hr_attendance_id.check_in:
                    punch_datetimes.append(record.hr_attendance_id.check_in)
                if record.hr_attendance_id.check_out:
                    punch_datetimes.append(record.hr_attendance_id.check_out)
            if punch_datetimes:
                check_in = min(punch_datetimes)
                check_out = max(punch_datetimes)
            record.check_in_computed = check_in
            record.check_out_computed = check_out

    def _get_zk_api_datetimes(self):
        self.ensure_one()
        punch_datetimes = []
        for punch_time in self.zk_attendance_ids.mapped('punch_time'):
            punch_datetime = self._get_naive_datetime(punch_time)
            punch_datetimes.append(punch_datetime)
        return punch_datetimes

    def _get_naive_datetime(self, punch_time_str):
        """Convert att_date and punch_time strings to a native datetime object in GMT"""
        cairo_tz = pytz.timezone("Africa/Cairo")
        gmt_tz = pytz.timezone("UTC")
        date_obj = self.date
        time_obj = datetime.strptime(punch_time_str, "%H:%M").time()
        naive_datetime = datetime.combine(date_obj, time_obj)
        localized_datetime = cairo_tz.localize(naive_datetime)
        gmt_datetime = localized_datetime.astimezone(gmt_tz)
        return gmt_datetime.replace(tzinfo=None)