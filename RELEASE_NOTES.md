# v2.1.0-beta.2

- **Prepare PDF for review** carries through the watermark on a confidential Word draft.
- **Prepare PDF for publication** removes Report Interview's **CONFIDENTIAL DRAFT** watermark from a temporary copy of the finished Word report. The original draft keeps its watermark and Word edits.
- Review and publication PDFs now use a standard XMP packet, which fixes PAC's unexpected XML declaration error.

Both export paths passed desktop testing with synthetic reports. Run the final Acrobat Pro and PAC checks on the exact PDF you intend to publish.

This release includes an x64 MSI, a portable ZIP, and SHA-256 checksums. The Windows packages are unsigned. PDF preparation requires desktop Microsoft Word and runs locally.
