##############################################################################
#
# Copyright (c) 2004-2010 TINY SPRL. (http://tiny.be) 
#                     and Peter Dapper <verkoop at of-is.nl>
#                     and Konrad Wojas <info at wojas.nl>
#                          All Rights Reserved.
#                     
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################
#
# This filter imports .mt940-files. It's based on the old filter, with a 
# completely new MT940 parsing engine that can be tested and used independently
# from OpenERP account_bankimport
#
from osv import fields, osv
import pooler
from mt940_parser import parse_mt940, get_sign

DATE_FORMAT = '%d/%m/%y'

def get_data(self, cr, uid, bankData, bank_statement):
    """OpenERP account_bankimport filter function"""

    # first parse the data before doing anything else
    sheets = parse_mt940(bankData)

    # connection
    pool = pooler.get_pool(cr.dbname)
    
    bank_statement_output = []
    
    for sheet in sheets:
        for entry in sheet.entries:
            st_line = {}

            st_line['val_date'] = entry.value_date.strftime(DATE_FORMAT)
            st_line['date'] = st_line['val_date']
            if entry.entry_date:
                st_line['entry_date'] = entry.entry_date.strftime(DATE_FORMAT)
            else:
                st_line['entry_date'] = st_line['val_date']
                
            if entry.dc=='D':
                # payment
                st_line['account_id'] = bank_statement['def_pay_acc']
            else:
                # receive
                st_line['account_id'] = bank_statement['def_rec_acc']

            st_line['amount'] = get_sign(entry.dc) * entry.amount
            
            st_line['free_comm'] = ""
            st_line['partner_id'] = 0
            st_line['type'] = 'general'

            st_line['partner_acc_number'] = entry.other_account
            st_line['cntry_number'] = entry.other_account
            st_line['ref'] = entry.other_account
            
            st_line['name'] = entry.name
            st_line['contry_name'] = entry.name
            st_line['free_comm'] = entry.description

            # check if there is already a statement like this...
            check_ids = pool.get('account.bank.statement.line').search(cr, uid, [
                ('amount', '=', st_line['amount']), 
                ('date', '=', entry.value_date),
                ('name', '=', st_line['name'])
            ])
            if check_ids:
                # already exists, don't add
                continue
            
            # check if there already is a relation ..., and use the ID
            bank_ids = pool.get('res.partner.bank').search(cr, uid, [
                ('acc_number', '=', st_line['partner_acc_number'])
            ])
            if bank_ids:
                bank = pool.get('res.partner.bank').browse(cr, uid, bank_ids[0], context={})
                if bank.partner_id:
                    st_line['partner_id'] = bank.partner_id.id
                    partner = pool.get('res.partner').browse(cr, uid, bank.partner_id, context={})
                    if bank.partner_id.supplier == True and bank.partner_id.customer == False:
                        st_line['account_id'] = bank.partner_id.property_account_receivable.id
                        st_line['type'] ='supplier'
                    elif bank.partner_id.customer == True and bank.partner_id.supplier == False:
                        st_line['account_id'] = bank.partner_id.property_account_payable.id
                        st_line['type'] = 'customer'
            
            bank_statement_output.append(st_line)
            
    return bank_statement_output


