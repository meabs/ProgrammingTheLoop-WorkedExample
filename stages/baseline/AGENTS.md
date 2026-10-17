# Agent guidance (storefront-api)
Source and tests are authoritative. Read the source to confirm before you rely on any doc.
Run all checks with one command: `bash scripts/test.sh`
Calls to other services go through `app/clients/`. Follow `app/clients/catalogue.py`.
The inventory service is owned by another team and is not in this workspace.
Its contract is pinned in `contracts/` (version in `contracts/PINNED`). Do not edit it.
Report the commands you ran and their real output; say what you could not verify.
