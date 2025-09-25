from datetime import datetime, time
from odoo import models

class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    def _compute_related_records_count(self):
        for line in self:
            date_from = line.slip_id.date_from
            date_to = line.slip_id.date_to
            employee_id = line.slip_id.employee_id
            if line.salary_rule_id.code not in ['PRESENT_DAYS', 'REST_ALLOW']:
                super(HrPayslipLine, line)._compute_related_records_count()
            elif line.salary_rule_id.code == 'PRESENT_DAYS':
                attendance_count = self.env['hr.attendance'].search_count(
                    [('check_in', '>=', date_from), ('check_in', '<=', date_to),
                     ('employee_id', '=', employee_id.id)]
                )
                line.update({'related_records_count': attendance_count})
            elif line.salary_rule_id.code == 'REST_ALLOW':
                from_date_midnight = datetime.combine(date_from, time.min)
                end_of_to_date = datetime.combine(date_to, time.max)
                weekend_days = self.env['hr.work.entry'].search_count([
                    ('employee_id', '=', employee_id.id),
                    ('date_start', '>=', from_date_midnight),
                    ('date_stop', '<=', end_of_to_date),
                    ('work_entry_type_id.code', '=', 'REST100')
                ])
                line.update({'related_records_count': weekend_days})

    def open_related_records(self):
        self.ensure_one()
        date_from = self.slip_id.date_from
        date_to = self.slip_id.date_to
        employee_id = self.slip_id.employee_id
        if self.salary_rule_id.code not in ['PRESENT_DAYS', 'REST_ALLOW']:
            return super(HrPayslipLine, self).open_related_records()
        elif self.salary_rule_id.code == 'PRESENT_DAYS':
            action = self.env["ir.actions.actions"]._for_xml_id(
                "samalink_hr.action_hr_attendance_list"
            )
            action['domain'] = [
                ('check_in', '>=', date_from), ('check_in', '<=', date_to),
                ('employee_id', '=', employee_id.id)
            ]
            return action
        elif self.salary_rule_id.code == 'REST_ALLOW':
            from_date_midnight = datetime.combine(date_from, time.min)
            end_of_to_date = datetime.combine(date_to, time.max)
            action = self.env["ir.actions.actions"]._for_xml_id(
                "samalink_hr.action_hr_rest_allow_list"
            )
            action['domain'] = [
                ('employee_id', '=', employee_id.id),
                ('date_start', '>=', from_date_midnight),
                ('date_stop', '<=', end_of_to_date),
                ('work_entry_type_id.code', '=', 'REST100')
            ]
            return action