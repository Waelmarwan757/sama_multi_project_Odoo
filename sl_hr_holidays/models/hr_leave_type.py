from odoo import models, fields


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    requests_limit = fields.Integer(string="Requests Limit (Monthly)", default=3, help="Maximum number of leave requests an employee can make in a month.")
    request_offset = fields.Integer(string="Request Before (Days)", default=0, help="Number of days to offset the leave request.")