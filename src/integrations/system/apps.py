"""System control tools - open/close apps, manage files, power management.

LangChain tools that the LangGraph agent can call.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from langchain_core.tools import tool


# ─── Application Control ───────────────────────────────────────────

APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "vscode": "code",
    "visual studio code": "code",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "slack": "slack.exe",
    "teams": "ms-teams.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "whatsapp": "WhatsApp.exe",
    "telegram": "Telegram.exe",
}

PROCESS_MAP = {
    "notepad": "notepad.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "vscode": "Code.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
    "slack": "slack.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "whatsapp": "WhatsApp.exe",
    "telegram": "Telegram.exe",
}


@tool
def open_application(name: str) -> str:
    """Open an application by name on Windows.

    Args:
        name: Application name (e.g., 'notepad', 'chrome', 'calculator', 'spotify', 'vscode', 'slack', 'whatsapp')
    """
    name_lower = name.lower().strip()
    executable = APP_MAP.get(name_lower, name_lower)

    try:
        subprocess.Popen(
            executable, shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return f"Opened {name}."
    except Exception as e:
        return f"Failed to open {name}: {e}"


@tool
def close_application(name: str) -> str:
    """Close an application by name on Windows.

    Args:
        name: Application name (e.g., 'notepad', 'chrome', 'slack')
    """
    name_lower = name.lower().strip()
    process = PROCESS_MAP.get(name_lower, f"{name_lower}.exe")

    try:
        result = subprocess.run(
            ["taskkill", "/f", "/im", process],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return f"Closed {name}."
        return f"Could not find {name} running."
    except Exception as e:
        return f"Failed to close {name}: {e}"


# ─── Power Management ──────────────────────────────────────────────

@tool
def power_control(action: str, delay_seconds: int = 0) -> str:
    """Control system power state - shutdown, restart, sleep, or lock.

    Args:
        action: One of 'shutdown', 'restart', 'sleep', 'lock', 'hibernate'
        delay_seconds: Delay before action (default: 0, immediate). Max 3600 (1 hour).
    """
    delay = max(0, min(3600, delay_seconds))

    match action.lower().strip():
        case "shutdown":
            cmd = f"shutdown /s /t {delay}"
            msg = f"Shutting down in {delay} seconds." if delay else "Shutting down now."
        case "restart":
            cmd = f"shutdown /r /t {delay}"
            msg = f"Restarting in {delay} seconds." if delay else "Restarting now."
        case "sleep":
            cmd = "rundll32.exe powrprof.dll,SetSuspendState 0,1,0"
            msg = "Putting system to sleep."
        case "hibernate":
            cmd = "shutdown /h"
            msg = "Hibernating."
        case "lock":
            cmd = "rundll32.exe user32.dll,LockWorkStation"
            msg = "Locking the screen."
        case "cancel":
            cmd = "shutdown /a"
            msg = "Cancelled scheduled shutdown/restart."
        case _:
            return f"Unknown action: {action}. Use: shutdown, restart, sleep, hibernate, lock, cancel"

    try:
        subprocess.run(cmd, shell=True, capture_output=True)
        return msg
    except Exception as e:
        return f"Failed to {action}: {e}"


# ─── Volume Control ────────────────────────────────────────────────

@tool
def set_volume(level: int) -> str:
    """Set the system volume level.

    Args:
        level: Volume level from 0 (mute) to 100 (max)
    """
    level = max(0, min(100, level))
    try:
        ps_script = f"""
        $wshShell = New-Object -ComObject WScript.Shell
        1..50 | ForEach-Object {{ $wshShell.SendKeys([char]174) }}
        1..{level // 2} | ForEach-Object {{ $wshShell.SendKeys([char]175) }}
        """
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=10,
        )
        return f"Volume set to {level}%."
    except Exception as e:
        return f"Failed to set volume: {e}"


# ─── File Management ───────────────────────────────────────────────

@tool
def list_files(directory: str = ".") -> str:
    """List files and folders in a directory.

    Args:
        directory: Path to the directory (default: current directory)
    """
    try:
        path = Path(directory).expanduser().resolve()
        if not path.exists():
            return f"Directory not found: {directory}"
        if not path.is_dir():
            return f"Not a directory: {directory}"

        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        result = [f"Contents of {path}:\n"]
        for item in items[:50]:
            prefix = "[D]" if item.is_dir() else "[F]"
            result.append(f"  {prefix} {item.name}")

        total = sum(1 for _ in path.iterdir())
        if total > 50:
            result.append(f"\n  ... and {total - 50} more items")

        return "\n".join(result)
    except PermissionError:
        return f"Permission denied: {directory}"
    except Exception as e:
        return f"Error listing files: {e}"


@tool
def search_files(query: str, directory: str = ".") -> str:
    """Search for files by name pattern in a directory.

    Args:
        query: File name pattern to search for (e.g., '*.py', 'report*')
        directory: Directory to search in (default: current directory)
    """
    try:
        path = Path(directory).expanduser().resolve()
        if not path.exists():
            return f"Directory not found: {directory}"

        matches = list(path.rglob(query))[:20]
        if not matches:
            return f"No files matching '{query}' found in {directory}."

        result = [f"Found {len(matches)} file(s) matching '{query}':\n"]
        for match in matches:
            result.append(f"  [F] {match}")
        return "\n".join(result)
    except Exception as e:
        return f"Error searching files: {e}"


# ─── System Info ───────────────────────────────────────────────────

@tool
def get_system_info() -> str:
    """Get system information (OS, user, time, disk space)."""
    import platform
    import shutil
    from datetime import datetime

    info = [
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"User: {os.getenv('USERNAME', 'unknown')}",
        f"Computer: {platform.node()}",
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Python: {platform.python_version()}",
    ]

    try:
        total, used, free = shutil.disk_usage("C:\\")
        info.append(f"Disk (C:): {free // (1024**3)}GB free / {total // (1024**3)}GB total")
    except Exception:
        pass

    return "\n".join(info)


@tool
def run_system_command(command: str) -> str:
    """Run a safe read-only system command.

    Args:
        command: The command to run (e.g., 'ipconfig', 'systeminfo', 'tasklist')
    """
    safe_prefixes = [
        "ipconfig", "systeminfo", "hostname", "whoami",
        "date /t", "time /t", "ver",
        "dir", "tree", "type",
        "ping", "nslookup", "tracert",
        "netstat", "tasklist",
        "wmic cpu get", "wmic memorychip get",
    ]

    command_lower = command.lower().strip()
    if not any(command_lower.startswith(p) for p in safe_prefixes):
        return (
            f"Command '{command}' is not allowed. "
            "Safe commands: ipconfig, systeminfo, hostname, whoami, dir, ping, tasklist, etc."
        )

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            output += f"\nError: {result.stderr.strip()}"
        return output or "Command completed with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Error running command: {e}"


# ─── Reminders ─────────────────────────────────────────────────────

@tool
def set_reminder(message: str, minutes: int = 0) -> str:
    """Set a reminder that will show as a Windows notification.

    Args:
        message: The reminder message
        minutes: Minutes from now (0 = immediate notification)
    """
    if minutes <= 0:
        # Immediate notification
        ps_script = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">AI Assistant Reminder</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("AI Assistant").Show($toast)
        """
        try:
            subprocess.run(
                ["powershell", "-Command", ps_script],
                capture_output=True, timeout=10,
            )
            return f"Reminder set: '{message}'"
        except Exception:
            # Fallback to msg command
            subprocess.run(
                ["msg", "*", f"Reminder: {message}"],
                capture_output=True, timeout=10,
            )
            return f"Reminder set: '{message}'"
    else:
        # Schedule for later using Windows Task Scheduler
        from datetime import datetime, timedelta
        run_time = datetime.now() + timedelta(minutes=minutes)
        time_str = run_time.strftime("%H:%M")
        date_str = run_time.strftime("%m/%d/%Y")
        task_name = f"AIAssistant_Reminder_{int(run_time.timestamp())}"

        cmd = (
            f'schtasks /create /tn "{task_name}" /tr '
            f'"msg * Reminder: {message}" '
            f'/sc once /st {time_str} /sd {date_str} /f'
        )
        try:
            subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            return f"Reminder set for {run_time.strftime('%H:%M')}: '{message}'"
        except Exception as e:
            return f"Failed to set reminder: {e}"


def get_system_tools() -> list:
    """Return all system integration tools."""
    return [
        open_application,
        close_application,
        power_control,
        set_volume,
        list_files,
        search_files,
        get_system_info,
        run_system_command,
        set_reminder,
    ]
