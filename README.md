# faxmail

PBXソフトウェアAsteriskを，FAXとEメールのgatewayとして構成するためのスクリプト集です。

## 概要

以下の事が可能になります。

- 受信したFAXをEメールで転送
  - FAXイメージは，PDF形式で添付されます。
- Eメール経由でFAXを送信
  - メール本文（HTMLまたはプレーンテキスト）と添付画像（PDF, TIFF, JPEG, PNG）をイメージ化してFAXで送信します。

## sendfax.py

Asteriskと連携し，EメールメッセージをFAXで送信します。

- Eメールに添付されている画像ファイルを抽出して，FAXで送信可能な形式(TIFF G3)に変換します。
  - 対応している画像形式は，PDF, TIFF, JPEG, PNGです。
  - PDF, TIFFは，複数ページに対応します。
  - 複数の画像ファイルが添付されている場合，出現順にページを結合します。
- メール本文のテキストをイメージ化します。
  - デフォルトでは本文のテキストは無視され，画像のみが送信されます。
  - メール本文の送信を指示すると，テキストもイメージ化して，画像と共に送信します。
  - HTML, プレーンテキスト, Markdown形式のテキストに対応します。
  - マルチパートメールの場合，最初のテキストパートを抽出します。
- メールヘッダから送信元（Reply-ToまたはFrom），件名（Subject）を抽出し，Asterisk側へ受け渡します。
  - 送信結果をメールで通知する際に，利用できます。

## 必要条件

スクリプトの実行には，以下のソフトウェアが必要です。

- Python
  - beautifulsoup4
  - markdown
- Ghostscript
- ImageMagick
- wkhtmltopdf

以下の環境で動作確認しました。

- Ubuntu 16.04
- Python 2.7.12
- beautifulsoup4 4.5.3
- Postfix 3.1.0
- Ghostscript 9.18
- ImageMagick 6.q16
- Asterisk 13
- wkhtmltopdf 0.12.4 (with patched qt)

pipコマンドとBeautifulSoup4ライブラリのインストールは，以下のコマンドで行いました。

    $ sudo apt install python-pip
    $ sudo pip install beautifulsoup4
    $ sudo pip install markdown

GhostscriptとImageMagick，Asteriskは，以下のコマンドでインストールしました。

    $ sudo apt install ghostscript
    $ sudo apt install imagemagick
    $ sudo apt install asterisk

wkhtmltopdfは，<https://wkhtmltopdf.org>よりダウンロードしたバイナリイメージを使用しました。

### 使い方

~~~console
usage: sendfax.py [-h] [--version] [-q {super,fine,normal}] [-t TYPE]
                  [--dry-run]
                  context peer number

Email to FAX gateway for Asterisk

positional arguments:
  context               Context for outgoing fax
  peer                  SIP peer entry
  number                Phone number of fax

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -t TYPE, --text TYPE  Select text type to extract (default: ignore text)
  -q {super,fine,normal}, --quality {super,fine,normal}
                        Image quality at fax transmission
  --dry-run             Send back FAX image
~~~

- contextに，`extension.conf`で定義したコンテキスト名を指定します。
- peerは，`sip.conf`で定義した接続先のpeer名を指定します。
- numberでは，送信先の電話番号を指定します。
- メールメッセージは，標準入力から与えられるものとします。
  - メッセージから添付画像を抽出してFAXとして送信します。
- `--text`オプションでテキスト形式を指定すると，添付画像に加えてメール本文を送信対象とします。
  - `html`を指定した場合，`Content-Type`が`text/html`のパートを抽出します。
  - `plane`を指定した場合，`Content-Type`が`text/plain`のパートを抽出します。
  - `markdown`を指定した場合，`Content-Type`が`text/plain`のパートを抽出し，Markdownとして解釈します。
  - `--text`オプションを指定しない場合，メール本文は送信対象としません。
- `--quality`オプションで，FAX送信画質を変更できます（デフォルト：`fine`）。
- `--dry-run`オプションを指定すると，FAXを送信しないで，送信イメージ画像を送信元へEメールで送り返します。

#### 件名（Subject）でのオプションの指示

Eメールの件名で，オプションを指定することができます。  
Subjectの末尾に以下の書式で記述します。

    Subject: <件名> { <オプション> }

指定できるオプションは，以下の3種類です。

- `-t`, `--text`
- `-q`, `--quality`
- `--dry-run`

記述例：

    Subject: 見積書送付の件 { -t html -q normal }

### 解説

- JPEG, PNG画像は，ImageMagickを利用していったんPDFに変換します。
- HTMLまたはプレーンテキスト形式のメール本文は，wkhtmltopdfでPDFに変換します。
- 最後にGhostscriptで，複数のPDFを連結しつつTIFF形式画像に変換にします。
- AsteriskへのFAX送信指示は，call fileを介して行います。
  - callファイルは，`/var/spool/asterisk/outgoing`ディレクトリに作られます。
  - tiffファイルは，`/var/spool/asterisk/fax`ディレクトリに作られます。

## sendmail.py

FAXの送受信結果をEメールで通知するためのスクリプトです。

- ファイルを添付したEメールを送信できます。
- 添付ファイルがTIFF形式の場合は，PDFに変換します。

### 必要条件

スクリプトの実行には，以下のソフトウェアが必要です。

- Python
- Postfix
- ImageMagick

以下の環境で動作確認しました。

- Ubuntu 16.04
- Python 2.7.12
- Postfix 3.1.0
- ImageMagick 6.q16

ImageMagickは，以下のコマンドでインストールしました。

    $ sudo apt install imagemagick

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

```console
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
  --version             show program's version number and exit
```

- BODYでは，エスケープシーケンス（'\n'等）が展開されます。

## FAX受信設定
### Asteriskの設定

Asteriskの基本的な設定については，Asteriskのマニュアル等を参照してください。

- `sip.conf`では，着信時にFAXを検出できるように`faxdetect=yes`を設定してください。
- 外線受発信用peerを設定してください（ここでは，peer名`trunk`）。

```ini
[general]
faxdetect=yes

[trunk]
; 外線受発信用peer
（省略）
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

    $ sudo service asterisk restart

## FAX送信設定
### postfixの設定

ここでは，`fax+<送信先電話番号>@example.com`宛に届いたメールをFAXで送信するものとします。

Postfixがfaxユーザーを認識するように，`/etc/aliases`にエントリを追加します。

```ini
fax: root
```

`/etc/aliases.db`を更新します。

    $ sudo newaliases

faxmailサービスを追加します。

- userは，Asteriskサービスの実行ユーザに合わせてください（ubuntuでは`asterisk`）。
- `sendfax.py`コマンドのパス，context名，peer名は，動作環境の設定に合わせてください。

```ini
faxmail   unix  -       n       n       -       1       pipe
        flags=q user=asterisk argv=/usr/local/bin/sendfax.py <context名> <peer名> ${extension}
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

    $ sudo service postfix restart

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

    $ sudo service asterisk restart

### セキュリティ対策について

上記設定では，FAX送信サービスの宛先を知られてしまうと誰でも利用できる状態となります。
実運用時には，以下のようなセキュリティ対策を実施してください。

- 宛先名（`fax`）を類推しにくい名前にする。
- 送信結果メールに管理者へのCCを付けて監視する。
- 送信元をホワイトリストで制限する。

## ライセンス

- The MIT License (MIT)
