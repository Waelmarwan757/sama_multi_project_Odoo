from odoo import models

class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def _compute_related_records_count(self):
        for line in self:
            if line.salary_rule_id.code != 'LATE_PENALTY':
                super(HrPayslipLine, line)._compute_related_records_count()
            else:
                date_from = line.slip_id.date_from
                date_to = line.slip_id.date_to
                employee_id = line.slip_id.employee_id
                leaves_count = self.env['hr.leave'].search_count([
                    ('employee_id', '=', employee_id.id),
                    ('request_date_from', '>=', date_from),
                    ('request_date_to', '<=', date_to),
                    ('state', '=', 'validate'),
                    ('holiday_status_id.code', '=', 'LATE'),
                ])
                line.update({'related_records_count': leaves_count})

    def open_related_records(self):
        self.ensure_one()
        if self.salary_rule_id.code != 'LATE_PENALTY':
            return super(HrPayslipLine, self).open_related_records()
        else:
            date_from = self.slip_id.date_from
            date_to = self.slip_id.date_to
            employee_id = self.slip_id.employee_id
            action = self.env["ir.actions.actions"]._for_xml_id(
                "sl_hr_holidays.action_hr_leave_payslip"
            )
            action['domain'] = [
                ('employee_id', '=', employee_id.id),
                ('request_date_from', '>=', date_from),
                ('request_date_to', '<=', date_to),
                ('state', '=', 'validate'),
                ('holiday_status_id.code', '=', 'LATE'),
            ]
            return action