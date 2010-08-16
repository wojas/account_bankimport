##############################################################################
#
# Copyright (c) 2004-2006 TINY SPRL. (http://tiny.be) and Eddy Boer
#                          All Rights Reserved.
#                    Fabien Pinckaers <fp@tiny.Be>
#                    Eddy Boer <tinyerp@EdbO.xs4all.nl>
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
# I used the code of account_coda as base for this module. The module does
# exactly the same thing as account_coda. The difference is the file-layout. 
#
# This module can import .asc-files (BRI-layout).
#

import time
from osv import osv,fields

import urllib, urllib2, sgmllib
from BeautifulSoup import BeautifulSoup, SoupStrainer
import re, string

def _opschonen(name):
	p = name.split('>')
	n = p[2].split('<')
	return n[0]
	
def _get_bank_data(bank_acc):

	p = {}
	
	urldata = {'number':bank_acc,'method':'POST'}
	
	data = urllib.urlencode(urldata)
	link = "http://www.ibannl.org/iban_check.php"
	
	req = urllib2.Request(link, data)
	f = urllib2.urlopen(req)
	s = f.read()
	
	soup = BeautifulSoup(''.join(s))
	test = soup.findAll('td')
	
	bank_id = 0
	
	if len(test) > 1 :
		p['iban'] = _opschonen(str(test[1]))
		p['bic'] = _opschonen(str(test[3]))
		p['bank_name'] = _opschonen(str(test[5]))
		
		
		return p
	
	else:
		return False
		
    




class account_bankimport_filters(osv.osv):
    _name = "account.bankimport.filters"
    _description = "Define the filters, which is related to the file"
    _columns = {
        'filter' : fields.char('Filtername', size=64, required=True),
        'name' : fields.char('Filename', size=128, required=True),
    }
account_bankimport_filters()

# Save data for each company
class res_company(osv.osv):
	_inherit = 'res.company'
	_columns = {
		'bank_journalid' :  fields.many2one('account.journal', 'Bank Journal', required=True),
		'def_payable' :  fields.many2one('account.account', 'Default Payable Account', required=True, domain=[('type','=','payable')]),
		'def_receivable' :  fields.many2one('account.account', 'Default Receivable Account', required=True, domain=[('type','=','receivable')]),
		'filters': fields.many2one('account.bankimport.filters', 'Filter', required=True),
		'bank_file' :  fields.char('File Location', size=128, required=True),
	}
res_company()

class account_bankimport(osv.osv):
    _name = "account.bankimport"
    _description = "import Bank statements-file for an Account"
    _columns = {
        'name': fields.char('Name', size=64),
        'file': fields.binary('bankimport file', readonly=True),
        'statement_id': fields.many2one('account.bank.statement','Generated Bank Statement', select=True,readonly=True),
        'note': fields.text('Import log', readonly=True),
        'journal_id': fields.many2one('account.journal','Bank Journal', readonly=True,select=True),
        'date': fields.date('Import Date', readonly=True,select=True),
        'user_id': fields.many2one('res.users','User', readonly=True, select=True),
    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'user_id': lambda self,cr,uid,context: uid,
    }
account_bankimport()

class account_bank_statement(osv.osv):
    _inherit = "account.bank.statement"
    _columns = {
        'bankimport_id':fields.many2one('account.bankimport','bankimport'),
        'state': fields.selection([('draft', 'Draft'),('draft_import', 'Draft Imported'),('confirm', 'Confirm')],
            'State', required=True,
            states={'confirm': [('readonly', True)]}, readonly="1"),
    }
    
    
account_bank_statement()

class bank_statement_line(osv.osv):
	_inherit = "account.bank.statement.line"
	_columns = {
		'bank_accnumber':fields.char('Bank account importfile', size=64, required=False),	
		'amount': fields.float('Amount', states={'draft_import': [('readonly', True)]} ),
		'ref': fields.char('Ref.', size=32, states={'draft_import': [('readonly', True)]} ),
		'name': fields.char('Name', size=64, required=True, states={'draft_import': [('readonly', True)]} ),
      'date': fields.date('Date', required=True, states={'draft_import': [('readonly', True)]} ),
		
            
	}
	
	def onchange_partner_id(self, cursor, user, line_id, partner_id, type, currency_id,
		context={}):
		if not partner_id:
			return {}
		res_currency_obj = self.pool.get('res.currency')
		res_users_obj = self.pool.get('res.users')
		
		company_currency_id = res_users_obj.browse(cursor, user, user,
			context=context).company_id.currency_id.id
			
		if not currency_id:
			currency_id = company_currency_id
		
		part = self.pool.get('res.partner').browse(cursor, user, partner_id,
			context=context)
		if part.supplier == 1 and part.customer == 0:
			account_id = part.property_account_payable.id
			type = 'supplier'
		elif part.supplier == 0 and part.customer == 1:
			account_id =  part.property_account_receivable.id
			type = 'customer'
		else:
			account_id = 0
			type = 'general'
				
		return {'value': {'type': type , 'account_id': account_id}}


	def write(self, cr, uid, ids, vals, context={}):
		acc_numbers = []
		
		if 'partner_id' in vals:
			db_data = self.pool.get('res.partner.bank').search(cr,uid, [('partner_id','=', vals['partner_id']) ] )
			acc_nums = self.pool.get('res.partner.bank').browse(cr,uid, db_data )
		
			import_acc = self.pool.get('account.bank.statement.line').browse(cr,uid, ids )
		
			for num in acc_nums:
				if num.acc_number:
					acc_numbers.append(num.acc_number)
				else:
					acc_numbers.append(num.iban)
		
			found_acc = False		
			for x in import_acc:
				if x.bank_accnumber in acc_numbers:
					found_acc = True
				
			if not found_acc:
				for x in import_acc:
					p = _get_bank_data(x.bank_accnumber)
				
					if p:
					# test if the bank exists
						bank_id = self.pool.get('res.bank').search(cr,uid,[('name','=',p['bank_name'])])
						if not bank_id:
							bank_id = pool.get('res.bank').create(cr,uid,{
									'name' : p['bank_name'],
									'bic' : p['bic'],
									'active' : 1,
								})
						else:
							bank_id = bank_id[0]
						
	
						bank_acc = self.pool.get('res.partner.bank').create(cr,uid,{
										'state' : 'bank',
										'partner_id': vals['partner_id'],
										'bank' : bank_id,
										'acc_number' : x.bank_accnumber,
								})
		
						bank_iban = self.pool.get('res.partner.bank').create(cr,uid,{
   	      						'state' : 'iban',
      	   						'partner_id': vals['partner_id'],
         							'bank' : bank_id,
         							'iban' : p['iban'],
         					})
         		
         			
					else:
						bank_acc = self.pool.get('res.partner.bank').create(cr,uid,{
       					  			'state' : 'bank',
         							'partner_id': vals['partner_id'],
          							'acc_number' : x.bank_accnumber,
         					})

    
     					
		return super(bank_statement_line, self).write(cr, uid, ids, vals, context)

	

bank_statement_line()
