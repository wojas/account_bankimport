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
import pooler
import time
import datetime
import wizard
import netsvc
import base64
from osv import fields, osv

result_form = """<?xml version="1.0"?>
<form string="Import ASC Statement">
<separator colspan="4" string="Results :" />
    <field name="note" colspan="4" nolabel="1" width="500"/>
</form>
"""

result_fields = {

    'note' : {'string':'Log','type':'text'}

}

def _bank_import(self, cr, uid, data, context):
    
    pool = pooler.get_pool(cr.dbname)

    # setting variables 
    line_name = 0
    str_log = ""
    err_log = ""
    str_log1 = ""
    st_line_name = line_name
    
    bank_statement={}
    bank_statement_lines={}
    bank_statements=[]

    ########################	 
	 # building the header. #
    ######################## 	 
    # First we get the company_id from the user.
    user_data = pool.get('res.users').browse(cr, uid, uid, context)
    
	 # No we get the company data (journals and the file to read)
    company_data = pool.get('res.company').browse(cr, uid, user_data.company_id.id, context)

    # create the base
    bankfile = company_data.bank_file
    def_pay_acc = company_data.def_payable.id
    def_rec_acc = company_data.def_receivable.id
    
    # get todays date and get the period. The todays date will also be used for the Date-field  
    today_date = datetime.date.today()
    periodDate = today_date.strftime('%Y-%m-%d')
    period_id = pool.get('account.period').search(cr,uid,[('date_start','<=',periodDate),('date_stop','>=',periodDate)])
    
    # getting the start data of the balance. We need this from the database
    # get the latest bank statement from the database (highest id
    cr.execute('select max(id) from account_bank_statement',)
    bal_id = cr.fetchone()[0]
    bal_prev = pool.get('account.bank.statement').browse(cr,uid,bal_id,context)
    
    if not bal_prev:
       # switch to 0	    
       bal_start = 0
    else :
       # use the balance_end_real as the start_balance for the new statement
       bal_start = bal_prev.balance_end_real    
    
    # fill the bankstatement
    bank_statement["bank_statement_line"]={}
    bank_statement['date'] = today_date.strftime('%d/%m/%Y')
    bank_statement['journal_id']=company_data.bank_journalid.id
    bank_statement['period_id'] = period_id[0]
    bank_statement['def_pay_acc'] = def_pay_acc
    bank_statement['def_rec_acc'] = def_rec_acc
    bank_statement['state']='draft'
    bank_statement["balance_start"]= bal_start
    # Because the company is linked to a Partner, we can get also the
    # acc_number. We can even use it to verify if the right bankstatements
    # were be imported (acc_numbers should be equal).
    acc_number_id = pool.get('res.partner.bank').search(cr, uid, [('partner_id','=',company_data.partner_id.id)])
    
    # check if we got a bank / iban number
    if len(acc_number_id) > 0:
       bank_statement["acc_number"] = []    
       # create a list of numbers 
       for acc in acc_number_id:
          acc_number = pool.get('res.partner.bank').browse(cr,uid,acc)
         
          if acc_number.acc_number :
          	bank_statement["acc_number"].append(acc_number.acc_number.lower())
          else :
          	bank_statement["acc_number"].append(acc_number.iban.lower())
          
    else :
    	raise wizard.except_wizard('ERROR !', 'We got no bank / iban number.')
    #   str_log1 = "We got no bank / iban number!"
    #   return {'note':str_log1 ,'journal_id':0 , 'asc':0,'statment_id':0}

    # We use the company name and not the partner name
    bank_statement["acc_holder"] =  company_data.name  

	 # setting the end value of the balance
    bal_end = bal_start
    
    bank_statement['bal_start'] = bal_start
    bank_statement['bal_end'] = bal_end
    
    # based on the filter we parse the document
    filterObject = 'account.bankimport.filter.' + str(company_data.filters)
    
    bank_data = pooler.get_pool(cr.dbname).get( filterObject )
    
    exec "from filters import " + company_data.filters.name + " as parser"
    #__import__( company_data.filters.name )


    # opening the file speficied as bank_file and read the data
    try:
      bf = open(bankfile, 'r')
    	
      try:
         mydata = bf.read()
         recordlist = mydata.split('\n') # bf.readlines()
         recordlist.pop()
         data = parser.get_data(self,cr,uid,recordlist,bank_statement) # parse the data through the filter
      finally:
         bf.close()
    except IOError:
       raise
          

    bank_statements.append(bank_statement)
    bkst_list=[]
    bk_st_id=0

    nb_err=0
    err_log=''
    str_log=''
    std_log=''
    str_log1 = str_log1 + "  Bank Statements were Imported  :  "
    str_not=''
    str_not1=''
    
    period = []
    
   
    # check if we have new bank statement lines.
    if len(data) >= 1:
    	p_bank_state = []
    	p_state_line = {}
    	
    	# move each line to the right period
    	for line in data:    		
    		periodDate = time.strftime('%Y-%m-%d', time.strptime(line['date'], '%d/%m/%y') )
    			
    		# get the period
    		periodD = pool.get('account.period').search(cr,uid,[('date_start','<=',periodDate),('date_stop','>=',periodDate)])[0]
    		
    		# check if the period already exists in the dictonairy
    		if periodD in p_state_line:
    			w = p_state_line[periodD] # fill the array with existing data
    		else:
    			w = []
    			
    		w.append(line)
    		p_state_line[periodD] = w
    		if periodD not in period:
    			period.append(periodD)

		# sort the periods
		period.sort()
		
		# set the start balance
		bal_start = float(bank_statement['balance_start'])
		
		# we have now a dictionary of statement lines based on the period, so we can create the bankstatements now    			
    	for li in period:
    		lines = p_state_line[li]    		
    		total = 0.0
    		
    		# calculate the ending balance
    		for lin in lines:
    			total += float(lin['amount'])
    		bal_end += total
    		
    		try:
    			bk_st_id = pool.get('account.bank.statement').create(cr,uid,{
    							'journal_id': bank_statement['journal_id'],
    							'date':today_date.strftime('%Y-%m-%d'),
    							'period_id':li,
    							'balance_start': bal_start,
    							'balance_end_real': bal_end,
    							'state':'draft',
    						})
    						
    			for line in lines:
    				str_not1="Partner name : %s\nPartner Account Number : %s\nCommunication : %s\nValue Date : %s\nEntry Date : %s\n" %(line["contry_name"],line["cntry_number"],line["free_comm"],line["val_date"],line["entry_date"][0])
    				
    				id=pool.get('account.bank.statement.line').create(cr,uid,{
    							'name':line['name'],
    							'date': time.strftime('%Y-%m-%d', time.strptime(line['date'], '%d/%m/%y') ),
    							'amount': line['amount'],
    							'partner_id':line['partner_id'] or 0,
    							'account_id':line['account_id'],
    							'statement_id': bk_st_id,
    							'note':str_not1,
    							'ref':line['ref'],
    							'bank_accnumber':line['partner_acc_number'],
    							'type':line['type'],
    						})
    			cr.commit()
    			
    			str_not= "\n \n Account Number: %s \n Account Holder Name: %s " %(bank_statement["acc_number"],bank_statement["acc_holder"])
    			std_log = std_log + "\nDate  : %s, Starting Balance :  %.2f , Ending Balance : %.2f "\
    					%(bank_statement['date'], bal_start, bal_end)
    			bkst_list.append(bk_st_id)

    			# move ending balance to the start balance   			
    			bal_start = bal_end
	
    		except osv.except_osv, e:
    			cr.rollback()

    		except osv.except_osv, e:
    			cr.rollback()
    			nb_err+=1
    			err_log= err_log +'\n Application Error : ' + str(e)
    			raise # REMOVEME
    		
    		except Exception, e:
    			cr.rollback()
    			nb_err+=1
    			err_log= err_log +'\n System Error : '+str(e)
    			raise # REMOVEME
    			
    		except :
    			cr.rollback()
    			nb_err+=1
    			err_log= err_log +'\n Unknown Error'
    			raise
    	err_log= err_log + '\n\nNumbers of statements : '+ str(len([bkst_list]))     
    	err_log= err_log + '\nNumber of error :'+ str(nb_err) +'\n'

    	   	
    	pool.get('account.bankimport').create(cr, uid,{
    		'file': base64.encodestring(mydata),
    		'statement_id':bk_st_id,
    		'note':str(str_log1) + str(str_not) + str(std_log+err_log),
    		'journal_id':company_data.bank_journalid.id,
    		'date':time.strftime("%Y-%m-%d"),
    		'user_id':uid,
    	})
    else:
       raise wizard.except_wizard('WARNING !', 'No new records found, nothing imported.')
	 # close the file
    bf.close()
#    return {}	 
     
    return {'note':str_log1 + std_log + err_log ,'journal_id': company_data.bank_journalid.id, 'asc': company_data.bank_file,'statment_id':bkst_list}

    
class bank_import(wizard.interface):
    def _action_open_window(self, cr, uid, data, context):
        form=data['form']
        return {
            'domain':"[('id','in',(%s,))]"%(",".join(map(str,form['statment_id']))),
            'name': 'Statement',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'account.bank.statement',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'res_id':form['statment_id'],
        }
    states = {
         'init' : {
            'actions' : [_bank_import],
            'result' : {'type' : 'form',
                    'arch' : result_form,
                    'fields' : result_fields,
                    'state' : [('end', '_Close', 'gtk-close'),('open', '_Open Statement','gtk-ok')]}
         },
         
         'extraction' : {
            'actions' : [_bank_import],
            'result' : {'type' : 'form',
                    'arch' : result_form,
                    'fields' : result_fields,
                    'state' : [('end', '_Close', 'gtk-close'),('open', '_Open Statement','gtk-ok')]}
        },
        'open': {
            'actions': [],
            'result': {'type': 'action', 'action': _action_open_window, 'state': 'end'}

            },

    }
bank_import("account.bank_import")
