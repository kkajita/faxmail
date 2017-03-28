#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
import email

PDF_DIR = '/tmp'
TIFF_DIR = '/var/spool/asterisk/fax'
OUTGOING_DIR = '/var/spool/asterisk/outgoing'
GS = 'gs'

OUTGOING_MESSAGE = '''Channel: SIP/{faxnumber}@{trunk}
WaitTime: 30
MaxRetries: 2
RetryTime: 300
Archive: yes
Context: {context}
Extension: send
Priority: 1
Set: FAXFILE={faxfile}
Set: FAXNUMBER={faxnumber}
'''

def extract_pdfs(message, basename):
    for i, part in enumerate(message.walk()):
        if part.get_content_type() == 'application/pdf':
            pdf_file = os.path.join(PDF_DIR, basename + str(i) + '.pdf')
            with open(pdf_file, 'w') as f:
                f.write(part.get_payload(decode=True))
            yield pdf_file

def pdfs2tif(pdf_files, basename):
    import subprocess
    tif_file = os.path.join(TIFF_DIR, basename + '.tif')
    command = [
        GS, '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiffg4', '-sPAPERSIZE=a4',
        '-sOutputFile='+tif_file] + pdf_files
    proc = subprocess.Popen(command)
    proc.communicate()
    return tif_file

def create_callfile(basename, **params):
    call_file = os.path.join(OUTGOING_DIR, basename + '.call')
    with open(call_file, 'w') as f:
        f.write(OUTGOING_MESSAGE.format(**params))

def main(context, trunk, faxnumber):
    import time
    import sys
    basename = str(int(time.time()))
    message = email.message_from_file(sys.stdin)
    pdf_files = list(extract_pdfs(message, basename))
    tif_file = pdfs2tif(pdf_files, basename)
    create_callfile(basename, context=context, trunk=trunk, faxnumber=faxnumber, faxfile=tif_file)

if __name__ == '__main__':
    par = argparse.ArgumentParser(description="FAX gateway for Asterisk")
    par.add_argument('context', help='context name')
    par.add_argument('trunk', help='SIP trunk')
    par.add_argument('number', help='FAX number')
    args = par.parse_args()
    main(args.context, args.trunk, args.number)
