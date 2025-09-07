import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

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