import logging
from datetime import datetime, timedelta
import pytz
from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError
from odoo.addons.hr_attendance_deviation.tools import Converter

_logger = logging.getLogger(__name__)

class HrAttendanceMiddleware(models.Model):
    _name = 'hr.attendance.middleware'
    _inherit = ['mail.thread']
    _description = 'HR Attendance Middleware'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('work_entries_error', 'W.E. Error'),
        ('work_entries_valid', 'W.E. Fixed'),
        ('attendance_creation_error', 'A.C. Error'),
        ('attendance_created', 'A. Created'),
        ('attendance_adjustment_error', 'A.A. Error'),
        ('attendance_adjusted', 'A. Adjusted'),
    ], string='Status', default='draft', readonly=True, tracking=True, help='W.E.: Work Entries, A.C.: Attendance Creation, A.A.: Attendance Adjustment')

    # General Information fields
    employee_id = fields.Many2one('hr.employee', string='Employee')
    date = fields.Date(string='Attendance Date')

    # Computed fields
    hr_attendance_id = fields.Many2one('hr.attendance', string='HR Attendance', compute='_compute_hr_attendance')
    working_time_ids = fields.Many2many('resource.calendar.attendance', string='Working Times', compute='_compute_working_times')
    work_entry_ids = fields.Many2many('hr.work.entry', string='Work Entries', compute='_compute_work_entries')
    zk_attendance_ids = fields.Many2many('zk.attendance', string='ZK Attendances', compute='_compute_zk_attendances')
    check_in_computed = fields.Datetime(string='In', compute='_compute_checkings')
    check_out_computed = fields.Datetime(string='Out', compute='_compute_checkings')
    in_mode = fields.Selection([('manual', 'Manual'), ('systray', 'Systray'), ('technical', 'Technical')], compute='_compute_checkings', string='In Mode')
    out_mode = fields.Selection([('manual', 'Manual'), ('systray', 'Systray'), ('technical', 'Technical')], compute='_compute_checkings', string='Out Mode')
    best_work_time_id = fields.Many2one('resource.calendar.attendance', string='Best Work Time', compute='_compute_best_work_time')
    is_check_in_close_to_start = fields.Boolean(string='Check-In Close to Start', compute='_compute_is_check_in_close_to_start', help='Indicates if the check-in time is closer to the start of the shift than to the end.')

    # Final to adjust fields
    check_in_final = fields.Datetime(string='In', compute='_compute_checking_adjustments', readonly=True)
    check_out_final = fields.Datetime(string='Out', compute='_compute_checking_adjustments', readonly=True)

    # Final computed fields
    late_check_in = fields.Float(
        string='Late ',
        compute='_compute_late_early_times',
        store=True,
        help='Time in hours that the employee checked in late.',
    )
    early_check_out = fields.Float(
        string='Early',
        compute='_compute_late_early_times',
        store=True,
        help='Time in hours that the employee checked out early.',
    )

    # Force fields
    force_best_work_time_id = fields.Many2one('resource.calendar.attendance', string='Force Best Work Time', domain="[('id', 'in', working_time_ids)]", help='Manually set best work time to override computed value.', tracking=True)
    force_check_in = fields.Float(string='Force In', help='Manually set check-in time to override computed value.', tracking=True)
    force_check_out = fields.Float(string='Force Out', help='Manually set check-out time to override computed value.', tracking=True)
    force_late_check_in = fields.Float(string='Force Late In', help='Manually set late check-in hours to override computed value.', tracking=True)
    force_early_check_out = fields.Float(string='Force Early Out', help='Manually set early check-out hours to override computed value.', tracking=True)

    @api.ondelete(at_uninstall=True)
    def _ondelete_unsettle_zk_attendance(self):
        for record in self:
            record.zk_attendance_ids.write({'is_settled': False})

    @api.constrains('employee_id', 'date')
    def _check_unique_attendance(self):
        for record in self:
            existing = self.search_count([
                ('employee_id', '=', record.employee_id.id),
                ('date', '=', record.date),
                ('id', '!=', record.id),
            ])
            if existing:
                raise ValidationError(_("An attendance middleware record for employee %s on date %s already exists.") % (record.employee_id.name, record.date))

    @api.depends('check_in_final', 'check_out_final', 'best_work_time_id', 'date')
    def _compute_late_early_times(self):
        for record in self:
            late_duration = 0
            early_duration = 0
            if record.best_work_time_id and record.date:
                shift_start_datetime, shift_end_datetime = record._get_shift_datetimes(record.best_work_time_id, record.date)
                if record.check_in_final:
                    late_duration = (record.check_in_final - shift_start_datetime).total_seconds() / 60.0 / 60.0
                if record.check_out_final:
                    early_duration = (shift_end_datetime - record.check_out_final).total_seconds() / 60.0 / 60.0
            record.late_check_in = max(late_duration, 0)
            record.early_check_out = max(early_duration, 0)

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
            in_mode = 'technical'
            out_mode = 'technical'
            punch_datetimes = []
            systray_datetimes = []
            if record.employee_id and record.zk_attendance_ids:
                punch_datetimes.extend(record._get_zk_api_datetimes())
            if record.hr_attendance_id:
                if record.hr_attendance_id.check_in and record.hr_attendance_id.in_mode == 'systray':
                    punch_datetimes.append(record.hr_attendance_id.check_in)
                    systray_datetimes.append(record.hr_attendance_id.check_in)
                if record.hr_attendance_id.check_out and record.hr_attendance_id.out_mode == 'systray':
                    punch_datetimes.append(record.hr_attendance_id.check_out)
                    systray_datetimes.append(record.hr_attendance_id.check_out)
            if punch_datetimes:
                check_in = min(punch_datetimes)
                check_out = max(punch_datetimes)
                if check_in in systray_datetimes:
                    in_mode = 'systray'
                else:
                    in_mode = 'technical'
                if check_out in systray_datetimes:
                    out_mode = 'systray'
                else:
                    out_mode = 'technical'
            record.in_mode = in_mode
            record.out_mode = out_mode
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

    def action_fix_work_entries(self, bulk=False):
        work_entry_type_attendance = self.env.ref("hr_work_entry.work_entry_type_attendance")
        records = self.filtered(lambda r: 'error' not in r.state)
        records.regenerate_work_entries()
        for record in records:
            best_work_time = record.force_best_work_time_id or record.best_work_time_id
            if bulk:
                best_work_time = record.best_work_time_id
            if not best_work_time:
                record.message_post(body=_("No suitable working time found for the attendance date."))
                record.state = 'work_entries_error'
                continue
            min_date_start = None
            max_date_stop = None
            start_work_entry = None
            end_work_entry = None
            leave_duration = 0
            try:
                hour_from_time, hour_to_time = best_work_time._get_time_objects()
                hours_per_day = best_work_time.calendar_id.hours_per_day
                # Analyze existing work entries
                for work_entry in record.work_entry_ids:
                    if work_entry.work_entry_type_id != work_entry_type_attendance:
                        leave_duration += work_entry.duration
                    if not min_date_start or work_entry.date_start < min_date_start:
                        min_date_start = work_entry.date_start
                        start_work_entry = work_entry
                    if not max_date_stop or work_entry.date_stop > max_date_stop:
                        max_date_stop = work_entry.date_stop
                        end_work_entry = work_entry
                # Adjust attendance work entries
                if start_work_entry:
                    work_entry_start = record._convert_to_gmt_naive(record.date, hour_from_time) # Set anyway to shift start
                    work_entry_stop = work_entry_start + timedelta(hours=hours_per_day - leave_duration)
                    if start_work_entry.work_entry_type_id != work_entry_type_attendance:
                        work_entry_stop = work_entry_start + timedelta(hours=leave_duration)
                    if work_entry_stop > work_entry_start:
                        start_work_entry.write({'date_start': work_entry_start, 'date_stop': work_entry_stop})
                        record.state = 'work_entries_valid'
                    else:
                        record.message_post(body=_("Invalid work entry times after adjustment start: %s - end: %s." % (work_entry_start, work_entry_stop)))
                        record.state = 'work_entries_error'
                if end_work_entry:
                    work_entry_stop = record._convert_to_gmt_naive(record.date, hour_to_time) # Set anyway to shift end
                    work_entry_start = work_entry_stop - timedelta(hours=hours_per_day - leave_duration)
                    if end_work_entry.work_entry_type_id != work_entry_type_attendance:
                        work_entry_start = work_entry_stop - timedelta(hours=leave_duration)
                    if work_entry_stop > work_entry_start:
                        end_work_entry.write({'date_start': work_entry_start, 'date_stop': work_entry_stop})
                    else:
                        record.message_post(body=_("Invalid work entry times after adjustment end: %s - end: %s." % (work_entry_start, work_entry_stop)))
                        record.state = 'work_entries_error'
            except Exception as e:
                record.message_post(body=_("Failed to fix work entries: %s" % str(e)))
                record.state = 'work_entries_error'

    def regenerate_work_entries(self):
        regenerate_wizard = self.env['hr.work.entry.regeneration.wizard'].sudo()
        for record in self:
            wizard = regenerate_wizard.create({
                'employee_ids': [Command.set([record.employee_id.id])],
                'date_from': record.date,
                'date_to': record.date,
            })
            wizard.with_context(work_entry_skip_validation=True).regenerate_work_entries()

    def action_adjust_checkings(self):
        self._compute_checking_adjustments()

    @api.depends('check_in_computed', 'check_out_computed', 'best_work_time_id', 'is_check_in_close_to_start')
    def _compute_checking_adjustments(self):
        allowed_late_minutes = self.env['ir.config_parameter'].sudo().get_param('hr_attendance_deviation.allowed_late_minutes', default=30)
        allowed_early_leaving_minutes = self.env['ir.config_parameter'].sudo().get_param('hr_attendance_deviation.allowed_early_leaving_minutes', default=15)
        check_in_out_tolerance_minutes = self.env['ir.config_parameter'].sudo().get_param('hr_zk_api_attendance.check_in_out_tolerance_minutes', default=15)
        
        for record in self:
            check_in = record.check_in_computed
            check_out = record.check_out_computed
            try:
                if check_in and check_out and abs(check_in - check_out) < timedelta(minutes=check_in_out_tolerance_minutes):
                    hour_from_time, hour_to_time = record.best_work_time_id._get_time_objects()
                    if record.is_check_in_close_to_start: # Check-in is correct
                        check_out = record._convert_to_gmt_naive(record.date, hour_to_time) - timedelta(minutes=allowed_early_leaving_minutes + 1) # Set check-out to shift end - (allowed early leaving + 1 minute) to apply penalty
                    else: # Check-out is correct
                        check_in = record._convert_to_gmt_naive(record.date, hour_from_time) + timedelta(minutes=allowed_late_minutes + 1) # Set check-in to shift start + (allowed late + 1 minute) to apply penalty
            except Exception as e:
                record.message_post(body=_("Failed to adjust check-in/check-out times: %s" % str(e)))
                record.state = 'attendance_adjustment_error'
            record.update({
                'check_in_final': check_in,
                'check_out_final': check_out,
            })

    def action_adjust_or_create_hr_attendance(self, bulk=False):
        records = self.filtered(lambda r: 'error' not in r.state)
        zk_attendance_ids = []
        for record in records:
            zk_attendance_ids.extend(record.zk_attendance_ids.ids)
            force_check_in, force_check_out, force_late_check_in, force_early_check_out = None, None, None, None
            if not bulk:
                force_check_in, force_check_out, force_late_check_in, force_early_check_out = record._get_forced_values()
            check_in = force_check_in or record.check_in_final
            check_out = force_check_out or record.check_out_final
            in_mode = record.in_mode if record.check_in_computed == check_in else 'technical'
            out_mode = record.out_mode if record.check_out_computed == check_out else 'technical'
            vals = {
                'employee_id': record.employee_id.id,
                'check_in': check_in,
                'check_out': check_out,
                'late_check_in': force_late_check_in or record.late_check_in,
                'early_check_out': force_early_check_out or record.early_check_out,
                'in_mode': in_mode,
                'out_mode': out_mode,
                'zk_attendance_ids': [Command.set(record.zk_attendance_ids.ids)],
                'middleware_id': record.id,
            }
            compute_overtime = False
            if record.hr_attendance_id:
                vals.pop('employee_id')  # Employee cannot be changed on write
                try:
                    record.hr_attendance_id.write(vals)
                    record.state = 'attendance_adjusted'
                    record.message_post(body=_("HR Attendance adjusted successfully vals: %s" % vals))
                    compute_overtime = True
                except Exception as e:
                    record.message_post(body=_("Failed to adjust HR Attendance: %s" % str(e)))
                    record.state = 'attendance_adjustment_error'
            else:
                try:
                    new_attendance = self.env['hr.attendance'].create(vals)
                    record.message_post(body=_("HR Attendance created successfully vals: %s" % vals))
                    record.state = 'attendance_created'
                    compute_overtime = True
                except Exception as e:
                    record.message_post(body=_("Failed to create HR Attendance: %s" % str(e)))
                    record.state = 'attendance_creation_error'
            if compute_overtime:
                record.hr_attendance_id._compute_overtime_hours()
        return zk_attendance_ids

    def _get_forced_values(self):
        self.ensure_one()
        force_check_in, force_check_out, force_late_check_in, force_early_check_out = None, None, None, None
        if self.force_check_in > 0:
            force_check_in = self.force_check_in
        if self.force_check_out > 0:
            force_check_out = self.force_check_out
        if self.force_late_check_in > 0:
            force_late_check_in = self.force_late_check_in
        if self.force_early_check_out > 0:
            force_early_check_out = self.force_early_check_out
        if any([
            self.force_check_in > 0,
            self.force_check_out > 0,
            self.force_late_check_in > 0,
            self.force_early_check_out > 0,
        ]):
            self.message_post(body=_("Attendance record has been forced adjusted with values: %s") % {
                'force_check_in': force_check_in,
                'force_check_out': force_check_out,
                'force_late_check_in': force_late_check_in,
                'force_early_check_out': force_early_check_out,
            })
        return force_check_in, force_check_out, force_late_check_in, force_early_check_out

    @api.depends('employee_id', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.employee_id and record.date:
                record.display_name = f"{record.employee_id.name} - {record.date.strftime('%Y-%m-%d')}"
            else:
                record.display_name = "Undefined"
