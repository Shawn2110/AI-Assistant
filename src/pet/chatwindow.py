"""Chat window that opens when you click the desktop pet.

A modern-looking chat UI built with tkinter.
Shows conversation history, has an input field, and connects
to the active AI agent.
"""

from __future__ import annotations

import asyncio
import threading
import tkinter as tk
from tkinter import scrolledtext

from src.core.config import get_settings
from src.core.logger import get_logger

log = get_logger(__name__)


class ChatWindow:
    """Chat window UI that connects to the AI agent."""

    def __init__(self, parent_root: tk.Tk, on_close=None):
        self.settings = get_settings()
        self.persona = self.settings.persona
        self._agent = None
        self._on_close = on_close

        # Create toplevel window
        self.window = tk.Toplevel(parent_root)
        self.window.title(f"{self.persona.name} - Chat")
        self.window.geometry("450x600")
        self.window.configure(bg="#0d1117")
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self._close)

        self._build_ui()
        self._add_message(self.persona.name, self.persona.get_greeting(), is_bot=True)

    def _build_ui(self):
        """Build the chat UI."""
        # Header
        header = tk.Frame(self.window, bg="#161b22", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Provider info
        active = self.settings.ai.active_provider or "not set"
        all_provs = self.settings.all_providers
        model = all_provs[active].model if active in all_provs else ""

        tk.Label(
            header,
            text=f"  {self.persona.name}",
            font=("Segoe UI", 14, "bold"),
            fg="#58a6ff",
            bg="#161b22",
            anchor="w",
        ).pack(side=tk.LEFT, padx=5, pady=10)

        tk.Label(
            header,
            text=f"{active}: {model}  ",
            font=("Segoe UI", 9),
            fg="#8b949e",
            bg="#161b22",
            anchor="e",
        ).pack(side=tk.RIGHT, padx=5, pady=10)

        # Chat display area
        self.chat_display = scrolledtext.ScrolledText(
            self.window,
            wrap=tk.WORD,
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            padx=15,
            pady=10,
            state=tk.DISABLED,
            cursor="arrow",
            insertbackground="#c9d1d9",
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Configure text tags for styling
        self.chat_display.tag_config("bot_name", foreground="#58a6ff", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("user_name", foreground="#7ee787", font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_config("bot_msg", foreground="#c9d1d9", font=("Segoe UI", 10))
        self.chat_display.tag_config("user_msg", foreground="#e6edf3", font=("Segoe UI", 10))
        self.chat_display.tag_config("system", foreground="#8b949e", font=("Segoe UI", 9, "italic"))

        # Input area
        input_frame = tk.Frame(self.window, bg="#161b22")
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.input_field = tk.Entry(
            input_frame,
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 11),
            relief=tk.FLAT,
            insertbackground="#c9d1d9",
        )
        self.input_field.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5), pady=8, ipady=8)
        self.input_field.bind("<Return>", self._on_send)
        self.input_field.focus_set()

        send_btn = tk.Button(
            input_frame,
            text="Send",
            bg="#238636",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._on_send(None),
            padx=15,
        )
        send_btn.pack(side=tk.RIGHT, padx=5, pady=8)

    def _add_message(self, sender: str, text: str, is_bot: bool = False):
        """Add a message to the chat display."""
        self.chat_display.config(state=tk.NORMAL)

        name_tag = "bot_name" if is_bot else "user_name"
        msg_tag = "bot_msg" if is_bot else "user_msg"

        self.chat_display.insert(tk.END, f"\n{sender}\n", name_tag)
        self.chat_display.insert(tk.END, f"{text}\n", msg_tag)

        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _add_system_message(self, text: str):
        """Add a system/status message."""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"\n{text}\n", "system")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)

    def _on_send(self, event):
        """Handle sending a message."""
        message = self.input_field.get().strip()
        if not message:
            return

        self.input_field.delete(0, tk.END)
        self._add_message("You", message, is_bot=False)

        # Disable input while processing
        self.input_field.config(state=tk.DISABLED)
        self._add_system_message(f"{self.persona.name} is thinking...")

        # Run AI in background thread
        def _process():
            try:
                if not self._agent:
                    from src.ai.agent import AssistantAgent
                    from src.integrations import get_all_tools
                    tools = get_all_tools()
                    self._agent = AssistantAgent(settings=self.settings, tools=tools)

                loop = asyncio.new_event_loop()
                response = loop.run_until_complete(self._agent.chat(message))
                loop.close()

                self.window.after(0, lambda: self._show_response(response))
            except Exception as e:
                self.window.after(0, lambda: self._show_error(str(e)))

        threading.Thread(target=_process, daemon=True).start()

    def _show_response(self, response: str):
        """Show AI response in chat."""
        # Remove "thinking" message
        self.chat_display.config(state=tk.NORMAL)
        content = self.chat_display.get("1.0", tk.END)
        lines = content.split("\n")
        # Remove last system message
        for i in range(len(lines) - 1, -1, -1):
            if "is thinking..." in lines[i]:
                start_idx = f"{i}.0"
                end_idx = f"{i + 1}.0"
                self.chat_display.delete(start_idx, end_idx)
                break
        self.chat_display.config(state=tk.DISABLED)

        self._add_message(self.persona.name, response, is_bot=True)
        self.input_field.config(state=tk.NORMAL)
        self.input_field.focus_set()

        # Notify pet of response (for speech bubble)
        if self._on_close and hasattr(self._on_close, "__self__"):
            pass  # Pet will pick it up

    def _show_error(self, error: str):
        """Show error in chat."""
        self.chat_display.config(state=tk.NORMAL)
        content = self.chat_display.get("1.0", tk.END)
        lines = content.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            if "is thinking..." in lines[i]:
                start_idx = f"{i}.0"
                end_idx = f"{i + 1}.0"
                self.chat_display.delete(start_idx, end_idx)
                break
        self.chat_display.config(state=tk.DISABLED)

        self._add_system_message(f"Error: {error}")
        self.input_field.config(state=tk.NORMAL)
        self.input_field.focus_set()

    def _close(self):
        """Close the chat window."""
        self.window.destroy()
        if self._on_close:
            self._on_close()
