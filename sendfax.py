#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse

PDF_DIR = '/tmp'
TIFF_DIR = '/var/spool/asterisk/fax'
OUTGOING_DIR = '/var/spool/asterisk/outgoing'
GS = 'gs'

OUTGOING_MESSAGE = '''Channel: SIP/{faxnumber}@{trunk}
WaitTime: 30
MaxRetries: 0
RetryTime: 300
Archive: yes
Priority: 1
Context: {context}
Extension: send
Set: FAXFILE={faxfile}
Set: FAXNUMBER={faxnumber}
'''

def extract_pdfs(stream, basename):
    import email
    message = email.message_from_file(stream)
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

def create_callfile(context, trunk, faxnumber, tif_file, basename):
    call_file = os.path.join(OUTGOING_DIR, basename)
    with open(call_file, 'w') as f:
        f.write(OUTGOING_MESSAGE.format(context=context, trunk=trunk, faxnumber=faxnumber, faxfile=tif_file))

def main(context, trunk, faxnumber):
    import time
    import sys
    basename = str(int(time.time()))
    pdf_files = list(extract_pdfs(sys.stdin, basename))
    tif_file = pdfs2tif(pdf_files, basename)
    create_callfile(context, trunk, faxnumber, tif_file, basename)

if __name__ == '__main__':
    par = argparse.ArgumentParser(description="FAX gateway for Asterisk")
    par.add_argument('context', help='context name')
    par.add_argument('trunk', help='SIP trunk')
    par.add_argument('number', help='FAX number')
    args = par.parse_args()
    main(args.context, args.trunk, args.number)