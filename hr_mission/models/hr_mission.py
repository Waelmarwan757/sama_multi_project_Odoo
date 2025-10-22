import logging
from datetime import datetime, time, timedelta
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class HrMission(models.Model):
    _name = 'hr.mission'
    _inherit = ['mail.thread']
    _description = 'HR Mission'
    _rec_name = 'employee_id'

    def _default_employee(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return employee.id if employee else False

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True, default=_default_employee)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id')
    current_location_id = fields.Many2one('hr.work.location', related='employee_id.work_location_id')
    manager_id = fields.Many2one('hr.employee', string='Manager', related='employee_id.parent_id')
    start_date = fields.Date(string='Mission Start Date', required=True, default=fields.Date.context_today, tracking=True)
    end_date = fields.Date(string='Mission End Date', required=True, default=fields.Date.context_today, tracking=True)
    destination = fields.Char(string='Destination', required=True, tracking=True)
    mission_type = fields.Selection([
        ('installation', 'Installation'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other')
    ], string='Mission Type', required=True, tracking=True)
    note = fields.Text(string='Additional Notes', tracking=True)
    manager_reason = fields.Text(string='Reason of Approval/Rejection (Manager)', tracking=True)
    hr_reason = fields.Text(string='Reason of Approval/Rejection (HR)', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Submitted'),
        ('manager_approved', 'Manager Approved'),
        ('hr_approved', 'HR Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    attendance_ids = fields.One2many('hr.attendance', 'mission_id', string='Attendance Records', readonly=True)

    @api.constrains('employee_id')
    def _check_one_mission(self):
        for record in self:
            existing_missions = self.search_count([
                ('employee_id', '=', record.employee_id.id),
                ('state', 'in', ['draft']),
                ('id', '!=', record.id)
            ])
            if existing_missions:
                raise ValidationError("There is already an ongoing mission request for this employee.")

    def action_submit(self):
        for record in self:
            if record.employee_id.user_id != self.env.user:
                raise ValidationError("You can only submit mission requests for your own employee record.")
        self.write({'state': 'confirmed'})

    def action_manager_approve(self):
        is_hr = self.env.user.has_group('hr_mission.group_hr_mission_manager')
        if not self.env.user.has_group('hr_mission.group_hr_mission_officer'):
            raise ValidationError("You have to be a Manager to approve this request.")
        for record in self:
            if record.manager_id.user_id != self.env.user and not is_hr:
                raise ValidationError("You can only approve mission requests for your own managed employee record.")
        self.write({'state': 'manager_approved'})

    def action_hr_approve(self):
        if not self.env.user.has_group('hr_mission.group_hr_mission_manager'):
            raise ValidationError("You have to be a HR responsible to approve this request.")
        self._create_attendance_records()
        self.write({'state': 'hr_approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_cancel(self):
        # Delete associated attendance records upon cancellation
        self.env['hr.attendance'].search([('mission_id', 'in', self.ids)]).unlink()
        self.write({'state': 'cancelled'})

    def _create_attendance_records(self):
        attendance_work_type = self.env.ref('hr_work_entry.work_entry_type_attendance')
        vals_list = []
        for record in self:
            current_date = record.start_date
            while current_date <= record.end_date:
                date_midnight = datetime.combine(current_date, time.min)
                end_of_date = datetime.combine(current_date, time.max)
                work_entry = self.env['hr.work.entry'].search([
                    ('employee_id', '=', record.employee_id.id),
                    ('date_start', '>=', date_midnight),
                    ('date_stop', '<=', end_of_date),
                    ('work_entry_type_id', '=', attendance_work_type.id)
                ])
                vals_list.append({
                    'employee_id': record.employee_id.id,
                    'check_in': work_entry.date_start,
                    'check_out': work_entry.date_stop,
                    'mission_id': record.id
                })
                current_date += timedelta(days=1)
        self.env['hr.attendance'].create(vals_list)
