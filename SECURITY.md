# Security and private report data

The application processes reports locally and has no network listener, AI integration or telemetry. Drafts are plaintext JSON in the current user's local application-data folder. OS access controls and approved storage/backup practices protect them; the application does not encrypt drafts.

Do not submit confidential report content, interview identities, evidence notes or draft files through public GitHub issues. Report ordinary bugs with a minimal synthetic example. For a vulnerability involving sensitive information, coordinate privately with the maintainer before sharing details or data.

The installer is unsigned. Verify the artifact's SHA-256 against its accompanying checksum. The application runs as the current user and is not designed to process untrusted template packages. Keep the supplied template unchanged unless you are maintaining an intentional template revision.

Review exported Word documents and the final PDF separately. The application does not certify factual accuracy, legal sufficiency, confidentiality decisions or accessibility compliance.
