using System;
using System.Globalization;

namespace SmartSkin.Core.Routing;

public enum TopologyKind
{
    NoInput,
    SingleClosedBoundary,
    ClosedBoundaryLoop,
    SectionSet,
    OpenChain,
    BranchedFrame,
    HybridFrame,
    PointSet,
    PointGuidedFrame,
    SurfaceContextOnly,
    Unsupported,
    Unresolved
}

public sealed class TopologyAnalysis
{
    internal TopologyAnalysis(
        TopologyKind kind,
        int selectedCount,
        int curveCount,
        int openCurveCount,
        int closedCurveCount,
        int unresolvedCurveCount,
        int brepEdgeCount,
        int pointCount,
        int contextObjectCount,
        int unsupportedCount,
        int endpointNodeCount,
        int connectedComponentCount,
        int endNodeCount,
        int throughNodeCount,
        int junctionNodeCount,
        bool? singleClosedCurveIsPlanar)
    {
        Kind = kind;
        SelectedCount = selectedCount;
        CurveCount = curveCount;
        OpenCurveCount = openCurveCount;
        ClosedCurveCount = closedCurveCount;
        UnresolvedCurveCount = unresolvedCurveCount;
        BrepEdgeCount = brepEdgeCount;
        PointCount = pointCount;
        ContextObjectCount = contextObjectCount;
        UnsupportedCount = unsupportedCount;
        EndpointNodeCount = endpointNodeCount;
        ConnectedComponentCount = connectedComponentCount;
        EndNodeCount = endNodeCount;
        ThroughNodeCount = throughNodeCount;
        JunctionNodeCount = junctionNodeCount;
        SingleClosedCurveIsPlanar = singleClosedCurveIsPlanar;
    }

    public TopologyKind Kind { get; }

    public int SelectedCount { get; }

    public int CurveCount { get; }

    public int OpenCurveCount { get; }

    public int ClosedCurveCount { get; }

    public int UnresolvedCurveCount { get; }

    public int BrepEdgeCount { get; }

    public int PointCount { get; }

    public int ContextObjectCount { get; }

    public int UnsupportedCount { get; }

    public int EndpointNodeCount { get; }

    public int ConnectedComponentCount { get; }

    public int EndNodeCount { get; }

    public int ThroughNodeCount { get; }

    public int JunctionNodeCount { get; }

    public bool? SingleClosedCurveIsPlanar { get; }

    public string ToEvidenceLine()
    {
        return "Evidence:"
            + $" curves={CurveCount.ToString(CultureInfo.InvariantCulture)}"
            + $" (open={OpenCurveCount.ToString(CultureInfo.InvariantCulture)},"
            + $" closed={ClosedCurveCount.ToString(CultureInfo.InvariantCulture)},"
            + $" unresolved={UnresolvedCurveCount.ToString(CultureInfo.InvariantCulture)},"
            + $" edges={BrepEdgeCount.ToString(CultureInfo.InvariantCulture)})"
            + $"; points={PointCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; context={ContextObjectCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; unsupported={UnsupportedCount.ToString(CultureInfo.InvariantCulture)}";
    }

    public string ToEndpointGraphLine()
    {
        return "Endpoint graph:"
            + $" nodes={EndpointNodeCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; components={ConnectedComponentCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; ends={EndNodeCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; through={ThroughNodeCount.ToString(CultureInfo.InvariantCulture)}"
            + $"; junctions={JunctionNodeCount.ToString(CultureInfo.InvariantCulture)}";
    }
}

internal static class RoutingTokens
{
    public static string Topology(TopologyKind kind)
    {
        return kind switch
        {
            TopologyKind.NoInput => "NO_INPUT",
            TopologyKind.SingleClosedBoundary => "SINGLE_CLOSED_BOUNDARY",
            TopologyKind.ClosedBoundaryLoop => "CLOSED_BOUNDARY_LOOP",
            TopologyKind.SectionSet => "SECTION_SET",
            TopologyKind.OpenChain => "OPEN_CHAIN",
            TopologyKind.BranchedFrame => "BRANCHED_FRAME",
            TopologyKind.HybridFrame => "HYBRID_FRAME",
            TopologyKind.PointSet => "POINT_SET",
            TopologyKind.PointGuidedFrame => "POINT_GUIDED_FRAME",
            TopologyKind.SurfaceContextOnly => "SURFACE_CONTEXT_ONLY",
            TopologyKind.Unsupported => "UNSUPPORTED",
            TopologyKind.Unresolved => "UNRESOLVED",
            _ => throw new ArgumentOutOfRangeException(nameof(kind))
        };
    }

    public static string Strategy(SurfaceStrategy strategy)
    {
        return strategy switch
        {
            SurfaceStrategy.PlanarSrf => "PLANAR_SRF",
            SurfaceStrategy.EdgeSrf => "EDGE_SRF",
            SurfaceStrategy.Loft => "LOFT",
            SurfaceStrategy.Patch => "PATCH",
            SurfaceStrategy.NetworkSrf => "NETWORK_SRF",
            _ => throw new ArgumentOutOfRangeException(nameof(strategy))
        };
    }
}
