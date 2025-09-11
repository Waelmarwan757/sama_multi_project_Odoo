import logging
import calendar
from datetime import timedelta
from odoo import models, api, fields
from odoo.exceptions import ValidationError

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    @api.constrains('employee_id', 'request_date_from', 'holiday_status_id')
    def _check_requests_limit(self):
        for record in self:
            if record.holiday_status_id.requests_limit > 0:
                first_day = record.request_date_from.replace(day=1)
                last_day = record.request_date_from.replace(day=calendar.monthrange(record.request_date_from.year, record.request_date_from.month)[1])
                domain = [
                    ('employee_id', '=', record.employee_id.id),
                    ('state', 'not in', ['refuse', 'cancel']),
                    ('request_date_from', '>=', first_day),
                    ('request_date_to', '<=', last_day),
                    ('holiday_status_id', '=', record.holiday_status_id.id),
                ]
                requests_count = self.search_count(domain)
                if requests_count > record.holiday_status_id.requests_limit:
                    raise ValidationError(f"You have reached the maximum number of leave requests ({record.holiday_status_id.requests_limit}) for {record.holiday_status_id.name} in {record.request_date_from.strftime('%B %Y')}.")

    @api.constrains('request_date_from', 'holiday_status_id')
    def _check_request_offset(self):
        today = fields.Date.context_today(self)
        requests = self.filtered(lambda r: r.holiday_status_id.enable_request_offset)
        for record in requests:
            limit_date = record.request_date_from - timedelta(days=record.holiday_status_id.request_offset)
            if today > limit_date:
                raise ValidationError(f"The leave request must be at least on or before {limit_date}.")