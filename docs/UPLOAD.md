# Publish a Smart Skin patch

GitHub is the only source of published code, workflows and build artifacts.
Google Drive stores only the project journal. Do not deliver source ZIPs,
publication kits or CI artifacts through Drive.

## Before publication

1. Re-read the live `main` commit and require the expected base.
2. Keep one architectural objective and increment the version.
3. Verify the changed-file allowlist, `git diff --check`, version identity,
   workflow syntax and the tests for the changed layer.
4. For a UI-only patch, prove production C# files are byte-for-byte unchanged.
5. Stop on a changed base, failed check or unexpected file.

## Publication

Publish one fast-forward commit to `main` through authenticated Git or the
connected GitHub Git Data API. Preserve released history and stable identities.
Never force-push, overwrite an old version, use GitHub's browser file editor or
ask the user to publish a prepared archive.

When the Git Data API is used, create blobs and one tree from the verified base,
create the commit, then update `main` with `force=false`. Read back the live
commit and its tree before treating publication as complete.

## After publication

Wait for the patch workflow on the exact published commit. Require every
expected step and the versioned artifact to succeed. Download and inspect the
artifact identity before field testing.

Install the green artifact through its normal managed installer, but do not
turn installation into a separate user test. The user reports installation
only if a real problem occurs. Run the focused Rhino test for the changed layer
one case at a time and preserve its machine output in the project journal.
