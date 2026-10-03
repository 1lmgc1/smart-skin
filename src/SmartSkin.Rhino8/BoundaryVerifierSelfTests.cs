using System;
using System.Collections.Generic;
using System.Linq;
using Rhino;
using Rhino.Geometry;
using SmartSkin.Core;

namespace SmartSkin.Rhino8;

/// <summary>Small native regression fixtures. Runs on the Rhino command thread,
/// once per process before the first match. Never accesses RhinoDoc.</summary>
internal static class BoundaryVerifierSelfTests
{
    private const double Tolerance = 0.0001;
    private static readonly string Prefix = "SMARTSKIN_"
        + BuildIdentity.FromAssembly(typeof(BoundaryVerifierSelfTests).Assembly).Patch;
    private static bool? _passed;
    public static string LastFailure { get; private set; } = string.Empty;

    public static bool EnsurePassed()
    {
        if (_passed.HasValue) return _passed.Value;
        var failures = new List<string>();
        var count = 0;
        void Test(string name, Action action)
        {
            count++;
            try
            {
                action();
                RhinoApp.WriteLine(Prefix + "_SELFTEST | case=" + name + " | PASS");
            }
            catch (Exception exception)
            {
                var detail = OneLine(exception.Message);
                failures.Add(name + ": " + detail);
                RhinoApp.WriteLine(Prefix + "_SELFTEST | case=" + name + " | FAIL | " + detail);
            }
        }

        Test("single_trimmed_closed_edge", () =>
        {
            using var disk = Disk(2);
            using var target = disk.DuplicateBrep();
            Check(disk.Edges.Count == 1, "Fixture must have one boundary edge.");
            Check(CheckAgainst(disk, target).Verified, "A coincident planar circle must pass G2.");
        });
        Test("four_edge_closed_loop", () =>
        {
            using var cap = Rectangle();
            using var target = cap.DuplicateBrep();
            Check(cap.Edges.Count == 4, "Fixture must have four edges.");
            Check(CheckAgainst(cap, target).Verified, "A four-edge planar loop must pass G2.");
        });
        Test("split_edge_same_face", () =>
        {
            using var cap = Rectangle();
            using var target = cap.DuplicateBrep();
            RequireValidFixture(cap, "before_split");
            var middle = cap.Edges[0].Domain.ParameterAt(0.5);
            Check(cap.Edges.SplitEdgeAtParameters(0, new[] { middle }) == 1, "Could not split fixture edge.");

            // Low-level edge splitting can leave a new vertex tolerance unset.
            // Record that state, but do not require it: Rhino may initialize it in a future runtime.
            var rawValid = cap.IsValidWithLog(out var rawLog);
            RhinoApp.WriteLine(Prefix + "_FIXTURE | case=split_edge_same_face | stage=POST_SPLIT"
                + " | valid=" + rawValid + " | validity_log=" + OneLine(rawLog));

            // Finish ONLY this synthetic fixture. This does not change a document tolerance,
            // repair a user's Brep, bypass IsValid, or alter the production verifier.
            // McNeel's low-level SplitEdge completion pattern:
            // https://discourse.mcneel.com/t/161849/3
            cap.SetTolerancesBoxesAndFlags(
                bLazy: true,
                bSetVertexTolerances: true,
                bSetEdgeTolerances: false,
                bSetTrimTolerances: false,
                bSetTrimIsoFlags: false,
                bSetTrimTypeFlags: false,
                bSetLoopTypeFlags: false,
                bSetTrimBoxes: false);
            cap.Compact();
            RequireValidFixture(cap, "after_split_finalization");
            Check(cap.Faces.Count == 1 && cap.Edges.Count == 5 && cap.Vertices.Count == 5,
                "Finalized fixture must retain one face, five edges and five vertices.");
            Check(target.Faces.Count == 1 && target.Edges.Count == 4,
                "The unsplit comparison fixture must retain four edges.");
            using var capSurface = cap.Faces[0].DuplicateSurface();
            using var targetSurface = target.Faces[0].DuplicateSurface();
            Check(capSurface is not null && targetSurface is not null
                && GeometryBase.GeometryEquals(capSurface, targetSurface),
                "Splitting a boundary must not change its underlying surface.");
            RhinoApp.WriteLine(Prefix + "_FIXTURE | case=split_edge_same_face | stage=FINALIZED"
                + " | valid=True | faces=1 | edges=5 | vertices=5 | target_edges=4 | surface_unchanged=True");

            var metrics = CheckAgainst(cap, target);
            Check(metrics.Verified, "A split boundary must still pass G2: " + metrics.Reason + "; " + metrics.Message);
            Check(metrics.BoundaryEdgeCount == 5 && metrics.BoundaryComponents == 1
                && metrics.CoveredCandidateEdges == 5 && metrics.CoveredTargetEdges == 4
                && metrics.SampleCount > 0 && metrics.MaximumGap <= Tolerance,
                "G2 pass must retain full five-to-four boundary coverage within the unchanged tolerance.");
        });
        Test("numeric_gap_above_old_prefilter", () =>
        {
            using var cap = Rectangle();
            using var target = cap.DuplicateBrep();
            Check(cap.Translate(new Vector3d(0, 0, 0.1)), "Fixture translation failed.");
            var metrics = CheckAgainst(cap, target);
            Check(!metrics.Verified && metrics.Available && metrics.MaximumGap > 2 * Tolerance
                && metrics.Reason == "BOUNDARY_GAP_OUT_OF_TOLERANCE", "A large gap must be numeric and rejected, not reported as a missing edge.");
        });
        Test("extra_boundary_component", () =>
        {
            using var outer = new Circle(Plane.WorldXY, 2).ToNurbsCurve();
            using var inner = new Circle(Plane.WorldXY, 1).ToNurbsCurve();
            var annuli = Brep.CreatePlanarBreps(new Curve[] { outer, inner }, Tolerance);
            if (annuli is null) throw new InvalidOperationException("Annulus construction failed.");
            try
            {
                Check(annuli.Length == 1, "Expected one annulus.");
                using var target = Disk(2);
                var metrics = CheckAgainst(annuli[0], target);
                Check(!metrics.Verified && metrics.Reason == "MULTIPLE_BOUNDARY_COMPONENTS",
                    "An additional hole must not disappear from validation.");
            }
            finally { foreach (var brep in annuli) brep?.Dispose(); }
        });
        Test("G1_rejects_tilted_boundary_normals", () =>
        {
            using var cap = BumpedSurface(4, 1);
            using var target = Rectangle();
            var metrics = CheckAgainst(cap, target, MatchContinuityLevel.Tangency);
            Check(metrics.Available && !metrics.Verified && metrics.Reason == "NORMAL_OUT_OF_TOLERANCE",
                "A G0-only cap must not pass G1: " + metrics.Reason);
        });
        Test("G2_rejects_curvature_with_G1_preserved", () =>
        {
            using var cap = BumpedSurface(6, 2);
            using var target = Rectangle();
            var metrics = CheckAgainst(cap, target);
            Check(metrics.Available && !metrics.Verified && metrics.Reason == "CURVATURE_OUT_OF_TOLERANCE",
                "A tangent but curved boundary must not pass flat G2: " + metrics.Reason);
        });
        Test("Average_keeps_trimmed_target_guard", () =>
        {
            using var disk = Disk(2);
            using var rectangle = Rectangle();
            Check(disk.Edges.All(edge => !BoundaryMatchVerifier.IsAverageTargetEligible(edge)), "Trimmed circular targets must not enable Average.");
            Check(rectangle.Edges.All(BoundaryMatchVerifier.IsAverageTargetEligible), "Natural rectangular targets should remain eligible.");
        });

        _passed = failures.Count == 0;
        LastFailure = string.Join("; ", failures);
        RhinoApp.WriteLine(Prefix + "_SELFTEST " + (_passed.Value ? "PASS" : "FAIL")
            + " | cases=" + count + " | failed=" + failures.Count + " | scope=VALIDATOR_ONLY | document_access=NONE");
        return _passed.Value;
    }

