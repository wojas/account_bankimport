##############################################################################
#
# Copyright (c) 2010 Konrad Wojas <info at wojas.nl>
#                          All Rights Reserved.
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
"""
Supported banks:
- NL Bizner
- NL ABN-AMRO
"""

import sys
import re
import datetime 
from decimal import Decimal

class Sheet(object):
    """
    This class represents a MT940 sheet/message. It can contain multiple
    entries/transactions.
    """

    # 20
    id = None
    # 25
    account = None
    # 28
    page = None
    # 60F/60M
    start_saldo = None
    start_saldo_date = None
    # 62M/62F
    end_saldo = None
    end_saldo_date = None
    # 61 and 86; list of Entry instances
    entries = None

    def __init__(self):
        self.entries = []

    @property
    def is_nl_abnamro(self):
        return self.id == 'ABN AMRO BANK NV'

    @property
    def is_nl_bizner(self):
        return not self.is_nl_abnamro

    def __repr__(self):
        s = ['Sheet:']
        for a in ['id', 'account', 'page', 'start_saldo', 'start_saldo_date', 
                'end_saldo', 'end_saldo_date']:
            val = getattr(self, a)
            s.append('  %s: %r' % (a, val))
        for e in self.entries:
            es = repr(e)
            esl = es.split('\n')
            for l in esl:
                s.append('  %s' % l)
        return '\n'.join(s)


class Entry(object):
    """
    This class represents a MT940 entries/transactions. It's always contained
    within a Sheet when returned by this parser.
    """
    pattern = r"""
        ^
        (?P<value_date>[0-9]{6})
        (?P<entry_date>[0-9]{4})?
        (?P<dc>[DC])
        (?P<funds_code>[A-Z])?
        (?P<amount>[0-9,]{1,15})
        (?P<txtype>N[0-9A-Z]{3})
        (?P<other_account>[0-9A-Z]{1,16})?
        (?P<other_info>.+?)?
        $
    """
    regexp = re.compile(pattern, re.VERBOSE)
    r_nl_abnamro_account = re.compile(r"^([0-9]{2}\.[0-9]{2}\.[0-9]{2}\.[0-9]{3}) (.{19})")
    r_nl_abnamro_giro = re.compile(r"^GIRO +([0-9]+) (.{17})")
    r_clean_desc = re.compile(r"[ >]+")

    # 25
    my_account = None
    # 61
    value_date = None 
    entry_date = None           # optional
    dc = None                   # normalized to 'D' or 'C'
    funds_code = None           # optional
    amount = None               # Decimal
    txtype = None               # 4 letter transaction type
    other_account = None        # optional
    other_info = None           # optional (serving bank, other reference)
    # 86
    name = ''                   # first line from raw description
    description = ''            # compacted
    description_raw = None

    def __init__(self, tag61):
        m = self.regexp.match(tag61)
        self.value_date = parse_date(m.group('value_date'))
        ed = m.group('entry_date')
        if ed:
            # FIXME: can this date be in the next year?
            self.entry_date = parse_date(m.group('value_date'), year=self.value_date.year)
        self.dc = m.group('dc')
        self.funds_code = m.group('funds_code')
        self.amount = parse_balance(m.group('amount'))
        self.txtype = m.group('txtype')
        self.other_account = clean_account(m.group('other_account'))
        self.other_info = m.group('other_info')

    is_atm = None
    is_pin = None

    @property
    def refself(self):
        return self.my_account == self.other_account
    
    def parse86(self, msg):
        self.description_raw = msg

        if self.other_account == 'NONREF':
            # NL ABN-MRO
            self.is_atm = False
            self.is_pin = False
            set_name = False
            m = self.r_nl_abnamro_account.match(msg)
            if m:
                # starts with account number
                self.other_account = m.group(1).replace('.', '')
                self.name = m.group(2).strip()
                set_name = True
            else:
                m = self.r_nl_abnamro_giro.match(msg)
                if m:
                    # starts with giro number
                    self.other_account = 'P' + m.group(1)
                    self.name = m.group(2).strip()
                    set_name = True
                else:
                    # other info
                    self.is_atm = msg.startswith('GEA ') or msg.startswith('CHIP ')
                    self.is_pin = msg.startswith('BEA ')

            if set_name and self.name=='':
                self.other_account = clean_account(self.other_account)
                self.name = msg.split('\n')[0][32:].strip()

            if self.other_account=='NONREF':
                self.other_account = ''
            
            # replace one or more ' ' or '>' by a single space
            self.description = self.r_clean_desc.sub(' ', msg)
                
        else:
            # NL Bizner

            # this works for Bizner exports, might not work for other banks
            lines = msg.split('\n')
            name1 = self.r_clean_desc.sub(' ', lines[0].replace('>', ', '))
            self.name = name1.replace(' ,', ',').strip().rstrip(',').strip()

            # get the description
            # replace one or more ' ' or '>' by a single space
            self.description = self.r_clean_desc.sub(' ', msg)
            
            self.is_atm = 'GELDAUTOMAAT' in self.description_raw 
            self.is_pin = 'PINAUTOMAAT' in self.description_raw 

    def __repr__(self):
        s = ['Entry:']
        for a in ['value_date', 'entry_date', 'dc', 'funds_code', 'amount', 'txtype', 
                'other_account', 'name', 'description', 'description_raw', 
                'is_atm', 'is_pin', 'refself']:
            val = getattr(self, a)
            s.append('  %s: %r' % (a, val))
        return '\n'.join(s)


