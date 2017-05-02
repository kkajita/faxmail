#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Email to FAX gateway for Asterisk
"""
import os
import subprocess
import functools

TEMP_DIR = '/tmp'
TIFF_DIR = '/var/spool/asterisk/fax'
OUTGOING_DIR = '/var/spool/asterisk/outgoing'
RESOLUTIONS = {
    'normal': '-r204x98',
    'fine': '-r204x196',
    'super': '-r204x392',
}

OUTGOING_MESSAGE = '''Channel: SIP/{channel}
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

HTML_PARSER = "html.parser"

# 送信対象MIMEサブタイプのデフォルト値
# pdf, tiff, jpeg, png, html, plain
DEFAULT_SUBTYPES = ['pdf', 'tiff', 'jpeg', 'png']

def image2pdf_command(from_file, to_file):
    "ラスタ画像→PDF変換コマンド"
    return ['convert', from_file, to_file]

def plain2pdf_command(dpi, encoding, from_file, to_file):
    "テキスト→PDF変換コマンド"
    return ['wkhtmltopdf', '--disable-smart-shrinking', '--dpi', str(dpi),
            '--encoding', encoding, from_file, to_file]

def html2pdf_command(dpi, from_file, to_file):
    "HTML→PDF変換コマンド"
    return ['wkhtmltopdf', '--disable-smart-shrinking', '--dpi', str(dpi), '--grayscale', from_file, to_file]

def raster_command(quality, pdf_files, tiff_file):
    "PDFラスタライズコマンド"
    return [
        'gs', '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiffg3', '-sPAPERSIZE=a4', '-dFIXEDMEDIA', '-dPDFFitPage', RESOLUTIONS[quality],
        '-sOutputFile='+tiff_file] + pdf_files

def convert(command, from_file, to_file):
    "画像形式変換コマンドを実行"
    args = command(from_file, to_file)
    if args:
        proc = subprocess.Popen(args)
        proc.communicate()
        return to_file
    return None

def extract_pdfs(message, basename, targets, dpi):
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
        charset = part.get_content_charset()
        data = part.get_payload(decode=True)
        if maintype == 'application' and subtype == 'pdf':
            yield writefile(data, temp_file(i, 'pdf'))
        elif maintype == 'image':
            image_file = writefile(data, temp_file(i, subtype))
            yield convert(image2pdf_command, image_file, temp_file(i, 'pdf'))
        elif maintype == 'text' and subtype == 'plain':
            plain_file = writefile(data, temp_file(i, 'txt'))
            command = functools.partial(plain2pdf_command, dpi, charset)
            yield convert(command, plain_file, temp_file(i, 'txt'))
        elif maintype == 'text' and subtype == 'html':
            from bs4 import BeautifulSoup
            body = data.decode(charset)
            root = BeautifulSoup(body, HTML_PARSER)
            meta = BeautifulSoup('<meta http-equiv="Content-Type" content="text/html; charset="utf-8">', HTML_PARSER)
            root.head.append(meta)
            html_file = writefile(str(root), temp_file(i, subtype))
            command = functools.partial(html2pdf_command, dpi)
            yield convert(command, html_file, temp_file(i, 'pdf'))

def pdfs2fax(quality, pdf_files, basename):
    "複数のPDFファイルをひとつのTIFFファイルに変換"
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

def sendfax(message, context, peer, faxnumber, types, quality, dpi):
    "メールメッセージから画像を抽出して，FAX送信するようAsteriskに指示する。"
    import time
    basename = str(int(time.time()))
    replyto = message.get('Reply-To', message['From'])
    subject = message['Subject'] if message['Subject'] else 'Send Fax to ' + faxnumber
    options = extract_options(subject).union(set(types))
    pdf_files = [f for f in extract_pdfs(message, basename, options, dpi) if f]
    fax_file = pdfs2fax(get_quality(options, quality), pdf_files, basename) if pdf_files else '<<EMPTY>>'
    channel = faxnumber + '@' + peer if peer else faxnumber
    create_callfile(basename, context=context, channel=channel, faxnumber=faxnumber,
                    faxfile=fax_file, replyto=replyto, subject=subject)

def main():
    "コマンドライン解析"
    import sys
    import argparse
    import email
    par = argparse.ArgumentParser(description=__doc__)
    par.add_argument('context', help='Context for incomming fax')
    par.add_argument('number', help='Phone number of fax')
    par.add_argument('-p', '--peer', default=None, help='SIP peer entry')
    par.add_argument('-q', '--quality', default='fine', choices=RESOLUTIONS.keys(),
                     help='Image quality at fax transmission')
    par.add_argument('-t', '--types', metavar='SUBTYPE', default=DEFAULT_SUBTYPES, action='append',
                     help='Add MIME subtypes to extract (default: {0})'.format(",".join(DEFAULT_SUBTYPES)))
    par.add_argument('-d', '--dpi', default=384, help='Resolution when rendering HTML (default: 384)')
    args = par.parse_args()
    message = email.message_from_file(sys.stdin)
    sendfax(message, args.context, args.peer, args.number, args.types, args.quality, args.dpi)

if __name__ == '__main__':
    main()
