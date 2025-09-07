import logging
import pytz
from datetime import datetime, time, timedelta
from odoo import models, fields, api, exceptions


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
    is_outside_main_shift = fields.Boolean(
        string='Outside Main Shift',
        compute='_compute_is_outside_main_shift',
        help='Indicates whether the attendance is outside the main shift hours.',
        store=True,
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
    invalid_corrected = fields.Boolean(
        string='Corrected',
        default=False,
        help='Indicates whether the invalid attendance record has been corrected.',
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

    @api.depends('check_in', 'check_out', 'work_entry_id.date_start', 'work_entry_id.date_stop')
    def _compute_is_outside_main_shift(self):
        for attendance in self:
            attendance.is_outside_main_shift = attendance._is_outside_main_shift()

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

    def get_late_days_hours(self):
        allowed_late_minutes = self.env['ir.config_parameter'].sudo().get_param('hr_attendance_deviation.allowed_late_minutes', default=30)
        allowed_late_hours = int(allowed_late_minutes) / 60.0
        late_attendances = self.filtered(lambda att: att.late_check_in > allowed_late_hours)
        late_days = len(late_attendances)
        late_hours = sum(late_attendances.mapped('late_check_in'))
        return {'late_days': late_days, 'late_hours': late_hours}

    def action_bulk_correct_invalid_attendance(self):
        for record in self:
            record._action_correct_invalid_attendance()
        self.write({'invalid_corrected': True})

    def _action_correct_invalid_attendance(self):
        self.ensure_one()
        self._set_check_in_out()

    def _set_check_in_out(self): # Set Check-in or Check-out to nearest Shift time
        self.ensure_one()
        if self.in_out_validity == 'valid' or not self.work_entry_id and self.invalid_corrected:
            return # Aborting if valid or no work entry and already corrected
        allowed_late_minutes = self.env['ir.config_parameter'].sudo().get_param('hr_attendance_deviation.allowed_late_minutes', default=30)
        # Differentiate between Check-in and Check-out
        punch_datetime = self.check_in
        # Is punch time near Shift start or end?
        start_proximity = abs(punch_datetime - self.work_entry_id.date_start)
        end_proximity = abs(punch_datetime - self.work_entry_id.date_stop)

        if start_proximity < end_proximity:
            # Punch time is closer to Shift start
            self.check_out = self.work_entry_id.date_stop
        else:
            # Punch time is closer to Shift end
            self.check_in = self.work_entry_id.date_start + timedelta(minutes=allowed_late_minutes + 1)

    def action_bulk_adjust_work_entry_time(self):
        for record in self:
            record._action_adjust_work_entry_time()

    def _action_adjust_work_entry_time(self):
        self.ensure_one()
        if self.employee_id.contract_id.multi_shifts and self.is_outside_main_shift:
            self._update_work_entry_dates()

    def _is_outside_main_shift(self):
        self.ensure_one()
        if self.work_entry_id:
            return self._is_outside_shift(self.work_entry_id.date_start, self.work_entry_id.date_stop)
        else:
            return False

    def _is_outside_shift(self, date_start, date_stop):
        """
            Check if both Check-in and Check-out miss the main shift start and end
        """
        self.ensure_one()
        allowed_late_minutes = self.env['ir.config_parameter'].sudo().get_param('hr_attendance_deviation.allowed_late_minutes', default=30)
        if self.work_entry_id:
            start_missed = abs(self.check_in - date_start) > timedelta(minutes=allowed_late_minutes + 30)
            end_missed = abs(self.check_out - date_stop) > timedelta(minutes=allowed_late_minutes + 30)
            return start_missed and end_missed
        else:
            return False

    def _update_work_entry_dates(self):
        closest_shift = self._get_closest_shift()
        if self.work_entry_id :
            shift_start_datetime, shift_end_datetime = closest_shift
            self.work_entry_id.write({
                'date_start': shift_start_datetime,
                'date_stop': shift_end_datetime
            })

    def _get_closest_shift(self):
        weekday_attendances = self._get_weekday_attendances()
        date = self.check_in.date()
        closest_shift = None
        for shift in weekday_attendances:
            shift_hour_from_time = self._float_to_time(shift.hour_from)
            shift_hour_to_time = self._float_to_time(shift.hour_to)
            shift_start_datetime = self._convert_to_gmt(date, shift_hour_from_time)
            shift_end_datetime = self._convert_to_gmt(date, shift_hour_to_time)
            if not closest_shift:
                closest_shift = (shift_start_datetime, shift_end_datetime)
            else:
                current_closest_start, current_closest_end = closest_shift
                current_proximity = abs(self.check_in - current_closest_start) + abs(self.check_out - current_closest_end)
                new_proximity = abs(self.check_in - shift_start_datetime) + abs(self.check_out - shift_end_datetime)
                if new_proximity < current_proximity:
                    closest_shift = (shift_start_datetime, shift_end_datetime)
        return closest_shift

    def _get_weekday_attendances(self):
        """
        Get the weekday attendances that should employee attend.
        if chick-in is on Monday, it should return
        the attendances for this day.
        return: recordset of resource.calendar.attendance
        example:
            monday 9:00 17:00
            monday 11:00 19:00
            monday 12:00 20:00
        """
        resource_calendar_ids = []
        if self.employee_id.contract_id.multi_shifts:
            resource_calendar_ids.extend(self.employee_id.contract_id.resource_calendar_ids.ids)
        working_schedule_ids = self.employee_id.contract_id.resource_calendar_id.ids
        weekday_attendances = self.env['resource.calendar.attendance'].search([
            ('dayofweek', '=', str(self.check_in.weekday())),
            ('calendar_id', 'in', resource_calendar_ids)
        ])
        return weekday_attendances

    def _float_to_time(self, float_time):
        hours = int(float_time // 1)
        minutes = int(float_time % 1) * 60
        time_str = f"{hours:02}:{minutes:02}:00"
        return datetime.strptime(time_str, "%H:%M:%S").time()

    def _convert_to_gmt(self, date_obj, time_obj):
        cairo_tz = pytz.timezone("Africa/Cairo")
        gmt_tz = pytz.timezone("UTC")
        naive_datetime = datetime.combine(date_obj, time_obj)
        localized_datetime = cairo_tz.localize(naive_datetime)
        gmt_datetime = localized_datetime.astimezone(gmt_tz)
        return gmt_datetime.replace(tzinfo=None)

    @api.model
    def cron_correct_invalid_attendance(self):
        invalid_attendances = self.search([('in_out_validity', '!=', 'valid'), ('invalid_corrected', '=', False), ('work_entry_id', '!=', False)])
        invalid_attendances.action_bulk_correct_invalid_attendance()

    @api.model
    def cron_adjust_work_entry_time(self):
        attendances = self.search([('is_outside_main_shift', '=', True)])
        attendances.action_bulk_adjust_work_entry_time()