class MT940ParseError(Exception):
    pass


def clean_account(s):
    """Cleans an account number by removing leading zeros"""
    if s.startswith('P'):
        prefix = 'P'
        number = s[1:]
    else:
        prefix = ''
        number = s
    while number[0]=='0':
        number = number[1:]
    return prefix + number

_cents = Decimal('0.01')
def parse_balance(s):
    bal = Decimal(s.replace(',', '.'))
    return bal.quantize(_cents)

def parse_date(s, year=None):
    if len(s)==4:
        if not year:
            raise ValueError('date %r contains no year and no year passed' % s)
        month = int(s[0:2])
        day = int(s[2:4])
    else:
        year = int(s[0:2])
        if year < 60:
            year += 2000
        else:
            year += 1900
        month = int(s[2:4])
        day = int(s[4:6])
    return datetime.date(year, month, day)

def get_sign(dc):
    if dc=='D':
        return -1
    elif dc=='C':
        return 1
    else:
        raise ValueError("dc must be 'D' or 'C', not %r" % dc)


def parse_mt940(f):
    """
    Parse an MT940 file from file-like object f.
    Returns a list of Sheet instances.
    """
    read_lineno = 0
    lineno = 0
    current_line = ''
    sheets = []

    def process_current_line():
        # this will process each multiline tag
        if not current_line:
            return
        
        # strip extra whitespace, like newlines
        line = current_line.strip()
        if not line:
            return
        if not line.startswith(':'):
            raise MT940ParseError('Found garbage at line %i: "%s"' % (lineno, line))

        # split in tag (without colon) and message
        tag, msg = line[1:].split(':', 1)
        tag = tag.upper()
        
        # new sheet tag
        if tag=='940':
            # start a new sheet
            sheets.append(Sheet())
            return
        
        # we must be in a sheet at this point; current sheet is the last sheet
        if not sheets:
            raise MT940ParseError('Extra tag before sheet at line %i' % lineno)
        sheet = sheets[-1]
        
        # parse tags
        if tag=='20':
            sheet.id = msg
        elif tag=='25':
            sheet.account = clean_account(msg)
        elif tag=='28':
            sheet.page = msg
        elif tag in ['60F', '60M', '62F', '62M']:
            dc = msg[0]
            date = msg[1:7]
            cur = msg[7:10]
            bal = msg[10:25]
            amount = get_sign(dc) * parse_balance(bal)
            pdate = parse_date(date)
            if tag.startswith('60'):
                sheet.start_saldo = amount
                sheet.start_saldo_date = pdate
            else:
                sheet.end_saldo = amount
                sheet.end_saldo_date = pdate
        elif tag=='61':
            entry = Entry(msg.replace('\n', ' '))
            entry.my_account = sheet.account
            sheet.entries.append(entry)
        elif tag=='86':
            if not sheet.entries or sheet.entries[-1].description_raw is not None:
                raise MT940ParseError('Description (86) before statement (61) at line %i' % lineno)
            entry = sheet.entries[-1]
            entry.parse86(msg)
        elif tag in []:
            # just ignore these tags
            pass
        else:
            raise MT940ParseError('Unknown tag %s at line %i (not explicitly ignored)' % (tag, lineno))
    
    # loop over all text lines and combine them per tag
    for line in f:
        read_lineno += 1
        line = line.strip()
        
        # ABN-AMRO fixes
        if line=='ABNANL2A' or line=='-':
            continue
        if line=='940':
            line = ':940:'
        
        # parse
        if line.startswith(':'):
            # new tag
            process_current_line()
            current_line = line
            lineno = read_lineno
        else:
            # extra line for current tag
            current_line += '\n' + line
    
    # process last line
    process_current_line()

    return sheets


if __name__=='__main__':
    sheets = parse_mt940(sys.stdin)
    for sheet in sheets:
        print sheet
