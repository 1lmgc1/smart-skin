using System;
using System.Collections.Generic;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

// Compatibility adapter for the existing physical W tolerance. These original-curve
// intersections are NEVER used to construct the native support, guides or trim curves.
internal sealed class NativeSupportContractScale
{
    internal double Scale;
    internal double OperatorLimit => Math.Max(1e-5 / Scale, 1e-8);
    internal double UsableHalfWidth;
    internal double StraightThreshold;
    internal const double HistoricalValidationFraction = 0.85;
    internal const string Provenance = "LEGACY_PHYSICAL_TOLERANCE_FROM_ORIGINAL_CURVE_INTERSECTIONS_ONLY";

    private sealed class Span
    {
        internal NativeCompareInput.Edge Edge = null!;
        internal Interval Domain;
        internal Point3d[] Controls = Array.Empty<Point3d>();
    }

    internal static NativeSupportContractScale Create(NativeCompareInput input, int upperSide,
        Vector3d normal, Vector3d width, Vector3d depth, Action checkpoint)
    {
        var upper = input.Sides[upperSide]; var lower = input.Sides[(upperSide + 2) % 4];
        var origin = upper[0].Start + (upper[upper.Count - 1].End - upper[0].Start) * 0.5;
        var spans = ReadSpans(upper, checkpoint);
        var box = BoundingBox.Empty; double magnitude = 0;
        foreach (var point in spans.SelectMany(span => span.Controls))
        {
            box.Union(point);
            magnitude = Math.Max(magnitude, Math.Max(Math.Abs(point.X), Math.Max(Math.Abs(point.Y), Math.Abs(point.Z))));
        }
        var threshold = Math.Max(input.Tolerance * 1e-6,
            Math.Max(Math.Max(box.Diagonal.Length, input.Tolerance) * 1e-10, 128 * 2.2204460492503131e-16 * magnitude));
        if (!NativeCompareMath.Finite(threshold) || threshold > input.Tolerance * 0.01)
            throw Unsupported("UNRESOLVED_SOURCE_PRECISION");
        bool Straight(Span span) => Math.Abs((span.Controls[span.Controls.Length - 1] - span.Controls[0]) * width) > threshold
            && span.Controls.All(point => Vector3d.CrossProduct(point - span.Controls[0], width).Length <= threshold);
        var indices = Enumerable.Range(0, spans.Count).Where(i => Straight(spans[i])).ToArray();
        if (indices.Length == 0 || indices[0] == 0 || indices[indices.Length - 1] == spans.Count - 1
            || indices[indices.Length - 1] - indices[0] + 1 != indices.Length)
            throw Unsupported("UNRESOLVED_CENTRAL_STRAIGHT_RUN");
        var central = indices.Select(i => spans[i]).ToList();
        var lineOrigin = central[0].Controls[0];
        var projected = new List<double>();
        foreach (var span in central)
        {
            if (span.Controls.Any(point => Vector3d.CrossProduct(point - lineOrigin, width).Length > threshold))
                throw Unsupported("NONCOLLINEAR_CENTRAL_RUN");
            RequireMonotone(span, origin, width);
            projected.Add((span.Controls[0] - origin) * width);
            projected.Add((span.Controls[span.Controls.Length - 1] - origin) * width);
        }
        var lo = projected.Min(); var hi = projected.Max();
        if (lo >= -input.Tolerance * 10 || hi <= input.Tolerance * 10 || Math.Abs(lo + hi) > input.Tolerance)
            throw Unsupported("NONCENTERED_CENTRAL_RUN");
        var lowerSpans = ReadSpans(lower, checkpoint);
        var lowerOrigin = lower[0].Start;
        foreach (var span in lowerSpans)
        {
            if (span.Controls.Any(point => Vector3d.CrossProduct(point - lowerOrigin, width).Length > input.Tolerance))
                throw Unsupported("NONTRANSVERSE_LOWER_RUN");
            RequireMonotone(span, origin, width);
        }
        var half = Math.Min(Math.Min(-lo, hi), Math.Min(Math.Abs((lower[0].Start - origin) * width),
            Math.Abs((lower[lower.Count - 1].End - origin) * width)));
        if (!NativeCompareMath.Finite(half) || half <= input.Tolerance * 10) throw Unsupported("NO_USABLE_WIDTH");
        var local = BoundingBox.Empty;
        // Five is a historical tolerance-calibration input, not a network topology or guide count.
        for (var station = 0; station < 5; station++)
        {
            var level = HistoricalValidationFraction * half * (station * 0.5 - 1);
            foreach (var chain in new[] { central, lowerSpans })
            {
                var point = AtLevel(chain, origin, width, level, threshold, input.Tolerance, checkpoint);
                var delta = point - origin;
                local.Union(new Point3d(delta * normal, delta * width, delta * depth));
            }
        }
        var scale = Math.Max(local.Diagonal.Length, 1e-9);
        if (!NativeCompareMath.Finite(scale) || scale <= 0) throw Unsupported("INVALID_COMPATIBILITY_SCALE");
        return new NativeSupportContractScale { Scale = scale, UsableHalfWidth = half, StraightThreshold = threshold };
    }

