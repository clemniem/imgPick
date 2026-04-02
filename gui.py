#!/usr/bin/env python3
"""imgPick GUI — Konfigurationsfenster für die CLI."""

import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from scorer import DEFAULT_POSITIVE_PROMPTS, DEFAULT_NEGATIVE_PROMPTS

# Tooltip texts for all settings
TOOLTIPS = {
    "input_folder": "Der Ordner mit deinen Urlaubsfotos und -videos.\nAlle Unterordner werden standardmässig mit durchsucht.",
    "output_folder": "Hierhin werden die ausgewählten Fotos und Videos kopiert.\nWird automatisch erstellt, falls er nicht existiert.",
    "top_percent": "Wie viel Prozent deiner Fotos behalten werden sollen.\nNach Duplikat-Entfernung werden die besten X% nach Score ausgewählt.",
    "tech_weight": "Wie stark der technische Score (Schärfe, Helligkeit, Kontrast) gewichtet wird.\n0.0 = nur CLIP, 1.0 = nur Technik, 0.4 = Standard-Mix.",
    "top_percent_videos": "Wie viel Prozent der kurzen Videoclips behalten werden.\nClips werden nach Bildqualität und optional CLIP bewertet.",
    "max_clips": "Wie viele Highlight-Szenen maximal aus einem langen Video extrahiert werden.\nJede Szene wird als separater Clip exportiert.",
    "clip_threshold": "Videos kürzer als dieser Wert (in Sekunden) gelten als Kurzclips\nund werden als Ganzes bewertet. Längere Videos werden\nin Szenen zerlegt und die besten Szenen extrahiert.",
    "dedup_threshold": "Ab welcher Ähnlichkeit zwei Bilder als Duplikat gelten.\n0.95 = nur fast identische, 0.85 = auch ähnliche Motive.\nNiedriger = aggressivere Duplikat-Erkennung.",
    "use_clip": "CLIP ist ein KI-Modell das Bilder inhaltlich versteht.\nEs bewertet wie 'urlaubswürdig' ein Foto aussieht.\nOhne CLIP wird nur technische Qualität bewertet.\nErster Start lädt ~350 MB Modelldaten herunter.",
    "use_dedup": "Erkennt und entfernt fast identische Fotos (z.B. Serienaufnahmen).\nBehält immer das beste Foto aus einer Gruppe.",
    "use_video": "Wenn deaktiviert, werden nur Fotos verarbeitet.\nVideos im Eingabeordner werden dann ignoriert.",
    "recursive": "Wenn aktiviert, werden auch alle Unterordner durchsucht.\nDeaktivieren wenn nur der Hauptordner gescannt werden soll.",
    "dry_run": "Bewertet alle Dateien und erstellt den Report,\nkopiert aber keine Dateien in den Ausgabeordner.\nGut zum Testen der Einstellungen.",
    "positive_prompts": "Beschreibungen von Bildern die du behalten willst.\nCLIP vergleicht jedes Foto mit diesen Texten.\nAnpassen je nach Urlaub, z.B.:\n- Strandurlaub: 'beautiful beach', 'ocean sunset'\n- Städtetrip: 'historic architecture', 'city skyline'",
    "negative_prompts": "Beschreibungen von Bildern die aussortiert werden sollen.\nFotos die diesen Texten ähneln bekommen Abzüge.\nZ.B. 'blurry photo', 'dark image', 'overexposed'.",
}


class ImgPickApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("imgPick — Urlaubsfotos & Videos auswählen")
        self.geometry("750x900")
        self.minsize(650, 750)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self._build_ui()

    def _build_ui(self):
        # Scrollable frame for all controls
        self.main_frame = ctk.CTkScrollableFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Folder selection ---
        self._add_section_label("Ordner")

        self.input_var = ctk.StringVar()
        self._add_folder_row("Eingabeordner:", self.input_var, self._browse_input, "input_folder")

        self.output_var = ctk.StringVar()
        self._add_folder_row("Ausgabeordner:", self.output_var, self._browse_output, "output_folder")

        # --- Photo settings ---
        self._add_section_label("Fotos")

        self.top_percent_var = ctk.IntVar(value=30)
        self._add_slider_row("Fotos behalten (%):", self.top_percent_var, 10, 100, 1, "top_percent")

        self.tech_weight_var = ctk.DoubleVar(value=0.4)
        self._add_slider_row("Gewicht tech. Score:", self.tech_weight_var, 0.0, 1.0, 0.05, "tech_weight")

        # --- Video settings ---
        self._add_section_label("Videos")

        self.top_percent_videos_var = ctk.IntVar(value=50)
        self._add_slider_row("Kurzclips behalten (%):", self.top_percent_videos_var, 10, 100, 1, "top_percent_videos")

        self.max_clips_var = ctk.IntVar(value=2)
        self._add_slider_row("Max. Highlights/Video:", self.max_clips_var, 1, 5, 1, "max_clips")

        self.clip_threshold_var = ctk.IntVar(value=180)
        self._add_slider_row("Kurzclip-Schwelle (s):", self.clip_threshold_var, 60, 600, 10, "clip_threshold")

        # --- Dedup settings ---
        self._add_section_label("Duplikaterkennung")

        self.dedup_threshold_var = ctk.DoubleVar(value=0.95)
        self._add_slider_row("Ähnlichkeitsschwelle:", self.dedup_threshold_var, 0.80, 1.00, 0.01, "dedup_threshold")

        # --- Checkboxes ---
        self._add_section_label("Optionen")

        checkbox_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        checkbox_frame.pack(fill="x", pady=(0, 5))

        self.use_clip_var = ctk.BooleanVar(value=True)
        self._add_checkbox_row(checkbox_frame, "CLIP-Modell verwenden", self.use_clip_var, "use_clip")

        self.use_dedup_var = ctk.BooleanVar(value=True)
        self._add_checkbox_row(checkbox_frame, "Duplikat-Check", self.use_dedup_var, "use_dedup")

        self.use_video_var = ctk.BooleanVar(value=True)
        self._add_checkbox_row(checkbox_frame, "Videos verarbeiten", self.use_video_var, "use_video")

        self.recursive_var = ctk.BooleanVar(value=True)
        self._add_checkbox_row(checkbox_frame, "Rekursiv scannen", self.recursive_var, "recursive")

        self.dry_run_var = ctk.BooleanVar(value=False)
        self._add_checkbox_row(checkbox_frame, "Dry-Run (nur bewerten)", self.dry_run_var, "dry_run")

        # --- CLIP Prompts ---
        self._add_section_label("CLIP-Prompts")

        prompt_label_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        prompt_label_row.pack(fill="x")
        ctk.CTkLabel(prompt_label_row, text="Positive Prompts (ein Prompt pro Zeile):").pack(side="left")
        self._add_info_button(prompt_label_row, "positive_prompts")

        self.positive_prompts_text = ctk.CTkTextbox(self.main_frame, height=70)
        self.positive_prompts_text.pack(fill="x", pady=(0, 5))
        self.positive_prompts_text.insert("1.0", "\n".join(DEFAULT_POSITIVE_PROMPTS))

        neg_label_row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        neg_label_row.pack(fill="x")
        ctk.CTkLabel(neg_label_row, text="Negative Prompts (ein Prompt pro Zeile):").pack(side="left")
        self._add_info_button(neg_label_row, "negative_prompts")

        self.negative_prompts_text = ctk.CTkTextbox(self.main_frame, height=70)
        self.negative_prompts_text.pack(fill="x", pady=(0, 5))
        self.negative_prompts_text.insert("1.0", "\n".join(DEFAULT_NEGATIVE_PROMPTS))

        # --- Progress & Log (below scrollable frame) ---
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=False, padx=10, pady=(0, 5))

        self.progress_label = ctk.CTkLabel(bottom_frame, text="Bereit")
        self.progress_label.pack(anchor="w")

        self.progress_bar = ctk.CTkProgressBar(bottom_frame)
        self.progress_bar.pack(fill="x", pady=(2, 5))
        self.progress_bar.set(0)

        self.log_text = ctk.CTkTextbox(bottom_frame, height=150, state="disabled")
        self.log_text.pack(fill="both", expand=True, pady=(0, 5))

        # --- Start button ---
        self.start_button = ctk.CTkButton(
            bottom_frame, text="Start", command=self._on_start, height=40, font=ctk.CTkFont(size=16)
        )
        self.start_button.pack(fill="x", pady=(0, 5))

        # --- Open folder button (hidden initially) ---
        self.open_folder_button = ctk.CTkButton(
            bottom_frame, text="Ausgabeordner öffnen", command=self._open_output_folder,
            height=35, state="disabled",
        )
        self.open_folder_button.pack(fill="x")

        self._process = None

    def _add_section_label(self, text: str):
        ctk.CTkLabel(
            self.main_frame, text=text, font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(10, 5))

    def _add_info_button(self, parent, tooltip_key: str):
        """Add a small info button that shows a tooltip popup on click."""
        btn = ctk.CTkButton(
            parent, text="?", width=24, height=24,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="gray50", hover_color="gray40",
            corner_radius=12,
            command=lambda: self._show_tooltip(tooltip_key),
        )
        btn.pack(side="left", padx=(5, 0))

    def _show_tooltip(self, key: str):
        """Show a tooltip popup with info text."""
        text = TOOLTIPS.get(key, "Keine Info verfügbar.")

        popup = ctk.CTkToplevel(self)
        popup.title("Info")
        popup.geometry("400x200")
        popup.transient(self)
        popup.grab_set()

        # Center on parent
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 200) // 2
        popup.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            popup, text=text, justify="left", wraplength=360,
            font=ctk.CTkFont(size=13),
        ).pack(padx=20, pady=(15, 10), anchor="w")

        ctk.CTkButton(popup, text="OK", width=80, command=popup.destroy).pack(pady=(0, 15))

    def _add_folder_row(self, label: str, var: ctk.StringVar, browse_cmd, tooltip_key: str):
        row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=120).pack(side="left")
        self._add_info_button(row, tooltip_key)
        ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=(5, 5))
        ctk.CTkButton(row, text="...", width=40, command=browse_cmd).pack(side="right")

    def _add_slider_row(self, label: str, var, from_, to, step, tooltip_key: str):
        row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=180).pack(side="left")
        self._add_info_button(row, tooltip_key)

        value_label = ctk.CTkLabel(row, text=str(var.get()), width=50)
        value_label.pack(side="right")

        def on_change(val):
            if isinstance(var, ctk.IntVar):
                var.set(int(float(val)))
                value_label.configure(text=str(int(float(val))))
            else:
                var.set(round(float(val), 2))
                value_label.configure(text=f"{float(val):.2f}")

        slider = ctk.CTkSlider(
            row, from_=from_, to=to,
            number_of_steps=int((to - from_) / step),
            command=on_change,
        )
        slider.set(var.get())
        slider.pack(side="left", fill="x", expand=True, padx=5)

    def _add_checkbox_row(self, parent, label: str, var: ctk.BooleanVar, tooltip_key: str):
        """Add a checkbox with an info button next to it."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkCheckBox(row, text=label, variable=var).pack(side="left")
        self._add_info_button(row, tooltip_key)

    def _browse_input(self):
        path = filedialog.askdirectory(title="Eingabeordner wählen")
        if path:
            self.input_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Ausgabeordner wählen")
        if path:
            self.output_var.set(path)

    def _build_cli_args(self) -> list[str]:
        """Build CLI argument list from current GUI state."""
        args = [
            self.input_var.get(),
            self.output_var.get(),
            "--top-percent", str(self.top_percent_var.get()),
            "--top-percent-videos", str(self.top_percent_videos_var.get()),
            "--max-clips", str(self.max_clips_var.get()),
            "--short-clip-threshold", str(self.clip_threshold_var.get()),
            "--dedup-threshold", str(self.dedup_threshold_var.get()),
            "--tech-weight", str(self.tech_weight_var.get()),
        ]

        if not self.use_clip_var.get():
            args.append("--no-clip")
        if not self.use_dedup_var.get():
            args.append("--no-dedup")
        if not self.use_video_var.get():
            args.append("--no-video")
        if not self.recursive_var.get():
            args.append("--no-recursive")
        if self.dry_run_var.get():
            args.append("--dry-run")

        # Prompts
        pos = [l.strip() for l in self.positive_prompts_text.get("1.0", "end").strip().split("\n") if l.strip()]
        neg = [l.strip() for l in self.negative_prompts_text.get("1.0", "end").strip().split("\n") if l.strip()]
        if pos:
            args.extend(["--positive-prompts", ",".join(pos)])
        if neg:
            args.extend(["--negative-prompts", ",".join(neg)])

        return args

    def _on_start(self):
        """Validate inputs and launch CLI as subprocess."""
        if not self.input_var.get():
            self._show_error("Bitte Eingabeordner wählen")
            return
        if not self.output_var.get():
            self._show_error("Bitte Ausgabeordner wählen")
            return
        if not Path(self.input_var.get()).is_dir():
            self._show_error("Eingabeordner existiert nicht")
            return

        # Disable start, clear log
        self.start_button.configure(state="disabled")
        self.open_folder_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.progress_label.configure(text="Starte...")

        # Build command
        cli_args = self._build_cli_args()
        cmd = [sys.executable, str(Path(__file__).parent / "main.py")] + cli_args

        # Launch in background thread
        thread = threading.Thread(target=self._run_subprocess, args=(cmd,), daemon=True)
        thread.start()

    def _run_subprocess(self, cmd: list[str]):
        """Run CLI subprocess and parse stdout line by line."""
        self._summary_lines = []
        self._collecting_summary = False

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in self._process.stdout:
                line = line.rstrip("\n")
                # Collect summary lines after STATUS:done
                if self._collecting_summary and line.startswith("  "):
                    self._summary_lines.append(line.strip())
                if "STATUS:done:" in line:
                    self._collecting_summary = True
                self.after(0, self._handle_line, line)

            self._process.wait()
            self.after(0, self._on_done, self._process.returncode)

        except Exception as e:
            self.after(0, self._log, f"ERROR: {e}")
            self.after(0, self._on_done, 1)

    def _handle_line(self, line: str):
        """Parse a single stdout line and update UI."""
        if line.startswith("PROGRESS:"):
            parts = line.split(":")
            if len(parts) >= 4:
                try:
                    current = int(parts[2])
                    total = int(parts[3])
                    if total > 0:
                        self.progress_bar.set(current / total)
                    filename = parts[4] if len(parts) > 4 else ""
                    self.progress_label.configure(text=f"{parts[1]}: {current}/{total} {filename}")
                except ValueError:
                    pass
        elif line.startswith("STATUS:"):
            parts = line.split(":", 2)
            if len(parts) >= 3:
                self.progress_label.configure(text=parts[2])
                self._log(parts[2])
        elif line.startswith("WARN:"):
            self._log(f"⚠ {line[5:]}")
        elif line.startswith("ERROR:"):
            self._log(f"✗ {line[6:]}")
        else:
            self._log(line)

    def _log(self, text: str):
        """Append text to the log textbox."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_done(self, return_code: int):
        """Called when subprocess finishes."""
        self._process = None
        self.start_button.configure(state="normal")

        if return_code == 0:
            self.progress_bar.set(1.0)
            self.progress_label.configure(text="Fertig!")
            if not self.dry_run_var.get():
                self.open_folder_button.configure(state="normal")
            # Show summary dialog
            if self._summary_lines:
                self._show_summary(self._summary_lines)
        else:
            self.progress_label.configure(text="Fehler aufgetreten")
            self._log(f"Prozess beendet mit Code {return_code}")

    def _show_summary(self, lines: list[str]):
        """Show a summary dialog after successful processing."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Zusammenfassung")
        dialog.geometry("400x250")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Verarbeitung abgeschlossen!",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(15, 10))

        for line in lines:
            ctk.CTkLabel(dialog, text=line, font=ctk.CTkFont(size=13)).pack(anchor="w", padx=20, pady=1)

        button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(15, 10))

        if not self.dry_run_var.get():
            ctk.CTkButton(
                button_frame, text="Ordner öffnen", command=lambda: [self._open_output_folder(), dialog.destroy()]
            ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(button_frame, text="Schliessen", command=dialog.destroy).pack(side="left", expand=True, padx=5)

    def _open_output_folder(self):
        """Open output folder in system file browser."""
        from utils import open_folder
        path = Path(self.output_var.get())
        if path.is_dir():
            open_folder(path)

    def _show_error(self, msg: str):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Fehler")
        dialog.geometry("300x100")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=msg).pack(pady=20)
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack()


def main():
    app = ImgPickApp()
    app.mainloop()


if __name__ == "__main__":
    main()
