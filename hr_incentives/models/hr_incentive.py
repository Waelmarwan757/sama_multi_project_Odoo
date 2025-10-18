from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrIncentive(models.Model):
    _name = 'hr.incentive'
    _description = 'HR Incentive'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    current_contract_id = fields.Many2one('hr.contract', related='employee_id.contract_id', string='Contract', store=True)
    type = fields.Selection([
        ('bonus', 'Bonus'),
        ('penalty', 'Penalty')
    ], string='Incentive Type', required=True, default='bonus')
    based_on = fields.Selection([
        ('days', 'Days'),
        ('amount', 'Amount')
    ], string='Based On', required=True, default='days')
    days = fields.Integer(string='Days')
    amount = fields.Float(string='Amount', compute="_compute_amount", store=True, readonly=False)
    date = fields.Date(string='Date', default=fields.Date.today)
    description = fields.Text(string='Description')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'First Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft')
    work_location_id = fields.Many2one(related="employee_id.work_location_id", domain="[('address_id', '=', address_id)]")

    @api.depends('type', 'days', 'current_contract_id.wage')
    def _compute_amount(self):
        for record in self:
            if record.based_on == 'days' and record.days > 0:
                day_rate = record.current_contract_id.wage / 30 if record.current_contract_id else 0
                amount = record.days * day_rate
                if record.type == 'bonus':
                    record.amount = amount
                elif record.type == 'penalty':
                    record.amount = -amount

    @api.constrains('days', 'amount')
    def _check_days_amount(self):
        for record in self:
            if record.based_on == 'days' and record.days <= 0:
                raise ValidationError("Days must be positive when based on days.")
            if record.based_on == 'amount' and record.amount == 0:
                raise ValidationError("Amount must not be zero when based on amount.")

    @api.constrains('employee_id')
    def _check_current_wage(self):
        for record in self:
            if not record.current_contract_id or record.current_contract_id.wage <= 0:
                raise ValidationError("The employee must have a current contract with a positive wage.")

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_validate(self):
        self.write({'state': 'validated'})

    def action_approve(self):
        if not self.env.user.has_group('hr_incentives.group_hr_incentives_manager'):
            self.action_validate()
        else:
            self.write({'state': 'approved'})

    def action_refuse(self):
        self.write({'state': 'rejected'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})