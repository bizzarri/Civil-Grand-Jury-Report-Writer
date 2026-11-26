# v2.1.0-beta.1

This is the first beta of the Windows Report Writer. It adds a local PDF preparation workflow for review in Acrobat Pro.

- In **File → Prepare PDF for review**, select the finished Word report and choose where to save the review copy. Report Interview uses desktop Word to create a tagged PDF with heading bookmarks.
- The PDF uses the report's document title, displays it in Acrobat, and includes the PDF/UA-1 identifier. The app fills in missing link descriptions where it can identify the link and lists any pages that need attention.
- Open the review copy in Acrobat Pro. Run **Check for accessibility**, complete the manual checks, and run **Verify compliance with PDF/UA-1 (syntax checks only)** in Print Production → Preflight. Fix any issues and recheck the saved PDF.

PDF preparation runs on the PC and requires desktop Microsoft Word. The reviewer uses Acrobat Pro. Java and veraPDF are unnecessary for this workflow.

## Test on Windows

Use the portable x64 ZIP in a fresh folder and launch `ReportInterview.exe`. The x64 MSI is also available. Windows 10 or 11 and .NET Framework 4.8 or later are required. The packages are unsigned. Compare the download with `SHA256SUMS.txt`.

Use a dummy report with an internal recommendation-to-finding link. Verify that **Title** passes in Acrobat, that the link opens the intended finding, and that accessibility and Preflight checks run on the saved review copy. Use synthetic data when reporting issues.
