"""Disposable Rhino/Eto preview and new-only transactional commit.

Numerical PreviewState has no Rhino dependency, so its transition invariants
can be tested without pretending that the native GUI has been exercised.
All RhinoCommon/Eto calls execute synchronously on Rhino's command/UI thread.
"""

import math
import time
import json
import hashlib
from collections import namedtuple


HANDLE_EDIT_SCHEMA = "smartskin.uv-handles.v1"
ATTACHMENT_PROOF_SCHEMA = "smartskin.attachments.v2"
EDIT_PROOF_SCHEMA = "smartskin.edit-proof.v2"
SHARED_METRICS = ("position", "normal_angle_degrees", "shape_operator")
MAX_PREVIEW_PATCHES = 128
MAX_PREVIEW_GUIDES = 128
COLD_BUILD_SECONDS = 180.0
CACHED_BUILD_SECONDS = 60.0
NATIVE_SCREEN_SECONDS = 15.0
VIEWPORT_PICK_SECONDS = 0.25
UI_PUMP_INTERVAL_SECONDS = 0.025
KERNEL_TIMING_FIELDS = ("prepare_seconds", "geometry_seconds", "validation_seconds",
                        "atlas_screen_seconds", "basis_seconds", "evaluate_seconds")


def _native_owner_api():
    try:
        import _smartskin_p08e1_native_owner_separation as module
    except ModuleNotFoundError as error:
        if error.name != "_smartskin_p08e1_native_owner_separation":
            raise
        import native_owner_separation as module
    return module


def _verify_atlas_separation(result, source_model, request):
    try:
        import _smartskin_p08e1_atlas_separation as module
    except ModuleNotFoundError as error:
        if error.name != "_smartskin_p08e1_atlas_separation":
            raise
        import atlas_separation as module
    if module.verify_atlas_separation(result, source_model, request=request) is not True:
        raise RuntimeError("A fresh complete projected-atlas separation screen is required.")


_CONVERSION_ISSUER = object()
_ConversionBinding = namedtuple("_ConversionBinding", "issuer context descriptor_digest breps guides fingerprints")


def _conversion_descriptor_digest(result, limit):
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    patches = result.get("patches", result.get("surfaces", []))
    if "surfaces" in result and encode(patches) != encode(result["surfaces"]):
        raise RuntimeError("Native conversion and validated surface descriptors disagree.")
    raw = encode({"patches": patches, "guides": result.get("guides", []),
                  "edit_request": result.get("edit_request")}).encode("utf-8")
    if len(raw) > limit:
        raise RuntimeError("The exact conversion descriptor snapshot exceeds its finite memory budget.")
    return hashlib.sha256(raw).hexdigest()


def _converted_fingerprints(breps, guides, context, cancelled):
    if len(breps) > MAX_PREVIEW_PATCHES or len(guides) > MAX_PREVIEW_GUIDES:
        raise RuntimeError("Native conversion fingerprint count exceeds its budget.")
    budget = _native_owner_api()._Budget(context.limits, cancelled)
    objects = tuple(breps) + tuple(guides)
    memory = 0
    for item in objects:
        size = int(budget.call(item.MemoryEstimate))
        if size < 0:
            raise RuntimeError("A native geometry memory estimate is invalid.")
        memory += size
        if memory > context.limits.max_snapshot_bytes:
            raise RuntimeError("Native conversion fingerprint memory exceeds its budget.")
    return tuple(context.adapter.fingerprint(item, budget) for item in objects)


def _issue_checked_conversion(result, breps, guides, context, cancelled=None):
    """Only called after the production converter's exact coefficient readback."""
    if (context is None or len(breps) != len(result.get("patches", result.get("surfaces", [])))
            or len(guides) != len(result.get("guides", []))):
        raise RuntimeError("Checked native conversion does not cover every current descriptor.")
    hashes = _converted_fingerprints(breps, guides, context, cancelled)
    return _ConversionBinding(_CONVERSION_ISSUER, context,
                              _conversion_descriptor_digest(result, context.limits.max_snapshot_bytes),
                              tuple(breps), tuple(guides), hashes)


def _verify_checked_conversion(binding, result, breps, guides, context, cancelled=None):
    if (type(binding) is not _ConversionBinding or binding.issuer is not _CONVERSION_ISSUER
            or binding.context is not context or len(binding.breps) != len(breps)
            or len(binding.guides) != len(guides)
            or any(a is not b for a, b in zip(binding.breps, breps))
            or any(a is not b for a, b in zip(binding.guides, guides))):
        raise RuntimeError("A converter-issued binding for these exact native Breps and guides is required.")
    if _conversion_descriptor_digest(result, context.limits.max_snapshot_bytes) != binding.descriptor_digest:
        raise RuntimeError("The native conversion belongs to different surface, guide or request descriptors.")
    fingerprints = _converted_fingerprints(breps, guides, context, cancelled)
    if fingerprints != binding.fingerprints:
        changed = [index for index, (current, previous) in enumerate(zip(fingerprints, binding.fingerprints))
                   if current != previous]
        brep_indices = [index for index in changed if index < len(breps)]
        guide_indices = [index - len(breps) for index in changed if index >= len(breps)]
        raise RuntimeError("Converted native Brep or guide geometry changed after exact readback. "
                           "Generated Brep indices={0}; guide indices={1}.".format(brep_indices[:8], guide_indices[:8]))


class NativeScreenState:
    """Own a native context and a non-serializable receipt outside the result.

    Invalidating a request destroys this state's authority to reuse its old
    receipt, even when later restoring numerically identical geometry/values.
    """
    def __init__(self, source_model, context=None):
        self.source_model = source_model
        self.context = context
        self.receipt = None
        self.conversion = None
        self.generation = 0
        self.closed = False

    def invalidate(self):
        self.generation += 1
        self.receipt = None
        self.conversion = None

    def screen(self, breps, result, request=None, cancelled=None, guides=(), conversion=None):
        self.invalidate()
        generation = self.generation
        if self.closed or self.context is None:
            raise RuntimeError("A live captured-owner context is required before native screening.")

        def stale():
            return self.closed or self.generation != generation or (cancelled is not None and cancelled())

        ready, reason = geometry_commit_acceptance(result)
        if not ready:
            raise RuntimeError("Numerical readiness blocked: " + reason)
        ready, reason = attachment_acceptance(result, self.source_model)
        if not ready:
            raise RuntimeError("Attachment acceptance blocked: " + reason)
        if stale():
            raise RuntimeError("Native screening cancelled or superseded.")
        _verify_atlas_separation(result, self.source_model, request)
        ledger = result.get("native_contact_ledger")
        if not isinstance(ledger, dict) or ledger.get("checked") is not True:
            raise RuntimeError("A checked current native-contact ledger is required.")
        _verify_checked_conversion(conversion, result, breps, guides, self.context, stale)
        api = _native_owner_api()
        receipt = api.screen_native_owners(breps, self.context, ledger, request=request, cancelled=stale)
        if stale():
            raise RuntimeError("Native screening cancelled or superseded.")
        if api.verify_receipt(receipt, breps, self.context, ledger, request=request, cancelled=stale) is not True:
            raise RuntimeError("The native owner-separation receipt could not be verified.")
        _verify_atlas_separation(result, self.source_model, request)
        _verify_checked_conversion(conversion, result, breps, guides, self.context, stale)
        if stale():
            raise RuntimeError("Native screening cancelled or superseded.")
        self.receipt = receipt
        self.conversion = conversion
        return receipt

    def verify(self, breps, result, request=None, cancelled=None, guides=()):
        if self.closed or self.receipt is None or self.context is None:
            raise RuntimeError("A fresh native owner-separation receipt is required; restored values must be screened again.")
        generation = self.generation
        def stale():
            return self.closed or self.generation != generation or (cancelled is not None and cancelled())
        try:
            if stale():
                raise RuntimeError("Native receipt verification cancelled or superseded.")
            ready, reason = geometry_commit_acceptance(result)
            if not ready:
                raise RuntimeError("Numerical readiness blocked: " + reason)
            ready, reason = attachment_acceptance(result, self.source_model)
            if not ready:
                raise RuntimeError("Attachment acceptance blocked: " + reason)
            _verify_atlas_separation(result, self.source_model, request)
            _verify_checked_conversion(self.conversion, result, breps, guides, self.context, stale)
            if _native_owner_api().verify_receipt(self.receipt, breps, self.context,
                    result.get("native_contact_ledger"), request=request, cancelled=stale) is not True:
                raise RuntimeError("The native owner-separation receipt could not be verified.")
            if stale():
                raise RuntimeError("Native receipt verification cancelled or superseded.")
            return True
        except Exception:
            self.invalidate()
            raise

    def close(self):
        self.invalidate()
        self.closed = True
        if self.context is not None:
            _safe_cleanup(self.context.dispose)
            self.context = None


def _shared_metric_values(values, description):
    if not isinstance(values, dict) or set(values) != set(SHARED_METRICS):
        raise ValueError("Complete shared G0/G1/G2 " + description + " are required.")
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
           for value in values.values()):
        raise ValueError("Shared G0/G1/G2 " + description + " must be finite and nonnegative.")
    return {key: float(values[key]) for key in SHARED_METRICS}


def geometry_commit_acceptance(result):
    """Authorize native conversion only; a separate receipt still gates commit."""
    if not isinstance(result, dict) or any(result.get(key) is not True for key in
            ("valid", "geometry_valid")) or result.get("fatal") is not False:
        return False, "The evaluated geometry is invalid or fatal."
    if (result.get("disposition") != "native_screen_pending"
            or result.get("experimental_commit_allowed") is not False
            or ("native_screen_pending" in result and result["native_screen_pending"] is not True)):
        return False, "Only explicit native_screen_pending numerical readiness permits native conversion."
    for key in ("commit_allowed", "can_commit"):
        if key in result and result[key] is not True:
            return False, "The evaluated result explicitly disallows commit."
    if result.get("preview_only") is True or result.get("inspection_only") is True:
        return False, "The evaluated result is explicitly inspection-only."
    if "commit_disposition" in result and result["commit_disposition"] != "native_screen_pending":
        return False, "The evaluated result has a conflicting commit disposition."
    return True, "Numerical checks permit conversion; a fresh native separation receipt is still required."


