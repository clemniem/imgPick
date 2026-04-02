# imgPick — Claude Code Rules

## Git-Workflow
- Jede Story aus der ROADMAP.md bekommt einen eigenen, sauberen Commit
- Commit-Message Format: `Story X.Y: <kurze Beschreibung>`
- Keine Story-übergreifenden Commits — eine Story = ein Commit
- Vor dem Commit sicherstellen, dass der Code lauffähig ist

## Projekt
- Python-Projektmanagement via `uv` (nicht pip, conda, poetry)
- Windows-Kompatibilität beachten (pathlib, kein shell=True, etc.)
- Plan steht in PLAN.md, Roadmap in ROADMAP.md — bei Änderungen aktuell halten
