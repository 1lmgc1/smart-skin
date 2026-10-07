using System;
using System.Collections.Generic;
using System.Linq;
using Rhino.Geometry;
using Rhino.Geometry.Intersect;

namespace SmartSkin.Rhino8;

internal sealed class NativeSupportEvaluation : IDisposable
{
    internal readonly List<(NativeSupportSource.Station Station, Point2d UV)> Mapped = new();
    internal Curve? NormalizedLoop;
    internal bool Eligible;
    internal string Disposition = "NOT_EVALUATED";
    internal int RegularityWitnesses;
    public void Dispose() => NormalizedLoop?.Dispose();
}

internal static class NativeSupportMeasure
{
    internal const double NormalizedUvTolerance = 1e-8;
    private sealed class Worst
    {
        internal double Value = double.NaN;
        internal NativeSupportSource.Station? Station;
        internal Point2d UV;
        internal void Add(double value, NativeSupportSource.Station station, Point2d uv)
        {
            if (NativeCompareMath.Finite(value) && (double.IsNaN(Value) || value > Value)) { Value = value; Station = station; UV = uv; }
        }
        internal string Format(string key) => key + "=" + NativeCompareProbeProtocol.Number(Value)
            + " | " + key + "_source_t=" + NativeCompareProbeProtocol.Number(Station?.Parameter ?? double.NaN)
            + " | " + key + "_kind=" + (Station?.Kind ?? "NOT_VERIFIED")
            + " | " + key + "_uv=(" + NativeCompareProbeProtocol.Number(Station is null ? double.NaN : UV.X) + "," + NativeCompareProbeProtocol.Number(Station is null ? double.NaN : UV.Y) + ")";
    }

