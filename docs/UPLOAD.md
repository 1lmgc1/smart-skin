# Publish a Smart Skin patch

Do not use GitHub's browser upload for project patches. It is not the Smart Skin delivery path because it can omit directories and does not provide a reproducible base-to-target transition.

## Supported route

Each repository patch is delivered as an immutable patch kit containing:

- the expected base commit;
- the target commit or mail-formatted Git patch;
- an installer that stops if the remote `main` commit is not the expected base;
- a manifest and hashes;
- the patch-specific verification instructions.

Run the kit from Windows PowerShell or its `RUN_*.cmd` launcher. The installer clones the repository into a temporary diagnostic directory, verifies the base, applies the patch, checks required files, commits when needed, and pushes a fast-forward update to `main`.

The only interactive step may be GitHub authentication through Git Credential Manager. Never paste a token into a project file or commit it.

## After push

Open the repository's **Actions** tab and inspect the patch workflow. If it is green, download the versioned artifact and follow `FIELD_TEST.md` inside it.

If installation or CI fails, return the complete `SMARTSKIN_* FAIL` output or the complete failing Actions step log. Do not make speculative edits in GitHub's browser editor.
