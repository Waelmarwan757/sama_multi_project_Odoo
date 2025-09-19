import logging
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
