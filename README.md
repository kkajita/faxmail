faxmail
=======

メールに添付されたPDFのイメージをFAXで送信する FAX gateway です。

## 概要

- 標準入力から読み込んだメールに添付されているPDFファイルを抽出します。
- Ghostscriptを使って，PDFをTIFF形式に変換します。
- call fileを`/var/spool/asterisk/outgoing`ディレクトリに置き，AsteriskにFAXの送信を指示します。

## 必要条件

以下の環境で動作確認を取りました。

- Ubuntu 16.04
- Python 2.7.12
- Postfix 3.1.0
- Ghostscript 9.18
- Asterisk 13

## 使い方

```
faxmail.py <trunk名> <送信先電話番号>
```

## インストール
### Ghostscript

```
$ sudo apt install ghostscript
```

### Asterisk

```
$ sudo apt install asterisk
```

Asteriskの設定については，その他のサイトを参照してください。

### faxmail.py

ここでは，`/usr/local/bin/faxmail.py`に配置するものとします。

### postfix

`fax+<電送信先話番号>@example.co.jp`宛に届いたメールをFAXで送信するものとします。

faxユーザーを認識するように`/etc/aliases`にエントリを追加します。
```
fax:	root
```
`/etc/aliases.db`を更新します。
```
$ sudo newaliases
```

faxmailサービスを追加します。
```
$ sudo vim /etc/postfix/master.cf

faxmail   unix  -       n       n       -       1       pipe
        flags=q user=asterisk argv=/usr/local/bin/faxmail.py <trun名> ${extension}
```

配送先リストファイルを追加します。
```
$ sudo vim /etc/postfix/main.cf

transport_maps = regexp:/etc/postfix/transport.reg
```

```
$ sudo vim /etc/postfix/transport.reg

/^fax\+([-0-9]){6,11}@example.co.jp$/ faxmail:
```

postfixサービスを再起動します。

```
$ sudo service postfix restart
```

## ライセンス

- The MIT License (MIT)
