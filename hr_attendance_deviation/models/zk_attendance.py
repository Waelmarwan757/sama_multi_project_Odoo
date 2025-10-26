from odoo import models, Command

class ZkAttendance(models.Model):
    _inherit = 'zk.attendance'

    def _get_grouped_data(self):
        groups = self.env['zk.attendance'].read_group(
            domain=[('id', 'in', self.ids), ('hr_attendance_id', '=', False), ('att_date', '!=', date.today())],
            fields=['employee_id', 'att_date', 'punch_time'],
            groupby=['employee_id', 'att_date:day', 'punch_time', 'id'],
            lazy=False
        )
        data = defaultdict(lambda: defaultdict(lambda: []))
        for group in groups:
            employee_id = group['employee_id'][0]
            att_date = group['att_date:day']

            data[employee_id][att_date].append(Command.link(group['id'][0]))

        return data

    def cron_auto_link_hr_attendance(self):
