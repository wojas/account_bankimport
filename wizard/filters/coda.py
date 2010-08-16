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
# This filter imports .coda-files (CODA-layout).
#


from osv import fields, osv
import time
import pooler
import conversion


def get_data(self, cr, uid, bankData, bank_statement):
      pool = pooler.get_pool(cr.dbname)
   
      bal_end = bank_statement['bal_end']
      bank_statement_lines={}
      bank_statements=[]
      line_name = 0
      str_log = ""
      err_log = ""
      str_log1 = ""
      st_line_name = line_name
    
      # parse every line in the file and get the right data
      for line in bankData:
        if line[0] == '0':
            # header data
#            bank_statement={}
#            bank_statement_lines={}
            bank_statement["bank_statement_line"]={}
            #bank_statement['date'] = conversion.str2date(line[5:11])
            #period_id = pool.get('account.period').search(cr,uid,[('date_start','<=',time.strftime("%y/%m/%d",time.strptime(bank_statement['date'],"%d/%m/%y"))),('date_stop','>=',time.strftime("%y/%m/%d",time.strptime(bank_statement['date'],"%d/%m/%y")))])
            #period_id = pool.get('account.period').search(cr,uid,[('date_start','<=',time.strftime('%Y-%m-%d',time.strptime(bank_statement['date'],"%y/%m/%d"))),('date_stop','>=',time.strftime('%Y-%m-%d',time.strptime(bank_statement['date'],"%y/%m/%d")))])
            #bank_statement['period_id'] = period_id[0]
            #bank_statement['state']='draft'
        elif line[0] == '1':
            # old balance data
            bal_start = conversion.list2float(line[43:58])
            if line[42] == '1':
                bal_start = - bal_start
            bank_statement["balance_start"]= bal_start
            bank_statement["acc_number"]=line[5:17]
            bank_statement["acc_holder"]=line[64:90]

        elif line[0]=='2':
            # movement data record 2
            if line[1]=='1':
                # movement data record 2.1
                st_line = {}
                st_line['statement_id']=0
                st_line['name'] = line[2:10]
                st_line['date'] = conversion.str2date(line[115:121])
                st_line_amt = conversion.list2float(line[32:47])

                if line[61]=='1':
                    st_line['ref']=(line[65:77])
                    st_line['free_comm']=''
                else:
                    st_line['free_comm']=line[62:115]
                    st_line['ref']=''

                st_line['val_date']=time.strftime('%Y-%m-%d',time.strptime(conversion.str2date(line[47:53]),"%y/%m/%d")),
                st_line['entry_date']=time.strftime('%Y-%m-%d',time.strptime(conversion.str2date(line[115:121]),"%y/%m/%d")),
                st_line['partner_id']=0
                if line[31] == '1':
                    st_line_amt = - st_line_amt
                    st_line['account_id'] = bank_statement['def_pay_acc']
                else:
                    st_line['account_id'] = bank_statement['def_rec_acc']
                st_line['amount'] = st_line_amt
                bank_statement_lines[st_line['name']]=st_line
                bank_statement["bank_statement_line"]=bank_statement_lines

            elif line[1] == '3':
                # movement data record 3.1
                st_line_name = line[2:10]
                st_line_partner_acc = str(line[10:47]).strip()
                cntry_number=line[10:47]
                contry_name=line[47:125]
                #bank_ids = pool.get('res.partner.bank').search(cr,uid,[('number','=',st_line_partner_acc)])
                bank_ids = pool.get('res.partner.bank').search(cr,uid,[('acc_number','=',st_line_partner_acc)])
                if bank_ids:
                    bank = pool.get('res.partner.bank').browse(cr,uid,bank_ids[0],context={})
                    line=bank_statement_lines[st_line_name]
                    line['cntry_number']=cntry_number
                    line['contry_name']=contry_name

                    if line and bank.partner_id:
                        line['partner_id']=bank.partner_id.id
                        if line['amount'] < 0 :
                            line['account_id']=bank.partner_id.property_account_payable.id
                        else :
                            line['account_id']=bank.partner_id.property_account_receivable.id

                        bank_statement_lines[st_line_name]=line
                else:
                    line=bank_statement_lines[st_line_name]
                    line['cntry_number']=cntry_number
                    line['contry_name']=contry_name
                    bank_statement_lines[st_line_name]=line


                bank_statement["bank_statement_line"]=bank_statement_lines
        elif line[0]=='3':
            pass
        elif line[0]=='8':
            # new balance record
            bal_end = conversion.list2float(line[42:57])
            if line[41] == '1':
                bal_end = - bal_end
            bank_statement["balance_end_real"]= bal_end

        elif line[0]=='9':
            # footer record
            pass
            #bank_statements.append(bank_statement)
     #end for
      return bank_statement 

