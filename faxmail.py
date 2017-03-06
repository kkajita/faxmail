#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

SPOOL = '/var/spool/asterisk'
GS = '/usr/bin/gs'

OUTGOING = '''Channel: SIP/{extension}@{trunk}
WaitTime: 30
Maxretries: 3
RetryTime: 300
Application: SendFax
Data: {data}
'''

def fetch_pdfs(stream, basename):
    """メールに添付されているPDFを抽出してファイルとして書き出す。"""
    import email
    message = email.message_from_file(stream)
    for i, part in enumerate(message.walk()):
        if part.get_content_type() == 'application/pdf':
            pdf_file = os.path.join(SPOOL, 'fax', basename + str(i) + '.pdf')
            with open(pdf_file, 'w') as f:
                f.write(part.get_payload(decode=True))
            yield pdf_file

def pdf2tif(pdf_files, basename):
    """複数のPDFファイルを結合して，ひとつのTIFFファイルに変換する。"""
    import subprocess
    tif_file = os.path.join(SPOOL, 'fax', basename + '.tif')
    command = [
        GS, '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiffg4', '-sPAPERSIZE=a4',
        '-sOutputFile='+tif_file] + pdf_files
    proc = subprocess.Popen(command)
    proc.communicate()
    return tif_file

def create_callfile(trunk, extension, tif_file, basename):
    """callfileを作成する。"""
    call_file = os.path.join(SPOOL, 'outgoing', basename)
    with open(call_file, 'w') as f:
        f.write(OUTGOING.format(trunk=trunk, extension=extension, data=tif_file))

def main(trunk, extension):
    import time
    basename = str(int(time.time()))
    pdf_files = fetch_pdfs(sys.stdin, basename)
    tif_file = pdf2tif(list(pdf_files), basename)
    create_callfile(trunk, extension, tif_file, basename)
    for path in pdf_files:
        os.remove(path)

if __name__ == '__main__':
    import sys
    main(sys.argv[1], sys.argv[2])
