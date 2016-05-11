# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution, third party addon
#    Copyright (C) 2004-2016 Vertel AB (<http://vertel.se>).
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
from openerp import models, fields, api, _
import base64
from datetime import datetime
#https://www.stylusstudio.com/edifact/frames.htm

import logging
_logger = logging.getLogger(__name__)

class edi_envelope(models.Model):
    _inherit = 'edi.envelope' 
    
    @api.one
    def fold(self,route): # Folds messages in an envelope
        for m in self.env['edi.message'].search([('envelope_id','=',None),('route_id','=',route.id)]):
            m.envelope_id = self.id
        envelope = super(edi_envelope,self).fold(route)
        if route.envelope_type == 'edifact':
            interchange_controle_ref = ''
            date = ''
            time = ''
            UNA = "UNA:+.? '"
            UNB = "UNB+UNOC:3+%s:14+%s:14+%s:%s+%s++ICARSP4'" % (route.partner_id.company_id.partner_id.gs1_gln, route.partner_id.gs1_gln, date, time, interchange_control_ref)
            body = ''.join([base64.b64decode(m.body) for m in envelope.message_ids])
            UNZ = "UNZ+%s+627'" % (len(envelope.message_ids),len(body))
            envelope.body = base64.b64encode(UNA + UNB + body + UNZ)
        return envelope

    def _create_UNB_segment(self,sender, recipient):
        self._seg_count += 1
        return "UNB+UNOC:3+%s:14+%s:14+%s:%s+%s++ICARSP4'" % (sender.gs1_gln, recipient.gs1_gln, date, time, interchange_control_ref)


class edi_route(models.Model):
    _inherit = 'edi.route' 
    
    edi_type = fields.Selection(selection_add=[('ORDERS','ORDERS'),('ORDRSP','ORDRSP')])
    envelope_type = fields.Selection(selection_add=[('edifact','Edifact')])


def _escape_string(s):
    if isinstance(s, basestring):
        return s.replace('?', '??').replace('+', '?+').replace(':', '?:').replace("'", "?'") #.replace('\n', '') needed?
    return s



