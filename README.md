faxmail
=======

PBXソフトウェアAsteriskを，FAXと電子メールのgatewayとして構成するためのスクリプトです。  

## 概要

以下が可能になります。
- 受信したFAXをメールで転送
  - FAXイメージは，PDF形式で添付されます。
- メール経由でFAXを送信
  - 送信先電話番号は，メールアドレスの一部（例：`fax+<送信先電話番号>@example.com`）を使って指示します。
  - メールに添付されたPDFをFAXで送信します。

## sendfax.py

メールに添付されたPDFのイメージをFAXで送信します。  

- Ghostscriptを使って，メールから抽出したPDFをTIFF形式ファイルに変換します。
- `/var/spool/asterisk/outgoing`ディレクトリにcall fileを置くことで，
  AsteriskにFAXの送信を指示します。
- メールヘッダから送信元（Reply-ToまたはFrom），件名（Subject）を抽出し，Asterisk側へ受け渡します。
- 本文のテキストは無視します。

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

- メールメッセージは，標準入力から与えられるものとします。
- contextに，`extension.conf`で定義したコンテキスト名を指定します。
- trunkには，`sip.conf`で定義した接続先のセクション名を指定します。
- numberで，送信先の電話番号を指定します。

## sendmail.py

FAXの送受信結果をメールで通知するためのスクリプトです。

- ファイルを添付したメールを送信できます。
- 添付ファイルがTIFF形式の場合は，PDFに変換します。

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

### 設定

デフォルトでは，同一マシン上にsmtpサーバが稼働しているものとしています。  
gmailなど外部のSMTPサーバを利用する場合は，`sendmail.py`先頭の設定を適宜書き換えて利用してください。

```python
# gmailを利用する場合の設定
USE_TLS = True
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = 'foo@gmail.com'
SMTP_PASSWORD = 'password'
```

### 使い方

```
usage: sendmail.py [-h] [-a [ATTACHMENT [ATTACHMENT ...]]] [-f FROMADDR]
                   [-c CCADDR] [-s SUBJECT] [-b BODY]
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
  -c CCADDR, --cc CCADDR
                        carbon copy address
  -s SUBJECT, --subject SUBJECT
                        subject of the email
  -b BODY, --body BODY  content of the email
```

- BODYでは，エスケープシーケンス（'\n'等）が展開されます。

## FAX受信設定
### Asteriskの設定

Asteriskの基本的な設定については，Asteriskのマニュアルやその他のサイトを参照してください。

`sip.conf`では，着信時にFAXを検出できるように`faxdetect=yes`を設定してください。

```ini
[general]
faxdetect=yes

[trunk]
; SIP trunkの設定（省略）
```

`extension.conf`の設定例を以下に示します。

- 外線に着信するとボイスメールが応答します。
- FAXの発信音を検出した場合，`fax`というextenにジャンプします。
- FAX受信用context（`[fax-rx]`）では，保存先ファイル名を指定してReceiveFAXを実行します。
- 受信したFAXイメージファイルを，`TOADDR`宛にメール送信します。

```ini
[globals]
; メール送信情報
TOADDR=info@example.com
FROMADDR=Fax Agent <fax@example.com>

[incoming]
; 外線着信
exten => trunk,1,NoOp(**** INCOMING FAX ****)
exten => trunk,n,Answer()
exten => trunk,n,Wait(1)
exten => trunk,n,VoiceMail(200)
exten => trunk,n,Hangup

; FAX検出
exten => fax,1,NoOp(**** FAX DETECTED ****)
exten => fax,n,Goto(fax-rx,receive,1)

[fax-rx]
exten => receive,1,NoOP(*** RECEIVE FAX START ***)
exten => receive,n,Set(FAXFILE=/var/spool/asterisk/fax/${EPOCH}.tif)
exten => receive,n,ReceiveFAX(${FAXFILE})
exten => receive,n,Hangup

exten => h,1,NoOP(*** RECEIVE FAX FINISHED: STATUS=${FAXSTATUS} ***)
exten => h,n,GotoIf($["${FAXSTATUS}" != "SUCCESS"]?failed)
exten => h,n,System(/usr/local/bin/sendmail.py ${TOADDR} -f "${FROMADDR}" -a ${FAXFILE} -s "Fax Received from ${CALLERID(num)}")
exten => h,n,Hangup
exten => h,n(failed),System(/usr/local/bin/sendmail.py "${TOADDR}" -f "${FROMADDR}" -a ${FAXFILE} -s "[FAILED] Fax Received from ${CALLERID(num)}" -b "STATUS: ${FAXSTATUS}\nERROR: ${FAXERROR}\n\n")
```

