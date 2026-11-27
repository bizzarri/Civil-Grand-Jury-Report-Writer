# Changelog

## 2.1.0-beta.2

- Add **Prepare PDF for publication** to remove the writer’s draft watermark from a temporary Word copy.
- Write PDF metadata as a standard XMP packet to fix PAC’s unexpected XML declaration error.

## 2.1.0-beta.1

- Prepare a tagged PDF review copy from a finished Word report.
- Carry over the report title, set the title display preference and add the PDF/UA-1 identifier.
- Fill in missing link descriptions where possible and identify pages that need review in Acrobat Pro.

## 2.0.2-alpha.1 — 2026-11-15

- Start new reports in the Report Logic Matrix and open it anytime from the top toolbar.
- Record facts and sources, link facts to findings, and review each finding alongside its recommendations.
- Append selected verified fact statements to Discussion. Changes to supporting facts flag linked findings for review.
- Export incomplete or complete working copies with a confidential draft watermark.

## 2.0.1-alpha.1 — 2026-11-09

First tagged public alpha release for testing and feedback.

- Changed the report cover wording to **County Grand Jury**.
- Added an alpha version label to the application and installer, with versions driven by `VERSION`.
- Assigned the MSI a new product identity and retained the upgrade family for existing 2.0.0 installations.
- Added checked release packages, portable ZIP and SHA-256 checksums to GitHub prereleases.
- Publish only after engine, native-control and MSI verification checks pass, using the exact tested commit.

## 2.0.0 — 2026-11-09

Initial public native Windows version.

- Guided interview based on the revised accessible CGJA report template.
- Local autosave, resumable drafts, revision conflict checks and import of browser-version JSON drafts.
- Missing required sections displayed with navigation back to the relevant step.
- Structured findings, evidence notes and author verification; recommendations linked to supporting findings.
- Word export preserving template styles and automatic independent F/R numbering, with clickable links to findings.
- Native Windows Forms interface over a Go command-line engine, without a browser or web server.
- Per-user x64 MSI installation with a Start menu shortcut, repair/removal actions and draft retention.
- Synthetic tests and package-preservation checks; no AI or cloud processing at runtime.

Known scope: narrative text only for general sections; add nested headings, tables, figures and attachments in Word. Manual response references need review. Full install/repair/uninstall, visual Word pagination and screen-reader testing remain to be completed on a suitable Windows test machine.