def approved_upper_source_corners(source_model):
    """Derive the two allowed vertices from captured source-role provenance.

    The capture constructor independently validates this native-boundary
    evidence. A result-supplied allowlist is never consulted here. Parameters
    are exact native endpoints, not a neighborhood or a normalized guess.
    """
    if not isinstance(source_model, dict):
        raise ValueError("Captured native source-role bindings are required.")
    evidence = source_model.get("source_boundaries", {})
    if (not isinstance(evidence, dict) or evidence.get("schema") != "native-boundaries-v1"
            or evidence.get("complete") is not True or evidence.get("status") != "validated"):
        raise ValueError("Validated captured native source-role bindings are required.")
    roles = evidence.get("roles", {})
    if (set(roles) != {"side0", "side1", "upper", "lower"}
            or len(roles["side0"]) != 1 or len(roles["side1"]) != 1
            or not roles["upper"] or not roles["lower"]):
        raise ValueError("The approved upper-corner role mapping is incomplete.")
    tolerance = float(source_model.get("absolute_tolerance", 0.0))
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("Captured model tolerance is required for source-corner identity.")

    def endpoint(record, traversal_end):
        key = record.get("source_key")
        if not isinstance(key, str) or not key:
            raise ValueError("A captured source corner has no owner-edge identity.")
        domain = tuple(float(value) for value in record.get("original_curve_domain", []))
        traversal = tuple(float(value) for value in record.get("traversal_domain", []))
        if (len(domain) != 2 or len(traversal) != 2 or not all(math.isfinite(value) for value in domain + traversal)
                or not domain[0] < domain[1] or set(traversal) != set(domain)):
            raise ValueError("A source corner must retain its exact original endpoint domain.")
        parameter = traversal[traversal_end]
        native_end = 0 if parameter == domain[0] else 1
        matches = [item for item in record.get("reference_corners", [])
                   if type(item.get("edge_end")) is int and item["edge_end"] == native_end
                   and item.get("edge_parameter") == parameter]
        if len(matches) != 1:
            raise ValueError("A source corner lacks a unique captured native endpoint witness.")
        point = tuple(float(value) for value in matches[0].get("point", []))
        if len(point) != 3 or not all(math.isfinite(value) for value in point):
            raise ValueError("A source corner lacks a finite captured endpoint location.")
        return key, parameter, point

    approved = {}
    for side_role, upper_record, upper_end in (("side0", roles["upper"][0], 0),
                                              ("side1", roles["upper"][-1], 1)):
        upper_key, upper_parameter, upper_point = endpoint(upper_record, upper_end)
        side_key, side_parameter, side_point = endpoint(roles[side_role][0], 0)
        if upper_key == side_key or math.dist(upper_point, side_point) > tolerance:
            raise ValueError("The approved upper and side roles do not meet at the captured source vertex.")
        corner_id = "upper:" + side_role
        approved[corner_id] = {"corner_id": corner_id, "role": "upper_source_corner", "side_role": side_role,
                               "upper_source_key": upper_key, "upper_native_parameter": upper_parameter,
                               "side_source_key": side_key, "side_native_parameter": side_parameter}
    return approved


def attachment_acceptance(result, source_model=None):
    """The old experimental PARTIAL gate is insufficient for this prototype."""
    proof = result.get("attachment_proof", {}) if isinstance(result, dict) else {}
    if not isinstance(proof, dict):
        return False, "Full finite-boundary attachment evidence is missing or malformed; inspection only."
    if (proof.get("schema") != ATTACHMENT_PROOF_SCHEMA
            or proof.get("checked") is not True
            or proof.get("source_full_finite_boundary_pass") is not True
            or proof.get("shared_full_finite_boundary_pass") is not True):
        return False, "Full finite source and shared-boundary attachments are not verified; inspection only."
    required_fields = {"schema", "checked", "source_full_finite_boundary_pass", "shared_full_finite_boundary_pass",
                       "corner_policy", "excluded_intervals", "excluded_points"}
    if set(proof) != required_fields:
        return False, "Attachment proof must explicitly bind exceptions; result-side allowlists or generic exemptions are forbidden."
    if proof.get("corner_policy") != "hard_upper_source_corners" or proof.get("excluded_intervals") != []:
        return False, "Finite-width attachment exclusions are forbidden; only the two approved upper source-corner points may be exceptional."
    try:
        approved = approved_upper_source_corners(source_model)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        return False, str(error)
    points = proof.get("excluded_points")
    if not isinstance(points, list) or len(points) > 2:
        return False, "Corner exceptions must be a bounded explicit list of approved source vertices."
    seen = set()
    for point in points:
        if not isinstance(point, dict):
            return False, "A corner exception lacks its captured native source identity."
        if any(type(point.get(key)) not in (int, float) or not math.isfinite(point[key])
               for key in ("upper_native_parameter", "side_native_parameter")):
            return False, "A corner exception must name exact finite native endpoint parameters."
        identifier = point.get("corner_id")
        if not isinstance(identifier, str) or identifier in seen or identifier not in approved or point != approved[identifier]:
            return False, "A corner exception is not exactly an approved upper source vertex; other endpoints and internal junctions are forbidden."
        seen.add(identifier)
    return True, "Full finite source and shared-boundary attachment checks passed for this result."


def verify_edit_result(request, result):
    """Recheck the exact request and invariant proof, including at commit."""
    if (not isinstance(request, dict) or request.get("schema") != HANDLE_EDIT_SCHEMA
            or set(request) != {"schema", "basis_id", "revision", "values"}
            or not isinstance(request.get("basis_id"), str) or not request["basis_id"]
            or type(request.get("revision")) is not int or request["revision"] < 0
            or not isinstance(request.get("values"), dict) or not 1 <= len(request["values"]) <= 128):
        raise ValueError("The per-handle edit request is missing or malformed.")
    if (not isinstance(result, dict) or any(not isinstance(key, str) or not key
            or type(value) not in (int, float) or not math.isfinite(value)
            for key, value in request["values"].items())):
        raise ValueError("The per-handle edit request must contain finite scalar handle values.")
    try:
        expected = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False)
        actual = json.dumps(result.get("edit_request"), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("The per-handle result does not have an exact finite request echo.") from None
    if actual != expected:
        raise ValueError("The geometry result does not match the requested per-handle edit.")
    proof = result.get("edit_proof", {})
    if (not isinstance(proof, dict) or proof.get("schema") != EDIT_PROOF_SCHEMA
            or any(proof.get(key) is not True for key in
                   ("checked", "source_2jets_unchanged", "shared_2jets_compatible"))):
        raise ValueError("Fixed-source preservation and post-edit shared two-jet compatibility was not verified for this edit.")
    residuals = _shared_metric_values(proof.get("shared_residuals"), "residuals")
    tolerances = _shared_metric_values(proof.get("shared_tolerances"), "tolerances")
    if any(residuals[key] > tolerances[key] for key in SHARED_METRICS):
        raise ValueError("An edited shared trace exceeds the required G0/G1/G2 compatibility tolerance.")
    if proof.get("symmetry_checked") is not True or proof.get("symmetry_compatible") is not True:
        raise ValueError("Fresh post-edit geometric symmetry was not verified.")
    symmetry_residual, symmetry_tolerance = proof.get("symmetry_residual"), proof.get("symmetry_tolerance")
    if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
           for value in (symmetry_residual, symmetry_tolerance)):
        raise ValueError("Geometric symmetry requires a finite residual and tolerance.")
    if symmetry_residual > symmetry_tolerance:
        raise ValueError("The edited geometry exceeds the required symmetry tolerance.")
    try:
        positions_request = json.dumps(result.get("handle_positions_request"), sort_keys=True,
                                       separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("Actual handle positions are not bound to a finite edit request.") from None
    if positions_request != expected:
        raise ValueError("Actual handle positions are missing or stale for this edit request.")
    positions = result.get("handle_positions")
    if not isinstance(positions, dict) or set(positions) != set(request["values"]):
        raise ValueError("The evaluator must return actual positions for every handle in this request.")
    for point in positions.values():
        if (not isinstance(point, (list, tuple)) or len(point) != 3
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)):
            raise ValueError("Evaluated handle positions must be finite three-dimensional points.")
    return {key: tuple(float(value) for value in point) for key, point in positions.items()}


class HandleEditToken(namedtuple("HandleEditTokenBase", "revision basis_id values")):
    """Immutable values captured for one evaluation; payload is a fresh copy."""
    __slots__ = ()

    @property
    def payload(self):
        return {"schema": HANDLE_EDIT_SCHEMA, "basis_id": self.basis_id,
                "revision": self.revision, "values": dict(self.values)}


