# Synthetic Data Only

This directory contains the self-contained webhook-remediation knowledge package.
The two HTML documents are synthetic Northstar Workspace runbooks; no personal,
production, credential, or private-URL data is permitted.

`manifest.json` is the source-of-record for the assignment submission. It pins each
asset's source ID, document version (in `notes` and HTML metadata), license,
PII-scan result, exact byte length, and SHA-256. Any document edit requires
regenerating its byte length and checksum before the manifest can pass the shared
`source_manifest_v1` contract.
