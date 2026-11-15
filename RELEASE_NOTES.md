# v2.0.2-alpha.1

New reports start in the Report Logic Matrix. Use the **Report Logic Matrix** button in the top toolbar to open it from any report section.

- Record facts and their sources, link them to findings, and link findings to recommendations. The review tab displays each finding and the evidence and recommendations connected to it.
- Choose **Open report** anytime. The matrix and the report use the same findings and recommendations. Existing drafts resume at their last report section.
- Select verified fact statements to append to Discussion. Source notes stay in the matrix. Editing a supporting fact or its sources flags linked findings for author review.
- Export a working Word copy with **File → Export confidential draft**. This option is available for incomplete reports and adds a faint **CONFIDENTIAL DRAFT** watermark. The standard report export omits the watermark and the matrix.

## Install

Run the x64 MSI, then open **Report Interview** from the Start menu. For the portable version, extract the ZIP and run `ReportInterview.exe` from the extracted folder. Windows 10 or 11 and .NET Framework 4.8 or later are required. The packages are unsigned. `SHA256SUMS.txt` contains both package checksums.

Back up `%LOCALAPPDATA%\ReportInterview\Drafts` before upgrading. If you also test with an earlier app, use a copy of the draft. Saving with an older version can discard matrix data. The app runs locally without AI, telemetry, or cloud processing.

## Review before publication

The two-verified-facts check is a review warning. The author decides which information belongs in the report. Check the Word layout and watermark appearance in your reader. The separate reviewer PDF remains a follow-up. Please use synthetic examples when reporting issues.
