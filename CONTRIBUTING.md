# Contributing

Open an issue describing the authoring problem and the behavior you expect, or submit a focused pull request. Use synthetic examples only. Never post actual grand jury drafts, interview identities, private evidence or credentials.

Keep the application usable offline. Preserve the distinction between author-entered facts, template guidance and completeness checks. Do not add content generation or external data transmission implicitly. AI conversation is deferred; proposals need an opt-in design, author acceptance of suggested edits and retained evidence provenance before implementation.

For code changes, run the Go tests and the native synthetic test described in the README. For installer changes, build the MSI and run `verify_msi.py`; test install, shortcut launch, repair and removal on an appropriate Windows test machine when possible. For exporter changes, retain package-part preservation checks and inspect actual Word output. State any verification you could not perform.

Use meaningful control names and keyboard navigation. Preserve the exact template’s styles, F/R numbering and heading semantics. Do not substitute a new Word template silently: template changes affect draft compatibility and require an explicit migration strategy.

Build outputs, scratch files and private drafts belong outside version control. The application source and documentation use the repository's MIT license; respect the separate template notice in `NOTICE.md`.
