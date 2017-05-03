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

# 送信対象CONTENTタイプ
CONTENT_TYPES = ['pdf', 'tiff', 'jpeg', 'png', 'html', 'plain']
DEFAULT_CONTENT_TYPES = ['pdf', 'tiff', 'jpeg', 'png']

def image2pdf_command(from_file, to_file):
    "ラスタ画像→PDF変換コマンド"
    return ['convert', from_file, to_file]

def plain2pdf_command(from_file, to_file):
    "テキスト→PDF変換コマンド"
    return ['wkhtmltopdf', '--disable-smart-shrinking', '--quiet', '--dpi', '384',
            '--encoding', 'utf-8', from_file, to_file]

def html2pdf_command(from_file, to_file):
    "HTML→PDF変換コマンド"
    return ['wkhtmltopdf', '--disable-smart-shrinking', '--quiet', '--dpi', '288', '--grayscale', from_file, to_file]

def raster_command(quality, pdf_files, tiff_file):
    "PDFラスタライズコマンド"
    return [
        'gs', '-q', '-dNOPAUSE', '-dBATCH',
        '-sDEVICE=tiffg3', '-sPAPERSIZE=a4', '-dFIXEDMEDIA', '-dPDFFitPage', RESOLUTIONS[quality],
        '-sOutputFile='+tiff_file] + pdf_files

def execute(args):
    "画像形式変換コマンドを実行"
    proc = subprocess.Popen(args)
    proc.communicate()

def decode_header(value):
    "メールヘッダをデコード"
    import email.header
    values = [v[0].decode(v[1] if v[1] else 'ascii') for v in email.header.decode_header(value)]
    return ''.join(values).encode('utf-8')

def extract_pdfs(message, basename, targets):
    "メッセージから送信対象のMIMEパートを抽出してPDF形式に変換"
    def temp_file(i, ext):
        "一時ファイル名を生成"
        return os.path.join(TEMP_DIR, basename + str(i) + '.' + ext)
    def writefile(utf8str, path):
        "MIMEパートから抽出したデータをファイル化"
        with open(path, 'wb') as f:
            f.write(utf8str)
        return path
    found_first_text = False
    for i, part in enumerate(message.walk()):
        maintype, subtype = part.get_content_maintype(), part.get_content_subtype()
        if subtype == 'octet-stream':
            _, ext = os.path.splitext(decode_header(part.get_filename()))
            if ext.lower() == '.pdf':
                subtype = 'pdf'
        if subtype not in targets:
            continue
        charset = part.get_content_charset()
        content = part.get_payload(decode=True)
        src_file = temp_file(i, subtype)
        dst_file = temp_file(i, 'pdf')
        if maintype == 'application' and subtype == 'pdf':
            writefile(content, dst_file)
            yield dst_file
        elif maintype == 'image':
            writefile(content, src_file)
            execute(image2pdf_command(src_file, dst_file))
            yield dst_file
        elif not found_first_text and maintype == 'text' and subtype == 'plain':
            src_file = temp_file(i, 'txt')
            writefile(content.decode(charset).encode('utf-8'), src_file)
            execute(plain2pdf_command(src_file, dst_file))
            found_first_text = True
            yield dst_file
        elif not found_first_text and maintype == 'text' and subtype == 'html':
            from bs4 import BeautifulSoup
            body = content.decode(charset)
            root = BeautifulSoup(body, HTML_PARSER)
            meta = BeautifulSoup('<meta http-equiv="Content-Type" content="text/html; charset="utf-8">', HTML_PARSER)
            root.head.append(meta)
            writefile(str(root), src_file)
            execute(html2pdf_command(src_file, dst_file))
            found_first_text = True
            yield dst_file

def pdfs2fax(quality, pdf_files, basename):
    "複数のPDFファイルをひとつのTIFFファイルに変換"
    fax_file = os.path.join(TIFF_DIR, basename + '.tiff')
    execute(raster_command(quality, pdf_files, fax_file))
    return fax_file

def create_callfile(basename, **params):
    "Asteriskに受け渡すcallfileを作成する。"
    import shutil
    temp_file = os.path.join(TEMP_DIR, basename + '.call')
    call_file = os.path.join(OUTGOING_DIR, basename + '.call')
    with open(temp_file, 'w') as f:
        f.write(OUTGOING_MESSAGE.format(**params))
    shutil.move(temp_file, call_file)

def sendback(status, **params):
    "FAX画像を送り返す"
    import sendmail
    body = OUTGOING_MESSAGE.format(**params)
    sendmail.sendmail(params['replyto'], 'sendfax', subject="[{0}] {1}".format(status, params['subject']),
                      body=body.encode('string-escape'), attachment=[params['faxfile']])

def sendfax(message, subject, context, peer, number, quality, types, dry_run, error):
    "メールメッセージから画像を抽出して，FAX送信するようAsteriskに指示する。"
    import time
    basename = str(int(time.time()))
    pdf_files = [f for f in extract_pdfs(message, basename, types) if f]
    fax_file = pdfs2fax(quality, pdf_files, basename) if pdf_files else '<<EMPTY>>'
    replyto = message.get('Reply-To', message['From'])
    subject = subject if subject else 'Send Fax to ' + number
    if error:
        sendback('ERROR', context=context, channel=number+'@'+peer, faxnumber=number,
                 faxfile=fax_file, replyto=replyto, subject=subject)
    elif dry_run:
        sendback('DRY-RUN', context=context, channel=number+'@'+peer, faxnumber=number,
                 faxfile=fax_file, replyto=replyto, subject=subject)
    else:
        create_callfile(basename, context=context, channel=number+'@'+peer, faxnumber=number,
                        faxfile=fax_file, replyto=replyto, subject=subject)

def extract_options(subject, default_args):
    "Subject文字列からオプションを抽出"
    import re
    import shlex
    import argparse
    mached = re.search(r'\{(.+)\}$', subject)
    if not mached:
        return default_args
    par = argparse.ArgumentParser()
    par.add_argument('-q', '--quality', default=default_args.get('quality'), choices=RESOLUTIONS.keys())
    par.add_argument('-t', '--types', default=default_args.get('types'), choices=CONTENT_TYPES, action='append')
    par.add_argument('--dry-run', default=default_args.get('dry_run'), action='store_true', help='Send back TIFF image')
    args = par.parse_args(shlex.split(mached.group(1)))
    default_args['quality'] = args.quality
    default_args['types'] = args.types
    default_args['dry_run'] = args.dry_run
    return default_args

def main():
    "コマンドライン解析"
    import argparse
    import email
    import sys
    par = argparse.ArgumentParser(description=__doc__)
    par.add_argument('context', help='Context for outgoing fax')
    par.add_argument('peer', help='SIP peer entry')
    par.add_argument('number', help='Phone number of fax')
    par.add_argument('-q', '--quality', default='fine', choices=RESOLUTIONS.keys(),
                     help='Image quality at fax transmission')
    par.add_argument('-t', '--types', metavar='CONTENTTYPE',
                     default=DEFAULT_CONTENT_TYPES, choices=CONTENT_TYPES, action='append',
                     help='Add content type to extract')
    par.add_argument('--dry-run', action='store_true', help='Send back TIFF image')
    args = vars(par.parse_args())
    message = email.message_from_file(sys.stdin)
    subject = decode_header(message.get('Subject'))
    try:
        args = extract_options(subject, args)
        args['error'] = False
    except SystemExit:
        args['error'] = True
    sendfax(message, subject, **args)

if __name__ == '__main__':
    main()
