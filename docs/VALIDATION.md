# Desktop build validation

Verified November 9, 2026.

- Built an x64 native Windows Forms interface and a Go command-line report engine. The desktop engine source contains no HTTP listener, browser assets or web-server implementation.
- All Go tests passed: Word package preservation, export validation, finding links, local command protocol, save/resume, revision conflict detection and safe import of existing-format drafts.
- Native control tests passed: required-section checks, finding/evidence entry, verification reset after edits, recommendation links, Unicode text, save/resume, Word export and draft import without changing the original draft.
- Native review and findings screens were captured and visually inspected. Tests used only clearly synthetic report content in separate scratch folders.
- Built the MSI with an embedded cabinet, per-user install location, HKCU installation marker, Start menu shortcut, standard file/registry/shortcut removal actions and repair/maintenance dialogs. Draft storage is outside the installer-managed application directory.
- Verified MSI table relationships and dialog/control references. Extracted the actual embedded cabinet and confirmed every packaged file matches the built application byte-for-byte.
- Windows Installer's in-process AppSearch and LaunchConditions actions passed for the actual package, including OS and .NET detection.
- Ran the native control tests again using the actual MSI-extracted executable and engine. All passed.

## Verification limits

A complete install, shortcut launch, repair and uninstall cycle could not be run in this sandbox. The administrative extraction attempt returned Windows Installer error 1601, with service access denied (0x80070005). Direct cabinet extraction, package checks and tests of the extracted application passed; the first full install on a normal Windows desktop remains to be verified.

The installer is unsigned. Windows/organization installation policy can affect whether it can be installed. It requires 64-bit Windows 10/11 and .NET Framework 4.8 or later; the MSI checks these prerequisites.

Visual Word pagination and screen-reader behavior remain unverified. Template-package preservation tests pass, but the actual report and final public PDF still require Word and accessibility review. This version retains the first version's narrative-text scope; tables, images and nested headings are added in Word after export.
