import logging
from odoo import models, fields, api
from odoo.exceptions import UserError


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

    def _attendance_action_change(self, geo_information=None):
        self.ensure_one()
        if not self.sudo().allow_check_from_odoo:
            raise UserError("You are not allowed to check in/out from Odoo. Please contact your administrator.")
        return super()._attendance_action_change(geo_information=geo_information)