class HandleEditState:
    """Selected-handle controller, never an alias for the old global factor.

    A catalog is an engine capability declaration, not mathematical proof.
    Every evaluated edit requires fixed original-source two-jets and compatible
    post-edit shared traces. New shared traces may move; they are not frozen.
    """

    def __init__(self, catalog=None, evaluator_available=False):
        self.enabled = False
        self.reason = "Local U/V handle editing is unavailable: the kernel has no verified constrained edit basis."
        self.basis_id = ""
        self.handles = {}
        self.values = {}
        self.last_valid_values = None
        self.last_valid_positions = None
        self.current_request_revision = None
        self.last_valid_revision = None
        self.shared_tolerances = None
        self.symmetry_tolerance = None
        self.selected_guide = None
        self.selected_handle = None
        if not catalog or not catalog.get("enabled", False):
            if catalog and catalog.get("reason"):
                self.reason = str(catalog["reason"])
            return
        if (catalog.get("schema") != HANDLE_EDIT_SCHEMA or not evaluator_available
                or catalog.get("preserves_attachment_order") != 2):
            raise ValueError("The per-handle kernel capability is incomplete or unsupported.")
        basis_id = catalog.get("basis_id")
        if not isinstance(basis_id, str) or not basis_id or len(basis_id) > 128:
            raise ValueError("A bounded stable handle-basis identity is required.")
        handles = catalog.get("handles", [])
        if not 1 <= len(handles) <= 128:
            raise ValueError("The handle catalog must contain one to 128 generated handles.")
        self.shared_tolerances = _shared_metric_values(catalog.get("shared_tolerances"), "catalog tolerances")
        self.symmetry_tolerance = catalog.get("symmetry_tolerance")
        if (type(self.symmetry_tolerance) not in (int, float) or not math.isfinite(self.symmetry_tolerance)
                or self.symmetry_tolerance < 0):
            raise ValueError("The prepared catalog must define a fixed finite geometric symmetry tolerance.")
        for source in handles:
            item = dict(source)
            identifier, guide = item.get("id"), item.get("guide_id")
            if (not isinstance(identifier, str) or not identifier or len(identifier) > 128
                    or identifier in self.handles or not isinstance(guide, str) or not guide
                    or len(guide) > 128 or item.get("varying_axis") not in ("u", "v")):
                raise ValueError("Handle and guide identities must be unique, bounded, and explicit.")
            for key in ("minimum", "maximum", "neutral"):
                item[key] = float(item[key])
                if not math.isfinite(item[key]):
                    raise ValueError("Handle ranges must be finite.")
            if not item["minimum"] <= item["neutral"] <= item["maximum"] or item["minimum"] == item["maximum"]:
                raise ValueError("The neutral handle value must lie within a nonempty range.")
            for key in ("anchor", "position", "direction"):
                item[key] = tuple(float(value) for value in item[key])
                if len(item[key]) != 3 or not all(math.isfinite(value) for value in item[key]):
                    raise ValueError("Handle display geometry must have finite three-dimensional coordinates.")
            if sum(value * value for value in item["direction"]) <= 1e-24:
                raise ValueError("A handle must have a nonzero local movement direction.")
            self.handles[identifier] = item
            self.values[identifier] = item["neutral"]
        for identifier, item in self.handles.items():
            partner_id = item.get("mirror_handle_id")
            if not isinstance(partner_id, str) or partner_id not in self.handles:
                raise ValueError("Every handle must name its mirrored partner or itself on the symmetry axis.")
            partner = self.handles[partner_id]
            if partner.get("mirror_handle_id") != identifier:
                raise ValueError("Mirrored handle links must be reciprocal.")
            if any(item.get(key) != partner.get(key) for key in
                   ("minimum", "maximum", "neutral", "units", "varying_axis")):
                raise ValueError("Mirrored handle pairs must have matching ranges, units and parameter direction.")
        self.basis_id = basis_id
        self.enabled = True
        self.reason = "Select a U/V handle. Its mirrored partner changes with it; other handle values are retained."

    def select_guide(self, guide_id):
        self.selected_guide = guide_id
        matches = [key for key, item in self.handles.items() if item["guide_id"] == guide_id]
        if self.selected_handle not in matches:
            self.selected_handle = matches[0] if matches else None
        return matches

    def select_handle(self, identifier):
        if identifier not in self.handles or self.handles[identifier]["guide_id"] != self.selected_guide:
            raise ValueError("The handle does not belong to the selected U/V guide.")
        self.selected_handle = identifier

    def set_selected_value(self, value):
        if not self.enabled or self.selected_handle is None:
            raise ValueError(self.reason)
        item = self.handles[self.selected_handle]
        partner = self.handles[item["mirror_handle_id"]]
        if item.get("locked_reason") or partner.get("locked_reason"):
            raise ValueError(str(item.get("locked_reason") or partner["locked_reason"]))
        value = float(value)
        if not math.isfinite(value) or not item["minimum"] <= value <= item["maximum"]:
            raise ValueError("The selected handle value is outside its supported range.")
        next_values = dict(self.values)
        next_values[self.selected_handle] = value
        next_values[item["mirror_handle_id"]] = value
        self.values = next_values
        # Even a repeated value is a newer request. It must not inherit the
        # displayed token's authorization while native Add events are running.
        self.current_request_revision = None

    def validate_values(self, values):
        if set(values) != set(self.handles):
            raise ValueError("The request must contain every catalog handle exactly once.")
        for identifier, item in self.handles.items():
            value = values[identifier]
            if (type(value) not in (int, float) or not math.isfinite(value)
                    or not item["minimum"] <= value <= item["maximum"]):
                raise ValueError("A requested handle is outside its finite supported range.")
            if value != values[item["mirror_handle_id"]]:
                raise ValueError("Mirrored handle values must be equal; asymmetric editing is unavailable.")
            if item.get("locked_reason") and value != item["neutral"]:
                raise ValueError(str(item["locked_reason"]))

    def snapshot(self, revision):
        if not self.enabled:
            raise ValueError(self.reason)
        self.validate_values(self.values)
        self.current_request_revision = int(revision)
        return HandleEditToken(self.current_request_revision, self.basis_id, tuple(sorted(self.values.items())))

    def verify_result(self, token, result):
        if token.basis_id != self.basis_id:
            raise ValueError("The edit request belongs to another prepared basis.")
        self.validate_values(dict(token.values))
        positions = verify_edit_result(token.payload, result)
        if result["edit_proof"]["shared_tolerances"] != self.shared_tolerances:
            raise ValueError("An edit result changed the prepared shared G0/G1/G2 tolerances.")
        if result["edit_proof"]["symmetry_tolerance"] != self.symmetry_tolerance:
            raise ValueError("An edit result changed the prepared geometric symmetry tolerance.")
        return positions

    def accept(self, token, result):
        positions = self.verify_result(token, result)
        if token.revision != self.current_request_revision or dict(token.values) != self.values:
            raise ValueError("A newer handle request superseded this evaluated result.")
        self.last_valid_values = dict(token.values)
        self.last_valid_positions = positions
        self.last_valid_revision = token.revision

    def verify_displayed_result(self, token, result):
        positions = self.verify_result(token, result)
        if (positions != self.last_valid_positions or dict(token.values) != self.last_valid_values
                or dict(token.values) != self.values or token.revision != self.current_request_revision):
            raise ValueError("The handle positions no longer match the displayed accepted preview.")

    def restore_last_valid(self):
        if self.last_valid_values is None:
            return False
        self.values = dict(self.last_valid_values)
        self.current_request_revision = self.last_valid_revision
        return True

    def display_handle(self):
        if self.selected_handle is None or self.last_valid_positions is None:
            return None
        item = self.handles[self.selected_handle]
        # Display the handle belonging to the visible accepted preview, not a
        # newer slider request whose geometry is still being evaluated.
        return item["anchor"], self.last_valid_positions[self.selected_handle]


def group_uv_guides(descriptors):
    """Group the existing exact pieces; U/V denotes the varying parameter."""
    groups = {}
    for index, item in enumerate(descriptors):
        kind = item.get("kind")
        if kind == "profile":
            number = int(item["piece"])
            identifier, axis, label = "profile:" + str(number), "v", "V profile " + str(number + 1)
        elif kind in ("row_collar", "row_middle"):
            number = int(item["row"])
            identifier, axis, label = "row:" + str(number), "u", "U row " + str(number + 1)
        elif item.get("guide_id") and item.get("varying_axis") in ("u", "v"):
            identifier, axis = str(item["guide_id"]), item["varying_axis"]
            label = str(item.get("label", identifier))
        else:
            continue
        if identifier not in groups:
            groups[identifier] = {"id": identifier, "varying_axis": axis, "label": label, "indices": []}
        groups[identifier]["indices"].append(index)
    return sorted(groups.values(), key=lambda item: (item["varying_axis"], item["id"]))


def evaluate_preview_request(prepared, edits, revision, cancelled):
    """A selected edit has its own API; failure cannot become a global edit."""
    token = edits.snapshot(revision) if edits.enabled else None
    if token is not None:
        result = prepared.evaluate_edit(token.payload, cancelled=cancelled)
        edits.verify_result(token, result)
        return result, token
    return prepared.evaluate(1.0, cancelled=cancelled), None


def evaluate_preview_cycle(prepared, edits, revision, cancelled, source_model, stage=None, timing=None):
    """Discover a lazily built handle basis after its checked baseline exists.

    A catalog captured before the first evaluate() may be intentionally empty.
    Never expose that later catalog over an unbound baseline: evaluate its real
    neutral request so positions, geometry and edit proof share one request.
    """
    if edits is not None and edits.enabled:
        result, token = evaluate_preview_request(prepared, edits, revision, cancelled)
        return result, token, edits
    if stage is not None:
        stage("BASELINE GEOMETRY AND CHECKS")
    result = prepared.evaluate(1.0, cancelled=cancelled)
    if timing is not None:
        timing("baseline", result.get("timing", {}))
    for check in (geometry_commit_acceptance(result), attachment_acceptance(result, source_model)):
        if not check[0]:
            raise ValueError(check[1] + " " + str(result.get("reason", "")))
    _verify_atlas_separation(result, source_model, None)
    if cancelled():
        raise RuntimeError("Preview preparation was cancelled or superseded.")
    provider = getattr(prepared, "handle_edit_catalog", None)
    refreshed = HandleEditState(provider() if callable(provider) else None,
                                callable(getattr(prepared, "evaluate_edit", None)))
    if not refreshed.enabled:
        raise ValueError("Selected U/V handles are unavailable after baseline validation: " + refreshed.reason)
    if stage is not None:
        stage("NEUTRAL U/V HANDLE CHECKS")
    started = time.monotonic()
    initial_neutral = getattr(prepared, "evaluate_initial_neutral", None)
    if callable(initial_neutral):
        token = refreshed.snapshot(revision)
        result = initial_neutral(token.payload, cancelled=cancelled)
        refreshed.verify_result(token, result)
    else:
        result, token = evaluate_preview_request(prepared, refreshed, revision, cancelled)
    if timing is not None:
        timing("neutral", {"evaluate_seconds": time.monotonic() - started})
    return result, token, refreshed


def kernel_timing_diagnostic(phase, metrics):
    """Only bounded scalar timings enter history; never model data or paths."""
    if phase not in ("baseline", "neutral") or not isinstance(metrics, dict):
        return None
    fields = ["phase=" + phase]
    for name in KERNEL_TIMING_FIELDS:
        value = metrics.get(name)
        if type(value) in (int, float) and 0 <= value <= 1e9 and math.isfinite(value):
            fields.append("{0}={1:.6g}".format(name, value))
    return "SMARTSKIN_P08E1_TIMING | " + " | ".join(fields) if len(fields) > 1 else None


def preview_command_prompt(state, editable=False, native_ready=False):
    if state.building or state.pending:
        return "Smart Skin is building and checking; controls stay disabled until READY; Esc cancels"
    if state.error:
        return "Smart Skin BLOCKED: see the window and command history for the failed stage; Esc closes"
    if state.can_accept:
        if not native_ready:
            return "Smart Skin restored preview: Enter rechecks native separation before acceptance; controls disabled; Esc cancels"
        return ("Smart Skin READY: click a preview guide/handle or select it in the window; adjust its slider; "
                "Enter/Space/right-click adds; Esc cancels" if editable else
                "Smart Skin baseline READY; local handles unavailable; Enter/Space/right-click adds; Esc cancels")
    return "Smart Skin has no acceptable preview; Esc closes"


def get_preview_decision(decision, state, native_screen):
    """A getter may pump a timer rebuild before returning an old Enter click."""
    before = (state.revision, native_screen.generation)
    result = decision.Get()
    return result, before == (state.revision, native_screen.generation)


