# Frameworks (plug-ins)

The four core frameworks always run. To add a tradition (for example contractualism, Ubuntu ethics or
Confucian role ethics), publish a small package:

```python
# my_pkg/frameworks.py
from ama.frameworks import Framework
CONTRACTUALISM = Framework(
    key="contractualism", title="Contractualism",
    description="What principles could no one reasonably reject? (Scanlon)",
    prompt="""You are an expert in Scanlon's contractualism ... Return valid JSON:
{{"framework": "Contractualism", "recommended_action": "...", "conviction_score": 7.0,
  "conviction_rationale": "..."}}

DILEMMA:
{fenced}
""")
```
```toml
# pyproject.toml of my_pkg
[project.entry-points."ama.frameworks"]
contractualism = "my_pkg.frameworks:CONTRACTUALISM"
```
Install the package, then set `AMA_EXTRA_FRAMEWORKS=contractualism`. The arbiter blends the new framework
with the others.

Requirements for a framework prompt:
- It contains `{fenced}`, where the user's text arrives fenced as data.
- Literal braces are doubled (`{{ }}`).
- It returns JSON with `recommended_action`, `conviction_score` (1–10) and `conviction_rationale`.

Add a few cases to `evalset/` that show what the new framework adds.
