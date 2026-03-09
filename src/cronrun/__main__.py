from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import threading
from datetime import datetime
from typing import Sequence

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

from . import __version__


USAGE = """usage:
  cronrun "<minute> <hour> <day-of-month> <month> <day-of-week> <command> [args...]"
  cronrun --loop <command> [args...]
  cronrun --log ...
  cronrun --help
  cronrun --version
"""


class RuntimeState:
    def __init__(self, *, log_enabled: bool) -> None:
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.threads_lock = threading.Lock()
        self.procs: set[subprocess.Popen[str] | subprocess.Popen[bytes]] = set()
        self.procs_lock = threading.Lock()
        self.log_enabled = log_enabled
        self.run_id = 0
        self.run_id_lock = threading.Lock()
        self.signal_logged = False
        self.signal_name: str | None = None
        self.signal_had_running_jobs = False


def eprint(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


def format_command(cmd: str | Sequence[str]) -> str:
    if isinstance(cmd, str):
        return cmd
    return shlex.join(cmd)


def log_event(state: RuntimeState, event: str, **fields: object) -> None:
    if not state.log_enabled:
        return
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    pairs = [f"{key}={value}" for key, value in fields.items()]
    suffix = f" {' '.join(pairs)}" if pairs else ""
    print(f"{ts} {event}{suffix}", file=sys.stderr, flush=True)


def current_running_jobs(state: RuntimeState) -> int:
    with state.procs_lock:
        return len(state.procs)


def allocate_run_id(state: RuntimeState) -> int:
    with state.run_id_lock:
        state.run_id += 1
        return state.run_id


def print_help() -> None:
    print(USAGE.rstrip())


def register_signal_handlers(state: RuntimeState) -> None:
    def _handler(signum: int, _frame: object) -> None:
        state.stop_event.set()
        if state.signal_name is None:
            try:
                state.signal_name = signal.Signals(signum).name
            except ValueError:
                state.signal_name = str(signum)
        if current_running_jobs(state) > 0:
            state.signal_had_running_jobs = True

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def emit_signal_logs_if_needed(state: RuntimeState) -> None:
    if not state.stop_event.is_set():
        return
    if state.signal_logged:
        return
    if state.signal_name is None:
        return
    log_event(state, "signal.received", signal=state.signal_name)
    if state.signal_had_running_jobs or current_running_jobs(state) > 0:
        log_event(state, "shutdown.waiting", running_jobs=max(1, current_running_jobs(state)))
    state.signal_logged = True


def validate_cron_expr(expr: str) -> None:
    try:
        croniter(expr, datetime.now())
    except (CroniterBadCronError, CroniterBadDateError, ValueError) as exc:
        raise ValueError(f"invalid cron expression: {exc}") from exc


def parse_crontab_line(line: str) -> tuple[str, str]:
    parts = line.split(maxsplit=5)
    if len(parts) < 5:
        raise ValueError("cron expression must have 5 fields")
    if len(parts) == 5:
        raise ValueError("command is required")
    expr = " ".join(parts[:5])
    command = parts[5].strip()
    if not command:
        raise ValueError("command is required")
    validate_cron_expr(expr)
    return expr, command


def wait_or_stop(state: RuntimeState, seconds: float) -> bool:
    if seconds <= 0:
        return not state.stop_event.is_set()
    return not state.stop_event.wait(timeout=seconds)


def run_process(
    state: RuntimeState,
    cmd: str | Sequence[str],
    *,
    shell: bool,
    run_id: int,
) -> None:
    command_text = format_command(cmd)
    started_at = datetime.now()
    log_event(state, "run.start", run_id=run_id, command=repr(command_text))

    popen_kwargs: dict[str, object] = {"shell": shell}
    if os.name == "nt":
        create_new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if create_new_group:
            popen_kwargs["creationflags"] = create_new_group
    else:
        # Isolate child from terminal SIGINT (Ctrl+C) sent to parent process group.
        popen_kwargs["start_new_session"] = True

    proc: subprocess.Popen[str] | subprocess.Popen[bytes]
    proc = subprocess.Popen(cmd, **popen_kwargs)  # noqa: S602
    with state.procs_lock:
        state.procs.add(proc)
    try:
        exit_code = proc.wait()
    finally:
        with state.procs_lock:
            state.procs.discard(proc)
    duration_ms = int((datetime.now() - started_at).total_seconds() * 1000)
    log_event(state, "run.done", run_id=run_id, duration_ms=duration_ms, exit_code=exit_code)


def join_all_threads(state: RuntimeState) -> None:
    while True:
        with state.threads_lock:
            alive = [t for t in state.threads if t.is_alive()]
            state.threads = alive
        if not alive:
            return
        for t in alive:
            t.join(timeout=0.1)


def run_cron_mode(state: RuntimeState, crontab_line: str) -> int:
    expr, command = parse_crontab_line(crontab_line)
    iterator = croniter(expr, datetime.now())
    while not state.stop_event.is_set():
        next_run = iterator.get_next(datetime)
        sleep_seconds = (next_run - datetime.now()).total_seconds()
        log_event(
            state,
            "cron.next",
            schedule=repr(expr),
            next_run=next_run.astimezone().isoformat(timespec="seconds"),
            wait_seconds=max(0, int(sleep_seconds)),
        )
        if not wait_or_stop(state, sleep_seconds):
            break
        run_id = allocate_run_id(state)
        thread = threading.Thread(
            target=run_process,
            args=(state, command),
            kwargs={"shell": True, "run_id": run_id},
            daemon=True,
        )
        thread.start()
        with state.threads_lock:
            state.threads.append(thread)
    emit_signal_logs_if_needed(state)
    join_all_threads(state)
    if state.stop_event.is_set():
        log_event(state, "shutdown.complete")
    return 0


def run_loop_mode(state: RuntimeState, command_args: Sequence[str]) -> int:
    if not command_args:
        raise ValueError("command is required for --loop")
    if len(command_args) == 1:
        loop_cmd: str | Sequence[str] = command_args[0]
    else:
        # Keep argv-style behavior for multiple args while running through shell.
        loop_cmd = shlex.join(command_args)
    while not state.stop_event.is_set():
        run_process(state, loop_cmd, shell=True, run_id=allocate_run_id(state))
        if state.stop_event.is_set():
            break
    if state.stop_event.is_set():
        emit_signal_logs_if_needed(state)
        log_event(state, "shutdown.complete")
    return 0


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False, prog="cronrun")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--help", action="store_true")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("rest", nargs="*")
    return parser.parse_args(list(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.help:
        print_help()
        return 0
    if args.version:
        print(__version__)
        return 0

    state = RuntimeState(log_enabled=args.log)
    register_signal_handlers(state)

    try:
        if args.loop:
            return run_loop_mode(state, args.rest)
        if len(args.rest) != 1:
            raise ValueError("cron mode expects exactly one CRONTAB_LINE argument")
        return run_cron_mode(state, args.rest[0])
    except ValueError as exc:
        eprint(str(exc))
        return 1
    except OSError as exc:
        eprint(str(exc))
        return 1
    except KeyboardInterrupt:
        # Normal stop path: keep behavior aligned with SIGINT handling.
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
