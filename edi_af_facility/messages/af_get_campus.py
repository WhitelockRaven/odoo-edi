# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution, third party addon
#    Copyright (C) 2004-2020 Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import pytz
import ast

import logging
_logger = logging.getLogger(__name__)

LOCAL_TZ = 'Europe/Stockholm'

class ediServiceNowOperation(models.Model):
    _name = "edi.service_now_operation"

    name = fields.Char(string="Name")
    opening_hours = fields.Char(string = 'Opening hours')
    personal_service_opening = fields.Char(string="Opening hours for personal service")
    office_code = fields.Char(string="Office code")
    organisational_belongin = fields.Char(string="Organisation")

    workplace_number = fields.Char(string="Workplace number")
    location_code = fields.Char(string="Location code")

    department_id = fields.Many2one(comodel_name='hr.department', string="Department")
    location_id = fields.Many2one(comodel_name='hr.location', string="Location")

    accessibilies = fields.Char()
    active = fields.Char()
    name = fields.Char()
    phone_hours = fields.Char()
    fax_number = fields.Char()
    email_address = fields.Char()
    phone_number = fields.Char()
    operation_id = fields.Char()
    last_operation_day = fields.Char()
    public_contact_name = fields.Char()
    public_contact_source = fields.Char()
    public_contact_user_name = fields.Char()
    visiting_address_street = fields.Char()
    visiting_address_zip = fields.Char()
    visiting_address_city = fields.Char()
    mailing_address_street = fields.Char()
    mailing_address_zip = fields.Char()
    mailing_address_city = fields.Char()
    campus_name = fields.Char()
    campus_workplace_number = fields.Char()
    campus_location_code = fields.Char()
    campus_county_number = fields.Char()
    campus_latitude = fields.Char()
    campus_longitude = fields.Char()
    x500_id = fields.Char()
    
    @api.one
    def compute_department_id(self):
        department = self.env['ir.model.data'].xmlid_to_res_id('__ais_import__.dptmnt_office_%s' % self.office_code)
        if department:
            self.department_id = department.id
        else:
            self.department_id = self.env['hr.department'].create({'office_code': self.office_code, 'note': _('Missing in AIS-F')}).id

    @api.one
    def compute_accessibilies(self, location_id, accessibility_list):
        for accessibility in accessibility_list:
            accessibility['location_id'] = location_id
            self.env['hr.location.accessibility'].create(accessibility)

    @api.one
    def compute_location_id(self, department_id):
        location = self.env['hr.location'].search('location_code', '=', location_code)
        #create partners from fields
        visitation_address_vals = {
            'type': 'visitation address',
            'street': self.visiting_address_street,
            'city': self.visiting_address_city,
            'zip': self.visiting_address_zip,
        }
        visitng_address = self.env['res.partner'].create(visitation_address_vals)
        mailing_address_vals = {
            'type': 'mailing address',
            'street': self.mailing_address_street,
            'city': self.mailing_address_city,
            'zip': self.mailing_address_zip,
        }
        mailing_address = self.env['res.partner'].create(mailing_address_vals)

        partner_vals = {
            'phone': self.phone_number,
            'fax': self.fax_number,        
        }

        partner = self.env['res.partner'].create(partner_vals)

        vals = {
            'name': self.name,
            'visiting_address_id': visitng_address.id,
            'mailing_address_id': mailing_address.id,
            'partner_id': partner.id,
            'opening_hours': self.opening_hours,
            'personal_service_opening': self.personal_service_opening,
            'workplace_number': self.workplace_number,
            'location_code': self.location_code,
        }
        
        if location:
            if not department_id in location.department_ids:
               location.department_ids = [(4, 0, department_id)]
            location.write(vals)
        else:
            vals['department_ids'] = [(4, 0, department_id)]
            self.env['hr.location'].create(vals)


class edi_message(models.Model):
    _inherit='edi.message'

    @api.one
    def unpack(self):
        if self.edi_type.id == self.env.ref('edi_af_facility.office_campus').id:
            # decode string and convert string to tuple, convert tuple to dict
            body = json.loads(self.body.decode("utf-8"))   

            for operation_rec in body:
                vals = {}
                for key in operation_rec.keys():
                    vals[key.replace('.','_')] = operation_rec[key]
                vals['accessibilities'] = "%s" % vals['accessibilities']

                operation = self.env['edi.service_now_operation'].create(vals)
                operation.compute_department_id()
                operation.compute_location_id(operation.department_id)
                operation.compute_accessibilies(operation.location_id, operation_rec['accessibilities'])
        else:
            super(edi_message, self).unpack()
        
    @api.model
    def create_partner_from_dict(self, vals, external_xmlid):
        obj = self.env['res.partner'].browse(self.env['ir.model.data'].xmlid_to_res_id(external_xmlid))
        if obj:
            obj.write(vals)
        else:
            obj = self.env['res.partner'].create(vals) 
            self.env['ir.model.data'].create(
                {
                'name': external_xmlid.split('.')[1], 
                'module': external_xmlid.split('.')[0],
                'model': obj._name,
                'res_id': obj.id
                })  
        return obj 

    @api.one
    def pack(self):
        if self.edi_type.id == self.env.ref('edi_af_facility.office_campus').id:
            if not self.model_record or self.model_record._name != 'res.partner' or not self.model_record.is_jobseeker:
                raise Warning("Appointment: Attached record is not a res.partner or not a jobseeker! {model}".format(model=self.model_record and self.model_record._name or None))

            obj = self.model_record #res.partner 
            self.body = self.edi_type.type_mapping.format(
                path = "service-now-on-site-operations/v1/operations"
            )
            envelope = self.env['edi.envelope'].create({
                'name': 'asok office request',
                'route_id': self.route_id.id,
                'route_type': self.route_type,
                # 'recipient': self.recipient.id,
                # 'sender': self.env.ref('base.main_partner').id,
                # 'application': app.name,
                # 'edi_message_ids': [(6, 0, msg_ids)]
                'edi_message_ids': [(6, 0, [self.id])]
            })
        else:
            super(edi_message, self).pack()
