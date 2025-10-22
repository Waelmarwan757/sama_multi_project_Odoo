from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrTransfer(models.Model):
    _name = 'hr.transfer'
    _inherit = ['mail.thread']
    _description = 'HR Transfer'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    date = fields.Date(string='Transfer Date', required=True, default=fields.Date.context_today, tracking=True)
    current_location_id = fields.Many2one('hr.work.location', related='employee_id.work_location_id', string='From Location', store=True, depends=['employee_id'])
    new_location_id = fields.Many2one('hr.work.location', string='To Location', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        # ('confirmed', 'Confirmed'),
        ('done', 'Transferred'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    reason = fields.Text(string='Reason for Transfer', required=True, tracking=True)

    @api.constrains('new_location_id')
    def _check_different_location(self):
        for record in self:
            if record.new_location_id == record.current_location_id:
                raise ValidationError("The new location must be different from the current location.")

    @api.constrains('employee_id')
    def _check_one_request(self):
        for record in self:
            existing_transfers = self.search_count([
                ('employee_id', '=', record.employee_id.id),
                ('state', '=', 'draft'),
                ('id', '!=', record.id)
            ])
            if existing_transfers:
                raise ValidationError("There is already an ongoing transfer request for this employee.")

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        for record in self:
            record.employee_id.work_location_id = record.new_location_id.id
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})