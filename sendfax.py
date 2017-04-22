#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Email to FAX gateway for Asterisk
"""

import os

TEMP_DIR = '/tmp'
TIFF_DIR = '/var/spool/asterisk/fax'
OUTGOING_DIR = '/var/spool/asterisk/outgoing'
GS = 'gs'
CONVERT = 'convert'
#RESOLUTION = '204x98'
RESOLUTION = '204x196'
#RESOLUTION = '204x392'

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
Set: REPLYTO={replyto}
Set: SUBJECT={subject}
'''

def convert(from_file, to_file):
    "ImageMagickを使って画像形式を変換"
    import subprocess
    proc = subprocess.Popen([CONVERT, from_file, to_file])
    proc.communicate()
    return to_file

def extract_pdfs(message, basename):
    "添付されている画像ファイルをいったんPDF形式に変換"
    def temp_file(i, ext):
        "一時ファイル名を生成"
        return os.path.join(TEMP_DIR, basename + str(i) + ext)
    def extract(part, path):
        "MIMEパートから抽出したデータをファイル化"
        with open(path, 'w') as f:
            f.write(part.get_payload(decode=True))
        return path
    for i, part in enumerate(message.walk()):
        pdf_file = temp_file(i, '.pdf')
        if part.get_content_type() == 'application/pdf':
            yield extract(part, pdf_file)
        elif part.get_content_type() == 'image/jpeg':
            jpeg_file = extract(part, temp_file(i, '.jpeg'))
            yield convert(jpeg_file, pdf_file)
        elif part.get_content_type() == 'image/png':
            png_file = extract(part, temp_file(i, '.png'))
            yield convert(png_file, pdf_file)

def pdfs2tif(pdf_files, basename):
    "複数のPDFファイルをひとつのTIFFファイルに変換"
    import subprocess
    tif_file = os.path.join(TIFF_DIR, basename + '.tif')
    command = [
        GS, '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiffg3', '-sPAPERSIZE=a4', '-dFIXEDMEDIA', '-dPDFFitPage', '-r'+RESOLUTION,
        '-sOutputFile='+tif_file] + pdf_files
    proc = subprocess.Popen(command)
    proc.communicate()
    return tif_file

def create_callfile(basename, **params):
    """
    Asteriskに受け渡すcallfileを作成する。
    本来は，他のディレクトリで作成してからmoveすべき。
    """
    call_file = os.path.join(OUTGOING_DIR, basename + '.call')
    with open(call_file, 'w') as f:
        f.write(OUTGOING_MESSAGE.format(**params))

def sendfax(message, context, trunk, faxnumber):
    "メールメッセージから画像を抽出して，FAX送信するようAsteriskに指示する。"
    import time
    basename = str(int(time.time()))
    replyto = message.get('Reply-To', message['From'])
    subject = message['Subject'] if message['Subject'] else 'Send Fax to ' + faxnumber
    pdf_files = list(extract_pdfs(message, basename))
    tif_file = pdfs2tif(pdf_files, basename) if pdf_files else '<<EMPTY>>'
    create_callfile(basename, context=context, trunk=trunk, faxnumber=faxnumber,
                    faxfile=tif_file, replyto=replyto, subject=subject)

def main():
    "コマンドライン解析"
    import sys
    import argparse
    import email
    par = argparse.ArgumentParser(description=__doc__)
    par.add_argument('context', help='context name')
    par.add_argument('trunk', help='SIP trunk')
    par.add_argument('number', help='FAX number')
    args = par.parse_args()
    message = email.message_from_file(sys.stdin)
    sendfax(message, args.context, args.trunk, args.number)

if __name__ == '__main__':
    main()
