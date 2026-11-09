# v2.0.1-alpha.1

First public alpha of Civil Grand Jury Report Writer, a native Windows application for guided report authoring. This prerelease is intended for testing and feedback.

## Downloads

- **MSI:** install for the current Windows user and launch Report Interview from the Start menu.
- **Portable ZIP:** extract the entire archive and run `ReportInterview.exe`; keep all companion files together.
- **SHA256SUMS.txt:** SHA-256 checksums for both packages.

Requires x64 Windows 10/11 and .NET Framework 4.8 or later. No separate Go or Python installation is needed. The binaries and installer are unsigned.

## Included

- Guided entry using the revised accessible CGJA report template.
- Missing-required-section checks, autosave, resumable drafts and import of browser-version JSON drafts.
- Structured findings, evidence references, author verification and linked recommendations.
- Word export preserving template styles and separate automatic F/R numbering, with clickable finding links.
- Updated cover wording: **County Grand Jury**.
- Native Windows interface and local Go engine. No browser, web server, AI, telemetry or cloud processing.

## Upgrading

Back up your draft folder before testing a new build. The MSI has a new product identity and is configured to upgrade the earlier 2.0.0 installation. Drafts remain at `%LOCALAPPDATA%\ReportInterview\Drafts` and are not removed by the installer. Browser-version drafts can be imported using **File → Import existing draft**. There is no automatic application updater.

## Known limits

- This is alpha software. Save backups and check your exports.
- General sections support narrative text. Add nested headings, accessible tables, images and attachments in Word after export.
- Response recipients, deadlines and manually entered F/R references require author review.
- Completeness checks and verification flags do not establish factual truth or legal sufficiency. The application never supplies missing report facts.
- Word pagination, screen-reader behavior and the exact final public PDF still require review. Template preservation is not accessibility certification.
- The source Word template retains an inherited external attached-template reference. Whether this produces a prompt in Word has not been reproduced; report any such message with its exact wording and the action that triggered it.
- Automated engine/native-control tests and MSI database/payload checks are required before publication. A full install/repair/uninstall/upgrade cycle has not been automated or independently verified on a clean Windows machine. The earlier 2.0.0 build was installed, removed and reinstalled successfully by the initial tester.

Please report problems through repository issues using synthetic examples. Do not attach confidential report drafts, interview identities or private evidence.
