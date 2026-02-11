from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    custody_ids = fields.One2many('hr.custody', 'employee_id', string='Custody')
    custody_count = fields.Integer(string='Custody Count', compute='_compute_custody_count')

    @api.depends('custody_ids')
    def _compute_custody_count(self):
        for employee in self:
            employee.custody_count = len(employee.custody_ids)

    def action_view_custody(self):
        self.ensure_one()
        return {
            'name': 'Custody',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'res_model': 'hr.custody',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
