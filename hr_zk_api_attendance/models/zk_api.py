import json
import requests
import logging
from urllib.parse import quote
from datetime import date
from odoo import models, fields, api, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

class ZkApi(models.Model):
    _name = 'zk.api'
    _description = 'ZK API'

    name = fields.Char(string='Name', required=True)
    url = fields.Char(string='URL', required=True)
    username = fields.Char(string='Username', required=True)
    password = fields.Char(string='Password', required=True)
    token = fields.Char(string='Token')
    active = fields.Boolean(string='Active', default=True)

    def _get_headers(self, renew_token=False):
        """Function to get the headers for API requests"""
        try:
            token = self.token
            if not token or renew_token:
                self.action_set_token()
        except Exception as e:
            _logger.error(f"Error getting auth token: {e}")
            raise UserError(_("Failed to get authentication token."))
        return {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }

    def _get_auth_token(self):
        endpoint = "/api-token-auth/"
        url = f"{self.url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
        }
        data = {
            "username": self.username,
            "password": self.password
        }

        response = requests.post(url, data=json.dumps(data), headers=headers)
        response.raise_for_status()  # Raise an error for bad responses

        return response.json().get('token')

    def action_sync_departments(self):
        """Function to set departments from ZK API"""
        headers = self._get_headers()
        self.env['zk.department'].sync_departments(headers, self.url)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
            'title': _('Success'),
            'message': _('Departments synchronized successfully.'),
            'type': 'success',
            'sticky': False,
            }
        }

    def action_sync_attendance(self, cron=False):
        """Function to set attendance from ZK API"""
        headers = self._get_headers()
        attendance_ids = self.env['zk.attendance'].sync_attendance(headers, self.url)
        if cron:
            return attendance_ids
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Attendance synchronized successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_set_token(self):
        """Function to set the token manually"""
        token = self._get_auth_token()
        self.token = token  # Store the token for future use

    def cron_auto_sync_attendance(self):
        """Cron job to automatically sync attendance"""
        for api in self.search([('active', '=', True)]):
            try:
                api.action_set_token()
                api.action_sync_departments()
                attendance_ids = api.action_sync_attendance(cron=True)
                _logger.info(f"Attendance records synced: {len(attendance_ids)}")
                attendance_ids.action_link_hr_attendance()
            except Exception as e:
                _logger.error(f"Error during cron auto sync attendance: {e}")