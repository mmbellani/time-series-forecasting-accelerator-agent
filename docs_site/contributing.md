# Contributing

Contributions from data scientists are welcome.

| Area | How to contribute |
|---|---|
| **Profiling** | Add indicators or profiles (e.g. for insurance claims data) |
| **Data preparation & scoring** | Add connectors, cleaning steps or metrics |
| **Skills** | Add a new folder in `.github/skills/` with its instructions |
| **Docs** | Edit pages in `docs_site/` — use the ✏️ icon on any page |

## Workflow

```bash
git checkout -b feature/my-change
# make changes
python -m mkdocs serve      # preview docs
git push origin feature/my-change
```

Then open a pull request into `development`.
