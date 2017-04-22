#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Send email with attachment while converting TIFF format to PDF.
"""

import smtplib
import os
import subprocess
import argparse
from email import encoders, utils
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import mimetypes

TEMP_DIR = "/tmp"

# localhostでSMTPサーバが稼働している場合
USE_TLS = False
SMTP_HOST = '127.0.0.1'
SMTP_PORT = 25
SMTP_USER = ''
SMTP_PASSWORD = ''

# gmailを利用する場合
#USE_TLS = True
#SMTP_HOST = 'smtp.gmail.com'
#SMTP_PORT = 587
#SMTP_USER = 'foo@gmail.com'
#SMTP_PASSWORD = 'password'

def attach_file(filename):
    "添付ファイルのMIMEパートを作成"
    data = open(filename, 'rb').read()
    mimetype, mimeencoding = mimetypes.guess_type(filename)
    if mimeencoding or (mimetype is None):
        mimetype = 'application/octet-stream'
    maintype, subtype = mimetype.split('/')
    if maintype == 'text':
        retval = MIMEText(data, _subtype=subtype)
    else:
        retval = MIMEBase(maintype, subtype)
        retval.set_payload(data)
        encoders.encode_base64(retval)
    retval.add_header('Content-Disposition', 'inline', filename=os.path.basename(filename))
    return retval

def tif2pdf(tif_file):
    "TIFFファイルをPDFファイルに変換"
    basename, _ = os.path.splitext(os.path.basename(tif_file))
    pdf_file = os.path.join(TEMP_DIR, basename + '.pdf')
    command = ['convert', tif_file, pdf_file]
    proc = subprocess.Popen(command)
    proc.communicate()
    return pdf_file

def create_message(fromaddr, toaddr, ccaddr, subject, text, attachments):
    "マルチパートMIMEメッセージを組み立てる"
    msg = MIMEMultipart()
    msg['To'] = toaddr
    msg['From'] = fromaddr
    if ccaddr:
        msg['Cc'] = ccaddr
    msg['Subject'] = subject
    msg['Date'] = utils.formatdate(localtime=True)
    msg['Message-ID'] = utils.make_msgid()
    msg.attach(MIMEText(text, _subtype='plain', _charset='utf-8'))
    for attachment in attachments:
        if not os.access(attachment, os.R_OK):
            continue
        mimetype, _ = mimetypes.guess_type(attachment)
        if mimetype == "image/tiff":
            attachment = tif2pdf(attachment)
        msg.attach(attach_file(attachment))
    return msg.as_string()

def sendmail(fromaddr, toaddr, ccaddr, message):
    "Eメールを送信する"
    smtp = smtplib.SMTP(host=SMTP_HOST, port=SMTP_PORT)
    if USE_TLS:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
    smtp.sendmail(fromaddr, [toaddr, ccaddr], message)
    smtp.close()

def main():
    "コマンドライン解析"
    par = argparse.ArgumentParser(description=__doc__)
    par.add_argument('toaddr', help='destination address')
    par.add_argument('-a', '--attachment', nargs='*', default=[], help='attachment files')
    par.add_argument('-f', '--from', default='noreply@example.com', help='sender address', dest='fromaddr')
    par.add_argument('-c', '--cc', default='', help='carbon copy address', dest='ccaddr')
    par.add_argument('-s', '--subject', default='', help='subject of the email')
    par.add_argument('-b', '--body', default='', help='content of the email')
    args = par.parse_args()
    message = create_message(args.fromaddr, args.toaddr, args.ccaddr,
                             args.subject, args.body.decode('string-escape'), args.attachment)
    sendmail(args.fromaddr, args.toaddr, args.ccaddr, message)

if __name__ == '__main__':
    main()
