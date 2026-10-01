# Smart Skin handoff - P04 source checkpoint

## Published baseline and local work

The verified runtime remains P03F1, version 0.0.6-p03f1, commit
`ada5c269c9d270e44952fcc297b611236c4a4782`. See `P03F1_CLOSURE.md` for the existing
CI/field evidence. Do not install a documentation-only rebuild or repeat its
closed test suite just because a session changed.

A separate documentation closure and P04 implementation are now local commits.
P04 is 0.0.8-p04, one native toolbar and button, with all production C# unchanged.
This source checkpoint is not the publication kit and contains no compiled P04.
The interrupted 0.0.7-p04/v001 and its old SHA values are historical only.

## Source of truth and delivery

Repository: <https://github.com/1lmgc1/smart-skin>.
The repository is authoritative for published source, workflows and artifacts.
A versioned full-history bundle backs up unpushed checkpoint commits. The Drive
journal stores decisions, exact checkpoint identity, location and status.
No direct file-by-file connector push, browser editor, or force-push replaces
the immutable kit route in UPLOAD.md.

## Resume procedure

1. Read AGENTS, P03F1_CLOSURE, PATCH_NOTES, P04_TOOLBAR and FIELD_TEST.
2. Restore the exact checkpoint bundle and check the base/closure/target SHA
   against its manifest. Inspect remote main; do not assume it is unchanged.
3. Perform queue P04.3: targeted diff/identity checks, PowerShell parsing and
   execution tests, publish-script harness (base, already-applied, wrong base,
   corrupted package). A Linux parse is not a Windows lifecycle execution.
4. Complete P04.4: immutable SmartSkin-P04-v002 kit and durable, read-back-checked
   copy. User runs RUN_P04.cmd only after that kit is explicitly delivered.
5. Check green build-p04 for the exact target, download and verify its artifact.
6. Managed install with Rhino closed, then focused GUI FIELD_TEST. Do not assign
   VERIFIED to P04 until visibility, button behavior and UI lifecycle pass.
7. Close P04 and sync repository/Drive documentation. No P05 before review.

## Current limitations

No P04 Windows build or Rhino execution has occurred at this checkpoint.
Native same-name RUI deployment was chosen from McNeel documentation. It avoids
load-order tricks and shared settings edits, but a missed first-load toolbar or
stale UI after uninstall must be diagnosed in the field rather than hidden by
manual import or Rhino-wide reset.
