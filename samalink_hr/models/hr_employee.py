import logging
from datetime import datetime, time, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    allow_check_from_odoo = fields.Boolean(string="Allow Check From Odoo", default=False, groups="base.group_system,hr.group_hr_user")

    @api.constrains('pin')
    def _check_pin(self):
        groups = self.read_group(
            domain=[('pin', '!=', False)],
            fields=['pin'],
            groupby=['pin']
        )
        for group in groups:
            if group['pin_count'] > 1:
                raise UserError(f"PIN Code {group['pin']} must be unique found {group['pin_count']} instances.")

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not (self.env.user.has_group('hr.group_hr_manager') or self.env.user.has_group('samalink_security_groups.group_samalink_hr_officer')):
            raise UserError("You cannot change the Manager field. Please contact your administrator.")

    def _attendance_action_change(self, geo_information=None):
        self.ensure_one()
        if not self.sudo().allow_check_from_odoo:
            raise UserError("You are not allowed to check in/out from Odoo. Please contact your administrator.")
        if not geo_information['latitude'] or not geo_information['longitude']:
            raise UserError("Location information is required for attendance actions.")
        return super()._attendance_action_change(geo_information=geo_information)

    def action_create_user(self):
        self.ensure_one()
        if self.user_id:
            raise ValidationError(_("This employee already has an user."))
        if not self.work_email and not self.mobile_phone:
            raise ValidationError(_("Employee must have a work email to create a user."))
        vals = {
            'create_employee_id': self.id,
            'name': self.name,
            'phone': self.work_phone,
            'mobile': self.mobile_phone,
            'login': self.work_email,
            'partner_id': self.work_contact_id.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('samalink_security_groups.group_samalink_employee').id])],
            'password': "1",
        }
        user = self.env['res.users'].sudo().create(vals)

    def action_generate_absent_entries(self, start_date=None, end_date=None):
        self.ensure_one()
        if not start_date or not end_date:
            start_date = fields.Date.today().replace(day=1)
            end_date = fields.Date.today()
        attendance_date_list = self._get_attendece_dates(start_date, end_date)
        self._unlink_existing_absent_entry(start_date, end_date)
        vals_list = []
        for current_date in attendance_date_list:
            vals_list.append({
                'employee_id': self.id,
                'date': current_date,
                'reason': 'Generated absent entry'
            })
        if vals_list:
            self.env['hr.absent.entry'].create(vals_list)

    def _get_attendece_dates(self, date_from, date_to):
        self.ensure_one()
        date_midnight = datetime.combine(date_from, time.min)
        end_of_date = datetime.combine(date_to, time.max)
        domain = [('check_in', '>=', date_midnight), ('check_in', '<=', end_of_date)]
        attendance_records = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '>=', date_from),
            ('check_out', '<=', date_to)
        ])
        return [date_time.date() for date_time in attendance_records.mapped('check_in')]

    def _unlink_existing_absent_entry(self, date_from, date_to):
        self.ensure_one()
        absent_entries = self.env['hr.absent.entry'].search([
            ('employee_id', '=', self.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ])
        absent_entries.sudo().unlink()
    
    def action_view_absent_entries(self):
        self.ensure_one()
        action = self.env.ref('samalink_hr.action_hr_absent_entry').read()[0]
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action