    private static List<Span> ReadSpans(IReadOnlyList<NativeCompareInput.Edge> chain, Action checkpoint)
    {
        var result = new List<Span>();
        foreach (var edge in chain)
        {
            checkpoint();
            using var curve = edge.Native.ToNurbsCurve();
            if (curve is null || curve.SpanCount > 512) throw Unsupported("SOURCE_SPAN_BUDGET");
            var indices = Enumerable.Range(0, curve.SpanCount);
            if (edge.Reverse) indices = indices.Reverse();
            foreach (var i in indices)
            {
                checkpoint();
                var domain = curve.SpanDomain(i);
                using var restricted = curve.Trim(domain);
                using var nurbs = restricted?.ToNurbsCurve();
                if (nurbs is null || nurbs.SpanCount != 1 || nurbs.Points.Count > 512) throw Unsupported("SOURCE_SPAN_RESTRICTION");
                var points = new List<Point3d>();
                foreach (var control in nurbs.Points)
                {
                    if (!control.Location.IsValid || !NativeCompareMath.Finite(control.Weight) || control.Weight <= 0)
                        throw Unsupported("INVALID_POSITIVE_WEIGHT_SOURCE_SPAN");
                    points.Add(control.Location);
                }
                if (edge.Reverse) points.Reverse();
                result.Add(new Span { Edge = edge, Domain = domain, Controls = points.ToArray() });
                if (result.Count > 1024) throw Unsupported("SOURCE_SPAN_BUDGET");
            }
        }
        return result;
    }

    private static void RequireMonotone(Span span, Point3d origin, Vector3d width)
    {
        var values = span.Controls.Select(point => (point - origin) * width).ToArray();
        var sign = Math.Sign(values[values.Length - 1] - values[0]);
        if (sign == 0) throw Unsupported("NONUNIQUE_TRANSVERSE_ROOT");
        for (var i = 1; i < values.Length; i++)
            if (sign * (values[i] - values[i - 1]) < 0) throw Unsupported("NONMONOTONE_TRANSVERSE_ROOT");
    }

    private static Point3d AtLevel(IReadOnlyList<Span> spans, Point3d origin, Vector3d width, double level,
        double precision, double positionalTolerance, Action checkpoint)
    {
        var hits = new List<(Span Span, double Parameter, Point3d Point)>();
        foreach (var span in spans)
        {
            checkpoint();
            var curve = span.Edge.Native; var a = span.Domain.T0; var b = span.Domain.T1;
            double Value(double t) => (curve.PointAt(t) - origin) * width - level;
            var fa = Value(a); var fb = Value(b);
            if (Math.Min(fa, fb) > precision || Math.Max(fa, fb) < -precision) continue;
            double parameter;
            if (Math.Abs(fa) <= precision) parameter = a;
            else if (Math.Abs(fb) <= precision) parameter = b;
            else
            {
                if (Math.Sign(fa) == Math.Sign(fb)) throw Unsupported("UNRESOLVED_TRANSVERSE_ROOT");
                for (var i = 0; i < 80; i++)
                {
                    checkpoint();
                    var mid = a + (b - a) * 0.5;
                    if (mid == a || mid == b) break;
                    var fm = Value(mid);
                    if (!NativeCompareMath.Finite(fm)) throw Unsupported("NONFINITE_TRANSVERSE_ROOT");
                    if (fm == 0) { a = b = mid; break; }
                    if (Math.Sign(fm) == Math.Sign(fa)) { a = mid; fa = fm; } else b = mid;
                }
                parameter = a + (b - a) * 0.5;
            }
            var point = curve.PointAt(parameter);
            if (!point.IsValid || Math.Abs((point - origin) * width - level) > Math.Max(positionalTolerance * 1e-4, 1e-9))
                throw Unsupported("TRANSVERSE_ROOT_RESIDUAL");
            bool SameRoot((Span Span, double Parameter, Point3d Point) old)
            {
                if (old.Point.DistanceTo(point) > positionalTolerance) return false;
                if (ReferenceEquals(old.Span.Edge, span.Edge))
                    return old.Parameter == parameter
                        && (parameter == old.Span.Domain.T0 || parameter == old.Span.Domain.T1)
                        && (parameter == span.Domain.T0 || parameter == span.Domain.T1);
                // Capture already proved each distinct source endpoint has one unique partner.
                // No near-parameter clustering can merge different interior roots.
                bool Endpoint(NativeCompareInput.Edge edge, double t) => t == edge.Native.Domain.T0 || t == edge.Native.Domain.T1;
                return Endpoint(old.Span.Edge, old.Parameter) && Endpoint(span.Edge, parameter);
            }
            if (!hits.Any(SameRoot)) hits.Add((span, parameter, point));
        }
        if (hits.Count != 1) throw Unsupported("NONUNIQUE_TRANSVERSE_ROOT");
        return hits[0].Point;
    }

    private static NativeCompareUnsupported Unsupported(string reason) => new("PHYSICAL_TOLERANCE_COMPATIBILITY_" + reason);
}
