# P08E1F2 — restore the proven release and installation pipeline

Version: **0.0.16-p08e1f2**.

## Objective and invariants

Retain the P08E1 bounded native skin construction and real shoulder-handle UI. Restore the established Windows installer contract from upstream `ec8b54b`/P07F2: fixed-GUID HKCU registration, stable `current` directory, known-owned file cleanup, genuine uninstall, unrelated-data preservation and no automatic Rhino launch.

The prior local delivery added two unjustified rejection conditions: HKLM plug-in presence and an administrator token. Neither condition established an actual registration conflict. Both are removed, along with automatic machine migration, immutable-version activation journals and rollback-as-uninstall. No HKLM plug-in registration or permission is changed by this installer.

A source archive is not an install artifact. Layout validation precedes prerequisites or any context-dependent decision. It does not secretly build, download or install from source.

## Required verification and delivery

The final published source commit must produce a successful Windows Actions run. Its mandatory steps include build, Core tests, pinned Python3.9 numerical/state tests, toolbar validation, exact package identity, real CMD/Windows PowerShell5.1 installer lifecycle and tested token contexts. Isolation redirects test targets; it must not replace shipped scripts or bypass the behavior under test.

Record source SHA, workflow/run/attempt, successful required steps, artifact ID, outer archive hash, inner install ZIP hash, manifest/build-info and runtime assembly identities. The delivered user file is the checked CI install ZIP, unchanged. A locally produced ZIP or source snapshot does not satisfy this gate.

## Status vocabulary

Use VERIFIED only for executed checks, STATICALLY CHECKED for named source/API structure checks, and NOT VERIFIED for unexecuted native behavior. CI does not certify Rhino loading, the Eto window, Join, collision freedom or whole-boundary G2. Existing finite source-end/upper-boundary limitations remain disclosed by the geometry engine.

Only a separate branch is published for this correction; no merge to main is implied.
