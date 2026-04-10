"""Background daemon - system tray bot that monitors and sends notifications.

Runs as a background process with a system tray icon.
Features:
  - System tray icon with assistant name
  - Windows toast notifications for reminders
  - Quick command input via tray menu
  - Background monitoring loop
  - Starts/stops the server for phone access
"""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime

from src.core.config import get_settings
from src.core.logger import get_logger, setup_logging

log = get_logger(__name__)


class AssistantDaemon:
    """Background daemon that lives in the system tray."""

    def __init__(self):
        self.settings = get_settings()
        self.persona = self.settings.persona
        self.running = False
        self._tray_icon = None
        self._monitor_thread = None
        self._reminders: list[dict] = []

    def start(self):
        """Start the daemon with system tray icon."""
        self.running = True
        log.info("daemon.starting", name=self.persona.name)

        # Start background monitor
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        # Send startup notification
        self._notify(
            f"{self.persona.name} Online",
            self.persona.get_greeting(),
        )

        # Start system tray (blocks on main thread)
        self._start_tray()

    def stop(self):
        """Stop the daemon."""
        self.running = False
        if self._tray_icon:
            self._tray_icon.stop()
        self._notify(
            f"{self.persona.name} Offline",
            self.persona.get_farewell(),
        )
        log.info("daemon.stopped")

    def add_reminder(self, message: str, at_time: datetime):
        """Add a reminder to the queue."""
        self._reminders.append({
            "message": message,
            "time": at_time,
            "fired": False,
        })
        log.info("daemon.reminder.added", message=message, time=at_time.isoformat())

    # --- System tray ------------------------------------------------

    def _start_tray(self):
        """Create and run the system tray icon."""
        try:
            import pystray
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            log.warning("daemon.tray.unavailable", reason="pystray or Pillow not installed")
            print(f"  {self.persona.name} running in background (no tray icon).")
            print("  Press Ctrl+C to stop.")
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop()
            return

        # Create icon image - a simple colored circle with initial
        icon_image = self._create_icon_image()

        # Build tray menu
        menu = pystray.Menu(
            pystray.MenuItem(
                f"{self.persona.name} - {self.persona.tagline}",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Chat", self._on_open_chat),
            pystray.MenuItem("Quick Command...", self._on_quick_command),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status", self._on_status),
            pystray.MenuItem("Settings", self._on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

        self._tray_icon = pystray.Icon(
            name="ai-assistant",
            icon=icon_image,
            title=f"{self.persona.name} - {self.persona.tagline}",
            menu=menu,
        )

        log.info("daemon.tray.started")
        self._tray_icon.run()

    def _create_icon_image(self):
        """Generate a simple tray icon with the assistant's initial."""
        from PIL import Image, ImageDraw

        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw a colored circle
        draw.ellipse([2, 2, size - 2, size - 2], fill=(30, 144, 255))

        # Draw the initial letter
        initial = self.persona.name[0].upper()
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("arial.ttf", 32)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), initial, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (size - text_w) / 2
        y = (size - text_h) / 2 - 2
        draw.text((x, y), initial, fill="white", font=font)

        return img

    # --- Tray menu callbacks ----------------------------------------

    def _on_open_chat(self, icon, item):
        """Open the interactive chat in a new terminal window."""
        import subprocess
        subprocess.Popen(
            ["cmd", "/c", "start", "cmd", "/k", "python", "-m", "src"],
            shell=True,
        )

    def _on_quick_command(self, icon, item):
        """Show a simple input dialog for a quick command."""
        import subprocess
        # Use PowerShell input dialog
        ps_script = f"""
        Add-Type -AssemblyName Microsoft.VisualBasic
        $input = [Microsoft.VisualBasic.Interaction]::InputBox(
            'Enter a command for {self.persona.name}:',
            '{self.persona.name} - Quick Command',
            ''
        )
        if ($input) {{
            python -m src $input
        }}
        """
        subprocess.Popen(
            ["powershell", "-Command", ps_script],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _on_status(self, icon, item):
        """Show current status as a notification."""
        active = self.settings.ai.active_provider or "not set"
        enabled_count = sum(
            1 for v in self.settings.integrations.values() if v.enabled
        )
        pending_reminders = sum(1 for r in self._reminders if not r["fired"])

        self._notify(
            f"{self.persona.name} Status",
            f"AI Provider: {active}\n"
            f"Integrations: {enabled_count} active\n"
            f"Pending reminders: {pending_reminders}",
        )

    def _on_settings(self, icon, item):
        """Open settings in a new terminal."""
        import subprocess
        subprocess.Popen(
            ["cmd", "/c", "start", "cmd", "/k", "python", "-m", "src", "--setup"],
            shell=True,
        )

    def _on_quit(self, icon, item):
        """Quit the daemon."""
        self.stop()

    # --- Background monitor -----------------------------------------

    def _monitor_loop(self):
        """Background loop that checks reminders and monitors state."""
        while self.running:
            now = datetime.now()

            # Check reminders
            for reminder in self._reminders:
                if not reminder["fired"] and now >= reminder["time"]:
                    reminder["fired"] = True
                    self._notify(
                        f"{self.persona.name} - Reminder",
                        reminder["message"],
                    )
                    log.info("daemon.reminder.fired", message=reminder["message"])

            # Clean up old fired reminders (older than 1 hour)
            self._reminders = [
                r for r in self._reminders
                if not r["fired"] or (now - r["time"]).seconds < 3600
            ]

            time.sleep(10)  # Check every 10 seconds

    # --- Notifications ----------------------------------------------

    def _notify(self, title: str, message: str):
        """Send a Windows toast notification."""
        try:
            from winotify import Notification

            toast = Notification(
                app_id=self.persona.name,
                title=title,
                msg=message,
                duration="short",
            )
            toast.show()
        except ImportError:
            # Fallback to basic Windows notification
            try:
                import subprocess
                subprocess.run(
                    ["powershell", "-Command",
                     f"[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null; "
                     f"$n = New-Object System.Windows.Forms.NotifyIcon; "
                     f"$n.Icon = [System.Drawing.SystemIcons]::Information; "
                     f"$n.Visible = $true; "
                     f"$n.ShowBalloonTip(5000, '{title}', '{message}', 'Info'); "
                     f"Start-Sleep -Seconds 5; $n.Dispose()"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                log.warning("daemon.notify.failed", title=title)
        except Exception as e:
            log.warning("daemon.notify.error", error=str(e))


def start_daemon():
    """Entry point for starting the daemon."""
    setup_logging("INFO")
    daemon = AssistantDaemon()

    try:
        daemon.start()
    except KeyboardInterrupt:
        daemon.stop()
