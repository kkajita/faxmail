faxmail
=======

Asteriskを利用してFAXの送受信を行うためのスクリプトです。

## sendfax.py

メールに添付されたPDFのイメージをFAXで送信します。  

### 概要

- 標準入力から読み込んだメールメッセージに添付されているPDFを抽出します。
- Ghostscriptを使って，PDFをTIFF形式に変換します。
- call fileを`/var/spool/asterisk/outgoing`ディレクトリに置くことで，FAXの送信をAsteriskに指示します。

### 必要条件

実行には，以下のソフトウェアが必要です。

- Python
- Ghostscript
- Asterisk

以下の環境で動作確認を取りました。

- Ubuntu 16.04
- Python 2.7.12
- Postfix 3.1.0
- Ghostscript 9.18
- Asterisk 13

GhostscriptとAsteriskは，以下のコマンドでインストールしました。

```
$ sudo apt install asterisk
$ sudo apt install ghostscript
```

### 使い方

```
usage: sendfax.py [-h] context trunk number

FAX gateway for Asterisk

positional arguments:
  context     context name
  trunk       SIP trunk
  number      FAX number

optional arguments:
  -h, --help  show this help message and exit
```

## sendmail.py

FAXの送受信結果をメールで通知するためのスクリプトです。

### 概要

- ファイルを添付したメールを送信できます。
- 添付ファイルがTIFF形式の場合は，PDFに変換します。
- 同一マシン上にsmtpサーバが稼働しているものとしています。

### 必要条件

実行には，以下のソフトウェアが必要です。

- Python
- Postfix
- ImageMagick

以下の環境で動作確認を取りました。

- Ubuntu 16.04
- Python 2.7.12
- Postfix 3.1.0
- ImageMagick 6.q16

ImageMagickは，以下のコマンドでインストールしました。

```
$ sudo apt install imagemagick
```
### 使い方

```
usage: sendmail.py [-h] [-a [ATTACHMENT [ATTACHMENT ...]]] [-f FROMADDR]
                   [-s SUBJECT] [-b BODY]
                   toaddr

Send mail with attachment. However, TIFF format files are converted to PDF.

positional arguments:
  toaddr                destination address

optional arguments:
  -h, --help            show this help message and exit
  -a [ATTACHMENT [ATTACHMENT ...]], --attachment [ATTACHMENT [ATTACHMENT ...]]
                        attachment files
  -f FROMADDR, --from FROMADDR
                        sender address
  -s SUBJECT, --subject SUBJECT
                        subject of the email
  -b BODY, --body BODY  content of the email
```

## FAX受信設定
### Asteriskの設定

Asteriskの基本的な設定については，Asteriskのマニュアルやその他のサイトを参照してください。

着信時にFAXを検出するために，`sip.conf`に`faxdetect=yes`を設定してください。

```ini
[general]
faxdetect=yes

[trank]
; SIP trankの設定（省略）
```

`extension.conf`では，FAX検出後のルールを追加します。

受信したFAXイメージは，`TOADDR`宛にメール送信されます。

```ini
[globals]
; メール送信情報
TOADDR=foo@example.com
FROMADDR=fax@example.com

[incoming]
; 外線着信
exten => trank,1,NoOp(**** INCOMING FAX ****)
exten => trank,n,Answer()
exten => trank,n,Goto(fax-rx,receive,1)

; FAX検出
exten => fax,1,NoOp(**** FAX DETECTED ****)
exten => fax,n,Goto(fax-rx,receive,1)

[fax-rx]
exten => receive,1,NoOP(*** RECEIVE FAX START ***)
exten => receive,n,Set(FAXFILE=/var/spool/asterisk/fax/${EPOCH}.tif)
exten => receive,n,ReceiveFAX(${FAXFILE})
exten => receive,n,Hangup
exten => h,1,NoOP(*** RECEIVE FAX FINISHED ***)
exten => h,n,System(/usr/local/bin/sendmail.py ${TOADDR} -a ${FAXFILE} -f ${FROMADDR} -s "fax received from ${CALLERID(num)}")
```

asteriskサービスを再起動します。

```
$ sudo service asterisk restart
```

## FAX送信設定

受信したメールをFAXで送信するFAX gatewayとして構成します。  

### postfixの設定

ここでは，`fax+<電送信先話番号>@example.com`宛に届いたメールをFAXで送信するものとします。

faxユーザーを認識するように，`/etc/aliases`にエントリを追加します。
```
fax:	root
```
`/etc/aliases.db`を更新します。
```
$ sudo newaliases
```

faxmailサービスを追加します。  
`sendfax.py`コマンドのパス，context名，trank名は，実行環境の設定に合わせてください。

```ini
$ sudo vim /etc/postfix/master.cf

faxmail   unix  -       n       n       -       1       pipe
        flags=q user=asterisk argv=/usr/local/bin/sendfax.py fax-tr trank ${extension}
```

`/etc/postfix/main.cf`に，配送先リストファイルを追加します。

```ini
transport_maps = regexp:/etc/postfix/transport.reg
```

`/etc/postfix/transport.reg`に，faxmailサービスに配信すべきメールアドレスのパターンを記述します。

```ini
/^fax\+([-0-9]){6,11}@example.com$/ faxmail:
```

postfixサービスを再起動します。

```
$ sudo service postfix restart
```

### Asteriskの設定

`extension.conf`にFAX送信時に利用するcontext（ここでは，`fax-tr`）を追加します。

FAX送信結果は，`TOADDR`宛にメールで通知されます。

```ini
[globals]
; FAXヘッダ設定
HEADERINFO=09999999999
LOCALSTATIONID=SOME COMPANY
; メール送信情報
TOADDR=foo@example.com
FROMADDR=fax@example.com

[fax-tr]
exten => send,1,NoOP(*** SEND FAX START: File=${FAXFILE} ***)
exten => send,n,Set(FAXFILE=${FAXFILE})
exten => send,n,Set(FAXNUMBER=${FAXNUMBER})
exten => send,n,Set(FAXOPT(ecm)=yes)
exten => send,n,Set(FAXOPT(headerinfo)=${HEADERINFO})
exten => send,n,Set(FAXOPT(localstationid)=${LOCALSTATIONID})
exten => send,n,SendFax(${FAXFILE})
exten => send,n,Hangup
exten => h,1,NoOP(*** SEND FAX FINISHED: STATUS=${FAXSTATUS} ***)
exten => h,n,System(/usr/local/bin/sendmail.py ${TOADDR} -a ${FAXFILE} -f ${FROMADDR} -s "fax send to ${FAXNUMBER}" -b "STATUS: ${FAXSTATUS}\nERROR: ${FAXERROR}\nPAGES: ${FAXPAGES}\nSTATIONID: ${REMOTESTATIONID}\nBITRATE: ${FAXBITRATE}\nRESOLUTION: ${FAXRESOLUTION}\n\n")
```

asteriskサービスを再起動します。

```
$ sudo service asterisk restart
```

## ライセンス

- The MIT License (MIT)
