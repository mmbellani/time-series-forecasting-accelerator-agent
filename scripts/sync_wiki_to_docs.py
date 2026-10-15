"""Copy the detailed pages from wiki/ into docs_site/, fixing GitHub-Wiki links.

Usage (from the repo root):
    python scripts/sync_wiki_to_docs.py          # dry run: shows what would change
    python scripts/sync_wiki_to_docs.py --apply  # overwrite docs_site pages
Then run:  python -m mkdocs build --strict
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI, DOCS = ROOT / "wiki", ROOT / "docs_site"

MAP = {
    "Home": "index.md",
    "Getting-Started": "getting-started/index.md",
    "Pipeline-Overview": "pipeline/index.md",
    "01-Data-Preparation": "pipeline/01-data-preparation.md",
    "02-Exploratory-Data-Analysis": "pipeline/02-eda.md",
    "03-Profiling-Intermittent": "pipeline/03-profiling.md",
    "04-Clustering": "pipeline/04-clustering.md",
    "05-Feature-Engineering": "pipeline/05-feature-engineering.md",
    "06-Train-Test-Select-Tune": "pipeline/06-train-tune.md",
    "Skills-Overview": "skills/index.md",
    "Skill-clustering-dtw": "skills/clustering-dtw.md",
    "Skill-forecasting-moving-average": "skills/forecasting-moving-average.md",
    "Skill-forecasting-prophet": "skills/forecasting-prophet.md",
    "Skill-forecasting-intermittent": "skills/forecasting-intermittent.md",
    "Skill-forecasting-chronos2": "skills/forecasting-chronos2.md",
    "Skill-forecast-explainability": "skills/forecast-explainability.md",
    "Skill-error-analysis": "skills/error-analysis.md",
    "Skill-hierarchical-reconciliation": "skills/hierarchical-reconciliation.md",
}
# Skipped on purpose: Publishing (GitHub Wiki-specific), _Sidebar, _Footer.


def rel(src: str, dst: str) -> str:
    up = "../" * src.count("/")
    return up + dst


def fix_links(text: str, target: str) -> str:
    def to_md(name: str):
        name = name.strip().replace(" ", "-")
        page, _, anchor = name.partition("#")
        if page in MAP:
            return rel(target, MAP[page]) + (f"#{anchor}" if anchor else "")
        return None

    # [[Page]] or [[Label|Page]]
    def wiki_link(m):
        label, _, page = m.group(1).partition("|")
        page = page or label
        url = to_md(page)
        return f"[{label}]({url})" if url else label

    # [Label](Page) / [Label](Page.md) / [Label](Page#anchor)
    def md_link(m):
        label, href = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#|/)", href):
            return m.group(0)
        url = to_md(href.removesuffix(".md").replace(".md#", "#"))
        if url:
            return f"[{label}]({url})"
        # repo file link (e.g. ../src/...) -> absolute GitHub link
        clean = href.lstrip("./")
        return f"[{label}](https://github.com/mmbellani/time-series-forecasting-accelerator-agent/blob/main/{clean})"
    text = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", md_link, text)
    # wiki-style links last, so their output is not rewritten again
    return re.sub(r"\[\[([^\]]+)\]\]", wiki_link, text)


def main(apply: bool):
    for name, target in MAP.items():
        src = WIKI / f"{name}.md"
        if not src.exists():
            print(f"skip   {name}.md (not found)")
            continue
        out = fix_links(src.read_text(encoding="utf-8"), target)
        dst = DOCS / target
        print(("write  " if apply else "would  ") + f"{src.name} -> docs_site/{target}")
        if apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main("--apply" in sys.argv)
