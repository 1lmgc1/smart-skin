"""Exact, bounded local-immersion certificate for isolated upper-corner charts.

The supplied binary64 homogeneous Bezier net is the mathematical input. Its
entire v=0 row must be one identical homogeneous point, with positive weights.
The projected Jacobian numerator must have an exact factor r=v. Only that
factor is removed; its signed quotient must be strictly positive on the whole
closed square, including r=0. No finite neighborhood is omitted.

This proves local immersion for every r>0, not global injectivity, native
attachment, G2, or permission to introduce a corner. The caller must separately
bind upper:side0/side1 to the approved, capture-derived physical source vertex.
"""
from fractions import Fraction
import math
import weakref
import numpy as np

try:
    import _smartskin_p08e1_fan_shared_jets as _fj
except ModuleNotFoundError as exc:
    if exc.name != "_smartskin_p08e1_fan_shared_jets":
        raise
    import fan_shared_jets as _fj


_MAX_DEGREE = 40
_MAX_CONTROLS = 16384
_MAX_BITS = 8192
_MAX_WORK = 100_000_000
_MAX_SECONDS = 90.0
_MAX_ELEMENTS = 32768
_MAX_PACKED_BITS = 16_000_000
_MAX_LIVE_BYTES = 128 * 1024 * 1024
_MAX_DEPTH = 14
_MAX_CELLS = 512
_SCOPE = ('A passed result proves local projected immersion for every 0 < r <= 1 of the supplied '
          'binary64 upper chart; no global injectivity, attachment or G2 proof.')


class _NotCertified(ValueError):
    pass


