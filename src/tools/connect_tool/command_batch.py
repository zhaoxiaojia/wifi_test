"""Shared helpers for running host-side shell commands."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass
class CommandResult:
    """Container describing a completed shell command."""

    command: str
    stdout: str
    stderr: str
    returncode: int


class CommandExecutionError(RuntimeError):
    """Raised when a host command exits with a non-zero code."""


class CommandTimeoutError(RuntimeError):
    """Raised when a host command exceeds the allotted timeout."""


class CommandRunner:
    """Lightweight wrapper around :mod:`subprocess` with consistent logging."""

    def __init__(self, encoding: str = "utf-8") -> None:
        self.default_encoding = encoding

    def popen(
        self,
        cmd: Sequence[str] | str,
        *,
        shell: bool = False,
        encoding: str | None = None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) -> subprocess.Popen[str]:
        """Launch a subprocess and return the raw ``Popen`` handle."""
        process = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=stdout,
            stderr=stderr,
            encoding=encoding or self.default_encoding,
            errors="ignore",
        )
        return process

    def run(
        self,
        cmd: Sequence[str] | str,
        *,
        shell: bool = False,
        timeout: float | None = None,
    ) -> CommandResult:
        """Execute a command and capture its stdout/stderr."""
        logging.info("Executing host command: %s", cmd)
        process = self.popen(cmd, shell=shell)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            stdout, stderr = process.communicate()
            logging.error("Command timed out after %ss: %s", timeout, cmd)
            raise CommandTimeoutError(f"Timeout while running: {cmd}") from exc
        return CommandResult(
            command=" ".join(cmd) if isinstance(cmd, Iterable) and not isinstance(cmd, str) else str(cmd),
            stdout=stdout or "",
            stderr=stderr or "",
            returncode=process.returncode,
        )


class CommandBatch:
    """Accumulates commands to be executed sequentially with shared error handling."""

    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner
        self._entries: list[tuple[str, float | None, bool, bool]] = []

    def add(
        self,
        command: str,
        *,
        timeout: float | None = None,
        shell: bool = True,
        ignore_error: bool = True,
    ) -> None:
        """Enqueue a new command for execution."""
        if not command:
            return
        self._entries.append((command, timeout, shell, ignore_error))

    def run(self) -> List[CommandResult]:
        """Run all queued commands in order."""
        results: List[CommandResult] = []
        while self._entries:
            command, timeout, shell, ignore_error = self._entries.pop(0)
            try:
                result = self._runner.run(command, shell=shell, timeout=timeout)
            except CommandTimeoutError:
                if not ignore_error:
                    raise
                continue
            if result.returncode != 0:
                logging.warning(
                    "Command exited with %s: %s\nstderr: %s",
                    result.returncode,
                    result.command,
                    result.stderr.strip(),
                )
                if not ignore_error:
                    raise CommandExecutionError(result.stderr)
            results.append(result)
        return results
