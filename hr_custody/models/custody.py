from odoo import models, fields, api, _
from datetime import date

class HrCustody(models.Model):
    _name = 'hr.custody'
    _description = 'Employee Custody'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True)
    custody_type_id = fields.Many2one('hr.custody.type', string='Custody Type')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    contract_id = fields.Many2one('hr.contract', string='Contract')
    date_receive = fields.Date(string='Receive Date', required=True, default=fields.Date.today)
    date_return = fields.Date(string='Return Date')
    image = fields.Binary(string='Image')
    note = fields.Text(string='Notes')
    state = fields.Selection([
        ('received', 'Received'),
        ('cleared', 'Cleared')
    ], string='Status', default='received', track_visibility='onchange')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            # Find running contract
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '=', 'open')
            ], limit=1)
            if contract:
                self.contract_id = contract.id

    def action_clear(self):
        for rec in self:
            rec.state = 'cleared'
            rec.date_return = date.today()