    internal static NativeSupportEvaluation Evaluate(string name, Surface support, NativeSupportSource source,
        Action checkpoint, Action<string> write, BrepFace? activeRegion = null)
    {
        var result = new NativeSupportEvaluation();
        var policy = source.Policy;
        var positionTolerance = source.PositionTolerance;
        var angleTolerance = source.AngleToleranceRadians;
        var all = policy is not null;
        var incidenceFailed = false; var jetsFailed = false; var mappingFailed = false;
        try
        {
            if (support.IsClosed(0) || support.IsClosed(1) || support.IsPeriodic(0) || support.IsPeriodic(1))
                throw new NativeCompareUnsupported("UNSUPPORTED_PERIODIC_SUPPORT_UV_BRANCH");
            foreach (var group in source.Stations.GroupBy(station => station.Source))
            {
                var gapWorst = new Worst(); var angleWorst = new Worst(); var operatorWorst = new Worst();
                var projectedAngle = new Worst(); var projectedW = new Worst();
                string? firstFailure = null;
                var resolved = 0; var passed = 0; var clipped = 0; var ambiguous = 0; var frames = 0; var upperPoints = 0;
                var gapFailures = 0; var angleFailures = 0; var operatorFailures = 0; var frameFailures = 0;
                foreach (var station in group)
                {
                    checkpoint();
                    var mapped = Map(support, station.Point, positionTolerance, checkpoint,
                        out var uv, out var gap, out var reason);
                    if (reason == "DOMAIN_BOUNDARY_WITH_GAP") clipped++;
                    if (reason == "AMBIGUOUS_UV_BRANCH") ambiguous++;
                    NativeCompareMeasure.SurfaceFrame a = null!, b = null!;
                    var boundaryRegular = false;
                    if (mapped && activeRegion is not null)
                    {
                        mapped = BoundaryLocation(activeRegion, station.Point, positionTolerance,
                            out uv, out gap, out a, out boundaryRegular, out reason);
                        if (mapped && activeRegion.IsPointOnFace(uv.X, uv.Y, positionTolerance) == PointFaceRelation.Exterior)
                        { mapped = false; reason = "OUTSIDE_TRIMMED_REGION"; }
                    }
                    if (mapped) resolved++;
                    gapWorst.Add(gap, station, uv);
                    var regular = mapped && (activeRegion is null ? TryFrame(support, uv.X, uv.Y, out a) : boundaryRegular)
                        && NativeCompareMeasure.Frame(station.Source.Native, station.Parameter, positionTolerance, out b);
                    double angle = double.NaN, residual = double.NaN;
                    if (regular)
                    {
                        var dot = Math.Max(-1, Math.Min(1, a.Normal * b.Normal));
                        angle = Math.Acos(Math.Abs(dot));
                        residual = NativeCompareMath.OperatorSpectralResidual(a.Operator, b.Operator, dot < 0 ? -1 : 1);
                        frames++;
                        projectedAngle.Add(angle, station, uv); projectedW.Add(residual, station, uv);
                        if (gap <= positionTolerance && !station.UpperPoint)
                        { angleWorst.Add(angle, station, uv); operatorWorst.Add(residual, station, uv); }
                    }
                    if (station.UpperPoint)
                    {
                        upperPoints++;
                        write("SMARTSKIN_NATIVE_SUPPORT_UPPER_POINT | support=" + name + " | source=" + station.Source.Label
                            + " | source_t=" + NativeCompareProbeProtocol.Number(station.Parameter)
                            + " | gap=" + NativeCompareProbeProtocol.Number(gap) + " | angle_radians=" + NativeCompareProbeProtocol.Number(angle)
                            + " | full_W=" + NativeCompareProbeProtocol.Number(residual)
                            + " | scope=EXACT_ROLE_BOUND_UPPER_ATTACHMENT_POINT_ONLY | position_required=true");
                    }
                    if (!mapped) mappingFailed = true;
                    if (!NativeCompareMath.Finite(gap) || gap > positionTolerance) { incidenceFailed = true; gapFailures++; }
                    if (mapped && gap <= positionTolerance && !station.UpperPoint)
                    {
                        if (!regular) { jetsFailed = true; frameFailures++; }
                        if (!NativeCompareMath.Finite(angle) || angle > angleTolerance) { jetsFailed = true; angleFailures++; }
                        if (policy is not null && (!NativeCompareMath.Finite(residual) || residual > policy.OperatorTolerance)) { jetsFailed = true; operatorFailures++; }
                    }
                    var stationPassed = policy?.StationEligible(mapped, regular, gap, angle, residual, station.UpperPoint) ?? false;
                    if (stationPassed) passed++;
                    else
                    {
                        all = false;
                        firstFailure ??= "t=" + NativeCompareProbeProtocol.Number(station.Parameter) + ",kind=" + station.Kind
                            + ",uv=(" + NativeCompareProbeProtocol.Number(uv.X) + "," + NativeCompareProbeProtocol.Number(uv.Y) + "),reason="
                            + (policy is null ? "PHYSICAL_W_CONTRACT_UNRESOLVED" : !mapped ? reason : gap > positionTolerance ? "SUPPORT_G0_GAP"
                                : !regular ? "SOURCE_OR_SUPPORT_FRAME_UNRESOLVED" : angle > angleTolerance ? "PARENT_NORMAL" : "PARENT_FULL_W");
                    }
                    if (mapped) result.Mapped.Add((station, uv));
                }
                write("SMARTSKIN_NATIVE_SUPPORT_SOURCE | support=" + name + " | source=" + group.Key.Label
                    + " | side=" + group.First().Side + " | expected=" + group.Count() + " | resolved=" + resolved
                    + " | precheck_passed=" + passed + " | frames=" + frames + " | domain_boundary_with_gap=" + clipped
                    + " | ambiguous_uv=" + ambiguous + " | exact_upper_points=" + upperPoints
                    + " | gap_failures=" + gapFailures + " | angle_failures=" + angleFailures
                    + " | W_failures=" + operatorFailures + " | frame_failures=" + frameFailures
                    + " | " + gapWorst.Format("support_gap") + " | " + angleWorst.Format("strict_angle_radians")
                    + " | " + operatorWorst.Format("strict_full_W_spectral")
                    + " | " + projectedAngle.Format("projected_angle_radians") + " | " + projectedW.Format("projected_full_W_spectral")
                    + " | first_failure=" + (firstFailure ?? "NONE")
                    + " | finite_bands=NONE_EXCLUDED | measure_target=" + (activeRegion is null ? "UNDERLYING_SUPPORT" : "FINAL_TRIMMED_BOUNDARY"));
            }
            if (result.Mapped.Count != source.Stations.Count) all = false;
            if (all)
            {
                result.NormalizedLoop = SampledLoop(support, result.Mapped);
                if (!InteriorRegularity(support, result.NormalizedLoop, checkpoint, out result.RegularityWitnesses))
                    throw new NativeCompareUnsupported("UNRESOLVED_SELECTED_REGION_REGULARITY");
            }
            result.Eligible = all;
            result.Disposition = policy is null ? "PHYSICAL_W_CONTRACT_UNRESOLVED_METRICS_ONLY" : all ? "SAMPLED_SUPPORT_PRECHECK_ELIGIBLE"
                : mappingFailed ? "UNRESOLVED_SUPPORT_UV_MAPPING"
                : incidenceFailed && jetsFailed ? "SUPPORT_G0_AND_PARENT_JET_PRECHECK_FAILURE"
                : incidenceFailed ? "SUPPORT_G0_INCIDENCE_FAILURE" : "SUPPORT_PARENT_JET_PRECHECK_FAILURE";
        }
        catch (NativeCompareUnsupported exception) { result.Disposition = exception.Message; result.Eligible = false; }
        catch { result.Dispose(); throw; }
        write("SMARTSKIN_NATIVE_SUPPORT_PRECHECK | support=" + name + " | disposition=" + result.Disposition
            + " | G0=" + NativeCompareProbeProtocol.Number(positionTolerance)
            + " | angle_radians=" + NativeCompareProbeProtocol.Number(angleTolerance)
            + " | angle_degrees=" + NativeCompareProbeProtocol.Number(angleTolerance * 180 / Math.PI)
            + " | source_control_hull_scale=" + NativeCompareProbeProtocol.Number(source.FullHullScale)
            + " | full_hull_W_reference_only=" + NativeCompareProbeProtocol.Number(1e-5 / source.FullHullScale)
            + " | full_hull_is_not_a_gate=true | contract_scale=" + NativeCompareProbeProtocol.Number(source.Compatibility?.Scale ?? double.NaN)
            + " | W_contract=" + source.ContractStatus
            + " | absolute_full_W_limit=" + NativeCompareProbeProtocol.Number(policy?.OperatorTolerance ?? double.NaN)
            + " | stations=" + source.Stations.Count + " | max_stations=" + NativeSupportSource.MaximumStations
            + " | uv_tolerance_normalized=" + NormalizedUvTolerance
            + " | regularity=SOURCE_STATIONS_AND_SELECTED_INTERIOR_GRID | regularity_min_witnesses=9"
            + " | regularity_witnesses=" + result.RegularityWitnesses + " | global_branch_and_separation=NOT_VERIFIED"
            + " | threshold_preserves_existing_physical_contract=" + (policy is not null) + " | sampled_screen_not_production_certificate=true"
            + " | rejection_is_not_geometric_impossibility=true | production_acceptance=NOT_VERIFIED | global_G2=NOT_VERIFIED");
        return result;
    }

