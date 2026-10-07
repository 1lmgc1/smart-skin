using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal static class NativeSupportTrimmer
{
    internal static void Trim(string name, Surface surface, NativeSupportEvaluation precheck, NativeCompareInput input,
        NativeSupportSource source, List<NativeCompareCandidate> previews, Action checkpoint, Action<string> write)
    {
        var watch = Stopwatch.StartNew();
        Curve? originalLoop = null; Brep? newSupport = null; Brep? fragments = null;
        var regions = new List<Brep>();
        try
        {
            // Incidence and UV-branch screens use independently mapped ORIGINAL source stations.
            // Do not require a fitted Pullback at document tolerance to meet an unrelated 1e-8 UV fit tolerance.
            if (!precheck.Eligible || precheck.NormalizedLoop is null)
                throw new NativeCompareUnsupported("SUPPORT_PRECHECK_NOT_ELIGIBLE");
            originalLoop = OriginalLoop(input);
            newSupport = surface.ToBrep(); // Only this newly allocated support face is split.
            if (newSupport is null || !NativeCompareMeasure.Bounded(newSupport, out _))
                throw new NativeCompareUnsupported("INVALID_NEW_SUPPORT_BREP");
            checkpoint();
            var splitWatch = Stopwatch.StartNew();
            fragments = newSupport.Faces[0].Split(input.Sides.SelectMany(side => side).Select(edge => (Curve)edge.Native), input.Tolerance);
            var splitMilliseconds = splitWatch.ElapsedMilliseconds;
            if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
            write("SMARTSKIN_NATIVE_SUPPORT_SPLIT | support=" + name + " | native_ms=" + splitMilliseconds
                + " | cutters=ORIGINAL_FINITE_SELECTED_3D_BREP_EDGES | split_target=NEW_UNTRIMMED_SUPPORT_ONLY"
                + " | fitted_pullback_gate=NONE | UV_screen=INDEPENDENT_SOURCE_AND_RETURNED_TRIMS | support_extended=false | parent_modified=false");
            if (fragments is null || !fragments.IsValid || fragments.Faces.Count == 0 || fragments.Faces.Count > 16)
                throw new NativeCompareUnsupported("SPLIT_FAILED_OR_FRAGMENT_LIMIT");
            var eligibility = new List<bool>();
            foreach (var face in fragments.Faces)
            {
                checkpoint();
                var region = face.DuplicateFace(false); regions.Add(region);
                var eligible = RegionCorrespondence(region, originalLoop, source, input, checkpoint, out var report);
                eligibility.Add(eligible);
                write("SMARTSKIN_NATIVE_SUPPORT_REGION | support=" + name + " | index=" + (regions.Count - 1)
                    + " | " + report + " | area_ranking=NONE | sampled_candidate_eligible=" + eligible);
            }
            var selected = NativeSupportTrimPolicy.UniqueIndex(eligibility);
            if (selected < 0) throw new NativeCompareUnsupported(selected == -2 ? "AMBIGUOUS_COMPLETE_SPLIT_REGIONS" : "NO_COMPLETE_ORIGINAL_LOOP_SPLIT_REGION");
            var chosen = regions[selected];
            using var finalSurface = chosen.Faces[0].DuplicateSurface();
            using var finalCheck = NativeSupportMeasure.Evaluate(name + ":TrimmedBoundary", finalSurface, source, checkpoint, write, chosen.Faces[0]);
            if (!finalCheck.Eligible) throw new NativeCompareUnsupported("TRIMMED_ORIGINAL_BOUNDARY_RECHECK_FAILED");
            var copy = chosen.DuplicateBrep();
            try { previews.Add(new NativeCompareCandidate(name + ":Trimmed:FINITE_CHECKS_ONLY:NOT_VERIFIED", copy)); copy = null!; }
            finally { copy?.Dispose(); }
            write("SMARTSKIN_NATIVE_SUPPORT_TRIM | support=" + name + " | disposition=ONE_ORIGINAL_LOOP_REGION_WITH_SAMPLED_BOUNDARY_PRECHECK"
                + " | elapsed_ms=" + watch.ElapsedMilliseconds + " | global_G2=NOT_VERIFIED | separation=NOT_VERIFIED | Add_available=false");
        }
        catch (NativeCompareUnsupported exception)
        { write("SMARTSKIN_NATIVE_SUPPORT_TRIM | support=" + name + " | disposition=" + exception.Message + " | elapsed_ms=" + watch.ElapsedMilliseconds + " | no_fallback=true"); }
        finally
        {
            foreach (var region in regions) region.Dispose();
            fragments?.Dispose(); newSupport?.Dispose(); originalLoop?.Dispose();
        }
    }

    private static bool RegionCorrespondence(Brep region, Curve originalLoop, NativeSupportSource source,
        NativeCompareInput input, Action checkpoint, out string report)
    {
        report = "status=INVALID_REGION";
        if (!NativeCompareMeasure.Bounded(region, out _)) return false;
        var outer = region.Loops.Count(loop => loop.LoopType == BrepLoopType.Outer);
        var inner = region.Loops.Count - outer;
        if (outer != 1 || inner != 0) { report = "outer_loops=" + outer + " | undeclared_holes_or_rims=" + inner; return false; }
        if (!ReturnedTrimLoopIsSimple(region.Faces[0])) { report = "status=RETURNED_TRIM_UV_LOOP_NOT_SIMPLE_OR_CLOSED"; return false; }
        var edges = region.Edges.Where(edge => edge.Valence == EdgeAdjacency.Naked).ToArray();
        var passedSources = 0;
        foreach (var group in source.Stations.GroupBy(station => station.Source))
        {
            var complete = true;
            foreach (var station in group)
            {
                checkpoint();
                if (!ClosestGap(station.Point, edges, out var gap) || gap > input.Tolerance) complete = false;
            }
            if (complete) passedSources++;
        }
        var passedBoundary = 0;
        foreach (var edge in edges)
        {
            checkpoint();
            if (DirectedBoundaryCoverage(edge, input.Edges.Select(sourceEdge => sourceEdge.Native).ToArray(), input.Tolerance, checkpoint)) passedBoundary++;
        }
        // Native edge direction need not follow boundary traversal. The actual outer trim loop owns that order.
        using var boundary = region.Loops.Single(loop => loop.LoopType == BrepLoopType.Outer).To3dCurve();
        var loopGap = double.NaN;
        var loopMatched = boundary is not null && boundary.IsClosed && CurveGap(originalLoop, boundary, input.Tolerance, out loopGap);
        var eligible = NativeSupportTrimPolicy.RegionEligible(region.IsValid, outer, inner, loopMatched,
            input.Edges.Count, passedSources, edges.Length, passedBoundary,
            passedSources == input.Edges.Count && passedBoundary == edges.Length);
        report = "outer_loops=" + outer + " | undeclared_holes=" + inner + " | fully_sampled_source_pieces=" + passedSources + "/" + input.Edges.Count
            + " | original_unjoined_locus_output_edges=" + passedBoundary + "/" + edges.Length + " | original_closed_loop_matched=" + loopMatched
            + " | native_loop_gap=" + NativeCompareProbeProtocol.Number(loopGap) + " | boundary_order=ACTUAL_OUTER_TRIM_TRAVERSAL"
            + " | continuity_not_inferred_from_region_selection=true";
        return eligible;
    }

    private static bool DirectedBoundaryCoverage(BrepEdge edge, IReadOnlyList<BrepEdge> originalPieces, double tolerance, Action checkpoint)
    {
        // A single output edge is a subset of the original loop: never require the entire
        // closed source loop to lie on this one edge. The joined-loop test below is bidirectional.
        using var nurbs = edge.ToNurbsCurve();
        if (nurbs is null || nurbs.Points.Count > 2048 || edge.SpanCount > 1024) return false;
        var measured = 0;
        for (var span = 0; span < edge.SpanCount; span++)
        {
            var domain = edge.SpanDomain(span);
            var a = Math.Max(domain.T0, edge.Domain.T0); var b = Math.Min(domain.T1, edge.Domain.T1);
            if (b <= a) continue;
            foreach (var fraction in new[] { 0.0, 1e-7, 1e-5, .25, .5, .75, 1 - 1e-5, 1 - 1e-7, 1.0 })
            {
                checkpoint();
                if (++measured > 8192) return false;
                var point = edge.PointAt(a + (b - a) * fraction);
                if (!ClosestGap(point, originalPieces, out var gap) || gap > tolerance) return false;
            }
        }
        return measured > 0;
    }

    private static bool ClosestGap(Point3d point, IEnumerable<BrepEdge> edges, out double gap)
    {
        gap = double.PositiveInfinity;
        foreach (var edge in edges)
        {
            if (!edge.ClosestPoint(point, out var parameter)) return false;
            var distance = edge.PointAt(parameter).DistanceTo(point);
            if (!NativeCompareMath.Finite(distance)) return false;
            gap = Math.Min(gap, distance);
        }
        return NativeCompareMath.Finite(gap);
    }
    private static bool CurveGap(Curve a, Curve b, double tolerance, out double gap)
    {
        gap = double.NaN;
        var measure = tolerance * .1;
        if (measure <= 0 || !Curve.GetDistancesBetweenCurves(a, b, measure, out var forward, out _, out _, out _, out _, out _)
            || !Curve.GetDistancesBetweenCurves(b, a, measure, out var reverse, out _, out _, out _, out _, out _)) return false;
        gap = Math.Max(forward, reverse);
        return NativeCompareMath.Finite(gap) && gap <= tolerance;
    }
    private static bool ReturnedTrimLoopIsSimple(BrepFace face)
    {
        if (face.Loops.Count != 1 || face.Loops[0].LoopType != BrepLoopType.Outer) return false;
        using var uv = face.Loops[0].To2dCurve();
        if (uv is null || !uv.IsClosed) return false;
        var u = face.Domain(0); var v = face.Domain(1);
        if (!NativeCompareMath.Finite(u.Length) || !NativeCompareMath.Finite(v.Length) || u.Length <= 0 || v.Length <= 0) return false;
        var normalize = Transform.Identity;
        normalize.M00 = 1 / u.Length; normalize.M03 = -u.T0 / u.Length;
        normalize.M11 = 1 / v.Length; normalize.M13 = -v.T0 / v.Length;
        return uv.Transform(normalize) && NativeSupportMeasure.Simple(uv);
    }

    private static Curve OriginalLoop(NativeCompareInput input)
    {
        var copies = new List<Curve>();
        try
        {
            foreach (var edge in input.Sides.SelectMany(side => side))
            {
                var copy = edge.Native.DuplicateCurve();
                try
                {
                    if (copy is null || (edge.Reverse && !copy.Reverse()))
                        throw new NativeCompareUnsupported("ORIGINAL_LOOP_VERIFICATION_COPY_FAILED");
                    copies.Add(copy); copy = null!;
                }
                finally { copy?.Dispose(); }
            }
            return JoinOne(copies, input.Tolerance);
        }
        finally { foreach (var curve in copies) curve.Dispose(); }
    }
    private static Curve JoinOne(IEnumerable<Curve> pieces, double tolerance)
    {
        var joined = Curve.JoinCurves(pieces, tolerance, true);
        if (joined is null || joined.Length != 1)
        { if (joined is not null) foreach (var curve in joined) curve.Dispose(); throw new NativeCompareUnsupported("UNRESOLVED_SINGLE_BOUNDARY_LOOP"); }
        return joined[0];
    }
}