    private static BoundaryMatchMetrics CheckAgainst(Brep cap, Brep target,
        MatchContinuityLevel continuity = MatchContinuityLevel.Curvature)
    {
        RequireValidFixture(cap, "verification_cap");
        RequireValidFixture(target, "verification_target");
        var settings = new CandidateBuildSettings(continuity, true, 5, false,
            MatchIsoDirection.Automatic, 80, true);
        return BoundaryMatchVerifier.Verify(cap,
            target.Edges.Where(edge => edge.Valence == EdgeAdjacency.Naked).ToArray(),
            settings, Tolerance, RhinoMath.ToRadians(1), "selftest", writeDiagnostics: false);
    }

    private static void RequireValidFixture(Brep brep, string stage)
    {
        Check(brep.IsValidWithLog(out var log), "FIXTURE_INVALID at " + stage + ": " + OneLine(log));
    }

    private static string OneLine(string? text)
    {
        return string.IsNullOrWhiteSpace(text) ? "none"
            : text!.Replace('\r', ' ').Replace('\n', ' ').Replace('|', '/').Trim();
    }

    private static Brep Rectangle() => Brep.CreateFromCornerPoints(
        new Point3d(0, 0, 0), new Point3d(3, 0, 0), new Point3d(3, 3, 0), new Point3d(0, 3, 0), Tolerance)
        ?? throw new InvalidOperationException("Rectangle construction failed.");

    private static Brep Disk(double radius)
    {
        using var curve = new Circle(Plane.WorldXY, radius).ToNurbsCurve();
        var breps = Brep.CreatePlanarBreps(curve, Tolerance);
        if (breps is not null && breps.Length == 1) return breps[0];
        if (breps is not null) foreach (var brep in breps) brep?.Dispose();
        throw new InvalidOperationException("Disk construction failed.");
    }

    private static Brep BumpedSurface(int count, int zeroRows)
    {
        using var surface = NurbsSurface.Create(3, false, count, count, count, count)
            ?? throw new InvalidOperationException("NURBS fixture allocation failed.");
        surface.KnotsU.CreateUniformKnots(1);
        surface.KnotsV.CreateUniformKnots(1);
        for (var u = 0; u < count; u++)
            for (var v = 0; v < count; v++)
            {
                var elevated = u >= zeroRows && u < count - zeroRows && v >= zeroRows && v < count - zeroRows;
                Check(surface.Points.SetPoint(u, v, new Point3d(3.0 * u / (count - 1),
                    3.0 * v / (count - 1), elevated ? 0.3 : 0.0)), "Setting fixture control point failed.");
            }
        var brep = surface.ToBrep();
        if (brep is not null && brep.IsValid) return brep;
        brep?.Dispose();
        throw new InvalidOperationException("NURBS fixture is invalid.");
    }

    private static void Check(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }
}
