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

class edi_message(models.Model):
    _inherit='edi.message'
            
    @api.one
    def unpack(self): #get the result of the request and update
        if self.edi_type.id == self.env.ref('edi_af_ag.ag_organisation').id:
            # decode string and convert string to tuple, convert tuple to dict
            body = dict(ast.literal_eval(self.body.decode("utf-8")))
            
            #start_time = datetime.strptime(body.get('start_time'), "%Y-%m-%dT%H:%M:%SZ")
            #stop_time = datetime.strptime(body.get('end_time'), "%Y-%m-%dT%H:%M:%SZ")


            # Integration gives us times in local (Europe/Stockholm) tz
            # Convert to UTC

            #start_time_utc = pytz.timezone(LOCAL_TZ).localize(start_time).astimezone(pytz.utc)
            #stop_time_utc = pytz.timezone(LOCAL_TZ).localize(stop_time).astimezone(pytz.utc)

            # schedules can exist every half hour from 09:00 to 16:00
            # check if calendar.schedule already exists 

            # type_id = self.env['calendar.appointment.type'].browse(body.get('type_id'))
            # schedule_id = self.env['calendar.schedule'].search([('type_id','=',type_id.id), ('start','=',start_time_utc)])
            identity = body.get('identitet')
            postal_address = body.get('basfakta').get('utdelningsadress') 
            visitation_address = body.get('basfakta').get('besoksadress')
            #orgnr = self.env['res.partner'].browse()
            partner = self.env['res.partner'].search([('company_registry', '=', identity.get('orgnr10')), ('cfar_number', '=', "")]) #if it doesn't have cfar it should only return a organisation
        
            
            if visitation_address.get('land') == "SE":
                visitation_address_dict = {
                'street': visitation_address.get('adress'),
                'city': visitation_address.get('postort'),
                'zip': visitation_address.get('postnr'),
                'country_id': 'base.se'
            }
            
            #clear out child_ids and append new visitation adress
            child_ids = [(0,0, visitation_address_dict)] #this might be incorrect
            if partner:
                # Update existing schedule only two values can change 
                vals = {
                    'name': identity.get('namn'),
                    'city': postal_address.get('postort'),
                    'street': postal_address.get('adress'),
                    'zip': postal_address.get('postnr'),
                    'phone': body.get('basfakta').get('telefon'),
                    'fax': body.get('basfakta').get('fax'),
                    'child_ids': child_ids
                }
                partner.write(vals)

            else:
                _logger.error("The partner doesn't exist")
        else:
            super(edi_message, self).unpack()

    @api.one
    def pack(self): #ask about thing that needs update
        if self.edi_type.id == self.env.ref('edi_af_ag.ag_organisation').id:
            if not self.model_record or self.model_record._name != 'res.partner':
                raise Warning("Appointment: Attached record is not an res.partner! {model}".format(model=self.model_record and self.model_record._name or None))

            obj = self.model_record
            self.body = self.edi_type.type_mapping.format( #takes url options, if no options are needed there will be a specific message size
                path = "masterdata-organisation/organisation",
                orgnr = obj.company_registry
            )

            envelope = self.env['edi.envelope'].create({
                'name': 'ag organisation request',
                'route_id': self.route_id.id,
                'route_type': self.route_type,
                # 'recipient': self.recipient.id,
                # 'sender': self.env.ref('base.main_partner').id,
                # 'application': app.name,
                # 'edi_message_ids': [(6, 0, msg_ids)]
                'edi_message_ids': [(6, 0, [self.id])]
            })

            # TODO: Decide if we want to fold here?
            # envelope.fold()
            
        else:
            super(edi_message, self).pack()
