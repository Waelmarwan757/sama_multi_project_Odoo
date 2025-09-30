from odoo import models, fields, api



class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    hr_leave_id = fields.Many2one('hr.leave', compute='_compute_hr_leave_id', store=True)

    @api.depends('employee_id', 'check_in', 'check_out')
    def _compute_hr_leave_id(self):
        for record in self:
            record.hr_leave_id = self.env['hr.leave'].search([
                ('employee_id', '=', record.employee_id.id),
                ('request_date_from', '=', fields.Date.today()),
                ('state', '=', 'validate'),
                ('holiday_status_id.code', '=', 'LATE'),
            ], limit=1)