def pick_native_preview(picker, guides, groups, handle_points, cancelled):
    """Hit-test only displayed exact curves/markers; never document objects.

    Rhino's native pick aperture and clipping planes decide hits. Point markers
    take precedence over their incident guides; cursor distance then camera
    depth resolves multiple hits. No partial scan may select a winner.
    """
    if len(guides) > MAX_PREVIEW_GUIDES or len(handle_points) > 128 or len(groups) > MAX_PREVIEW_GUIDES:
        raise ValueError("Viewport picking exceeds its bounded preview count.")
    curve_groups = {}
    for group in groups:
        for index in group["indices"]:
            if type(index) is not int or not 0 <= index < len(guides) or index in curve_groups:
                raise ValueError("The displayed guide-to-curve mapping is invalid.")
            curve_groups[index] = group["id"]
    candidates = []
    def collect(kind, identifier, geometry, curve=False):
        if cancelled():
            raise RuntimeError("Viewport picking was cancelled, superseded or exceeded its time budget.")
        values = picker.PickFrustumTest(geometry)
        if len(values) != (4 if curve else 3):
            raise RuntimeError("The native viewport pick returned an unsupported result.")
        if values[0]:
            if curve:
                parameter = float(values[1])
                if not math.isfinite(parameter) or not geometry.Domain.T0 <= parameter <= geometry.Domain.T1:
                    raise RuntimeError("The native viewport pick returned a parameter outside the exact guide domain.")
            depth, distance = float(values[-2]), float(values[-1])
            if not math.isfinite(depth) or not math.isfinite(distance) or distance < 0:
                raise RuntimeError("The native viewport pick returned an invalid distance or depth.")
            candidates.append((0 if kind == "handle" else 1, distance, -depth, identifier, kind))
    for identifier, point in handle_points.items():
        collect("handle", identifier, point)
    for index, identifier in curve_groups.items():
        collect("guide", identifier, guides[index], curve=True)
    if cancelled():
        raise RuntimeError("Viewport picking was cancelled, superseded or exceeded its time budget.")
    if not candidates:
        return None
    winner = min(candidates)
    return winner[4], winner[3]


class PreviewState:
    """Never accept an old preview under a newer visible handle setting."""

    def __init__(self):
        self.requested_h = 1.0
        self.valid_h = None
        self.revision = 0
        self.valid_revision = -1
        self.pending = True
        self.building = False
        self.cancelled = False
        self.closed = False
        self.error = None

    def request(self, handle):
        value = float(handle)
        if not math.isfinite(value) or value < 0.5 or value > 1.5:
            raise ValueError("Shoulder handle factor must be between 0.50 and 1.50.")
        if self.closed or self.cancelled:
            return
        self.requested_h = value
        self.revision += 1
        self.pending = True
        self.error = None

    def begin(self):
        if self.closed or self.cancelled or self.building or not self.pending:
            return None
        self.building = True
        self.pending = False
        return self.revision, self.requested_h

    def complete(self, token, successful, reason=None):
        self.building = False
        if self.closed or self.cancelled:
            return False
        if token[0] != self.revision:
            self.pending = True
            return False
        if successful:
            self.valid_revision, self.valid_h = token
            self.error = None
            return True
        self.error = reason or "The current setting did not produce valid geometry."
        return False

    def superseded(self, token):
        """Abort obsolete numerical work at its next cooperative checkpoint."""
        return self.closed or self.cancelled or token[0] != self.revision

    @property
    def can_accept(self):
        return (not self.closed and not self.cancelled and not self.building
                and not self.pending and self.error is None
                and self.valid_revision == self.revision
                and self.valid_h == self.requested_h)

    def cancel(self):
        self.cancelled = True
        self.pending = False

    def restore_last_valid(self):
        if self.valid_h is None or self.closed or self.cancelled or self.building:
            return False
        self.revision += 1
        self.requested_h = self.valid_h
        self.valid_revision = self.revision
        self.pending = False
        self.error = None
        return True

    def close(self):
        self.closed = True
        self.pending = False


def _homogeneous(descriptor):
    for name in ("homogeneous_cp", "homogeneousCP", "control_points_h"):
        if name in descriptor:
            return descriptor[name]
    raise ValueError("Kernel descriptor omitted homogeneous control points.")


def _rhino_knots(values, degree, count):
    values = [float(value) for value in values]
    if len(values) != count + degree + 1:
        raise ValueError("Kernel knot vector has the wrong length.")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Kernel knot vector is not finite.")
    if any(a > b for a, b in zip(values, values[1:])):
        raise ValueError("Kernel knots are not monotonic.")
    # openNURBS stores two fewer exterior knots than the standard convention.
    return values[1:-1]


def _control_point(rg, value):
    if len(value) != 4 or not all(math.isfinite(float(x)) for x in value):
        raise ValueError("Kernel returned non-finite homogeneous control points.")
    w = float(value[3])
    if w <= 0.0:
        raise ValueError("Kernel returned a non-positive rational weight.")
    xyz = [float(value[index]) / w for index in range(3)]
    if not all(math.isfinite(component) for component in xyz):
        raise ValueError("Kernel rational control point is outside finite native range.")
    # Pass the original homogeneous binary64 coefficients directly. A
    # divide-then-multiply Euclidean round trip can change one ULP and spoil
    # exact collapsed-pole identities. RhinoCommon's four-double overload is
    # homogeneous (available since Rhino5); xyz above is only a range check.
    return rg.ControlPoint(float(value[0]), float(value[1]), float(value[2]), w)


def _assert_native_control_point(control, expected):
    # Current RhinoCommon exposes homogeneous X/Y/Z and Weight directly.
    # Do not reconstruct them through the Euclidean Location property.
    actual = (float(control.X), float(control.Y), float(control.Z), float(control.Weight))
    if actual != tuple(float(x) for x in expected):
        raise ValueError("Native NURBS conversion changed a homogeneous control coefficient.")


def _dispose_all(items):
    for item in items:
        try:
            item.Dispose()
        except Exception:
            pass


def _safe_cleanup(action):
    """A failed/disposed widget must not prevent the remaining cleanup steps."""
    try:
        action()
        return True
    except Exception:
        return False


def _apply_brep_orientation(brep, descriptor):
    reversed_orientation = descriptor.get("orientation_reversed", False)
    if type(reversed_orientation) is not bool:
        raise ValueError("Surface orientation metadata must be an explicit Boolean.")
    if reversed_orientation:
        # Keep all U/V coordinates and source-role bindings unchanged.
        brep.Flip()
    if not brep.IsValid:
        raise ValueError("The oriented native preview Brep is invalid.")


def make_native_geometry(output, rg, cancelled, native_context):
    """Convert exact rational descriptors. Never fit sampled/polyline guides."""
    breps, guides = [], []
    try:
        patches = output.get("patches", output.get("surfaces", []))
        guide_specs = output.get("guides", [])
        if not patches or len(patches) > MAX_PREVIEW_PATCHES or len(guide_specs) > MAX_PREVIEW_GUIDES:
            raise ValueError("Kernel output exceeded the bounded preview contract.")
        for patch in patches:
            if cancelled():
                raise RuntimeError("Preview cancelled.")
            cp = _homogeneous(patch)
            nu, nv = len(cp), len(cp[0])
            du, dv = int(patch["degree_u"]), int(patch["degree_v"])
            if not 1 <= du <= 64 or not 1 <= dv <= 64 or nu * nv > 16384:
                raise ValueError("Kernel surface exceeds native preview limits.")
            if any(len(row) != nv for row in cp):
                raise ValueError("Kernel surface control net is not rectangular.")
            ku = _rhino_knots(patch["knots_u"], du, nu)
            kv = _rhino_knots(patch["knots_v"], dv, nv)
            surface = rg.NurbsSurface.Create(3, True, du + 1, dv + 1, nu, nv)
            if surface is None:
                raise RuntimeError("Rhino could not allocate a preview surface.")
            try:
                for i, knot in enumerate(ku):
                    surface.KnotsU[i] = knot
                for j, knot in enumerate(kv):
                    surface.KnotsV[j] = knot
                for i in range(nu):
                    if i % 8 == 0 and cancelled():
                        raise RuntimeError("Preview cancelled.")
                    for j in range(nv):
                        if not surface.Points.SetControlPoint(i, j, _control_point(rg, cp[i][j])):
                            raise ValueError("Rhino rejected a surface control point.")
                        _assert_native_control_point(surface.Points.GetControlPoint(i, j), cp[i][j])
                if not surface.IsValid:
                    raise ValueError("Rhino native NURBS surface validation failed.")
                brep = surface.ToBrep()
                if brep is None or not brep.IsValid:
                    if brep is not None:
                        brep.Dispose()
                    raise ValueError("Rhino native preview Brep validation failed.")
                try:
                    _apply_brep_orientation(brep, patch)
                except Exception:
                    brep.Dispose()
                    raise
                breps.append(brep)
            finally:
                surface.Dispose()
        for descriptor in guide_specs:
            if cancelled():
                raise RuntimeError("Preview cancelled.")
            if not isinstance(descriptor, dict):
                raise ValueError("Kernel guides must be exact NURBS descriptors.")
            cp = _homogeneous(descriptor)
            degree = int(descriptor["degree"])
            if not 1 <= degree <= 64 or len(cp) > 4096:
                raise ValueError("Kernel guide exceeds native preview limits.")
            knots = _rhino_knots(descriptor["knots"], degree, len(cp))
            curve = rg.NurbsCurve(3, True, degree + 1, len(cp))
            try:
                for i, knot in enumerate(knots):
                    curve.Knots[i] = knot
                for i, point in enumerate(cp):
                    _control_point(rg, point)  # Shared finite/positive-weight validation.
                    if not curve.Points.SetPoint(i, *[float(x) for x in point]):
                        raise ValueError("Rhino rejected a guide control point.")
                    _assert_native_control_point(curve.Points[i], point)
                if not curve.IsValid:
                    raise ValueError("Rhino native guide validation failed.")
                guides.append(curve)
            except Exception:
                curve.Dispose()
                raise
        binding = _issue_checked_conversion(output, breps, guides, native_context, cancelled)
        return breps, guides, binding
    except Exception:
        _dispose_all(breps + guides)
        raise


def _rollback_new_additions(doc, additions):
    complete = True
    for identifier in reversed(additions):
        try:
            obj = doc.Objects.FindId(identifier)
            if obj is not None and not obj.IsDeleted:
                complete = bool(doc.Objects.Delete(identifier, True)) and complete
        except Exception:
            complete = False
    for identifier in additions:
        try:
            obj = doc.Objects.FindId(identifier)
            complete = (obj is None or obj.IsDeleted) and complete
        except Exception:
            complete = False
    return complete


