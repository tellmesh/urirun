"""Scheduler snippets for urirun host task queues."""

from __future__ import annotations

import shlex
from pathlib import Path


def build_loop_command(
    *,
    project: str = ".",
    config: str | None = None,
    queue: str = "daily",
    max_tickets: int = 20,
    execute: bool = False,
    no_llm: bool = False,
) -> list[str]:
    command = [
        "urirun",
        "host",
        "task",
        "loop",
        "--project",
        project,
        "--queue",
        queue,
        "--max-tickets",
        str(max_tickets),
    ]
    if config:
        command.extend(["--config", config])
    if execute:
        command.append("--execute")
    if no_llm:
        command.append("--no-llm")
    return command


def shell_join(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def systemd_units(
    *,
    name: str = "urirun-daily",
    command: list[str],
    on_calendar: str = "09:00",
    working_directory: str | None = None,
) -> dict[str, str]:
    workdir = f"WorkingDirectory={working_directory}\n" if working_directory else ""
    service = (
        "[Unit]\n"
        "Description=urirun daily task queue\n\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"{workdir}"
        f"ExecStart={shell_join(command)}\n"
    )
    timer = (
        "[Unit]\n"
        "Description=Run urirun daily task queue\n\n"
        "[Timer]\n"
        f"OnCalendar=*-*-* {on_calendar}:00\n"
        "Persistent=true\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )
    return {f"{name}.service": service, f"{name}.timer": timer}


def cron_line(command: list[str], time_of_day: str = "09:00") -> str:
    hour, minute = time_of_day.split(":", 1)
    return f"{int(minute)} {int(hour)} * * * {shell_join(command)}"


def preview(
    *,
    kind: str = "systemd",
    name: str = "urirun-daily",
    project: str = ".",
    config: str | None = None,
    queue: str = "daily",
    max_tickets: int = 20,
    time_of_day: str = "09:00",
    execute: bool = False,
    no_llm: bool = False,
    working_directory: str | None = None,
) -> dict:
    command = build_loop_command(
        project=project,
        config=config,
        queue=queue,
        max_tickets=max_tickets,
        execute=execute,
        no_llm=no_llm,
    )
    result = {
        "kind": kind,
        "name": name,
        "command": command,
        "commandLine": shell_join(command),
        "queue": queue,
        "execute": execute,
    }
    if kind == "systemd":
        result["files"] = systemd_units(
            name=name,
            command=command,
            on_calendar=time_of_day,
            working_directory=working_directory,
        )
    elif kind == "cron":
        result["cron"] = cron_line(command, time_of_day)
    else:
        raise ValueError(f"unsupported scheduler kind: {kind}")
    return result


def install_systemd_user(files: dict[str, str], out_dir: str | None = None) -> list[str]:
    target = Path(out_dir or "~/.config/systemd/user").expanduser()
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in files.items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return written