asteriskサービスを再起動します。

```
$ sudo service asterisk restart
```

## FAX送信設定
### postfixの設定

ここでは，`fax+<送信先電話番号>@example.com`宛に届いたメールをFAXで送信するものとします。

Postfixがfaxユーザーを認識するように，`/etc/aliases`にエントリを追加します。
```
fax:	root
```
`/etc/aliases.db`を更新します。
```
$ sudo newaliases
```

faxmailサービスを追加します。
- userは，Asteriskサービスの実行ユーザに合わせてください。
- `sendfax.py`コマンドのパス，context名，trunk名は，実行環境の設定に合わせてください。

```ini
faxmail   unix  -       n       n       -       1       pipe
        flags=q user=asterisk argv=/usr/local/bin/sendfax.py fax-tr trunk ${extension}
```

`/etc/postfix/main.cf`に，配送先リストファイルを追加します。

```ini
transport_maps = regexp:/etc/postfix/transport.reg
```

`/etc/postfix/transport.reg`に，faxmailサービスに配信すべきメールアドレスのパターンを記述します。

```ini
/^fax\+([0-9]){10,11}(@.+)?$/ faxmail:
```

postfixサービスを再起動します。

```
$ sudo service postfix restart
```

### Asteriskの設定

`extension.conf`にFAX送信時に利用するcontext（`[fax-tr]`）を追加します。

- 送信先が応答しない場合は，リトライします（５分間隔，最大2回）。  
  - ただし，着信自体は成功したがFAXのデータ送信に失敗した場合にはリトライしません。
- FAX送信結果は，メール送信元へ通知されます。

```ini
[globals]
; FAXヘッダ設定
HEADERINFO=SOME COMPANY
LOCALSTATIONID=09999999999
; メール送信情報
FROMADDR=Fax Agent <fax@example.com>

[fax-tr]
exten => send,1,NoOP(*** SEND FAX START: File=${FAXFILE} ***)
exten => send,n,Set(FAXOPT(ecm)=yes)
exten => send,n,Set(FAXOPT(headerinfo)=${HEADERINFO})
exten => send,n,Set(FAXOPT(localstationid)=${LOCALSTATIONID})
exten => send,n,SendFax(${FAXFILE})
exten => send,n,Hangup

exten => failed,1,Set(FAXSTATUS=DIALFAIL)
exten => failed,n,Set(FAXERROR=No Answer)
exten => failed,n,Set(FAXPAGES=0)
exten => failed,n,Hangup

exten => h,1,NoOP(*** SEND FAX FINISHED: STATUS=${FAXSTATUS} ***)
exten => h,n,GotoIf($["${FAXSTATUS}" != "SUCCESS"]?failed)
exten => h,n,System(/usr/local/bin/sendmail.py "${REPLYTO}" -a "${FAXFILE}" -f "${FROMADDR}" -s "${SUBJECT}" -b "FAXNUMBER: ${FAXNUMBER}\nSTATUS: ${FAXSTATUS}\nPAGES: ${FAXPAGES}\nBITRATE: ${FAXBITRATE}\nRESOLUTION: ${FAXRESOLUTION}\n\n")
exten => h,n,Hangup
exten => h,n(failed),System(/usr/local/bin/sendmail.py "${REPLYTO}" -a "${FAXFILE}" -f "${FROMADDR}" -s "[FAILED] ${SUBJECT}" -b "FAXNUMBER: ${FAXNUMBER}\nSTATUS: ${FAXSTATUS}\nERROR: ${FAXERROR}\n\n")

```

asteriskサービスを再起動します。

```
$ sudo service asterisk restart
```

### セキュリティ対策について

上記設定では，FAX送信サービスの宛先を知られてしまうと誰でも利用できる状態となります。
実運用時には，以下のようなセキュリティ対策を実施してください。

- 宛先名（`fax`）を類推しにくい名前にする。
- 送信結果メールに管理者へのCCを付けて監視する。
- 送信元をホワイトリストで制限する。

## ライセンス

- The MIT License (MIT)
