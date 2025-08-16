from odoo import models, api
from odoo.exceptions import UserError

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def action_open_my_employee(self):
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)], limit=1)
        if not employee:
            raise UserError("No employee record linked to your user.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Employee Info',
            'res_model': 'hr.employee',
            'view_mode': 'form',
            'res_id': employee.id,
            'target': 'current',
            'view_id': self.env.ref('samalink_security_groups.hr_employee_my_info_form_view').id,
        }