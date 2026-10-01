# P04 toolbar deployment contract

P04 `0.0.8-p04` is accepted on runtime commit
`a9e854dec93cde1a0e74d2596081d863803993ae`; see `P04_CLOSURE.md`.
This file preserves the released one-button contract. The authorized
four-command follow-up is defined separately in `P04F1_TOOLBAR.md`.

## Native loading, not a startup callback

The RUI has the exact basename of the RHP and is copied into the same net48
build directory and the same managed current directory on installation.
McNeel documents same-name RUI loading at startup without first loading the
plug-in; a button command then loads the registered plug-in on demand.
Rhino 8 converts legacy toolbar groups to containers and keeps its own UI
customizations separately. Do not apply Rhino 9 direct-edit behavior here.

No code is added to SmartSkinPlugIn.OnLoad, no LoadAtStartup policy is changed,
and no UI is inserted into global settings. First-load visibility is a field
acceptance gate: if native discovery fails on Rhino 8.18, stop and diagnose it.

## Shape and durable IDs

One visible floating group at an ordinary on-screen location, one toolbar,
one button, one macro. The macro is exactly `! _SmartSurfaceBuild`.
No automatic Accept/Enter, SelNone, right-click action or menu extension.
Same IDs are reused on every build/update; future edits must preserve them.

Plug-in: `b3f42f21-1f15-45e6-9bc2-a68b0b27c877` (unchanged).

- rui: `66132d99-9d6c-512f-aea3-86d88fbf5eb0`.
- group: `ebed14d4-d943-5ac3-b2bc-74cfc7eaa798`.
- group_item: `c7770a71-565a-599e-8b5a-f78a36324ecd`.
- dock: `411a4bac-c0a5-52e7-b067-9cfbe5981dbd`.
- toolbar: `c2cb82d9-8ff1-5230-865f-af924412192d`.
- button: `e8384b80-33a1-5372-837d-b2605d097033`.
- macro: `388db0d8-f25d-5e76-849f-49b913de4229`.
- bitmap: `ccb35d2d-9542-5366-8f54-dd3da8cfbae0`.

## Images and validation

Legacy XML format v2 with inline PNG atlases: 16/24/32 pixel cells,
250 columns and one populated cell at index zero. The original project glyph
uses a surface lattice; no external font or stock image is embedded.
Test-Toolbar.ps1 validates bounded XML without DTD resolution, fixed identities,
references, exact macro, locale tooltips, PNG decoding and atlas dimensions.
It is a structural check, not a Rhino rendering test.

## Installation ownership

RUI is validated before modifying installed files/registry, copied alongside
the RHP, hash-checked at staging and final install, and recorded in install-info.
Migration removes only named Smart Skin components beside an old registered
RHP. Uninstall includes the installed RUI. The pre-existing managed installer
layout is retained; no unrelated migration or rollback redesign belongs here.
Native Rhino UI caches and layouts are not scraped or deleted. UI cleanup after
uninstall, preserving all other toolbars, remains a mandatory field check.

## Primary implementation references

- <https://developer.rhino3d.com/guides/rhinocommon/create-deploy-plugin-toolbar/>
- <https://developer.rhino3d.com/guides/general/rhino-ui-system/>
- <https://developer.rhino3d.com/guides/rhinocommon/procedurally-generate-toolbars/>
- <https://developer.rhino3d.com/en/guides/rhinocommon/localize-plugin-toolbar/>
- <https://github.com/mcneel/rpc/blob/rhino-7.x/RPC.rui>
