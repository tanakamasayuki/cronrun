# Changelog / 変更履歴

## Unreleased

## 1.0.2
- (EN) Added `--log` option for runtime events (`cron.next`, `run.start`, `run.done`, signal/shutdown logs).
- (JA) 実行時イベント（`cron.next`、`run.start`、`run.done`、シグナル/終了ログ）を出力する `--log` オプションを追加。

## 1.0.1
- (EN) Fixed SIGINT handling so running child processes can finish before exit.
- (JA) SIGINT（Ctrl+C）時に実行中の子プロセス完了を待ってから終了するよう修正。
- (EN) Changed README links to absolute GitHub URLs to avoid 404 on PyPI.
- (JA) PyPI上で404にならないよう、README内リンクをGitHub絶対URLに変更。

## 1.0.0
- (EN) Initial release
- (JA) 初期リリース
