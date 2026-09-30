using System;
using System.Collections.Generic;
using System.Linq;
using SmartSkin.Core.Preflight;

namespace SmartSkin.Core.Routing;

public sealed class SurfaceStrategyRouter
{
    private readonly TopologyClassifier _classifier;

    public SurfaceStrategyRouter()
        : this(new TopologyClassifier())
    {
    }

    public SurfaceStrategyRouter(TopologyClassifier classifier)
    {
        _classifier = classifier ?? throw new ArgumentNullException(nameof(classifier));
    }

    public SurfaceRouteReport Route(PreflightReport preflight)
    {
        if (preflight is null)
        {
            throw new ArgumentNullException(nameof(preflight));
        }

        var topology = _classifier.Classify(preflight.Snapshots, preflight.AbsoluteTolerance);
        var candidates = new List<SurfaceRouteCandidate>();
        var notes = new List<string>();

        if (preflight.Status == PreflightStatus.Blocked)
        {
            notes.Add("Preflight contains blocking errors; resolve them before any construction attempt.");
            AddPreflightNotes(preflight, notes);
            return new SurfaceRouteReport(RouteStatus.Blocked, topology, candidates, notes);
        }

        var status = RouteStatus.Ready;
        switch (topology.Kind)
        {
            case TopologyKind.SingleClosedBoundary:
                if (topology.SingleClosedCurveIsPlanar == true)
                {
                    AddCandidate(
                        candidates,
                        SurfaceStrategy.PlanarSrf,
                        100,
                        "One valid closed boundary is reported planar.");
                    AddCandidate(
                        candidates,
                        SurfaceStrategy.Patch,
                        65,
                        "Fallback when a fitted surface is preferred over an exact planar fill.");
                }
                else
                {
                    AddCandidate(
                        candidates,
                        SurfaceStrategy.Patch,
                        topology.SingleClosedCurveIsPlanar == false ? 90 : 80,
                        "A single closed boundary is not proven planar, so a fitted patch is the bounded route.");
                    status = topology.SingleClosedCurveIsPlanar.HasValue
                        ? RouteStatus.Ready
                        : RouteStatus.Review;
                }

                break;

            case TopologyKind.ClosedBoundaryLoop:
                if (topology.OpenCurveCount >= 2 && topology.OpenCurveCount <= 4)
                {
                    AddCandidate(
                        candidates,
                        SurfaceStrategy.EdgeSrf,
                        95,
                        "Two to four strict endpoint-connected curves form one closed boundary loop.");
                    AddCandidate(
                        candidates,
                        SurfaceStrategy.Patch,
                        60,
                        "Fallback when EdgeSrf quality or parameterization is unsuitable.");
                }
                else
                {
                    AddCandidate(
                        candidates,
                        SurfaceStrategy.Patch,
                        85,
                        "The closed loop has more than four segments, outside the direct EdgeSrf route.");
                    AddCandidate(
                        candidates,
                        SurfaceStrategy.NetworkSrf,
                        55,
                        "Secondary route only after future intersection-direction validation.");
                    status = RouteStatus.Review;
                }

                break;

            case TopologyKind.SectionSet:
                AddCandidate(
                    candidates,
                    SurfaceStrategy.Loft,
                    90,
                    "Multiple disconnected curves are most plausibly section curves.");
                AddCandidate(
                    candidates,
                    SurfaceStrategy.Patch,
                    50,
                    "Fallback when the section order or loft parameterization is unsuitable.");
                break;

            case TopologyKind.BranchedFrame:
                AddCandidate(
                    candidates,
                    SurfaceStrategy.Patch,
                    80,
                    "Endpoint junctions make a fitted patch safer than assuming U/V curve families.");
                AddCandidate(
                    candidates,
                    SurfaceStrategy.NetworkSrf,
                    60,
                    "Possible only after future validation of internal intersections and curve directions.");
                notes.Add("The frame contains endpoint junctions; P02 does not infer which branch is boundary or guide.");
                status = RouteStatus.Review;
                break;

            case TopologyKind.HybridFrame:
                AddCandidate(
                    candidates,
                    SurfaceStrategy.Patch,
                    75,
                    "Mixed connected and disconnected constraints favor a fitted patch.");
                AddCandidate(
                    candidates,
                    SurfaceStrategy.NetworkSrf,
                    50,
                    "Secondary route only after future intersection-family validation.");
                notes.Add("The selection mixes incompatible endpoint patterns; section order and boundary roles remain unresolved.");
                status = RouteStatus.Review;
                break;

            case TopologyKind.PointGuidedFrame:
                AddCandidate(
                    candidates,
                    SurfaceStrategy.Patch,
                    90,
                    "Patch can use the selected curves and points as fitting constraints.");
                notes.Add("P02 does not yet weight boundary curves differently from interior guide points.");
                status = RouteStatus.Review;
                break;

            case TopologyKind.PointSet:
                AddCandidate(
                    candidates,
                    SurfaceStrategy.Patch,
                    80,
                    "A point set can seed a fitted patch but does not define an explicit boundary.");
                notes.Add("Add boundary curves when edge position matters.");
                status = RouteStatus.Review;
                break;

            case TopologyKind.OpenChain:
                notes.Add("An open chain is only a boundary fragment; close the boundary or supply a separate section set.");
                status = RouteStatus.Blocked;
                break;

            case TopologyKind.SurfaceContextOnly:
                notes.Add("Only parent surfaces or polysurfaces were selected; select boundary edges or construction curves.");
                status = RouteStatus.Blocked;
                break;

            case TopologyKind.NoInput:
                notes.Add("No geometry was supplied for routing.");
                status = RouteStatus.Blocked;
                break;

            case TopologyKind.Unsupported:
                notes.Add("The selection contains geometry outside the P02 routing contract.");
                status = RouteStatus.Blocked;
                break;

            case TopologyKind.Unresolved:
                notes.Add("Curve closure or finite endpoint data is incomplete, so topology cannot be routed safely.");
                status = RouteStatus.Blocked;
                break;

            default:
                throw new ArgumentOutOfRangeException();
        }

        if (topology.ContextObjectCount > 0 && status != RouteStatus.Blocked)
        {
            notes.Add("Selected surfaces are treated as context only; P02 does not infer G0/G1/G2 continuity.");
            status = RouteStatus.Review;
        }

        if (preflight.Status == PreflightStatus.Warning)
        {
            if (status == RouteStatus.Ready)
            {
                status = RouteStatus.Review;
            }

            AddPreflightNotes(preflight, notes);
        }

        if (candidates.Count == 0)
        {
            status = RouteStatus.Blocked;
        }

        return new SurfaceRouteReport(status, topology, candidates, notes);
    }

    private static void AddCandidate(
        ICollection<SurfaceRouteCandidate> candidates,
        SurfaceStrategy strategy,
        int confidence,
        string rationale)
    {
        candidates.Add(new SurfaceRouteCandidate(
            candidates.Count + 1,
            strategy,
            confidence,
            rationale));
    }

    private static void AddPreflightNotes(PreflightReport preflight, ICollection<string> notes)
    {
        var visibleIssues = preflight.Issues.Take(4).ToArray();
        foreach (var issue in visibleIssues)
        {
            notes.Add($"{issue.Code}: {issue.Message}");
        }

        if (preflight.Issues.Count > visibleIssues.Length)
        {
            notes.Add($"{preflight.Issues.Count - visibleIssues.Length} additional preflight issue(s) omitted.");
        }
    }
}
