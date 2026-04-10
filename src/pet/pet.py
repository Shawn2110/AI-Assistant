"""Desktop pet -- animated mascot that walks on your screen.

Uses tkinter for a transparent overlay window.
The pet walks along the bottom of the screen (above the taskbar),
idles, sleeps, and shows speech bubbles when the AI responds.
Click to open chat, drag to move.
"""

from __future__ import annotations

import random
import tkinter as tk
from enum import Enum

from PIL import ImageTk

from src.core.config import get_settings
from src.core.logger import get_logger
from src.pet.sprites import SIZE, create_all_sprites

log = get_logger(__name__)


class PetState(str, Enum):
    IDLE = "idle"
    WALK = "walk"
    TALK = "talk"
    HAPPY = "happy"
    SLEEP = "sleep"
    BLINK = "blink"


class DesktopPet:
    """Animated desktop pet that lives on your screen."""

    def __init__(self):
        self.settings = get_settings()
        self.persona = self.settings.persona
        self.state = PetState.IDLE
        self.frame = 0
        self.direction = 1  # 1 = right, -1 = left
        self.idle_timer = 0
        self.blink_timer = 0
        self.speech_text = ""
        self.speech_timer = 0
        self._chat_window = None

        # Window
        self.root = tk.Tk()
        self.root.overrideredirect(True)        # No title bar
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-transparentcolor", "black")
        self.root.configure(bg="black")

        # Screen dimensions
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # Position: bottom of screen, above taskbar
        self.x = self.screen_w // 2
        self.y = self.screen_h - SIZE - 50  # 50px above bottom for taskbar

        self.root.geometry(f"{SIZE + 200}x{SIZE + 60}+{self.x}+{self.y}")

        # Canvas for drawing
        self.canvas = tk.Canvas(
            self.root,
            width=SIZE + 200,
            height=SIZE + 60,
            bg="black",
            highlightthickness=0,
        )
        self.canvas.pack()

        # Load sprites
        self.sprites = create_all_sprites()
        self.tk_images = {}  # Cache PhotoImage refs to prevent GC
        for state_name, frames in self.sprites.items():
            self.tk_images[state_name] = [ImageTk.PhotoImage(f) for f in frames]

        # Pet sprite on canvas
        self.pet_sprite = self.canvas.create_image(
            SIZE // 2, SIZE // 2 + 30, image=self.tk_images["idle"][0]
        )

        # Speech bubble (hidden by default)
        self.bubble_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="", outline="")
        self.bubble_text = self.canvas.create_text(0, 0, text="", fill="", anchor="sw")

        # Name label
        self.name_label = self.canvas.create_text(
            SIZE // 2, SIZE + 45,
            text=self.persona.name,
            fill="white",
            font=("Segoe UI", 8, "bold"),
        )

        # Drag support
        self._drag_data = {"x": 0, "y": 0}
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)

        # Behavior timers
        self._walk_target = None
        self._walk_steps = 0
        self._idle_count = 0
        self._dragging = False

    def run(self):
        """Start the pet."""
        log.info("pet.started", name=self.persona.name)
        self.say(self.persona.get_greeting())
        self._animate()
        self.root.mainloop()

    def say(self, text: str, duration: int = 4000):
        """Show a speech bubble above the pet."""
        self.speech_text = text
        self.speech_timer = duration // 100  # Convert to frame ticks
        self._set_state(PetState.TALK)
        self._update_bubble()

    def _update_bubble(self):
        """Draw or hide the speech bubble."""
        if self.speech_text and self.speech_timer > 0:
            # Truncate long text
            display = self.speech_text[:60]
            if len(self.speech_text) > 60:
                display += "..."

            self.canvas.itemconfig(
                self.bubble_text,
                text=display,
                fill="white",
                font=("Segoe UI", 9),
            )
            self.canvas.coords(self.bubble_text, SIZE // 2, 22)

            # Background
            bbox = self.canvas.bbox(self.bubble_text)
            if bbox:
                pad = 6
                self.canvas.coords(
                    self.bubble_bg,
                    bbox[0] - pad, bbox[1] - pad,
                    bbox[2] + pad, bbox[3] + pad,
                )
                self.canvas.itemconfig(
                    self.bubble_bg,
                    fill="#1a1a3e",
                    outline="#4488ff",
                    width=1,
                )
        else:
            self.canvas.itemconfig(self.bubble_text, text="", fill="")
            self.canvas.itemconfig(self.bubble_bg, fill="", outline="")

    def _set_state(self, state: PetState):
        """Change pet state."""
        if self.state != state:
            self.state = state
            self.frame = 0

    def _animate(self):
        """Main animation loop -- called every 100ms."""
        if self._dragging:
            self.root.after(100, self._animate)
            return

        self.frame = (self.frame + 1) % 4

        # Speech bubble countdown
        if self.speech_timer > 0:
            self.speech_timer -= 1
            if self.speech_timer <= 0:
                self.speech_text = ""
                self._update_bubble()
                self._set_state(PetState.HAPPY)

        # State behavior
        if self.state == PetState.WALK:
            self._do_walk()
        elif self.state == PetState.IDLE:
            self._do_idle()
        elif self.state == PetState.HAPPY:
            self._idle_count += 1
            if self._idle_count > 10:
                self._set_state(PetState.IDLE)
                self._idle_count = 0
        elif self.state == PetState.TALK:
            pass  # Stay in talk until speech timer runs out
        elif self.state == PetState.SLEEP:
            self._idle_count += 1
            if self._idle_count > 50:
                self._set_state(PetState.IDLE)
                self._idle_count = 0

        # Random blink
        self.blink_timer += 1
        if self.blink_timer > random.randint(20, 40):
            self.blink_timer = 0
            if self.state == PetState.IDLE:
                # Quick blink -- just show blink frame briefly
                current_state = self.state
                self._set_state(PetState.BLINK)
                # Will revert on next tick

        # Update sprite
        state_name = self.state.value
        frames = self.tk_images.get(state_name, self.tk_images["idle"])
        img = frames[self.frame % len(frames)]

        # Flip for direction
        self.canvas.itemconfig(self.pet_sprite, image=img)
        self._update_bubble()

        self.root.after(100, self._animate)

    def _do_idle(self):
        """Idle behavior -- occasionally start walking or sleeping."""
        self._idle_count += 1

        # After ~5 seconds idle, maybe walk
        if self._idle_count > random.randint(30, 60):
            self._idle_count = 0
            action = random.choice(["walk", "walk", "walk", "sleep", "idle"])
            if action == "walk":
                self._start_walk()
            elif action == "sleep":
                self._set_state(PetState.SLEEP)

    def _start_walk(self):
        """Begin walking to a random position."""
        self._set_state(PetState.WALK)
        target_x = random.randint(50, self.screen_w - SIZE - 50)
        self._walk_target = target_x
        self.direction = 1 if target_x > self.x else -1

    def _do_walk(self):
        """Walk toward target."""
        if self._walk_target is None:
            self._set_state(PetState.IDLE)
            return

        speed = 4
        self.x += speed * self.direction

        # Reached target?
        if (self.direction == 1 and self.x >= self._walk_target) or \
           (self.direction == -1 and self.x <= self._walk_target):
            self._walk_target = None
            self._set_state(PetState.IDLE)
            self._idle_count = 0
        else:
            self.root.geometry(f"+{self.x}+{self.y}")

    # --- Interaction ------------------------------------------------

    def _on_click(self, event):
        """Start drag."""
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._dragging = False

    def _on_drag(self, event):
        """Drag the pet."""
        self._dragging = True
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        self.x = self.root.winfo_x() + dx
        self.y = self.root.winfo_y() + dy
        self.root.geometry(f"+{self.x}+{self.y}")

    def _on_release(self, event):
        """End drag."""
        self._dragging = False

    def _on_double_click(self, event):
        """Double-click to open quick chat."""
        self._open_chat()

    def _on_right_click(self, event):
        """Right-click context menu."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"{self.persona.name}", state="disabled")
        menu.add_separator()
        menu.add_command(label="Chat...", command=self._open_chat)
        menu.add_command(label="Open Terminal Chat", command=self._open_terminal_chat)
        menu.add_separator()
        menu.add_command(label="Settings", command=self._open_settings)
        menu.add_command(label="Quit", command=self._quit)
        menu.post(event.x_root, event.y_root)

    def _open_chat(self):
        """Open the chat window."""
        if self._chat_window is not None:
            # Already open, focus it
            try:
                self._chat_window.window.lift()
                self._chat_window.window.focus_force()
                return
            except tk.TclError:
                self._chat_window = None

        self._set_state(PetState.HAPPY)

        from src.pet.chatwindow import ChatWindow
        self._chat_window = ChatWindow(
            self.root,
            on_close=lambda: setattr(self, '_chat_window', None),
        )

    def _open_terminal_chat(self):
        """Open full interactive chat in a terminal."""
        import subprocess
        subprocess.Popen(
            ["cmd", "/c", "start", "cmd", "/k", "python", "-m", "src"],
            shell=True,
        )

    def _open_settings(self):
        """Open settings in terminal."""
        import subprocess
        subprocess.Popen(
            ["cmd", "/c", "start", "cmd", "/k", "python", "-m", "src", "--setup"],
            shell=True,
        )

    def _quit(self):
        """Quit the pet."""
        self.say(self.persona.get_farewell(), duration=2000)
        self.root.after(2000, self.root.destroy)


def start_pet():
    """Entry point for the desktop pet."""
    from src.core.logger import setup_logging
    setup_logging("INFO")

    pet = DesktopPet()
    pet.run()
