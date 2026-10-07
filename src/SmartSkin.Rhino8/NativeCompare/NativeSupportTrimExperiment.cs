using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Rhino.Geometry;

namespace SmartSkin.Rhino8;

internal sealed class NativeSupportCandidate : IDisposable
{
    internal readonly string Name;
    internal readonly Brep Brep;
    internal NativeSupportCandidate(string name, Brep brep) { Name = name; Brep = brep; }
    public void Dispose() => Brep.Dispose();
}

internal static class NativeSupportTrimExperiment
{
    internal static void Run(NativeCompareInput input, NativeCompareSideBinding seedBinding,
        IReadOnlyList<NativeSupportCandidate> matches, List<NativeCompareCandidate> previews, Action checkpoint, Action<string> write)
    {
        NativeSupportSource source;
        try { source = NativeSupportSource.Create(input, checkpoint); }
        catch (NativeCompareUnsupported exception)
        { write("SMARTSKIN_NATIVE_SUPPORT_END | disposition=" + exception.Message + " | no_support_built=true"); return; }
        var eligibleCorners = new List<bool>();
        foreach (var match in matches)
        {
            checkpoint();
            var corners = OriginalCornerIncidences(match.Brep, input, seedBinding);
            eligibleCorners.Add(corners);
            write("SMARTSKIN_NATIVE_SUPPORT_CHOICE | match=" + match.Name + " | expected_natural_corner_incidences=" + corners
                + " | corner_binding=ORIGINAL_NATURAL_SIDE_ADJACENCY | boundary_edge_gap_is_not_support_gap=true | UV_loop_and_jets_pending=true");
        }
        var chosen = NativeSupportTrimPolicy.UniqueIndex(eligibleCorners);
        if (chosen >= 0) ProbeAndTrim(matches[chosen].Name + "Support", matches[chosen].Brep, input, source, previews, checkpoint, write);
        else write("SMARTSKIN_NATIVE_SUPPORT_CHOICE | disposition=" + (chosen == -2 ? "AMBIGUOUS_MATCH_CORNER_INCIDENCE" : "NO_MATCH_PRESERVES_EXPECTED_NATURAL_CORNER_INCIDENCE")
            + " | no_reverse_flag_hardcoded=true");

        Brep? blend = null;
        try
        {
            checkpoint();
            var first = input.Sides[(source.UpperSide + 1) % 4];
            var second = input.Sides[(source.UpperSide + 3) % 4];
            if (first.Count != 1 || second.Count != 1) throw new NativeCompareUnsupported("UNSUPPORTED_COMPOUND_NATURAL_SIDE_BLEND_BINDING");
            var a = first[0]; var b = second[0];
            var upper = input.Sides[source.UpperSide]; var lower = input.Sides[(source.UpperSide + 2) % 4];
            if (a.Start.DistanceTo(upper[upper.Count - 1].End) > input.Tolerance || b.End.DistanceTo(upper[0].Start) > input.Tolerance
                || a.End.DistanceTo(lower[0].Start) > input.Tolerance || b.Start.DistanceTo(lower[lower.Count - 1].End) > input.Tolerance)
                throw new NativeCompareUnsupported("UNRESOLVED_BLEND_ENDPOINT_CORRESPONDENCE");
            var watch = Stopwatch.StartNew();
            var result = Brep.CreateBlendSurface(NativeCompareMeasure.Face(a.Native)!, a.Native, a.Native.Domain, a.Reverse, BlendContinuity.Curvature,
                NativeCompareMeasure.Face(b.Native)!, b.Native, b.Native.Domain, !b.Reverse, BlendContinuity.Curvature);
            var nativeMilliseconds = watch.ElapsedMilliseconds;
            if (result is null || result.Length == 0) throw new NativeCompareUnsupported("NATIVE_SIDE_BLEND_FAILED");
            if (result.Length != 1)
            { foreach (var item in result) item.Dispose(); throw new NativeCompareUnsupported("UNSUPPORTED_MULTIPATCH_SIDE_BLEND"); }
            blend = result[0];
            if (!input.CopiesUnchanged()) throw new InvalidOperationException("COPIED_NATIVE_TARGET_CHANGED");
            write("SMARTSKIN_NATIVE_SUPPORT_BLEND | native_ms=" + nativeMilliseconds + " | first=" + a.Label + " | second=" + b.Label
                + " | first_reverse=" + a.Reverse + " | second_reverse=" + !b.Reverse
                + " | finite_domains=ORIGINAL_SELECTED_EDGES | endpoint_pairing=UPPER_TO_LOWER | requested=G2 | measured_G2=NOT_VERIFIED");
            if (!NativeCompareMeasure.Bounded(blend, out _)) throw new NativeCompareUnsupported("INVALID_OR_OVER_LIMIT_SIDE_BLEND");
            ProbeAndTrim("NativeSideBlendSupport", blend, input, source, previews, checkpoint, write);
        }
        catch (NativeCompareUnsupported exception)
        { write("SMARTSKIN_NATIVE_SUPPORT_BLEND | disposition=" + exception.Message + " | no_fallback=true"); }
        finally { blend?.Dispose(); }
    }

    private static bool OriginalCornerIncidences(Brep candidate, NativeCompareInput input, NativeCompareSideBinding binding)
    {
        var seen = new HashSet<int>();
        for (var side = 0; side < 4; side++)
        {
            var a = binding.Resolve(candidate, (side + 3) % 4); var b = binding.Resolve(candidate, side);
            if (a is null || b is null) return false;
            var shared = new[] { a.StartVertex, a.EndVertex }.Where(vertex => vertex is not null
                && (vertex.VertexIndex == b.StartVertex.VertexIndex || vertex.VertexIndex == b.EndVertex.VertexIndex)).ToArray();
            if (shared.Length != 1 || !seen.Add(shared[0].VertexIndex)) return false;
            var previous = input.Sides[(side + 3) % 4];
            if (shared[0].Location.DistanceTo(previous[previous.Count - 1].End) > input.Tolerance
                || shared[0].Location.DistanceTo(input.Sides[side][0].Start) > input.Tolerance) return false;
        }
        return seen.Count == 4;
    }

    private static void ProbeAndTrim(string name, Brep candidate, NativeCompareInput input, NativeSupportSource source,
        List<NativeCompareCandidate> previews, Action checkpoint, Action<string> write)
    {
        using var surface = candidate.Faces[0].DuplicateSurface(); // A NEW untrimmed support; no original parent is edited.
        if (surface is null) { write("SMARTSKIN_NATIVE_SUPPORT_END | support=" + name + " | disposition=NO_UNTRIMMED_SUPPORT"); return; }
        using var evidence = NativeSupportMeasure.Evaluate(name, surface, source, checkpoint, write);
        if (!evidence.Eligible)
        {
            write("SMARTSKIN_NATIVE_SUPPORT_TRIM | support=" + name + " | disposition=NOT_ATTEMPTED_PRECHECK_REJECTED"
                + " | no_extension=true | no_tolerance_increase=true");
            return;
        }
        NativeSupportTrimmer.Trim(name, surface, evidence, input, source, previews, checkpoint, write);
    }
}
