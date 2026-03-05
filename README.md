# cronrun

[日本語版 README](https://github.com/tanakamasayuki/cronrun/blob/main/README.ja.md)
[Specification](https://github.com/tanakamasayuki/cronrun/blob/main/SPEC.md)

`cronrun` is a CLI tool to run commands in either:

- cron mode: `cronrun "<CRONTAB_LINE>"`
- loop mode: `cronrun --loop <command> [args...]`

It is a foreground process (not a daemon): schedules exist only while `cronrun` is running.

## Install

```bash
pipx install cronrun
```

## Quick Start

```bash
# cron mode: run every minute
cronrun "* * * * * echo hello"

# loop mode: run immediately after each completion
cronrun --loop /bin/echo hello

# loop mode with shell expression
cronrun --loop "date; sleep 2"
```

## Usage

### cron mode

```bash
cronrun "<minute> <hour> <day-of-month> <month> <day-of-week> <command> [args...]"
```

- The first 5 fields are parsed as the cron expression
- The rest is treated as one command string and executed through shell (`/bin/sh -c` equivalent)
- No overlap protection: if the next schedule arrives while a previous run is still running, a new run starts

Examples:

```bash
cronrun "*/5 * * * * php worker.php"
cronrun "0 2 * * * ./backup.sh"
cronrun "* * * * * flock -n /tmp/worker.lock php worker.php"
```

### loop mode

```bash
cronrun --loop <command> [args...]
```

- Repeats: `run -> wait -> run again`
- Restarts immediately after each completion
- Commands run through shell
- Single argument is treated as the shell command string directly
- Multiple arguments are composed into one command string, then executed

Examples:

```bash
cronrun --loop "date; sleep 2"
cronrun --loop echo hello
cronrun --loop flock -n /tmp/worker.lock php worker.php
```

## Signal Handling

On `SIGINT` (`Ctrl+C`) or `SIGTERM`:

- Stop starting new runs
- Wait for currently running child processes
- Exit after they finish

If no child process is running, it exits immediately.

## Timezone and DST

- Schedule evaluation uses OS local timezone
- No tool-specific timezone option is provided
- DST transitions follow local time behavior

## Exit Codes

- `0`: normal exit (`--help`, `--version`, or graceful stop by signal)
- `1`: input or validation errors (invalid cron, missing command, invalid arguments)

## Notes

- Error messages are emitted to `stderr` as `error: <message>`
- `cronrun` does not manage crontab files, persistent daemonization, job history, or logging
