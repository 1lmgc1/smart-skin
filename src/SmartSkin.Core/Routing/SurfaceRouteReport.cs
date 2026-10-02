using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace SmartSkin.Core.Routing;

public enum RouteStatus
{
    Ready,
    Review,
    Blocked
}

public enum SurfaceStrategy
{
    PlanarSrf,
    EdgeSrf,
    Loft,
    MatchSrf,
    Patch,
    NetworkSrf
}

public sealed class SurfaceRouteCandidate
{
    public SurfaceRouteCandidate(
        int rank,
        SurfaceStrategy strategy,
        int confidence,
        string rationale)
    {
        if (rank < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(rank));
        }

        if (confidence < 0 || confidence > 100)
        {
            throw new ArgumentOutOfRangeException(nameof(confidence));
        }

        if (string.IsNullOrWhiteSpace(rationale))
        {
            throw new ArgumentException("A candidate rationale is required.", nameof(rationale));
        }

        Rank = rank;
        Strategy = strategy;
        Confidence = confidence;
        Rationale = rationale;
    }

    public int Rank { get; }

    public SurfaceStrategy Strategy { get; }

    public int Confidence { get; }

    public string Rationale { get; }
}

public sealed class SurfaceRouteReport
{
    internal SurfaceRouteReport(
        RouteStatus status,
        TopologyAnalysis topology,
        IReadOnlyList<SurfaceRouteCandidate> candidates,
        IReadOnlyList<string> notes)
    {
        Status = status;
        Topology = topology ?? throw new ArgumentNullException(nameof(topology));
        Candidates = candidates?.ToArray() ?? throw new ArgumentNullException(nameof(candidates));
        Notes = notes?.ToArray() ?? throw new ArgumentNullException(nameof(notes));
    }

    public RouteStatus Status { get; }

    public TopologyAnalysis Topology { get; }

    public IReadOnlyList<SurfaceRouteCandidate> Candidates { get; }

    public IReadOnlyList<string> Notes { get; }

    public SurfaceStrategy? PrimaryStrategy => Candidates.Count == 0
        ? null
        : Candidates[0].Strategy;

    public IReadOnlyList<string> ToDisplayLines(
        int maximumCandidateLines = 3,
        int maximumNoteLines = 8)
    {
        if (maximumCandidateLines < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumCandidateLines));
        }

        if (maximumNoteLines < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumNoteLines));
        }

        var lines = new List<string>
        {
            $"Routing status: {Status.ToString().ToUpperInvariant()}",
            $"Topology: {RoutingTokens.Topology(Topology.Kind)}",
            Topology.ToEvidenceLine(),
            Topology.ToEndpointGraphLine()
        };

        if (Candidates.Count == 0)
        {
            lines.Add("Candidates: none");
        }
        else
        {
            lines.Add("Candidates:");
            var visibleCandidateCount = Math.Min(Candidates.Count, maximumCandidateLines);
            for (var index = 0; index < visibleCandidateCount; index++)
            {
                var candidate = Candidates[index];
                lines.Add(
                    $"  {candidate.Rank.ToString(CultureInfo.InvariantCulture)}."
                    + $" {RoutingTokens.Strategy(candidate.Strategy)}"
                    + $" | confidence={candidate.Confidence.ToString(CultureInfo.InvariantCulture)}"
                    + $" | {candidate.Rationale}");
            }

            if (Candidates.Count > visibleCandidateCount)
            {
                lines.Add($"  ... {Candidates.Count - visibleCandidateCount} additional candidate(s) omitted");
            }
        }

        if (Notes.Count == 0)
        {
            lines.Add("Routing notes: none");
        }
        else
        {
            lines.Add("Routing notes:");
            var visibleNoteCount = Math.Min(Notes.Count, maximumNoteLines);
            for (var index = 0; index < visibleNoteCount; index++)
            {
                lines.Add($"  - {Notes[index]}");
            }

            if (Notes.Count > visibleNoteCount)
            {
                lines.Add($"  ... {Notes.Count - visibleNoteCount} additional note(s) omitted");
            }
        }

        return lines;
    }

    public string ToMachineLine(
        BuildIdentity identity,
        int objectCountBefore,
        int objectCountAfter)
    {
        if (identity is null)
        {
            throw new ArgumentNullException(nameof(identity));
        }

        var primary = PrimaryStrategy.HasValue
            ? RoutingTokens.Strategy(PrimaryStrategy.Value)
            : "NONE";

        return $"SMARTSKIN_{identity.Patch} PASS"
            + $" | version={identity.Version}"
            + $" | commit={identity.Commit}"
            + $" | route_status={Status.ToString().ToUpperInvariant()}"
            + $" | topology={RoutingTokens.Topology(Topology.Kind)}"
            + $" | primary={primary}"
            + $" | candidates={Candidates.Count.ToString(CultureInfo.InvariantCulture)}"
            + $" | selected={Topology.SelectedCount.ToString(CultureInfo.InvariantCulture)}"
            + $" | objects={objectCountBefore.ToString(CultureInfo.InvariantCulture)}->{objectCountAfter.ToString(CultureInfo.InvariantCulture)}";
    }
}
