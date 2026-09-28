# How to Publish this Wiki

This `/wiki` folder is authored with **GitHub Wiki** conventions so it can be published to the repository's wiki with a simple sync. A GitHub wiki is itself a Git repository, separate from the code repo, reachable at:

```
https://github.com/<org>/<repo>.wiki.git
```

## Conventions used here

- **Flat files** with hyphenated page names (`Pipeline-Overview.md` → page "Pipeline Overview").
- **`Home.md`** — the wiki landing page.
- **`_Sidebar.md`** — custom left navigation shown on every page.
- **`_Footer.md`** — footer shown on every page.
- **Internal links** use page names without extensions, e.g. `[Pipeline Overview](Pipeline-Overview)`.

## First-time publish

1. Enable the wiki: on GitHub, go to the repo **Settings → Features → Wikis** (check it on), then open the **Wiki** tab and create/save any page once so the `.wiki.git` repo exists.
2. Clone the wiki repo next to your code checkout:

   ```bash
   git clone https://github.com/<org>/fsto-fpa-revenue-forecasting-phase-2.wiki.git
   ```

3. Copy the contents of this `/wiki` folder into the cloned wiki repo:

   ```powershell
   Copy-Item -Path .\wiki\* -Destination ..\fsto-fpa-revenue-forecasting-phase-2.wiki\ -Recurse -Force
   ```

4. Commit and push:

   ```bash
   cd ..\fsto-fpa-revenue-forecasting-phase-2.wiki
   git add .
   git commit -m "Publish pipeline + skills documentation"
   git push origin master
   ```

> GitHub wikis use the `master` branch by default.

## Keeping it in sync

Edit the Markdown under `/wiki` in this code repo (so docs are versioned with the code and reviewed via PR), then re-run the copy + push in steps 3–4 to publish.

### Optional: automate with GitHub Actions

You can add a workflow that pushes `/wiki` to the `.wiki.git` repo on every change to `main`. A common approach uses [`Andrew-Chen-Wang/github-wiki-action`](https://github.com/Andrew-Chen-Wang/github-wiki-action) or a small script with a PAT that has `repo` scope. Ask if you'd like this workflow added.