def _bounded_commit_items(items, limit, label):
    """Bound direct helper inputs too, and freeze them against Add callbacks."""
    result = []
    for item in items:
        if len(result) >= limit:
            raise RuntimeError("The direct commit exceeds its finite " + label + " count budget.")
        result.append(item)
    return tuple(result)


def commit_new_geometry(doc, capture, breps, guides, handle, rhino, system,
                        attachment_result=None, edit_request=None, edit_state=None, cancelled=None, native_screen=None):
    """One undo scope, rollback only IDs created here; originals are untouched."""
    breps = _bounded_commit_items(breps, MAX_PREVIEW_PATCHES, "skin")
    guides = _bounded_commit_items(guides, MAX_PREVIEW_GUIDES, "guide")
    if cancelled is not None and not callable(cancelled):
        raise ValueError("The commit cancellation callback must be callable.")

    def require_not_cancelled():
        if cancelled is not None and cancelled():
            if isinstance(native_screen, NativeScreenState):
                native_screen.invalidate()
            raise RuntimeError("Commit cancelled; no result was accepted.")

    def _require_evidence_unchecked():
        ready, reason = attachment_acceptance(attachment_result, getattr(capture, "model", None))
        if not ready:
            raise RuntimeError("Attachment acceptance blocked: " + reason)
        ready, reason = geometry_commit_acceptance(attachment_result)
        if not ready:
            raise RuntimeError("Geometry acceptance blocked: " + reason)
        if edit_request is not None:
            try:
                verify_edit_result(edit_request, attachment_result)
                if edit_state is None:
                    raise ValueError("The prepared mirrored handle catalog and displayed positions are required at commit.")
                token = HandleEditToken(edit_request["revision"], edit_request["basis_id"],
                                        tuple(sorted(edit_request["values"].items())))
                edit_state.verify_displayed_result(token, attachment_result)
            except ValueError as error:
                raise RuntimeError("Selected-handle acceptance blocked: " + str(error)) from None
        elif attachment_result.get("edit_request") is not None:
            raise RuntimeError("An edited result requires its exact selected-handle request at commit.")
        if not isinstance(native_screen, NativeScreenState) or native_screen.source_model is not capture.model:
            raise RuntimeError("A separately held native separation receipt for this captured input is required.")
        native_screen.verify(breps, attachment_result, request=edit_request, cancelled=cancelled, guides=guides)

    def require_evidence():
        try:
            _require_evidence_unchecked()
        except Exception:
            if isinstance(native_screen, NativeScreenState):
                native_screen.invalidate()
            raise

    require_not_cancelled()
    ok, reason = capture.verify_sources(doc)
    if not ok:
        if isinstance(native_screen, NativeScreenState):
            native_screen.invalidate()
        raise RuntimeError("Sources changed during preview: " + reason)
    require_evidence()
    if not breps:
        raise RuntimeError("There is no valid current preview to add.")
    if not doc.UndoRecordingEnabled:
        raise RuntimeError("Undo recording is disabled; no result was added.")
    owns_record = not doc.UndoRecordingIsActive
    serial = (doc.BeginUndoRecord("Smart Skin experimental FULLCYCLE") if owns_record
              else doc.CurrentUndoRecordSerialNumber)
    if serial == 0:
        raise RuntimeError("A single undo record could not be established.")
    additions = []
    try:
        for kind, objects in (("skin", breps), ("guide", guides)):
            for index, geometry in enumerate(objects):
                require_not_cancelled()
                # This is mandatory even for a direct helper call. Recheck
                # before every native Add operation; there is no legacy
                # no-proof / experimental-partial transaction fallback.
                require_evidence()
                if not geometry.IsValid:
                    raise RuntimeError("A native result became invalid before commit.")
                attributes = rhino.DocObjects.ObjectAttributes()
                try:
                    attributes.Name = "Smart Skin {0} {1}".format(kind, index + 1)
                    attributes.SetUserString("SmartSkin.Route", "FULLCYCLE_SELECTED_UV_PROTOTYPE")
                    attributes.SetUserString("SmartSkin.ShoulderHandleFactor", "{:.2f}".format(handle))
                    if edit_request is not None:
                        attributes.SetUserString("SmartSkin.SelectedHandleRequest", json.dumps(edit_request, sort_keys=True))
                    identifier = (doc.Objects.AddBrep(geometry, attributes) if kind == "skin"
                                  else doc.Objects.AddCurve(geometry, attributes))
                finally:
                    attributes.Dispose()
                if identifier == system.Guid.Empty:
                    raise RuntimeError("Rhino could not add every result; rolling back this attempt.")
                additions.append(identifier)
        require_not_cancelled()
        require_evidence()
        ok, reason = capture.verify_sources(doc)
        if not ok:
            raise RuntimeError("Source proof changed at commit: " + reason)
        if doc.CurrentUndoRecordSerialNumber != serial or not doc.UndoRecordingIsActive:
            raise RuntimeError("The undo scope changed during commit.")
        if any(doc.Objects.FindId(identifier) is None or doc.Objects.FindId(identifier).IsDeleted
               for identifier in additions):
            raise RuntimeError("The complete new result could not be verified.")
    except Exception as original:
        if isinstance(native_screen, NativeScreenState):
            native_screen.invalidate()
        rollback_ok = _rollback_new_additions(doc, additions)
        if not rollback_ok:
            raise RuntimeError("New-only rollback was incomplete. Use Undo once and inspect the result.") from original
        raise
    finally:
        try:
            if owns_record:
                try:
                    ended = bool(doc.EndUndoRecord(serial))
                except Exception:
                    ended = False
                if not ended:
                    if isinstance(native_screen, NativeScreenState):
                        native_screen.invalidate()
                    restored = _rollback_new_additions(doc, additions)
                    raise RuntimeError("The single undo scope could not be closed. " +
                                       ("New additions were removed." if restored else
                                        "New-only rollback was incomplete; inspect the result and use Undo."))
        finally:
            _safe_cleanup(doc.Views.Redraw)
    return len(breps), len(guides)


def _number(value):
    try:
        value = float(value)
        return "{:.4g}".format(value) if math.isfinite(value) else "not finite"
    except (TypeError, ValueError):
        return "not reported"


def _metric_text(output):
    metrics = output.get("metrics", output.get("report", {}))
    # Bound displayed text and prefer measured quantities. No value is called
    # a global G2 certificate, even when all numerical samples happen to pass.
    lines = []
    if isinstance(metrics, dict):
        if "sample_count" in metrics:
            lines.append("Finite samples: " + _number(metrics["sample_count"]))
        if "full_boundary_pass" in metrics:
            lines.append("Finite boundary check: " + ("PASS" if metrics["full_boundary_pass"] else "FAIL")
                         + " | global G2: NOT VERIFIED")
        for label, prefix in (("Source", "source"), ("Upper boundary", "upper"),
                              ("Lower boundary", "lower"), ("Internal seams", "seam")):
            parts = []
            for suffix, caption in (("position_error", "gap"), ("angle_degrees", "normal deg"),
                                    ("curvature_error", "W residual")):
                key = prefix + "_" + suffix
                if key in metrics:
                    parts.append(caption + " " + _number(metrics[key]))
            if parts:
                lines.append(label + ": " + " | ".join(parts))
        if "position_tolerance" in metrics:
            lines.append("Limits: gap {0} | normal deg {1} | W {2}".format(
                _number(metrics.get("position_tolerance")),
                _number(metrics.get("angle_tolerance_degrees")),
                _number(metrics.get("curvature_tolerance"))))
        for key, caption in (("minimum_sampled_sine", "Minimum sampled tangent sine"),
                             ("minimum_sampled_jacobian", "Minimum sampled Jacobian"),
                             ("minimum_orientation_dot_h1", "Minimum orientation dot versus handle 1.00"),
                             ("sampled_max_curvature", "Maximum ordinary-grid curvature")):
            if key in metrics:
                lines.append(caption + ": " + _number(metrics[key]))
        hard_corner = metrics.get("hard_corner_curvature", {})
        if isinstance(hard_corner, dict) and hard_corner:
            value = hard_corner.get("logarithmic_sampled_max_curvature")
            lines.append("Approved hard-corner approach curvature: " + _number(value)
                         + " (logarithmic samples; growth toward the point is allowed, not globally bounded).")
        if "corner_policy" in metrics:
            lines.append(str(metrics["corner_policy"])[:300])
        for key in ("failing_intervals", "finite_corner_failures"):
            if key in metrics:
                lines.append(key.replace("_", " ") + ": " + str(metrics[key])[:400])
        for key, caption in (("upper_failure_intervals", "Upper failing parameter intervals"),
                             ("source_failure_intervals", "Source-end failing parameter intervals")):
            intervals = metrics.get(key, [])
            if intervals:
                lines.append(caption + ":")
                for interval in intervals[:8]:
                    lines.append("  " + str(interval)[:360])
                if len(intervals) > 8:
                    lines.append("  {0} additional failing intervals reported.".format(len(intervals) - 8))
    for warning in output.get("warnings", [])[:4]:
        lines.append(str(warning)[:200])
    return "\n".join(lines)


