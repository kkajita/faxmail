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
RESOLUTIONS = {
    'normal': '-r204x98',
    'fine': '-r204x196',
    'super': '-r204x392',
}

# 送信対象型式のデフォルト値
# pdf, tiff, jpeg, png, html, plain
DEFAULT_SUBTYPES = ['pdf', 'tiff', 'jpeg', 'png']

def image2pdf_command(from_file, to_file):
    "ラスタ画像→PDF変換コマンド"
    return ['convert', from_file, to_file]

def plain2pdf_command(encoding, from_file, to_file):
    "テキスト→PDF変換コマンド"
    return ['/usr/local/bin/wkhtmltopdf', '--disable-smart-shrinking', '--dpi', '360',
            '--encoding', encoding, from_file, to_file]

def html2pdf_command(from_file, to_file):
    "HTML→PDF変換コマンド"
    return ['/usr/local/bin/wkhtmltopdf', '--disable-smart-shrinking', '--dpi', '360', from_file, to_file]

def raster_command(quality, pdf_files, tiff_file):
    "PDFラスタライズコマンド"
    return [
        'gs', '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiffg3', '-sPAPERSIZE=a4', '-dFIXEDMEDIA', '-dPDFFitPage', RESOLUTIONS[quality],
        '-sOutputFile='+tiff_file] + pdf_files

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
        maintype, subtype = part.get_content_maintype(), part.get_content_subtype()
        if subtype not in targets:
            continue
        data = part.get_payload(decode=True)
        if maintype == 'applicatione' and subtype == 'pdf':
            yield writefile(data, temp_file(i, 'pdf'))
        elif maintype == 'image':
            image_file = writefile(data, temp_file(i, subtype))
            yield convert(image2pdf_command, image_file, temp_file(i, 'pdf'))
        elif maintype == 'text' and subtype == 'plain':
            import functools
            command = functools.partial(plain2pdf_command, part.get_content_charset())
            plain_file = writefile(data, temp_file(i, 'txt'))
            yield convert(command, plain_file, temp_file(i, 'txt'))
        elif maintype == 'text' and subtype == 'html':
            from bs4 import BeautifulSoup
            root = BeautifulSoup(data, "html.parser")
            meta = BeautifulSoup('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">', "html.parser")
            root.head.append(meta)
            html_file = writefile(str(root), temp_file(i, subtype))
            yield convert(html2pdf_command, html_file, temp_file(i, 'pdf'))

def pdfs2fax(quality, pdf_files, basename):
    "複数のPDFファイルをひとつのTIFFファイルに変換"
    import functools
    command = functools.partial(raster_command, quality)
    fax_file = os.path.join(TIFF_DIR, basename + '.tiff')
    return convert(command, pdf_files, fax_file)

def create_callfile(basename, **params):
    """
    Asteriskに受け渡すcallfileを作成する。
    本来は，他のディレクトリで作成してからmoveしたほうが安全
    """
    call_file = os.path.join(OUTGOING_DIR, basename + '.call')
    with open(call_file, 'w') as f:
        f.write(OUTGOING_MESSAGE.format(**params))

def extract_options(subject):
    "Subject文字列からオプションを抽出"
    import re
    plus = set(re.findall(r'\+(\w+)', subject))
    minus = set(re.findall(r'\-(\w+)', subject))
    return set(DEFAULT_SUBTYPES).union(plus).difference(minus)

def get_quality(options, quality):
    "Subject文字列に解像度の指示があれば差し替える"
    setting = options.intersection(set(RESOLUTIONS.keys()))
    return setting.pop() if setting else quality

def sendfax(message, context, trunk, faxnumber, types, quality):
    "メールメッセージから画像を抽出して，FAX送信するようAsteriskに指示する。"
    import time
    basename = str(int(time.time()))
    replyto = message.get('Reply-To', message['From'])
    subject = message['Subject'] if message['Subject'] else 'Send Fax to ' + faxnumber
    options = extract_options(subject).union(set(types))
    pdf_files = [f for f in extract_pdfs(message, basename, options) if f]
    fax_file = pdfs2fax(get_quality(options, quality), pdf_files, basename) if pdf_files else '<<EMPTY>>'
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
    par.add_argument('-q', '--quality', default='fine', choices=RESOLUTIONS.keys(), help='fax resolution')
    par.add_argument('-t', '--types', action='append', help='content types')
    args = par.parse_args()
    message = email.message_from_file(sys.stdin)
    sendfax(message, args.context, args.trunk, args.number, args.types, args.quality)

if __name__ == '__main__':
    main()
