# Code signing policy

Report Interview is preparing an application to the [SignPath Foundation](https://signpath.org/). Subject to approval, the project will use free code signing provided by [SignPath.io](https://about.signpath.io/), with the certificate provided by [SignPath Foundation](https://signpath.org/). The published v2.1.0-beta.1 packages are unsigned.

- **Author and reviewer:** [Maurice Bizzarri (@bizzarri)](https://github.com/bizzarri), repository owner. Contributions from people without commit access are reviewed before merging.
- **Signing approver:** The repository owner approves each release signing request after checking the source commit and automated build results.
- **Account security:** Project policy requires team members with repository or signing access to use MFA on GitHub and SignPath.

Signing requests will use the artifacts produced from the release commit by the repository’s Windows GitHub Actions workflow. The signing configuration will restrict eligible files to approved project outputs by filename and metadata. The project will not re-sign upstream binaries. The frozen PDF helper contains PyInstaller’s upstream bootloader and bundled Python components. Its eligibility for an individual signature must be confirmed before it is included as a signing target.

## Privacy

Report Interview stores drafts locally and does not transfer report data to other networked systems during normal use. It uses desktop Microsoft Word for PDF preparation. Reviewers use Acrobat Pro separately. Those applications have their own privacy settings. See the [security and private data policy](SECURITY.md).
