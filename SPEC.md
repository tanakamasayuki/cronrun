# cronrun Specification

## Overview

`cronrun` is a command-line tool that runs a specified command in either:

- crontab-style schedule mode
- simple loop mode

This tool is **not a resident daemon; it manages schedules only while running**.  
When the process exits, all schedules are terminated.
User-facing installation and usage examples are documented in `README.md`.

------------------------------------------------------------------------

# Execution Modes

## 1. cron mode

### Syntax

    cronrun "<CRONTAB_LINE>"

### Input Format

`<CRONTAB_LINE>` uses the same format as one crontab line.

    <minute> <hour> <day-of-month> <month> <day-of-week> <command> [args...]

Examples

    cronrun "* * * * * php worker.php"
    cronrun "*/5 * * * * flock -n /tmp/worker.lock php worker.php"
    cronrun "0 2 * * * ./backup.sh"

### Behavior

1. Split the input string into the **first 5 fields**
2. Treat the first 5 fields as the **cron expression**
3. Treat the remaining part as the **command to execute**

Example

    */5 * * * * php worker.php

↓

    schedule = */5 * * * *
    command  = php worker.php

### Scheduling

- Calculate the next execution time from the cron expression
- Wait until the next execution time
- Execute the command when the time is reached
- After the command exits, calculate the next execution time

### Time Basis

- Scheduling is based on **local time (OS local time zone)**
- No tool-specific timezone option is provided (such as `TZ`)
- Daylight Saving Time (DST) transitions are evaluated according to local time
- Non-existent local times (skipped during spring-forward) are skipped
- If the same local time appears twice (fall-back), each occurrence may be evaluated

### Overlapping Executions

- No concurrent execution control is provided
- If the next schedule arrives while a command is still running, a new execution is started
- If concurrent execution control is needed, use `flock` or similar tools

------------------------------------------------------------------------

# 2. loop mode

### Syntax

    cronrun --loop <command> [args...]

Examples

    cronrun --loop php worker.php
    cronrun --loop flock -n /tmp/worker.lock php worker.php

### Behavior

Repeat the following:

    Run command
    Wait for completion
    Run again

After a command exits, the next run starts **immediately**.

------------------------------------------------------------------------

# Signal Handling

Behavior when receiving `SIGINT` (Ctrl+C) or `SIGTERM`:

### Common Behavior

1. Stop starting new scheduled executions
2. If any command is currently running, **wait for it to finish**
3. Exit the process after running commands have finished

### When No Command Is Running

- Exit immediately

### Signal Forwarding to Child Processes

- The parent process does not explicitly send termination signals to child processes
- The parent process only does: "stop new starts + wait for existing child processes"

------------------------------------------------------------------------

# Command Execution

- Commands are run as **child processes**
- Standard input / output / error use the **same streams as the parent process**
- Command exit codes are not used for logging or control

### Execution Method

- `cron` mode:
    - Split `<CRONTAB_LINE>` into the first 5 fields as cron expression and treat the remainder as a command string
    - Execute the command string via shell (`/bin/sh -c` equivalent)
- `loop` mode:
    - If `--loop` gets exactly one argument, execute that string via shell (`/bin/sh -c` equivalent)
        - Example: `cronrun --loop "date; sleep 2"`
    - If `--loop` gets multiple arguments, compose them into one command string and execute via shell

------------------------------------------------------------------------

# Process Lifecycle

- This tool is **not a resident service**
- It works only while started by the user
- When the process exits, schedules are discarded

------------------------------------------------------------------------

# Dependency Specification

- Cron expressions use the **5-field format**

    minute hour day-of-month month day-of-week

- Seconds field is not supported

------------------------------------------------------------------------

# Error Handling

Exit as error in the following cases:

- Fewer than 5 fields in cron expression
- No command to execute
- Invalid cron expression

Exit code is `1`.

If the process is stopped normally by `SIGINT` / `SIGTERM` after startup, exit code is `0`.

------------------------------------------------------------------------

# CLI Helper Options

- `--help`: show usage and exit with code `0`
- `--version`: show version string and exit with code `0`
- `--log`: enable runtime logs to standard error output

------------------------------------------------------------------------

# Message Policy

- Print error messages to standard error output
- Error messages are written in English
- Format is `error: <message>`

------------------------------------------------------------------------

# Logging (`--log`)

When `--log` is specified, output runtime logs to standard error output.

- Timestamp format: ISO 8601 in local timezone
- `cron` mode:
    - `cron.next`: before waiting for next scheduled execution
    - `run.start`: when a child process starts
    - `run.done`: when a child process exits (include duration and exit code)
- `loop` mode:
    - `run.start`
    - `run.done` (include duration and exit code)
- On `SIGINT` / `SIGTERM`:
    - `signal.received`
    - `shutdown.waiting` (only if at least one child process is running)
    - `shutdown.complete` (when shutdown processing is fully complete)

------------------------------------------------------------------------

# Acceptance Tests (Minimum)

- `cronrun "* * * * * echo hi"` starts on one-minute intervals
- `cronrun --loop echo hi` runs repeatedly
- Invalid cron expression (example: `cronrun "x * * * * echo hi"`) exits with code `1`
- Missing command (example: `cronrun "* * * * *"`) exits with code `1`
- Sending `SIGTERM` while running stops new starts, waits for completion, then exits with code `0`

------------------------------------------------------------------------

# Out of Scope

The following are not handled by this tool:

- crontab file management
- resident daemon
- systemd timer
- job history management
- log management
- concurrent execution control