    internal static bool Map(Surface surface, Point3d point, double tolerance, Action checkpoint,
        out Point2d uv, out double gap, out string reason)
    {
        uv = new Point2d(double.NaN, double.NaN); gap = double.NaN; reason = "UV_MAPPING_FAILED";
        if (!surface.ClosestPoint(point, out var u, out var v)) return false;
        uv = new Point2d(u, v);
        var unit = Normalize(surface, uv);
        if (!unit.IsValid || unit.X < -NormalizedUvTolerance || unit.X > 1 + NormalizedUvTolerance
            || unit.Y < -NormalizedUvTolerance || unit.Y > 1 + NormalizedUvTolerance) { reason = "OUTSIDE_FINITE_SUPPORT_DOMAIN"; return false; }
        gap = surface.PointAt(u, v).DistanceTo(point);
        if (!NativeCompareMath.Finite(gap)) return false;
        if (gap > tolerance && (unit.X <= NormalizedUvTolerance || unit.X >= 1 - NormalizedUvTolerance
            || unit.Y <= NormalizedUvTolerance || unit.Y >= 1 - NormalizedUvTolerance)) reason = "DOMAIN_BOUNDARY_WITH_GAP";
        if (gap > tolerance) { if (reason != "DOMAIN_BOUNDARY_WITH_GAP") reason = "OFF_SUPPORT_GAP"; return true; }
        foreach (var seed in new[] { new Point2d(.1, .1), new Point2d(.9, .1), new Point2d(.9, .9), new Point2d(.1, .9) })
        {
            checkpoint();
            if (!surface.LocalClosestPoint(point, surface.Domain(0).ParameterAt(seed.X), surface.Domain(1).ParameterAt(seed.Y), out var su, out var sv))
            { reason = "UV_BRANCH_SEARCH_UNRESOLVED"; return false; }
            var other = Normalize(surface, new Point2d(su, sv));
            if (!other.IsValid || other.X < -NormalizedUvTolerance || other.X > 1 + NormalizedUvTolerance
                || other.Y < -NormalizedUvTolerance || other.Y > 1 + NormalizedUvTolerance)
            { reason = "LOCAL_UV_OUTSIDE_FINITE_DOMAIN"; return false; }
            var otherGap = surface.PointAt(su, sv).DistanceTo(point);
            if (!NativeCompareMath.Finite(otherGap)) return false;
            if (otherGap <= tolerance && other.DistanceTo(unit) > NormalizedUvTolerance)
            { reason = "AMBIGUOUS_UV_BRANCH"; return false; }
        }
        reason = "SAMPLED_UV_BRANCH_RESOLVED";
        return true;
    }

