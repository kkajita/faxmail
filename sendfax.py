#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Email to FAX gateway for Asterisk
"""
import os
import subprocess

TEMP_DIR = '/tmp'
TIFF_DIR = '/var/spool/asterisk/fax'
OUTGOING_DIR = '/var/spool/asterisk/outgoing'

#RESOLUTION = (204, 98)
RESOLUTION = (204, 196)
#RESOLUTION = (204, 392)

def res_string(factor):
    return "{0}x{1}".format(factor * RESOLUTION[0], factor * RESOLUTION[1])

# 送信対象型式のデフォルト値
# pdf, tiff, jpeg, png, html,...
DEFAULT_SUBTYPES = ['pdf', 'html']

def image2pdf_command(from_file, to_file):
    "ラスタ画像→PDF変換コマンド"
    return ['convert', from_file, to_file]

def html2pdf_command(from_file, to_file):
    "HTML→PDF変換コマンド"
    #return ['xvfb-run', 'wkhtmltopdf', from_file, to_file]
    return ['wkhtmltopdf', '--dpi', '360', from_file, to_file]

def raster_command(pdf_files, tiff_file):
    "PDFラスタライズコマンド"
    return [
        'gs', '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiff24nc', '-sPAPERSIZE=a4', '-dFIXEDMEDIA', '-dPDFFitPage', '-r' + res_string(2),
        '-sOutputFile='+tiff_file] + pdf_files

def tofax_command(from_file, to_file):
    "ラスタ画像二値化コマンド"
    return ['convert', '-format', 'fax', '-density', res_string(1),
            '-monochrome', '-type', 'Bilevel', '-despeckle', '-threshold', '80%', from_file, to_file]

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

def convert(command, from_file, to_file):
    "画像形式変換コマンドを実行"
    args = command(from_file, to_file)
    if args:
        proc = subprocess.Popen(args)
        proc.communicate()
        return to_file
    return None

def extract_pdfs(message, basename, targets):
    "送信対象のMIMEパートを抽出してPDF形式に変換"
    def temp_file(i, ext):
        "一時ファイル名を生成"
        return os.path.join(TEMP_DIR, basename + str(i) + '.' + ext)
    def writefile(utf8str, path):
        "MIMEパートから抽出したデータをファイル化"
        with open(path, 'wb') as f:
            f.write(utf8str)
        return path
    for i, part in enumerate(message.walk()):
        mtype, subtype = part.get_content_type().split('/')
        if subtype not in targets:
            continue
        data = part.get_payload(decode=True)
        if mtype == 'applicatione' and subtype == 'pdf':
            yield writefile(data, temp_file(i, 'pdf'))
        elif mtype == 'image':
            image_file = writefile(data, temp_file(i, subtype))
            yield convert(image2pdf_command, image_file, temp_file(i, 'pdf'))
        elif mtype == 'text' and subtype == 'html':
            from bs4 import BeautifulSoup
            root = BeautifulSoup(data, "html.parser")
            meta = BeautifulSoup('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">', "html.parser")
            root.head.append(meta)
            html_file = writefile(str(root), temp_file(i, subtype))
            yield convert(html2pdf_command, html_file, temp_file(i, 'pdf'))

def pdfs2fax(pdf_files, basename):
    "複数のPDFファイルをひとつのTIFFファイルに変換"
    tiff_file = os.path.join(TEMP_DIR, basename + '.tiff')
    fax_file = os.path.join(TIFF_DIR, basename + '.tiff')
    convert(raster_command, pdf_files, tiff_file)
    return convert(tofax_command, tiff_file, fax_file)

def create_callfile(basename, **params):
    """
    Asteriskに受け渡すcallfileを作成する。
    本来は，他のディレクトリで作成してからmoveしたほうが安全
    """
    call_file = os.path.join(OUTGOING_DIR, basename + '.call')
    with open(call_file, 'w') as f:
        f.write(OUTGOING_MESSAGE.format(**params))

def extract_subtypes(subject):
    "Subject文字列からオプションを抽出"
    import re
    plus = set(re.findall(r'\+(\w+)', subject))
    minus = set(re.findall(r'\-(\w+)', subject))
    return set(DEFAULT_SUBTYPES).union(plus).difference(minus)

def sendfax(message, context, trunk, faxnumber):
    "メールメッセージから画像を抽出して，FAX送信するようAsteriskに指示する。"
    import time
    basename = str(int(time.time()))
    replyto = message.get('Reply-To', message['From'])
    subject = message['Subject'] if message['Subject'] else 'Send Fax to ' + faxnumber
    subtypes = extract_subtypes(subject)
    pdf_files = [f for f in extract_pdfs(message, basename, subtypes) if f]
    fax_file = pdfs2fax(pdf_files, basename) if pdf_files else '<<EMPTY>>'
    create_callfile(basename, context=context, trunk=trunk, faxnumber=faxnumber,
                    faxfile=fax_file, replyto=replyto, subject=subject)

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
