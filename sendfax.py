#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
メールに添付されたPDFのイメージをFAXで送信する FAX gateway です。

    Usage: faxmail.py <CONTEXT名> <TRUNK名> <送信先電話番号>

標準入力に，メールデータを与えます。
"""

import os

PDF_DIR = '/tmp'
TIFF_DIR = '/var/spool/asterisk/fax'
OUTGOING_DIR = '/var/spool/asterisk/outgoing'
GS = 'gs'

OUTGOING_MESSAGE = '''Channel: SIP/{extension}@{trunk}
WaitTime: 30
MaxRetries: 3
RetryTime: 300
Archive: yes
Priority: 1
Context: {context}
Extension: send
Set: FAXFILE={faxfile}
'''

def fetch_pdfs(stream, basename):
    """メールに添付されているPDFを抽出してファイルとして書き出す。"""
    import email
    message = email.message_from_file(stream)
    for i, part in enumerate(message.walk()):
        if part.get_content_type() == 'application/pdf':
            pdf_file = os.path.join(PDF_DIR, basename + str(i) + '.pdf')
            with open(pdf_file, 'w') as f:
                f.write(part.get_payload(decode=True))
            yield pdf_file

def pdf2tif(pdf_files, basename):
    """複数のPDFファイルを結合して，ひとつのTIFFファイルに変換する。"""
    import subprocess
    tif_file = os.path.join(TIFF_DIR, basename + '.tif')
    command = [
        GS, '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiffg4', '-sPAPERSIZE=a4',
        '-sOutputFile='+tif_file] + pdf_files
    proc = subprocess.Popen(command)
    proc.communicate()
    return tif_file

def create_callfile(context, trunk, extension, tif_file, basename):
    """callfileを作成する。"""
    call_file = os.path.join(OUTGOING_DIR, basename)
    with open(call_file, 'w') as f:
        f.write(OUTGOING_MESSAGE.format(context=context, trunk=trunk, extension=extension, faxfile=tif_file))

def main(context, trunk, extension):
    """
    標準入力から読み込んだメールデータからPDFを抽出しTIFF形式に変換します。
    AsteriskにFAX送信を指示します。
    """
    import time
    basename = str(int(time.time()))
    pdf_files = list(fetch_pdfs(sys.stdin, basename))
    tif_file = pdf2tif(pdf_files, basename)
    create_callfile(context, trunk, extension, tif_file, basename)

if __name__ == '__main__':
    import sys
    main(sys.argv[1], sys.argv[2], sys.argv[3])