class _Budget:
    """Bit/work/time bounds plus conservative live tensor allocation bounds.

    Every owned object tensor is charged at the maximum allowed integer size,
    including Python integer and pointer overhead, until its last view dies.
    Packed convolution has a separate 16-million-bit cap. Bounded NumPy row
    temporaries and packed byte buffers require at most 64 MiB beyond the
    128 MiB owned-tensor limit. No unbounded matrix multiplication is used.
    """
    def __init__(self, cancelled, deadline):
        if cancelled is not None and not callable(cancelled):
            raise _NotCertified('invalid_cancellation_callback')
        def poll_cancelled():
            try:
                return bool(cancelled())
            except Exception as exc:
                raise _NotCertified('cancellation_callback_failed') from exc
        self.exact = _fj.ExactWorkBudget(
            max_work=_MAX_WORK, max_bits=_MAX_BITS, max_elements=_MAX_ELEMENTS,
            max_seconds=_MAX_SECONDS, cancelled=poll_cancelled if cancelled is not None else None,
            deadline=deadline)
        self.live_bytes = 0
        self.peak_bytes = 0
        self.exact.checkpoint('upper certificate entry', force_cancel=True)

    def check(self, phase, work=0):
        self.exact.checkpoint(phase, work)

    def inspect(self, value, phase):
        self.exact.inspect(value, phase)

    def zeros(self, shape, phase='exact tensor allocation'):
        self.exact.allocation(shape, phase)
        # CPython stores 30-bit bigint digits in 4 bytes; include object,
        # reference and alignment overhead rather than assuming packed bits.
        charge = math.prod(shape) * (64 + 4 * ((_MAX_BITS + 29) // 30))
        if self.live_bytes + charge > _MAX_LIVE_BYTES:
            raise _NotCertified('live_memory_budget_exhausted')
        self.live_bytes += charge
        self.peak_bytes = max(self.peak_bytes, self.live_bytes)
        try:
            out = np.empty(shape, dtype=object)
            out.fill(0)
        except BaseException:
            self.live_bytes -= charge
            raise
        weakref.finalize(out, self._release, charge)
        return out

    def _release(self, charge):
        self.live_bytes -= charge

    def report(self):
        out = self.exact.report()
        out.update(peak_owned_tensor_bytes=self.peak_bytes,
                   maximum_scratch_bytes=64 * 1024 * 1024,
                   max_integer_coefficient_bits=_MAX_BITS,
                   max_packed_representation_bits=_MAX_PACKED_BITS,
                   maximum_binary_depth=_MAX_DEPTH, maximum_cells=_MAX_CELLS)
        return out


def _trim(a):
    while a.shape[0] > 1 and not any(a[-1].flat):
        a = a[:-1]
    while a.shape[1] > 1 and not any(a[:, -1].flat):
        a = a[:, :-1]
    return a


def _add(a, b, budget, sign=1):
    phase = 'exact polynomial addition'
    out = budget.zeros((max(a.shape[0], b.shape[0]),
                        max(a.shape[1], b.shape[1])), phase)
    budget.check(phase, a.size + 2 * b.size)
    out[:a.shape[0], :a.shape[1]] = a
    for i in range(b.shape[0]):
        budget.check(phase, b.shape[1])
        out[i, :b.shape[1]] += sign * b[i]
        budget.inspect(out[i], phase)
    return _trim(out)


def _derivative(a, axis, budget):
    if axis:
        return _derivative(a.T, 0, budget).T
    if a.shape[0] == 1:
        return budget.zeros((1, 1))
    out = budget.zeros((a.shape[0] - 1, a.shape[1]))
    for i in range(1, a.shape[0]):
        budget.check('exact polynomial derivative', a.shape[1])
        out[i - 1] = i * a[i]
        budget.inspect(out[i - 1], 'exact polynomial derivative')
    return _trim(out)


def _binary64(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise _NotCertified('input_must_be_finite_binary64_numbers')
    value = float(value)
    if not math.isfinite(value):
        raise _NotCertified('nonfinite_input')
    return value


def _inputs(descriptor, normal, expected_sign, budget):
    if not isinstance(descriptor, dict) or descriptor.get('kind') != 'upper_hard_corner':
        raise _NotCertified('unsupported_chart_kind')
    side = descriptor.get('side')
    if type(side) is not int or side not in (0, 1) or descriptor.get(
            'approved_physical_corner_id') != 'upper:side%d' % side:
        raise _NotCertified('missing_or_mismatched_approved_upper_corner')
    if descriptor.get('collapsed_parameter_edge') != 'v=0':
        raise _NotCertified('unsupported_collapsed_parameter_edge')
    if type(expected_sign) not in (int, float) or expected_sign not in (-1, 1):
        raise _NotCertified('invalid_expected_orientation_sign')
    p, q = descriptor.get('degree_u'), descriptor.get('degree_v')
    if any(type(k) is not int or not 1 <= k <= _MAX_DEGREE for k in (p, q)):
        raise _NotCertified('input_degree_budget_exhausted')
    if (p + 1) * (q + 1) > _MAX_CONTROLS:
        raise _NotCertified('input_control_budget_exhausted')
    for name, degree in (('knots_u', p), ('knots_v', q)):
        knots = descriptor.get(name)
        if not isinstance(knots, (list, tuple, np.ndarray)) or len(knots) != 2 * (degree + 1):
            raise _NotCertified('single_normalized_Bezier_span_required')
        if [_binary64(x) for x in knots] != [0.] * (degree + 1) + [1.] * (degree + 1):
            raise _NotCertified('single_normalized_Bezier_span_required')
    domain = descriptor.get('domain')
    if not isinstance(domain, (list, tuple, np.ndarray)) or len(domain) != 2:
        raise _NotCertified('normalized_unit_square_required')
    if any(not isinstance(row, (list, tuple, np.ndarray)) or len(row) != 2 or
           [_binary64(x) for x in row] != [0., 1.] for row in domain):
        raise _NotCertified('normalized_unit_square_required')
    raw = descriptor.get('homogeneous_cp')
    if not isinstance(raw, (list, tuple, np.ndarray)) or len(raw) != p + 1:
        raise _NotCertified('invalid_control_net_shape')
    cp = np.empty((p + 1, q + 1, 4), dtype=float)
    for i, row in enumerate(raw):
        budget.check('control net validation', 4 * (q + 1))
        if not isinstance(row, (list, tuple, np.ndarray)) or len(row) != q + 1:
            raise _NotCertified('invalid_control_net_shape')
        for j, point in enumerate(row):
            if not isinstance(point, (list, tuple, np.ndarray)) or len(point) != 4:
                raise _NotCertified('invalid_control_net_shape')
            cp[i, j] = [_binary64(x) for x in point]
    if not np.all(cp[:, :, 3] > 0):
        raise _NotCertified('positive_Bernstein_weights_required')
    if not np.all(cp[:, 0] == cp[0, 0]):
        raise _NotCertified('constant_homogeneous_pole_row_required')
    if not isinstance(normal, (list, tuple, np.ndarray)) or len(normal) != 3:
        raise _NotCertified('invalid_reference_normal')
    n = np.asarray([_binary64(x) for x in normal], dtype=float)
    if not np.any(n):
        raise _NotCertified('zero_reference_normal')
    return cp, n


def _dyadic_integers(a, budget):
    ratios = [float(x).as_integer_ratio() for x in a.flat]
    exponent = max(d.bit_length() - 1 for _, d in ratios)
    out = budget.zeros(a.shape)
    for i, (n, d) in enumerate(ratios):
        if i % 64 == 0:
            budget.check('binary64 exact dyadic conversion', min(64, a.size - i))
        out.flat[i] = n << (exponent - (d.bit_length() - 1))
    budget.inspect(out, 'binary64 exact dyadic conversion')
    return out, exponent


def _bernstein_to_power(a, budget):
    def axis(a):
        n = a.shape[0] - 1
        out, work = budget.zeros(a.shape), budget.zeros(a.shape)
        work[:] = a
        for k in range(n + 1):
            budget.check('Bernstein to power', work.size + out.shape[1])
            out[k] = work[0] * math.comb(n, k)
            budget.inspect(out[k], 'Bernstein to power')
            if k < n:
                work[:-1] = work[1:] - work[:-1]
                work = work[:-1]
                budget.inspect(work, 'Bernstein forward differences')
        return out
    return _trim(axis(axis(a).T).T)


def _window_sums(a, window, shape, budget):
    """Exact convolution with a rectangular all-ones polynomial."""
    p = budget.zeros((a.shape[0] + 1, a.shape[1] + 1))
    for i in range(a.shape[0]):
        budget.check('convolution prefix sums', 4 * a.shape[1])
        for j in range(a.shape[1]):
            p[i + 1, j + 1] = a[i, j] + p[i, j + 1] + p[i + 1, j] - p[i, j]
        budget.inspect(p[i + 1], 'convolution prefix sums')
    out = budget.zeros(shape)
    for i in range(shape[0]):
        budget.check('convolution window sums', 4 * shape[1])
        lo, hi = max(0, i - window[0] + 1), min(a.shape[0], i + 1)
        for j in range(shape[1]):
            left, right = max(0, j - window[1] + 1), min(a.shape[1], j + 1)
            out[i, j] = p[hi, right] - p[lo, right] - p[hi, left] + p[lo, left]
        budget.inspect(out[i], 'convolution window sums')
    return out


def _convolve(a, b, budget):
    """Exact signed integer convolution, using carry-free Kronecker packing."""
    a, b = _trim(a), _trim(b)
    budget.check('convolution entry', a.size + b.size)
    if not any(a.flat) or not any(b.flat):
        return budget.zeros((1, 1))
    shape = (a.shape[0] + b.shape[0] - 1, a.shape[1] + b.shape[1] - 1)
    if max(shape) > 3 * _MAX_DEGREE + 1:
        raise _NotCertified('jacobian_degree_budget_exhausted')
    ka, kb = max(0, -min(a.flat)), max(0, -min(b.flat))
    # Offsets make every packed digit nonnegative. The slot bound prevents
    # carry between coefficients, including collisions within each 2D sum.
    bound = (int(max(a.flat) + ka) * int(max(b.flat) + kb) *
             min(a.shape[0], b.shape[0]) * min(a.shape[1], b.shape[1]))
    budget.inspect(bound, 'convolution coefficient bound')
    slot = max(1, (bound.bit_length() + 8) // 8)
    stride, slots = shape[1], math.prod(shape)
    if slots * slot * 8 > _MAX_PACKED_BITS:
        raise _NotCertified('packed_memory_budget_exhausted')

    def pack(x, offset):
        data = bytearray(((x.shape[0] - 1) * stride + x.shape[1]) * slot)
        for i in range(x.shape[0]):
            budget.check('Kronecker packing', x.shape[1] * max(1, slot // 8))
            for j in range(x.shape[1]):
                start = (i * stride + j) * slot
                data[start:start + slot] = int(x[i, j] + offset).to_bytes(slot, 'little')
        return int.from_bytes(data, 'little')

    aa, bb = pack(a, ka), pack(b, kb)
    # A single bigint multiplication is not interruptible. Operand sizes and
    # its size-derived limb-work charge are bounded before entering it.
    limbs_a, limbs_b = (aa.bit_length() + 29) // 30, (bb.bit_length() + 29) // 30
    budget.check('packed exact multiplication', limbs_a + limbs_b +
                 int(max(limbs_a, limbs_b) ** 1.585))
    product = aa * bb
    budget.check('packed exact multiplication completed', slots * max(1, slot // 8))
    raw = product.to_bytes(slots * slot, 'little')
    out = budget.zeros(shape)
    for i in range(shape[0]):
        budget.check('Kronecker unpacking', shape[1])
        for j in range(shape[1]):
            start = (i * stride + j) * slot
            out[i, j] = int.from_bytes(raw[start:start + slot], 'little')
        budget.inspect(out[i], 'Kronecker unpacking')
    for offset, other, window in ((ka, b, a.shape), (kb, a, b.shape)):
        if offset:
            sums = _window_sums(other, window, shape, budget)
            for i in range(shape[0]):
                budget.check('signed convolution correction', 2 * shape[1])
                out[i] -= offset * sums[i]
                budget.inspect(out[i], 'signed convolution correction')
            del sums
    if ka and kb:
        for i in range(shape[0]):
            budget.check('convolution offset correction', 4 * shape[1])
            count_u = min(a.shape[0], i + 1) - max(0, i - b.shape[0] + 1)
            for j in range(shape[1]):
                count_v = min(a.shape[1], j + 1) - max(0, j - b.shape[1] + 1)
                out[i, j] -= ka * kb * count_u * count_v
            budget.inspect(out[i], 'convolution offset correction')
    return _trim(out)


def _power_to_bernstein(a, budget):
    def axis(a):
        n = a.shape[0] - 1
        scale = math.lcm(*(math.comb(n, k) for k in range(n + 1)))
        out = budget.zeros(a.shape)
        for i in range(n + 1):
            for k in range(i + 1):
                factor = math.comb(i, k) * (scale // math.comb(n, k))
                budget.check('power to integer Bernstein', 2 * a.shape[1])
                out[i] += factor * a[k]
                budget.inspect(out[i], 'power to integer Bernstein')
        return out, scale
    u, scale_u = axis(a)
    v, scale_v = axis(u.T)
    denominator = scale_u * scale_v
    budget.inspect(denominator, 'Bernstein common denominator')
    return v.T, denominator


def _split(a, axis, budget):
    if axis:
        return tuple(x.T for x in _split(a.T, 0, budget))
    n = a.shape[0] - 1
    left, right, work = (budget.zeros(a.shape) for _ in range(3))
    work[:] = a
    for k in range(n + 1):
        budget.check('dyadic Bernstein subdivision', work.size + 2 * a.shape[1])
        factor = 1 << (n - k)
        left[k], right[n - k] = work[0] * factor, work[-1] * factor
        budget.inspect((left[k], right[n - k]), 'dyadic Bernstein subdivision')
        if k < n:
            work[:-1] = work[:-1] + work[1:]
            work = work[:-1]
            budget.inspect(work, 'dyadic de Casteljau sums')
    return left, right


def _strict_positive(coeff, denominator, budget):
    # Integer (index, depth) intervals retain exact dyadic endpoints without
    # converting the covered boxes to floating point or dropping any strip.
    pending = [(coeff, denominator, (0, 0, 0, 0), 0)]
    cells, leaves, used_depth, lower_bound = 0, 0, 0, None
    while pending:
        if cells >= _MAX_CELLS:
            raise _NotCertified('cell_budget_exhausted')
        a, den, box, depth = pending.pop()
        cells += 1
        used_depth = max(used_depth, depth)
        budget.check('closed-square strict sign', a.size)
        lower = min(a.flat)
        if lower > 0:
            bound = Fraction(int(lower), int(den))
            lower_bound = bound if lower_bound is None else min(lower_bound, bound)
            leaves += 1
            continue
        if min(a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]) <= 0:
            raise _NotCertified('nonpositive_exact_quotient_corner')
        if depth >= _MAX_DEPTH:
            raise _NotCertified('unresolved_quotient_at_depth_limit')
        axis = depth % 2
        if a.shape[axis] == 1:
            axis = 1 - axis
        first, second = _split(a, axis, budget)
        new_den = den << (a.shape[axis] - 1)
        budget.inspect(new_den, 'subdivision common denominator')
        i, du, j, dv = box
        boxes = ((2 * i, du + 1, j, dv), (2 * i + 1, du + 1, j, dv)) if axis == 0 else (
            (i, du, 2 * j, dv + 1), (i, du, 2 * j + 1, dv + 1))
        pending.extend(((second, new_den, boxes[1], depth + 1),
                        (first, new_den, boxes[0], depth + 1)))
    return lower_bound, dict(cells=cells, positive_leaf_count=leaves,
                             maximum_binary_depth=used_depth,
                             domain_covered='entire closed unit square')


def certify_isolated_upper_chart(descriptor, reference_normal, expected_sign,
                                 cancelled=None, deadline=None):
    """Return passed/reason/proof; invalid, cancelled or unresolved means false.

    Deadline is absolute time.monotonic() time. It only shortens the hard
    per-chart budget. No limits, exceptions or approval are read from arbitrary
    descriptor fields. Caller-owned physical approval remains a separate gate.
    """
    budget = None
    stage = 'input'
    proof = dict(scope=_SCOPE, arithmetic='exact integers of supplied binary64 values',
                 domain=[[0., 1.], [0., 1.]],
                 local_immersion_certified=False, global_injectivity_certified=False,
                 g2_certified=False, physical_corner_approval_verified=False,
                 excluded_positive_radius=0.0)
    try:
        budget = _Budget(cancelled, deadline)
        cp, normal = _inputs(descriptor, reference_normal, expected_sign, budget)
        proof.update(physical_corner_id=descriptor['approved_physical_corner_id'],
                     expected_sign=int(expected_sign), reference_normal=normal.tolist(),
                     constant_homogeneous_pole_row=True,
                     positive_weight_certificate='strictly positive input Bernstein weights')
        H, _ = _dyadic_integers(cp, budget)
        N, ne = _dyadic_integers(normal, budget)
        axis = max(range(3), key=lambda k: abs(N[k]))
        i, j = (axis + 1) % 3, (axis + 2) % 3
        X, Y = budget.zeros(H.shape[:2]), budget.zeros(H.shape[:2])
        for row in range(H.shape[0]):
            budget.check('homogeneous normal projection', 6 * H.shape[1])
            X[row] = N[axis] * H[row, :, i] - N[i] * H[row, :, axis]
            Y[row] = N[axis] * H[row, :, j] - N[j] * H[row, :, axis]
            budget.inspect((X[row], Y[row]), 'homogeneous normal projection')
        stage = 'exact_projected_Jacobian'
        X, Y, W = (_bernstein_to_power(a, budget) for a in (X, Y, H[:, :, 3]))
        Xu, Xv = _derivative(X, 0, budget), _derivative(X, 1, budget)
        Yu, Yv = _derivative(Y, 0, budget), _derivative(Y, 1, budget)
        Wu, Wv = _derivative(W, 0, budget), _derivative(W, 1, budget)
        def conv(a, b):
            return _convolve(a, b, budget)
        def cross2(a, b, c, d):
            return _add(conv(a, b), conv(c, d), budget, sign=-1)
        # W^3 times the projected rational Jacobian, avoiding spurious W
        # factors from the otherwise equivalent W^4 derivative expression.
        J = conv(cross2(Xu, Yv, Xv, Yu), W)
        J = _add(J, conv(cross2(Xu, Y, X, Yu), Wv), budget, sign=-1)
        J = _add(J, conv(cross2(X, Yv, Xv, Y), Wu), budget, sign=-1)
        sign = int(expected_sign) * (1 if N[axis] > 0 else -1)
        for row in range(J.shape[0]):
            budget.check('signed projected Jacobian', J.shape[1])
            J[row] *= sign
        proof['jacobian_numerator_degree'] = [J.shape[0] - 1, J.shape[1] - 1]
        stage = 'exact_radial_factor'
        if any(J[:, 0]):
            raise _NotCertified('radial_factor_not_exact')
        if J.shape[1] < 2:
            raise _NotCertified('identically_zero_projected_Jacobian')
        Q = _trim(J[:, 1:])
        proof['radial_factor'] = dict(parameter='v', symbol='r', collapsed_edge='v=0',
                                     exact_zero_constant_power_column=True,
                                     factors_removed=1, factorization='J(u,r)=r*Q(u,r)',
                                     quotient_strictly_positive_on_closed_square=False)
        proof['quotient_degree'] = [Q.shape[0] - 1, Q.shape[1] - 1]
        stage = 'integer_Bernstein_conversion'
        coefficients, denominator = _power_to_bernstein(Q, budget)
        stage = 'closed_square_subdivision'
        bound, coverage = _strict_positive(coefficients, denominator, budget)
        # H's common dyadic scale cancels against W^3. N's scale is retained
        # explicitly. The largest positive weight bounds W over the square.
        physical_scale = abs(int(N[axis])) * (1 << ne) * int(max(H[:, :, 3].flat)) ** 3
        budget.inspect(physical_scale, 'physical quotient lower bound')
        physical_bound = bound / physical_scale
        budget.inspect(physical_bound, 'physical quotient lower bound')
        proof.update(local_immersion_certified=True, coverage=coverage,
                     signed_projected_Jacobian_over_r_lower_bound=dict(
                         numerator=str(physical_bound.numerator),
                         denominator=str(physical_bound.denominator)),
                     method='exact dyadic integer Bernstein convex-hull subdivision')
        proof['radial_factor'].update(quotient_strictly_positive_on_closed_square=True,
                                     exact_radial_multiplicity=1)
        budget.exact.checkpoint('upper certificate completion', force_cancel=True)
        return dict(passed=True, reason='exact_positive_radial_quotient', proof=proof,
                    budget=budget.report())
    except (_NotCertified, _fj.FanGuardError, ValueError, TypeError, OverflowError,
            MemoryError, IndexError) as exc:
        # Late cancellation/deadline also invalidates any partially built proof.
        proof['local_immersion_certified'] = False
        if 'radial_factor' in proof:
            proof['radial_factor']['quotient_strictly_positive_on_closed_square'] = False
            proof['radial_factor'].pop('exact_radial_multiplicity', None)
        return dict(passed=False, reason=getattr(exc, 'code', None) or str(exc) or type(exc).__name__, stage=stage,
                    proof=proof, budget=budget.report() if budget is not None else {})
