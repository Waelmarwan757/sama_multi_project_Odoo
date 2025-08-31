import uuid
from odoo import models, fields, _


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    token = fields.Char(default=lambda self: str(uuid.uuid4()))

    def get_report_summary(self):
        return {
            _('Earnings'): sum(self.details_by_salary_rule_category_ids.filtered(lambda x: x.total > 0 and x.code not in ['NET', 'BASIC_SALARY']).mapped('total')),
            _('Deductions'): sum(self.details_by_salary_rule_category_ids.filtered(lambda x: x.total < 0).mapped('total')),
            _('Net'): self.details_by_salary_rule_category_ids.filtered(lambda x: x.code == 'NET').total,
        }

    def generate_access_token(self):
        for payslip in self:
            payslip.token = str(uuid.uuid4())

    def get_report_url(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/payslip/{self.token}?lang=ar_001&type=pdf"