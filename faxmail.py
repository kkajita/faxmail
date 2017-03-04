#!/usr/bin/env python
# -*- coding: utf-8 -*-

SPOOL = '/var/spool/asterisk'

def pdf2tif(pdf, tif_file):
    import subprocess
    command = [
	'/usr/bin/gs', '-q', '-dNOPAUSE', '-dBATCH',
	'-sDEVICE=tiffg4', '-sPAPERSIZE=a4',
	'-sOutputFile='+tif_file, '-'
    ]
    p = subprocess.Popen(command, stdin=subprocess.PIPE)
    p.communicate(pdf)

def fetch_pdf(f):
    import email
    message = email.message_from_file(f)
    for part in message.walk():
	if part.get_content_type() == 'application/pdf':
	    return part.get_payload(decode=True)

def create_callfile(trunk, extension, tif_file, call_file):
    outgoing = '''Channel: SIP/{extension}@{trunk}
WaitTime: 30
Maxretries: 3
RetryTime: 300
Application: SendFax
Data: {tif_file}'''
    with open(call_file, 'w') as f:
	f.write(outgoing.format(trunk=trunk, extension=extension, tif_file=tif_file))

if __name__ == '__main__':
    import sys
    import os
    from datetime import datetime
    trunk = sys.argv[1]
    extension = sys.argv[2]
    basename = datetime.now().strftime("%Y%m%d%H%M%S")
    tif_file = os.path.join(SPOOL, 'fax', basename + '.tif')
    call_file = os.path.join(SPOOL, 'outgoing', basename)

    pdf = fetch_pdf(sys.stdin)
    pdf2tif(pdf, tif_file)
    create_callfile(trunk, extension, tif_file, call_file)
