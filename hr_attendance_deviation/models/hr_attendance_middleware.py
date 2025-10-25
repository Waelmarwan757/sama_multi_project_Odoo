import logging
from datetime import datetime
import pytz
from odoo import models, fields, api, Command
from odoo.addons.hr_attendance_deviation.tools import Converter

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
    best_work_time_id = fields.Many2one('resource.calendar.attendance', string='Best Work Time', compute='_compute_best_work_time')
    is_check_in_close_to_start = fields.Boolean(string='Check-In Close to Start', compute='_compute_is_check_in_close_to_start', help='Indicates if the check-in time is closer to the start of the shift than to the end.')

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
            time_obj = datetime.strptime(punch_time, "%H:%M").time()
            punch_datetime = self._convert_to_gmt_naive(self.date, time_obj)
            punch_datetimes.append(punch_datetime)
        return punch_datetimes

    @api.depends('working_time_ids', 'check_in_computed')
    def _compute_best_work_time(self):
        for record in self:
            weekday_attendances = record.working_time_ids
            date = record.date
            closest_shift = None
            closest_to = 'start'
            lowest_time_diff = float('inf')
            for shift in weekday_attendances:
                shift_start_datetime, shift_end_datetime = record._get_shift_datetimes(shift, date)

                # Check is closest to shift start or shift end
                if record.check_in_computed:
                    time_diff_start = abs((record.check_in_computed - shift_start_datetime).total_seconds())
                    time_diff_end = abs((record.check_in_computed - shift_end_datetime).total_seconds())
                    min_diff = min(time_diff_start, time_diff_end)
                    if min_diff < lowest_time_diff:
                        lowest_time_diff = min_diff
                        closest_shift = shift.id
                    if min_diff == time_diff_start:
                        closest_to = 'start'
                    else:
                        closest_to = 'end'
                    
            record.best_work_time_id = closest_shift

    @api.depends('best_work_time_id', 'check_in_computed', 'date')
    def _compute_is_check_in_close_to_start(self):
        for record in self:
            is_close = False
            if record.best_work_time_id and record.check_in_computed:
                shift = record.best_work_time_id
                date = record.date
                shift_start_datetime, shift_end_datetime = record._get_shift_datetimes(shift, date)
                time_diff_start = abs((record.check_in_computed - shift_start_datetime).total_seconds())
                time_diff_end = abs((record.check_in_computed - shift_end_datetime).total_seconds())
                is_close = time_diff_start < time_diff_end
            record.is_check_in_close_to_start = is_close

    def _get_shift_datetimes(self, shift, date):
        shift_hour_from_time = self._convert_float_to_time(shift.hour_from)
        shift_hour_to_time = self._convert_float_to_time(shift.hour_to)
        shift_start_datetime = self._convert_to_gmt_naive(date, shift_hour_from_time)
        shift_end_datetime = self._convert_to_gmt_naive(date, shift_hour_to_time)
        return shift_start_datetime, shift_end_datetime

    def _convert_float_to_time(self, float_time):
        return Converter.float_to_time_obj(float_time)

    def _convert_to_gmt_naive(self, date_obj, time_obj):
        return Converter.date_time_to_gmt_naive(date_obj, time_obj)

    def action_fix_work_entries(self):
        for record in self:
            min_date_start = None
            max_date_stop = None
            start_work_entry = None
            end_work_entry = None
            hour_from_time, hour_to_time = record.best_work_time_id._get_time_objects()
            for work_entry in record.work_entry_ids:
                if not min_date_start or work_entry.date_start < min_date_start:
                    min_date_start = work_entry.date_start
                    start_work_entry = work_entry
                if not max_date_stop or work_entry.date_stop > max_date_stop:
                    max_date_stop = work_entry.date_stop
                    end_work_entry = work_entry
            if start_work_entry:
                start_work_entry.date_start = record._convert_to_gmt_naive(record.date, hour_from_time)
            if end_work_entry:
                end_work_entry.date_stop = record._convert_to_gmt_naive(record.date, hour_to_time)