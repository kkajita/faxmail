#!/usr/bin/env python
# -*- coding: utf-8 -*-

import smtplib
import os
import subprocess
import argparse
from email import encoders, utils
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import mimetypes

DESCRIPTION = "Send mail with attachment. However, TIFF format files are converted to PDF."
TEMP_DIR = "/tmp"
SMTP_HOST = "127.0.0.1"
SMTP_PORT = 25

def attach_file(filename):
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
    retval.add_header('Content-Disposition', 'attachment', filename=os.path.basename(filename))
    return retval

def tif2pdf(tif_file):
    basename, _ = os.path.splitext(os.path.basename(tif_file))
    pdf_file = os.path.join(TEMP_DIR, basename + '.pdf')
    command = ['convert', tif_file, pdf_file]
    proc = subprocess.Popen(command)
    proc.communicate()
    return pdf_file

def create_message(fromaddr, toaddr, subject, message, attachments):
    msg = MIMEMultipart()
    msg['To'] = toaddr
    msg['From'] = fromaddr
    msg['Subject'] = subject
    msg['Date'] = utils.formatdate(localtime=True)
    msg['Message-ID'] = utils.make_msgid()
    msg.attach(MIMEText(message, _subtype='plain'))
    for attachment in attachments:
        mimetype, _ = mimetypes.guess_type(attachment)
        if mimetype == "image/tiff":
            attachment = tif2pdf(attachment)
        msg.attach(attach_file(attachment))
    return msg.as_string()

def send_mail(fromaddr, toaddr, message):
    smtp = smtplib.SMTP(host=SMTP_HOST, port=SMTP_PORT)
    smtp.sendmail(fromaddr, [toaddr], message)
    smtp.close()

if __name__ == '__main__':
    par = argparse.ArgumentParser(description=DESCRIPTION)
    par.add_argument('toaddr', help='destination address')
    par.add_argument('-a', '--attachment', nargs='*', default=[], help='attachment files')
    par.add_argument('-f', '--from', default='noreply@example.com', help='sender address', dest='fromaddr')
    par.add_argument('-s', '--subject', default='', help='subject of the email')
    par.add_argument('-b', '--body', default='', help='content of the email')
    args = par.parse_args()
    message = create_message(args.fromaddr, args.toaddr,
                             args.subject, args.body.decode('string-escape'), args.attachment)
    send_mail(args.fromaddr, args.toaddr, message)