class edi_message(models.Model):
    _inherit='edi.message'
    
    _seg_count = 0
    _lin_count = 0

    def UNH(self,edi_type=False, version='D', release='96A', ass_code='EAN005'):
        self._seg_count += 1
        if not edi_type:
            edi_type = self.edi_type
        return "UNH+{ref_no}+{msg_type}:{version}:{release}:UN:{ass_code}'".format(ref_no=self.name,msg_type=edi_type,version=version,release=release, ass_code=ass_code)

    def BGM(self,doc_code=False, doc_no=False,status=''):
        #TODO: look up test mode on route and add to BGM
        
        # Beginning of message
        # doc_code = Order, Document/message by means of which a buyer initiates a transaction with a seller involving the supply of goods or services as specified, according to conditions set out in an offer, or otherwise known to the buyer.
        # BGM+220::9+20120215150105472'
        # doc_code 231 Purchase order response, Response to an purchase order already received.
        # BGM+231::9+201101311720471+4'
        # doc_code 351 Despatch advice, Document/message by means of which the seller or consignor informs the consignee about the despatch of goods.
        # BGM+351+SO069412+9'
        self._seg_count += 1
        if doc_code == 220: # Resp agency = EAN/GS1 (9),
            return "BGM+220::9+{doc_no}'".format(doc_no=_escape_string(doc_no))
        elif doc_code == 231: # Resp agency = EAN/GS1 (9), Message function code = Change (4)
            return "BGM+231::9+{doc_no}+4'".format(doc_no=_escape_string(doc_no))
        elif doc_code == 280: # Resp agency = EAN/GS1 (9), Message function code = Change (4)
            return "BGM+280::9+{doc_no}+9'".format(doc_no=_escape_string(doc_no)) 
        elif doc_code == 351:
            return "BGM+351+{doc_no}+9'".format(doc_no=_escape_string(doc_no))
        #return "BGM+{code}::{}+{doc_no}+{status}'".format(doc_no=_escape_string(doc_no), code=doc_code, status=status)
    
    def CPS(self):
        self._seg_count += 1
        return "CPS+%s'" % (self._lin_count + 1)
    
    def CNT(self, qualifier, value):
        self._seg_count += 1
        return "CNT+%s+%s'" % (qualifier, value)
    
    def DTM(self,func_code, dt=False, format=102):
        self._seg_count += 1
        #11	Despatch date and or time - (2170) Date/time on which the goods are or are expected to be despatched or shipped.
        #13 Terms net due date - Date by which payment must be made.
        #35	Delivery date/time, actual - Date/time on which goods or consignment are delivered at their destination.
        #50 Goods receipt date/time - Date/time upon which the goods were received by a given party.
        #132 Transport means arrival date/time, estimated
        #137 Document/message date/time, date/time when a document/message is issued. This may include authentication.
        #167 Charge period start date - The charge period's first date.
        #168 Charge period end date - The charge period's last date.
        if not dt:
            dt = fields.Datetime.now()
        dt = fields.Datetime.from_string(dt)
        if format == 102:
            dt = dt.strftime('%Y%M%d')
        elif format == 203:
            dt = dt.strftime('%Y%M%d%H%M')
        return "DTM+%s:%s:%s'" % (func_code, dt, format)

    def FTX(self, msg1, msg2='', msg3='', msg4='', msg5='', subj='ZZZ', func=1, ref='001'):
        self._seg_count += 1        
        return "FTX+%s+%s+%s+%s:%s:%s:%s:%s'" % (subj, func, ref, _escape_string(msg1), _escape_string(msg2), _escape_string(msg3), _escape_string(msg4), _escape_string(msg5))
    
    def GIN(self, sscc='373500310002299341'):
        self._seg_count += 1
        #BJ 		Serial shipping container code
        return "GIN+SS+%s'" % sscc
    
    #CR = Customer Reference
    def RFF(self, ref, qualifier='CR'):
        # CR = Customer reference, AAS = Transport document number, Reference assigned by the carrier or his agent to the transport document.
        self._seg_count += 1
        return "RFF+%s:%s'" % (qualifier, ref)

    def TAX(self, rate, tax_type = 'VAT', qualifier = 7, category = 'S'):
        self._seg_count += 1
        #qualifier
        #   7 = tax
        return "TAX+%s+%s+++:::%s+%s'" % (qualifier, tax_type, rate, category)
    
    def _NAD(self,role, partner, type='GLN'):
        self._seg_count += 1        
        if type == 'GLN':
            party_id = partner.gs1_gln
            if not party_id:
                #raise Warning('NAD missing GLN role=%s partner=%s' % (role,partner.name))
                party_id = 1 # Jusr for test
            code = 9
        return "NAD+%s+%s::%s'" % (role, party_id, code)
    
    def NAD_SU(self,type='GLN'):
        return self._NAD('SU',self.consignor_id,type)
    def NAD_BY(self,type='GLN'):
        return self._NAD('BY',self.consignee_id,type)
    def NAD_SH(self,type='GLN'):
        return self._NAD('SH',self.forwarder_id,type)
    def NAD_DP(self,type='GLN'):
        return sielf._NAD('DP',self.carrier_id,type)
    def NAD_CN(self,type='GLN'):
        return self._NAD('CN',self.consignee_id,type)
    
    #code = error/status code
    def LIN(self, line):
        self._seg_count += 1
        self._lin_count += 1
        item_nr_type = 'EU'
        if line._name == 'account.invoice.line':
            code = ''
        elif line._name == 'stock.pack.operation':
            code = ''
        elif line.product_uom_qty <= 0:
            code = 7 # Not accepted
        elif line.product_uom_qty != line.order_qty:
            code = 12 # Quantity changed
        else:
            code = 5 # Accepted without amendment
        return "LIN+%s+%s+%s:%s::%s'" %(self._lin_count, code, line.product_id.gs1_gtin14 or line.product_id.gs1_gtin13, item_nr_type, 9)
    
    def MOA(self, amount, qualifier = 203):
        self._seg_count += 1
        return "MOA+%s:%s'" % (qualifier, amount)
    
    def PAC(self):
        self._seg_count += 1
        #30 	½ EUR-pall
        #34     EUR 2-pall
        #35     EUR 3-pall
        #36     EUR 6-pall
        #37 	EUR-pall (EUR6)
        return "PAC+1+:52+34:::7350000000269'"
    
    def PAT(self, pttq=3, ptr=66, tr=1):
        self._seg_count += 1
        #pttq   4279 	Payment terms type qualifier
            #3 Fixed date - Payments are due on the fixed date specified.
        #ptr    2475 	Payment time reference, coded
            #66	Specified date - Date specified elsewhere.
		#tr     2009 	Time relation, coded
            #1	Date of order - Payment time reference is date of order.
        
        return "PAT+%s++%s:%s'" % (pttq, ptr, tr)
    
    def PCI(self):
        self._seg_count += 1
        #33E 		Marked with serial shipping container code (EAN Code)
        return "PCI+33E'"
    
    #SA = supplier code BP = buyer code
    def PIA(self,product, code):
        self._seg_count += 1
        prod_nr = None
        if code == 'SA':
            prod_nr = product.default_code or '#'
        elif code == 'BP':
            pass
        if prod_nr:
            return "PIA+5+%s:%s'" % (prod_nr, code)
        raise Warning("PIA: couldn't find product code (%s) for %s (id: %s)" % (code, product.name, product.id))

    def PRI(self):
        self._seg_count += 1
        pass
        
    def QTY(self,line, code = None):
        self._seg_count += 1
       
        if line._name == 'account.invoice.line':
            code = 47
            qty = line.quantity
        else:
            qty = line.product_uom_qty
        
         #~ if line.product_uom_qty != line.order_qty:
            #~ code = 12
        #~ else:
        if code:
            pass
        else:
            code = 21
        return "QTY+%s:%s'" % (code, qty)

    def UNS(self):
        self._seg_count += 1
        return "UNS+S'"

    def UNT(self):
        self._seg_count += 1
        return "UNT+{count}+{ref}'".format(count=self._seg_count,ref=self.name)

            
    def _get_partner(self, l):
        _logger.warn('get partner %s' % l)
        partner = None
        if l[2] == '9':
            partner = self.env['res.partner'].search([('gln', '=', l[0])])
        _logger.warn(partner)
        if len(partner) == 1:
            return partner[0]
        _logger.warn('Warning!')
        raise Warning("Unknown part %s" % len(l) >0 and l[0] or "[EMPTY LIST!]")
    
    def _parse_quantity(self, l):
        #if l[0] == '21':
        return float(l[1])
    
    def _get_product(self, l):
        product = None
        if l[1] == 'EN':
            product = self.env['product.product'].search([('gs1_gtin14', '=', l[0])])
        if product:
            return product
        raise Warning('Product not found! EAN: %s' % l[0])
    
    @api.model
    def _parse_date(self, l):
        if l[2] == '102':
            return fields.Datetime.to_string(datetime.strptime(l[1], '%Y%m%d'))        

