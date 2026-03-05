# cronrun

[English README](README.md)
[仕様書](SPEC.ja.md)

`cronrun` は、指定したコマンドを次のいずれかで実行するCLIツールです。

- cron モード: `cronrun "<CRONTAB_LINE>"`
- loop モード: `cronrun --loop <command> [args...]`

常駐デーモンではなく、`cronrun` 実行中のみスケジュールを管理します。

## インストール

```bash
pipx install cronrun
```

## クイックスタート

```bash
# cron モード: 毎分実行
cronrun "* * * * * echo hello"

# loop モード: 終了後すぐに再実行
cronrun --loop /bin/echo hello

# loop モードでシェル式を実行
cronrun --loop "date; sleep 2"
```

## 使い方

### cron モード

```bash
cronrun "<minute> <hour> <day-of-month> <month> <day-of-week> <command> [args...]"
```

- 先頭5フィールドを cron 式として解釈します
- 残りは1つのコマンド文字列としてシェル経由（`/bin/sh -c` 相当）で実行します
- 実行重複は制御しません。前回実行中でも次回時刻で新しい実行を開始します

例:

```bash
cronrun "*/5 * * * * php worker.php"
cronrun "0 2 * * * ./backup.sh"
cronrun "* * * * * flock -n /tmp/worker.lock php worker.php"
```

### loop モード

```bash
cronrun --loop <command> [args...]
```

- `実行 -> 終了待ち -> 再実行` を繰り返します
- 終了後は即座に次を開始します
- コマンドはシェル経由で実行します
- 引数が1つなら、その文字列をそのままシェルコマンドとして実行します
- 引数が複数なら、1つのコマンド文字列に組み立てて実行します

例:

```bash
cronrun --loop "date; sleep 2"
cronrun --loop echo hello
cronrun --loop flock -n /tmp/worker.lock php worker.php
```

## シグナル処理

`SIGINT`（Ctrl+C）または `SIGTERM` を受信した場合:

- 新規実行の開始を停止
- 実行中の子プロセスの終了を待機
- 終了後にプロセス終了

実行中の子プロセスがなければ即時終了します。

## タイムゾーン / DST

- スケジュール評価は OS のローカルタイムゾーンを使用
- ツール独自のタイムゾーン指定はなし
- DST 切り替えはローカルタイム準拠

## 終了コード

- `0`: 正常終了（`--help`、`--version`、シグナルでの正常停止）
- `1`: 入力/検証エラー（cron式不正、コマンド不足、引数不正）

## 補足

- エラーメッセージは `stderr` に `error: <message>` 形式で出力
- crontab ファイル管理、常駐化、ジョブ履歴、ログ管理は対象外

