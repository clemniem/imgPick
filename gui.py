#!/usr/bin/env python3
"""imgPick GUI — Konfigurationsfenster für die CLI."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from scorer import DEFAULT_POSITIVE_PROMPTS, DEFAULT_NEGATIVE_PROMPTS


class ImgPickApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("imgPick — Urlaubsfotos & Videos auswählen")
        self.geometry("700x850")
        self.minsize(600, 700)

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
        self._add_folder_row("Eingabeordner:", self.input_var, self._browse_input)

        self.output_var = ctk.StringVar()
        self._add_folder_row("Ausgabeordner:", self.output_var, self._browse_output)

        # --- Photo settings ---
        self._add_section_label("Fotos")

        self.top_percent_var = ctk.IntVar(value=30)
        self._add_slider_row("Fotos behalten (%):", self.top_percent_var, 10, 100, 1)

        self.tech_weight_var = ctk.DoubleVar(value=0.4)
        self._add_slider_row("Gewicht tech. Score:", self.tech_weight_var, 0.0, 1.0, 0.05)

        # --- Video settings ---
        self._add_section_label("Videos")

        self.top_percent_videos_var = ctk.IntVar(value=50)
        self._add_slider_row("Kurzclips behalten (%):", self.top_percent_videos_var, 10, 100, 1)

        self.max_clips_var = ctk.IntVar(value=2)
        self._add_slider_row("Max. Highlights/Video:", self.max_clips_var, 1, 5, 1)

        self.clip_threshold_var = ctk.IntVar(value=180)
        self._add_slider_row("Kurzclip-Schwelle (s):", self.clip_threshold_var, 60, 600, 10)

        # --- Dedup settings ---
        self._add_section_label("Duplikaterkennung")

        self.dedup_threshold_var = ctk.DoubleVar(value=0.95)
        self._add_slider_row("Ähnlichkeitsschwelle:", self.dedup_threshold_var, 0.80, 1.00, 0.01)

        # --- Checkboxes ---
        self._add_section_label("Optionen")

        checkbox_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        checkbox_frame.pack(fill="x", pady=(0, 5))

        self.use_clip_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(checkbox_frame, text="CLIP-Modell verwenden", variable=self.use_clip_var).pack(anchor="w", pady=2)

        self.use_dedup_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(checkbox_frame, text="Duplikat-Check", variable=self.use_dedup_var).pack(anchor="w", pady=2)

        self.use_video_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(checkbox_frame, text="Videos verarbeiten", variable=self.use_video_var).pack(anchor="w", pady=2)

        self.recursive_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(checkbox_frame, text="Rekursiv scannen", variable=self.recursive_var).pack(anchor="w", pady=2)

        self.dry_run_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(checkbox_frame, text="Dry-Run (nur bewerten)", variable=self.dry_run_var).pack(anchor="w", pady=2)

        # --- CLIP Prompts ---
        self._add_section_label("CLIP-Prompts")

        ctk.CTkLabel(self.main_frame, text="Positive Prompts (ein Prompt pro Zeile):").pack(anchor="w")
        self.positive_prompts_text = ctk.CTkTextbox(self.main_frame, height=70)
        self.positive_prompts_text.pack(fill="x", pady=(0, 5))
        self.positive_prompts_text.insert("1.0", "\n".join(DEFAULT_POSITIVE_PROMPTS))

        ctk.CTkLabel(self.main_frame, text="Negative Prompts (ein Prompt pro Zeile):").pack(anchor="w")
        self.negative_prompts_text = ctk.CTkTextbox(self.main_frame, height=70)
        self.negative_prompts_text.pack(fill="x", pady=(0, 5))
        self.negative_prompts_text.insert("1.0", "\n".join(DEFAULT_NEGATIVE_PROMPTS))

        # --- Start button ---
        self.start_button = ctk.CTkButton(
            self, text="Start", command=self._on_start, height=40, font=ctk.CTkFont(size=16)
        )
        self.start_button.pack(fill="x", padx=10, pady=(5, 10))

    def _add_section_label(self, text: str):
        ctk.CTkLabel(
            self.main_frame, text=text, font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(10, 5))

    def _add_folder_row(self, label: str, var: ctk.StringVar, browse_cmd):
        row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=120).pack(side="left")
        ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=(5, 5))
        ctk.CTkButton(row, text="...", width=40, command=browse_cmd).pack(side="right")

    def _add_slider_row(self, label: str, var, from_, to, step):
        row = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=180).pack(side="left")

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
        """Validate and start processing. Wired in Story 8.2."""
        if not self.input_var.get():
            self._show_error("Bitte Eingabeordner wählen")
            return
        if not self.output_var.get():
            self._show_error("Bitte Ausgabeordner wählen")
            return
        if not Path(self.input_var.get()).is_dir():
            self._show_error("Eingabeordner existiert nicht")
            return

        # Placeholder — subprocess launch in Story 8.2
        args = self._build_cli_args()
        print(f"Would run: python main.py {' '.join(args)}")

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
