from odoo import models

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_compute_sheet(self):
        res = super().action_compute_sheet()
        self.mapped('employee_id').action_generate_absent_entries(self.date_from, self.date_to)
        return res