    internal static Point2d Normalize(Surface surface, Point2d uv) => new(
        surface.Domain(0).NormalizedParameterAt(uv.X), surface.Domain(1).NormalizedParameterAt(uv.Y));

    internal static bool TryFrame(Surface surface, double u, double v, out NativeCompareMeasure.SurfaceFrame frame)
    {
        frame = new NativeCompareMeasure.SurfaceFrame();
        var curvature = surface.CurvatureAt(u, v);
        if (curvature is null) return false;
        var normal = curvature.Normal;
        if (!normal.Unitize()) return false;
        var a = curvature.Direction(0); var b = curvature.Direction(1);
        var ka = curvature.Kappa(0); var kb = curvature.Kappa(1);
        if (!a.Unitize() || !b.Unitize() || !NativeCompareMath.Finite(ka) || !NativeCompareMath.Finite(kb)
            || Math.Abs(a * b) > 1e-5 || Math.Abs(a * normal) > 1e-5 || Math.Abs(b * normal) > 1e-5) return false;
        frame.Normal = normal;
        frame.Operator = NativeCompareMath.Operator(ka, new[] { a.X, a.Y, a.Z }, kb, new[] { b.X, b.Y, b.Z }, 1);
        frame.Norm = Math.Sqrt(ka * ka + kb * kb);
        return frame.Operator.All(NativeCompareMath.Finite);
    }

    internal static bool BoundaryLocation(BrepFace face, Point3d point, double tolerance,
        out Point2d uv, out double gap, out NativeCompareMeasure.SurfaceFrame frame, out bool regular, out string reason)
    {
        uv = new Point2d(double.NaN, double.NaN); gap = double.NaN; frame = new NativeCompareMeasure.SurfaceFrame();
        regular = false; reason = "TRIM_BOUNDARY_PROJECTION_FAILED";
        var hits = new List<(BrepEdge Edge, double T, double Gap)>();
        foreach (var edge in face.Brep.Edges.Where(edge => edge.Valence == EdgeAdjacency.Naked))
        {
            if (!edge.ClosestPoint(point, out var t)) return false;
            var distance = edge.PointAt(t).DistanceTo(point);
            if (!NativeCompareMath.Finite(distance)) return false;
            hits.Add((edge, t, distance));
        }
        if (hits.Count == 0) return false;
        hits.Sort((a, b) => a.Gap.CompareTo(b.Gap));
        var best = hits[0]; gap = best.Gap;
        var tie = tolerance * 1e-4;
        foreach (var other in hits.Skip(1))
        {
            if (other.Gap - best.Gap > tie) break;
            var common = new[] { best.Edge.StartVertex, best.Edge.EndVertex }.Any(a =>
                new[] { other.Edge.StartVertex, other.Edge.EndVertex }.Any(b => a.VertexIndex == b.VertexIndex
                    && best.Edge.PointAt(best.T).DistanceTo(a.Location) <= tie
                    && other.Edge.PointAt(other.T).DistanceTo(b.Location) <= tie));
            if (!common) { reason = "AMBIGUOUS_TRIM_BOUNDARY_CORRESPONDENCE"; return false; }
        }
        var trim = NativeCompareSideBinding.Trim(best.Edge);
        if (!trim.GetTrimParameter(best.T, out var parameter)) return false;
        var position = trim.PointAt(parameter); uv = new Point2d(position.X, position.Y);
        if (!uv.IsValid || face.PointAt(uv.X, uv.Y).DistanceTo(best.Edge.PointAt(best.T)) > tolerance) return false;
        regular = NativeCompareMeasure.Frame(best.Edge, best.T, tolerance, out frame);
        reason = "ORIGINAL_SOURCE_TO_ACTUAL_TRIM_BOUNDARY";
        return true;
    }