def run(doc, capture, kernel):
    """Called only by the supported Rhino CPython command path."""
    import Rhino
    import System
    import Eto.Forms as forms
    import Eto.Drawing as drawing
    import System.Drawing as system_drawing
    from Rhino.Geometry import BoundingBox

    class Conduit(Rhino.Display.DisplayConduit):
        def __init__(self):
            super().__init__()
            self.closed = False
            self.breps, self.guides = [], []
            self.selected_guide_indices = set()
            self.handle_display = None
            self.handle_points = {}
            self.material = Rhino.Display.DisplayMaterial(system_drawing.Color.FromArgb(65, 195, 215))
            self.material.Transparency = 0.35

        def CalculateBoundingBox(self, event):
            if self.closed:
                return
            box = BoundingBox.Empty
            for item in self.breps + self.guides:
                box.Union(item.GetBoundingBox(True))
            for point in self.handle_points.values():
                box.Union(Rhino.Geometry.Point3d(*point))
            if self.handle_display is not None:
                for point in self.handle_display:
                    box.Union(Rhino.Geometry.Point3d(*point))
            if box.IsValid:
                event.IncludeBoundingBox(box)

        def PostDrawObjects(self, event):
            if self.closed:
                return
            for brep in self.breps:
                event.Display.DrawBrepShaded(brep, self.material)
                event.Display.DrawBrepWires(brep, system_drawing.Color.DarkCyan, 1)
            for index, curve in enumerate(self.guides):
                selected = index in self.selected_guide_indices
                event.Display.DrawCurve(curve, system_drawing.Color.Yellow if selected else system_drawing.Color.Orange,
                                        4 if selected else 2)
            for point in self.handle_points.values():
                event.Display.DrawPoint(Rhino.Geometry.Point3d(*point), Rhino.Display.PointStyle.Simple,
                                        4, system_drawing.Color.Orange)
            if self.handle_display is not None:
                anchor, point = [Rhino.Geometry.Point3d(*value) for value in self.handle_display]
                event.Display.DrawLine(anchor, point, system_drawing.Color.Yellow, 2)
                event.Display.DrawPoint(point, Rhino.Display.PointStyle.Simple, 6, system_drawing.Color.Yellow)

        def replace(self, breps, guides):
            previous = self.breps + self.guides
            self.breps, self.guides = breps, guides
            _dispose_all(previous)

        def close(self):
            if self.closed:
                return
            self.closed = True
            _safe_cleanup(lambda: setattr(self, "Enabled", False))
            _safe_cleanup(lambda: self.replace([], []))
            _safe_cleanup(self.material.Dispose)

    class PreviewMouse(Rhino.UI.MouseCallback):
        def __init__(self, session):
            super().__init__()
            self.session = session
            self.consumed_viewport = None

        def OnMouseDown(self, event):
            try:
                if (self.session.disposed or self.session.state.closed or self.session.state.cancelled
                        or event.MouseButton != Rhino.UI.MouseButton.Left or event.CtrlKeyDown or event.ShiftKeyDown
                        or event.Cancel):
                    return
                self.consumed_viewport = None
                if self.session.pick_viewport(event):
                    self.consumed_viewport = event.View.ActiveViewport.Id
                    event.Cancel = True
            except Exception:
                # A queued native callback may outlive its view/control.
                self.consumed_viewport = None

        def OnMouseUp(self, event):
            try:
                if (self.session.disposed or self.session.state.closed or self.session.state.cancelled
                        or event.MouseButton != Rhino.UI.MouseButton.Left):
                    return
                viewport = self.consumed_viewport
                self.consumed_viewport = None
                if viewport is not None and event.View is not None and event.View.ActiveViewport.Id == viewport:
                    event.Cancel = True
            except Exception:
                self.consumed_viewport = None

        def close(self):
            self.Enabled = False
            self.consumed_viewport = None

    class Session:
        def __init__(self):
            self.state = PreviewState()
            self.prepared = None
            self.native_screen = NativeScreenState(capture.model)
            self.edits = None
            self.valid_edit_token = None
            self.attachment_ready = False
            self.attachment_reason = "Full finite source and shared-boundary attachments are not verified; inspection only."
            self.guide_groups = []
            self.handle_ids = []
            self.output = None
            self.accept_requested = False
            self.closing_for_command = False
            self.suppress_changes = False
            self.disposed = False
            self.deadline = None
            self.timed_out = False
            self.stage_name = "PREPARING"
            self.build_started = None
            self.build_budget = None
            self.progress_updated = 0.0
            self.pumping_events = False
            self.reset_work_counters()
            self.conduit = Conduit()
            self.mouse = PreviewMouse(self)
            self.form = forms.Form()
            self.form.Title = "Smart Skin | native FULLCYCLE preview"
            self.form.ClientSize = drawing.Size(600, 740)
            self.form.Resizable = True
            self.form.Minimizable = False
            self.form.Maximizable = False
            self.form.ShowActivated = False
            self.form.Owner = Rhino.UI.RhinoEtoApp.MainWindowForDocument(doc)
            self.guide_selector = forms.DropDown()
            self.guide_selector.Enabled = False
            self.guide_selector.Width = 410
            self.handle_selector = forms.DropDown()
            self.handle_selector.Enabled = False
            self.handle_selector.Width = 410
            self.slider = forms.Slider()
            self.slider.MinValue = 0
            self.slider.MaxValue = 1000
            self.slider.Value = 500
            self.slider.TickFrequency = 100
            self.slider.Width = 280
            self.slider.Enabled = False
            self.slider.ToolTip = "Changes the selected guide handle and its mirrored partner through the constrained edit basis."
            self.value = forms.Label()
            self.value.Text = "unavailable"
            self.value.Width = 110
            self.handle_note = forms.Label()
            self.handle_note.Wrap = forms.WrapMode.Word
            self.handle_note.Height = 60
            self.handle_note.Text = "Checking whether a verified per-handle edit basis is available..."
            self.status = forms.TextArea()
            self.status.ReadOnly = True
            self.status.Wrap = True
            self.status.Height = 300
            self.status.Text = "Preparing native source-edge data..."
            self.limitation = forms.Label()
            self.limitation.Text = ("EXPERIMENTAL FIELD CANDIDATE: PREPARING AND CHECKING\n"
                               "Editing and acceptance are disabled until all required checks pass. "
                               "Only the two approved upper source corners may remain hard with rising curvature; "
                               "finite end-strip exemptions are forbidden.")
            self.limitation.Wrap = forms.WrapMode.Word
            instruction = forms.Label()
            instruction.Text = ("Enter / Space / right-click: accept only when the required attachment checks pass.\n"
                                "At READY, click a preview guide or handle, then use its slider. Lists also select.\n"
                                "Esc or closing this window: discard preview. Sources stay unchanged.")
            instruction.Wrap = forms.WrapMode.Word
            layout = forms.DynamicLayout()
            layout.Padding = drawing.Padding(16)
            layout.Spacing = drawing.Size(8, 10)
            caption = forms.Label()
            caption.Text = "Select a U/V guide and its own handle"
            layout.AddRow(caption)
            guide_label = forms.Label()
            guide_label.Text = "Guide"
            handle_label = forms.Label()
            handle_label.Text = "Handle"
            guide_row = forms.DynamicLayout()
            guide_row.AddRow(guide_label, self.guide_selector)
            handle_row = forms.DynamicLayout()
            handle_row.AddRow(handle_label, self.handle_selector)
            layout.AddRow(guide_row)
            layout.AddRow(handle_row)
            row = forms.DynamicLayout()
            row.Spacing = drawing.Size(8, 0)
            row.AddRow(self.slider, self.value)
            layout.AddRow(row)
            layout.AddRow(self.handle_note)
            layout.AddRow(self.limitation)
            layout.AddRow(self.status)
            layout.AddRow(instruction)
            self.form.Content = layout
            self.timer = forms.UITimer()
            self.timer.Interval = 0.25
            self.slider.ValueChanged += self.on_change
            self.guide_selector.SelectedIndexChanged += self.on_guide_change
            self.handle_selector.SelectedIndexChanged += self.on_handle_change
            self.timer.Elapsed += self.on_tick
            self.form.Closing += self.on_closing
            self.form.KeyDown += self.on_key
            self.slider.KeyDown += self.on_key
            self.guide_selector.KeyDown += self.on_key
            self.handle_selector.KeyDown += self.on_key
            self.status.KeyDown += self.on_key
            Rhino.RhinoApp.EscapeKeyPressed += self.on_escape
            self.conduit.Enabled = True
            self.mouse.Enabled = False

        def cancelled(self):
            # Pump only at explicit bounded kernel/native checkpoints. This
            # permits Esc and newer slider input; revision guards reject stale
            # results and the rebuilding guard prevents nested evaluations.
            self.cancel_checkpoints += 1
            if self.state.closed or self.state.cancelled:
                return True
            now = time.monotonic()
            if self.deadline is not None and now >= self.deadline:
                self.timed_out = True
                return True
            self.refresh_progress()
            if (not self.pumping_events and
                    (self.last_event_pump is None or now - self.last_event_pump >= UI_PUMP_INTERVAL_SECONDS)):
                self.pumping_events = True
                started = time.monotonic()
                self.last_event_pump = started
                self.event_pumps += 1
                try:
                    Rhino.RhinoApp.Wait()
                finally:
                    now = time.monotonic()
                    self.last_event_pump = now
                    self.event_pump_seconds += max(0.0, now - started)
                    self.pumping_events = False
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self.timed_out = True
                return True
            return self.state.closed or self.state.cancelled

        def reset_work_counters(self):
            self.last_event_pump = None
            self.cancel_checkpoints = 0
            self.event_pumps = 0
            self.event_pump_seconds = 0.0

        def work_diagnostic(self):
            return "checkpoints={0} | ui_pumps={1} | ui_pump_seconds={2:.3f}".format(
                self.cancel_checkpoints, self.event_pumps, self.event_pump_seconds)

        def report_kernel_timing(self, phase, metrics):
            line = kernel_timing_diagnostic(phase, metrics)
            if line is not None:
                Rhino.RhinoApp.WriteLine(line)

        def set_stage(self, name):
            self.stage_name = name
            self.refresh_progress(force=True)
            elapsed = 0.0 if self.build_started is None else time.monotonic() - self.build_started
            Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1_STAGE | {0} | elapsed={1:.1f}s | {2}".format(
                name, elapsed, self.work_diagnostic()))

        def refresh_progress(self, force=False):
            if self.disposed or self.state.closed or self.state.cancelled or not self.state.building:
                return
            now = time.monotonic()
            if not force and now - self.progress_updated < 0.5:
                return
            self.progress_updated = now
            elapsed = 0.0 if self.build_started is None else now - self.build_started
            self.status.Text = ("{0}\nElapsed {1:.1f} s / {2:g} s total budget.\n"
                                "Building and checking; guide/handle controls become available at READY.\n"
                                "Esc cancels between supported operations; one native call cannot be force-interrupted.").format(
                                    self.stage_name, elapsed, self.build_budget or CACHED_BUILD_SECONDS)
            Rhino.RhinoApp.SetCommandPrompt("Smart Skin: {0}; {1:.0f}/{2:g} s; Esc cancels".format(
                self.stage_name.lower(), elapsed, self.build_budget or CACHED_BUILD_SECONDS))

        def on_escape(self, sender, event):
            if self.disposed or self.state.closed:
                return
            self.native_screen.invalidate()
            self.mouse.close()
            self.state.cancel()
            self.timer.Stop()
            Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1_CANCEL_REQUEST | stage=" + self.stage_name)

        def on_closing(self, sender, event):
            if self.disposed or self.state.closed:
                return
            self.timer.Stop()
            if not self.closing_for_command:
                self.native_screen.invalidate()
                self.mouse.close()
                self.state.cancel()

        def on_key(self, sender, event):
            if self.disposed or self.state.closed or self.state.cancelled:
                return
            if event.Key == forms.Keys.Escape:
                event.Handled = True
                self.on_escape(sender, event)
            elif event.Key == forms.Keys.Enter or event.Key == forms.Keys.Space:
                event.Handled = True
                if self.prepare_acceptance():
                    self.accept_requested = True

        def on_change(self, sender, event):
            if self.suppress_changes or self.disposed or self.state.cancelled or self.state.closed:
                return
            if self.edits is None or not self.edits.enabled or not self.slider.Enabled:
                return
            self.accept_requested = False
            self.native_screen.invalidate()
            self.mouse.close()
            item = self.edits.handles[self.edits.selected_handle]
            value = item["minimum"] + (item["maximum"] - item["minimum"]) * self.slider.Value / 1000.0
            self.edits.set_selected_value(value)
            # Reuse the existing revision/cancellation machinery. The scalar
            # remains the fixed baseline; it is NEVER the selected edit input.
            self.state.request(1.0)
            self.value.Text = _number(value)
            self.timer.Stop()
            self.status.Text = "UPDATING: waiting for the selected handle edit. Acceptance is disabled."
            self.timer.Start()

        def refresh_handle_controls(self):
            previous_suppression = self.suppress_changes
            self.suppress_changes = True
            try:
                self.handle_ids = ([] if self.edits is None else self.edits.select_guide(self.edits.selected_guide))
                self.handle_selector.DataStore = [str(self.edits.handles[key].get("label", key)) for key in self.handle_ids]
                self.handle_selector.Enabled = bool(self.handle_ids)
                self.handle_selector.SelectedIndex = (self.handle_ids.index(self.edits.selected_handle) if self.handle_ids else -1)
                item = self.edits.handles.get(self.edits.selected_handle) if self.edits is not None else None
                partner = self.edits.handles[item["mirror_handle_id"]] if item is not None else None
                locked_reason = (item.get("locked_reason") or partner.get("locked_reason")) if item is not None else None
                self.slider.Enabled = bool(self.edits is not None and self.edits.enabled and self.attachment_ready
                                           and self.native_screen.receipt is not None
                                           and item and not locked_reason)
                self.mouse.Enabled = bool(self.state.can_accept and self.attachment_ready
                                          and self.native_screen.receipt is not None and self.edits is not None
                                          and self.edits.enabled and self.valid_edit_token is not None)
                if item is not None:
                    value = self.edits.values[self.edits.selected_handle]
                    self.slider.Value = int(round(1000 * (value - item["minimum"]) / (item["maximum"] - item["minimum"])))
                    self.value.Text = _number(value) + (" " + str(item["units"]) if item.get("units") else "")
                    self.handle_note.Text = (self.attachment_reason if not self.attachment_ready
                                             else str(locked_reason or self.edits.reason))
                else:
                    self.value.Text = "unavailable"
                    self.handle_note.Text = (self.attachment_reason if not self.attachment_ready else
                                             self.edits.reason if self.edits is not None and not self.edits.enabled else
                                             "This guide has no editable handle in the constrained basis.")
            finally:
                self.suppress_changes = previous_suppression

        def refresh_guide_choices(self, groups):
            self.guide_groups = groups
            previous_suppression = self.suppress_changes
            self.suppress_changes = True
            try:
                self.guide_selector.DataStore = [item["label"] for item in groups]
                self.guide_selector.Enabled = bool(groups)
                identifiers = [item["id"] for item in groups]
                current = self.edits.selected_guide
                index = identifiers.index(current) if current in identifiers else (0 if groups else -1)
                self.guide_selector.SelectedIndex = index
                self.edits.select_guide(identifiers[index] if index >= 0 else None)
                self.refresh_handle_controls()
            finally:
                self.suppress_changes = previous_suppression
            self.update_selection_display()

        def update_selection_display(self):
            selected = self.edits.selected_guide if self.edits is not None else None
            self.conduit.selected_guide_indices = next((set(item["indices"]) for item in self.guide_groups if item["id"] == selected), set())
            self.conduit.handle_display = self.edits.display_handle() if self.edits is not None else None
            self.conduit.handle_points = (dict(self.edits.last_valid_positions)
                                          if self.edits is not None and self.edits.last_valid_positions is not None else {})
            doc.Views.Redraw()

        def pick_viewport(self, event):
            if (self.disposed or self.state.closed or not self.state.can_accept or not self.attachment_ready
                    or self.native_screen.receipt is None or self.edits is None or not self.edits.enabled
                    or self.valid_edit_token is None or event.View is None or event.View.Document is None
                    or event.View.Document.RuntimeSerialNumber != doc.RuntimeSerialNumber
                    or event.View.InDynamicViewChange or isinstance(event.View, Rhino.Display.RhinoPageView)):
                return False
            revision = self.state.revision
            picker = None
            try:
                deadline = time.monotonic() + VIEWPORT_PICK_SECONDS
                self.edits.verify_displayed_result(self.valid_edit_token, self.output)
                ok, reason = capture.verify_sources(doc)
                if not ok:
                    self.native_screen.invalidate()
                    self.state.error = "Source proof changed."
                    self.status.Text = "BLOCKED: sources changed during preview. " + reason
                    self.refresh_handle_controls()
                    return False
                picker = Rhino.Input.Custom.PickContext()
                picker.View = event.View
                picker.PickStyle = Rhino.Input.Custom.PickStyle.PointPick
                picker.PickMode = Rhino.Input.Custom.PickMode.Wireframe
                viewport = event.View.ActiveViewport
                transform = viewport.GetPickTransform(event.ViewportPoint)
                line = viewport.ClientToWorld(event.ViewportPoint)
                if not transform.IsValid or not line.IsValid:
                    raise RuntimeError("The viewport does not have a valid pick frustum.")
                picker.SetPickTransform(transform)
                picker.PickLine = line
                picker.UpdateClippingPlanes()
                def stale():
                    return (self.disposed or self.state.closed or not self.state.can_accept
                            or self.state.revision != revision or self.native_screen.receipt is None
                            or time.monotonic() >= deadline)
                points = {key: Rhino.Geometry.Point3d(*point) for key, point in self.conduit.handle_points.items()}
                picked = pick_native_preview(picker, self.conduit.guides, self.guide_groups, points, stale)
                if picked is None or stale():
                    return False
                kind, identifier = picked
                guide_id = self.edits.handles[identifier]["guide_id"] if kind == "handle" else identifier
                self.edits.select_guide(guide_id)
                if kind == "handle":
                    self.edits.select_handle(identifier)
                previous_suppression = self.suppress_changes
                self.suppress_changes = True
                try:
                    self.guide_selector.SelectedIndex = next(index for index, group in enumerate(self.guide_groups)
                                                              if group["id"] == guide_id)
                    self.refresh_handle_controls()
                finally:
                    self.suppress_changes = previous_suppression
                self.update_selection_display()
                return True
            except Exception as error:
                if self.disposed or self.state.closed or self.state.cancelled:
                    return False
                detail = str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__
                _safe_cleanup(lambda: setattr(self.status, "Text", "Viewport selection unavailable: " + detail
                                              + "\nUse the Guide and Handle lists."))
                _safe_cleanup(lambda: Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1_PICK_UNAVAILABLE | " + detail[:300]))
                return False
            finally:
                if picker is not None:
                    _safe_cleanup(picker.Dispose)

        def on_guide_change(self, sender, event):
            if self.suppress_changes or self.disposed or self.state.closed or self.state.cancelled or self.edits is None:
                return
            index = self.guide_selector.SelectedIndex
            if not 0 <= index < len(self.guide_groups):
                return
            self.edits.select_guide(self.guide_groups[index]["id"])
            self.refresh_handle_controls()
            self.update_selection_display()

        def on_handle_change(self, sender, event):
            if self.suppress_changes or self.disposed or self.state.closed or self.state.cancelled or self.edits is None:
                return
            index = self.handle_selector.SelectedIndex
            if not 0 <= index < len(self.handle_ids):
                return
            self.edits.select_handle(self.handle_ids[index])
            self.refresh_handle_controls()
            self.update_selection_display()

        def on_tick(self, sender, event):
            if self.disposed or self.state.closed or self.state.cancelled:
                return
            self.timer.Stop()
            self.rebuild()

        def rebuild(self):
            token = self.state.begin()
            if token is None:
                return
            started = time.monotonic()
            budget_seconds = COLD_BUILD_SECONDS if self.prepared is None else CACHED_BUILD_SECONDS
            self.build_started, self.build_budget = started, budget_seconds
            self.deadline = started + budget_seconds
            self.timed_out = False
            self.reset_work_counters()
            self.native_screen.invalidate()
            self.mouse.close()
            breps, guides = [], []
            def evaluation_cancelled():
                # The UI pump can receive a newer slider value. Do not spend
                # another expensive fan rebuild finishing an obsolete value.
                return self.cancelled() or self.state.superseded(token)
            try:
                self.set_stage("PREPARING NATIVE NETWORK")
                if self.prepared is None:
                    # Input mapping contains only owned generic numerical data.
                    self.prepared = kernel.prepare(capture.model, cancelled=self.cancelled)
                self.set_stage("NUMERICAL ATTACHMENT AND ATLAS CHECKS")
                result, edit_token, self.edits = evaluate_preview_cycle(
                    self.prepared, self.edits, token[0], evaluation_cancelled, capture.model,
                    self.set_stage, self.report_kernel_timing)
                self.handle_note.Text = self.edits.reason
                ready, reason = geometry_commit_acceptance(result)
                if not ready:
                    raise ValueError(reason + " " + str(result.get("reason", "")))
                ready, reason = attachment_acceptance(result, capture.model)
                if not ready:
                    raise ValueError(reason)
                request = edit_token.payload if edit_token is not None else None
                _verify_atlas_separation(result, capture.model, request)
                groups = group_uv_guides(result.get("guides", []))
                if self.edits.enabled:
                    missing = {item["guide_id"] for item in self.edits.handles.values()} - {item["id"] for item in groups}
                    if missing:
                        raise ValueError("The constrained edit basis refers to missing preview guides.")
                self.ensure_owner_context(evaluation_cancelled)
                self.set_stage("NATIVE NURBS CONVERSION")
                breps, guides, conversion = make_native_geometry(result, Rhino.Geometry, evaluation_cancelled, self.native_screen.context)
                self.set_stage("NATIVE OWNER SEPARATION SCREEN")
                self.native_screen.screen(breps, result, request=request, cancelled=evaluation_cancelled,
                                          guides=guides, conversion=conversion)
                if edit_token is not None:
                    self.edits.accept(edit_token, result)
                if self.state.complete(token, True):
                    self.conduit.replace(breps, guides)
                    breps, guides = [], []
                    self.output = result
                    self.attachment_ready, self.attachment_reason = attachment_acceptance(result, capture.model)
                    self.valid_edit_token = edit_token
                    self.refresh_guide_choices(groups)
                    self.limitation.Text = ("EXPERIMENTAL NATIVE-SCREENED PREVIEW\n"
                                            "Numerical attachments, projected atlas and bounded owner screening completed. "
                                            "This is not a global nonintersection certificate or a verified native UI release.")
                    mode = ("Selected U/V handle result" if edit_token is not None else
                            "Baseline preview only; local handle editing is unavailable")
                    self.status.Text = ("{0}: {1}\n{2}\nNative owner receipt: current bounded screen completed.\n"
                                        "{3} native patches + {4} exact guides | {5:.2f} s\n{6}").format(
                                            "READY" if self.attachment_ready else "INSPECTION ONLY", mode,
                                            self.attachment_reason, len(self.conduit.breps), len(self.conduit.guides),
                                            time.monotonic() - started, _metric_text(result))
                    Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1_READY | guides={0} | handles={1} | elapsed={2:.1f}s".format(
                        len(groups), len(self.edits.handles), time.monotonic() - started))
                elif not self.state.cancelled:
                    self.native_screen.invalidate()
                    self.status.Text = "UPDATING: a newer handle setting is pending."
            except Exception as error:
                self.native_screen.invalidate()
                reason = ("The {0:g}-second build budget expired between supported operations.".format(budget_seconds)
                          if self.timed_out else str(error)
                          if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__)
                self.state.complete(token, False, reason)
                failed_current = token[0] == self.state.revision
                failure_label = "BLOCKED"
                if not self.state.closed and not self.state.cancelled:
                    # Only a rejected CURRENT revision may reset the slider.
                    # A newer request arriving while computing keeps priority.
                    if token[0] != self.state.revision:
                        self.status.Text = "UPDATING: rebuilding the newer handle setting."
                    elif self.state.restore_last_valid():
                        failure_label = "REJECTED"
                        if self.edits is not None and self.edits.enabled:
                            self.edits.restore_last_valid()
                        self.refresh_handle_controls()
                        self.update_selection_display()
                        self.status.Text = ("REJECTED selected handle edit: {0}\n"
                                            "Handle values and preview restored. A new Enter first rebuilds exact native copies "
                                            "and obtains a fresh native separation receipt.\n{1}").format(reason, _metric_text(self.output))
                    else:
                        self.status.Text = "BLOCKED: " + reason + "\nNo current result can be accepted."
                    if failed_current:
                        Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1_{0} | stage={1} | elapsed={2:.1f}s | {3}".format(
                            failure_label, self.stage_name, time.monotonic() - started, " ".join(reason.split())[:700]))
            finally:
                self.deadline = None
                _safe_cleanup(lambda: Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1_WORK | " + self.work_diagnostic()))
                _dispose_all(breps + guides)
                if self.state.pending and not self.state.cancelled and not self.state.closed:
                    self.timer.Start()
                doc.Views.Redraw()

        def ensure_owner_context(self, cancelled):
            if self.native_screen.context is None:
                self.set_stage("NATIVE OWNER SNAPSHOT")
                api = _native_owner_api()
                limits = api.ScreenLimits(seconds=NATIVE_SCREEN_SECONDS)
                self.native_screen.context = api.create_owner_context(doc, capture, Rhino, cancelled=cancelled, limits=limits)

        def rescreen_restored_preview(self):
            """A discarded receipt is never revived merely by restoring values."""
            revision = self.state.revision
            breps, guides = [], []
            self.state.building = True
            self.build_started, self.build_budget = time.monotonic(), CACHED_BUILD_SECONDS
            self.deadline = self.build_started + CACHED_BUILD_SECONDS
            self.timed_out = False
            self.reset_work_counters()
            def stale():
                return self.cancelled() or self.state.revision != revision
            try:
                self.native_screen.invalidate()
                self.set_stage("RECHECKING RESTORED PREVIEW")
                self.ensure_owner_context(stale)
                request = self.valid_edit_token.payload if self.valid_edit_token is not None else None
                ready, reason = geometry_commit_acceptance(self.output)
                if not ready:
                    raise ValueError(reason)
                _verify_atlas_separation(self.output, capture.model, request)
                breps, guides, conversion = make_native_geometry(self.output, Rhino.Geometry, stale, self.native_screen.context)
                self.native_screen.screen(breps, self.output, request=request, cancelled=stale,
                                          guides=guides, conversion=conversion)
                if stale():
                    raise RuntimeError("The restored-preview screen was cancelled or superseded.")
                self.conduit.replace(breps, guides)
                breps, guides = [], []
                self.update_selection_display()
                self.status.Text = "EXPERIMENTAL READY: a fresh bounded native separation screen completed for the restored result."
                return True
            except Exception as error:
                self.native_screen.invalidate()
                reason = ("The 60-second restored-preview screen budget expired."
                          if self.timed_out else str(error)
                          if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__)
                self.status.Text = "ACCEPTANCE BLOCKED: " + reason
                return False
            finally:
                self.deadline = None
                self.state.building = False
                _safe_cleanup(lambda: Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1_WORK | " + self.work_diagnostic()))
                _dispose_all(breps + guides)
                self.refresh_handle_controls()
                if self.state.pending and not self.state.cancelled and not self.state.closed:
                    self.timer.Start()
                doc.Views.Redraw()

        def prepare_acceptance(self):
            if self.disposed or self.state.closed or self.state.cancelled or self.state.building:
                return False
            self.timer.Stop()
            requested_revision = self.state.revision
            if self.state.pending:
                self.rebuild()
            # A failed pending setting may have visibly restored the previous
            # slider value. Require a NEW confirmation of that restored value.
            if self.state.revision != requested_revision:
                return False
            if not self.state.can_accept:
                return False
            self.attachment_ready, self.attachment_reason = attachment_acceptance(self.output, capture.model)
            if not self.attachment_ready:
                self.status.Text = "ACCEPTANCE BLOCKED: " + self.attachment_reason + "\n" + _metric_text(self.output)
                return False
            if self.edits is not None and self.edits.enabled:
                if (self.valid_edit_token is None or
                        dict(self.valid_edit_token.values) != self.edits.values):
                    return False
                self.edits.verify_displayed_result(self.valid_edit_token, self.output)
            ok, reason = capture.verify_sources(doc)
            if not ok:
                self.state.error = "Source proof changed."
                self.status.Text = "BLOCKED: sources changed during preview. " + reason
                return False
            if self.native_screen.receipt is None and not self.rescreen_restored_preview():
                return False
            if not self.state.can_accept:
                return False
            try:
                request = self.valid_edit_token.payload if self.valid_edit_token is not None else None
                self.native_screen.verify(self.conduit.breps, self.output, request=request,
                                          cancelled=lambda: self.state.closed or self.state.cancelled,
                                          guides=self.conduit.guides)
            except Exception as error:
                self.native_screen.invalidate()
                self.status.Text = "ACCEPTANCE BLOCKED: " + str(error)
                return False
            return True

        def close(self):
            if self.disposed:
                return
            self.disposed = True
            self.closing_for_command = True
            self.state.close()
            self.native_screen.invalidate()
            # Every unsubscribe/dispose is isolated: a queued event or an
            # already disposed Eto control cannot strand the native conduit.
            def unhook_escape():
                Rhino.RhinoApp.EscapeKeyPressed -= self.on_escape
            def unhook_slider():
                self.slider.ValueChanged -= self.on_change
                self.slider.KeyDown -= self.on_key
            def unhook_guide_selector():
                self.guide_selector.SelectedIndexChanged -= self.on_guide_change
                self.guide_selector.KeyDown -= self.on_key
            def unhook_handle_selector():
                self.handle_selector.SelectedIndexChanged -= self.on_handle_change
                self.handle_selector.KeyDown -= self.on_key
            def unhook_timer():
                self.timer.Elapsed -= self.on_tick
            def unhook_form():
                self.form.Closing -= self.on_closing
                self.form.KeyDown -= self.on_key
            def unhook_status():
                self.status.KeyDown -= self.on_key
            for action in (unhook_escape, self.timer.Stop, self.mouse.close, self.conduit.close, self.native_screen.close,
                           unhook_slider, unhook_guide_selector, unhook_handle_selector,
                           unhook_timer, unhook_form, unhook_status,
                           self.form.Close, self.form.Dispose, self.timer.Dispose,
                           doc.Views.Redraw):
                _safe_cleanup(action)

    session = Session()
    decision = None
    try:
        session.form.Show()
        session.rebuild()
        decision = Rhino.Input.Custom.GetOption()
        decision.AcceptNothing(True)
        decision.SetWaitDuration(100)
        while not session.state.cancelled and session.form.Visible:
            if session.accept_requested:
                # Recheck even after a form key event. A queued value change or
                # altered source cannot exploit an earlier acceptance request.
                if session.prepare_acceptance():
                    break
                session.accept_requested = False
            decision.SetCommandPrompt(preview_command_prompt(session.state, bool(session.edits and session.edits.enabled),
                                                             session.native_screen.receipt is not None))
            result, current_confirmation = get_preview_decision(decision, session.state, session.native_screen)
            if session.state.cancelled or not session.form.Visible:
                break
            if result == Rhino.Input.GetResult.Timeout:
                continue
            if result == Rhino.Input.GetResult.Nothing:
                if not current_confirmation:
                    continue
                if session.prepare_acceptance():
                    session.accept_requested = True
                    break
                continue
            session.state.cancel()
        if session.accept_requested and session.prepare_acceptance():
            skin_count, guide_count = commit_new_geometry(
                doc, capture, session.conduit.breps, session.conduit.guides,
                session.state.valid_h, Rhino, System, attachment_result=session.output,
                edit_request=session.valid_edit_token.payload if session.valid_edit_token is not None else None,
                edit_state=session.edits if session.valid_edit_token is not None else None,
                cancelled=lambda: session.disposed or session.state.closed or session.state.cancelled,
                native_screen=session.native_screen)
            Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1 ACCEPTED_SELECTED_UV_PROTOTYPE | skin={0} | guides={1} | mode={2} | sources=unchanged | full_G2=NOT_VERIFIED".format(
                skin_count, guide_count, "SELECTED_HANDLE" if session.valid_edit_token is not None else "BASELINE"))
            return True
        Rhino.RhinoApp.WriteLine("SMARTSKIN_P08E1 CANCELLED | added=0 | sources=unchanged")
        return False
    finally:
        if decision is not None:
            _safe_cleanup(decision.Dispose)
        session.close()
