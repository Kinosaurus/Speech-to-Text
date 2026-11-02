# Preserved source bundles

`recordings.zip` is the original recording bundle. The working audio library is
under `recordings/library/`; use that library for app runs and evaluation.

This folder preserves originals. It is not used as a runtime input folder.

## Transfer to another personal PC

Local transfer bundles are kept under an ignored `archives/transfer-<date>/`
directory. Code, tests, documentation and portable benchmark summaries travel
through Git. Recordings, downloaded corpora, raw benchmark outputs and model
caches remain local and are copied in separate ZIPs.

Clone or update the matching Git branch/commit first, then extract each ZIP at
the repository root so that `output/`, `recordings/` and `model-cache/` keep their
paths. Follow the bundle's `TRANSFER_README.txt` and verify its SHA-256 checksums.
Recreate the Python/WSL environments using [the setup guide](../docs/SETUPS.md);
virtual environments and compiled build directories are not portable inputs.

Historical benchmark JSON/logs retain this PC's absolute paths and original
hashes. Keep them as evidence. On a different checkout path, select the restored
audio/checkpoint paths for new runs rather than rewriting frozen artifacts.
The bundle is for transfer between the owner's PCs; keep downloaded corpus
recordings and transcripts out of public Git repositories and releases.