    private static Curve SampledLoop(Surface support, IReadOnlyList<(NativeSupportSource.Station Station, Point2d UV)> stations)
    {
        var points = new List<Point3d>();
        foreach (var station in stations)
        {
            var unit = Normalize(support, station.UV);
            var point = new Point3d(unit.X, unit.Y, 0);
            if (points.Count == 0 || point.DistanceTo(points[points.Count - 1]) > NormalizedUvTolerance) points.Add(point);
        }
        // Adjacent physical source endpoints must stay on the same UV branch, including representation seams.
        for (var i = 0; i < stations.Count; i++)
        {
            var next = (i + 1) % stations.Count;
            if (ReferenceEquals(stations[i].Station.Source, stations[next].Station.Source)) continue;
            if (Normalize(support, stations[i].UV).DistanceTo(Normalize(support, stations[next].UV)) > NormalizedUvTolerance)
                throw new NativeCompareUnsupported("INCONSISTENT_SOURCE_JUNCTION_UV_BRANCH");
        }
        if (!NativeSupportTrimPolicy.TryCloseScreeningLoop(points.Select(point => (point.X, point.Y)).ToArray(), NormalizedUvTolerance, out var closed))
            throw new NativeCompareUnsupported("UNRESOLVED_CYCLIC_UV_CLOSURE");
        var loop = new PolylineCurve(closed.Select(point => new Point3d(point.U, point.V, 0)));
        if (!loop.IsClosed || !Simple(loop)) { loop.Dispose(); throw new NativeCompareUnsupported("UNRESOLVED_SAMPLED_UV_SIMPLE_LOOP"); }
        return loop;
    }

    internal static bool Simple(Curve loop)
    {
        using var intersections = Intersection.CurveSelf(loop, NormalizedUvTolerance);
        if (intersections is null) return false;
        foreach (var hit in intersections)
        {
            if (hit.IsOverlap) return false;
            var a = loop.Domain.NormalizedParameterAt(hit.ParameterA); var b = loop.Domain.NormalizedParameterAt(hit.ParameterB);
            if (Math.Abs(a - b) < 1e-10 || (Math.Min(a, b) < 1e-10 && Math.Max(a, b) > 1 - 1e-10)) continue;
            return false;
        }
        return true;
    }
    private static bool InteriorRegularity(Surface support, Curve normalizedLoop, Action checkpoint, out int seen)
    {
        seen = 0;
        var box = normalizedLoop.GetBoundingBox(true);
        if (!box.IsValid || box.Max.X - box.Min.X <= NormalizedUvTolerance || box.Max.Y - box.Min.Y <= NormalizedUvTolerance) return false;
        var visited = new HashSet<(int U, int V)>();
        foreach (var divisions in new[] { 8, 16, 32 })
        {
            for (var i = 1; i < divisions; i++) for (var j = 1; j < divisions; j++)
            {
                if (!visited.Add((i * 32 / divisions, j * 32 / divisions))) continue;
                var point = new Point3d(box.Min.X + (box.Max.X - box.Min.X) * i / divisions,
                    box.Min.Y + (box.Max.Y - box.Min.Y) * j / divisions, 0);
                if (normalizedLoop.Contains(point, Plane.WorldXY, NormalizedUvTolerance) != PointContainment.Inside) continue;
                checkpoint(); seen++;
                if (!TryFrame(support, support.Domain(0).ParameterAt(point.X), support.Domain(1).ParameterAt(point.Y), out _)) return false;
            }
            if (seen >= 9) return true;
        }
        return false;
    }
}
