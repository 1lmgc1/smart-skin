using System;
using System.Collections.Generic;
using System.Linq;
using SmartSkin.Core.Preflight;

namespace SmartSkin.Core.Routing;

public sealed class TopologyClassifier
{
    private const int MaximumEndpointCount = PreflightOptions.DefaultMaximumItems * 2;

    public TopologyAnalysis Classify(
        IReadOnlyList<GeometrySnapshot> snapshots,
        double absoluteTolerance)
    {
        if (snapshots is null)
        {
            throw new ArgumentNullException(nameof(snapshots));
        }

        var curveLike = snapshots
            .Where(snapshot => snapshot.Kind == GeometryKind.Curve || snapshot.Kind == GeometryKind.BrepEdge)
            .ToArray();
        var openCurves = curveLike.Where(snapshot => snapshot.IsClosed == false).ToArray();
        var closedCurves = curveLike.Where(snapshot => snapshot.IsClosed == true).ToArray();
        var unresolvedCurveCount = curveLike.Count(snapshot => !snapshot.IsClosed.HasValue);
        var brepEdgeCount = curveLike.Count(snapshot => snapshot.Kind == GeometryKind.BrepEdge);
        var pointCount = snapshots.Count(snapshot => snapshot.Kind == GeometryKind.Point);
        var contextObjectCount = snapshots.Count(IsSurfaceContext);
        var unsupportedCount = snapshots.Count(snapshot => snapshot.Kind == GeometryKind.Other);

        var graph = EndpointGraph.Empty;
        var toleranceIsUsable = absoluteTolerance > 0.0
            && !double.IsNaN(absoluteTolerance)
            && !double.IsInfinity(absoluteTolerance);
        if (toleranceIsUsable && openCurves.Length * 2 <= MaximumEndpointCount)
        {
            graph = BuildEndpointGraph(openCurves, absoluteTolerance);
        }

        var kind = ResolveKind(
            snapshots.Count,
            curveLike.Length,
            openCurves.Length,
            closedCurves.Length,
            unresolvedCurveCount,
            pointCount,
            contextObjectCount,
            unsupportedCount,
            graph,
            toleranceIsUsable);

        bool? singleClosedCurveIsPlanar = closedCurves.Length == 1 && openCurves.Length == 0
            ? closedCurves[0].IsPlanar
            : null;

        return new TopologyAnalysis(
            kind,
            snapshots.Count,
            curveLike.Length,
            openCurves.Length,
            closedCurves.Length,
            unresolvedCurveCount,
            brepEdgeCount,
            pointCount,
            contextObjectCount,
            unsupportedCount,
            graph.NodeCount,
            graph.ComponentCount,
            graph.EndNodeCount,
            graph.ThroughNodeCount,
            graph.JunctionNodeCount,
            singleClosedCurveIsPlanar);
    }

    private static TopologyKind ResolveKind(
        int selectedCount,
        int curveCount,
        int openCurveCount,
        int closedCurveCount,
        int unresolvedCurveCount,
        int pointCount,
        int contextObjectCount,
        int unsupportedCount,
        EndpointGraph graph,
        bool toleranceIsUsable)
    {
        if (selectedCount == 0)
        {
            return TopologyKind.NoInput;
        }

        if (unsupportedCount > 0)
        {
            return TopologyKind.Unsupported;
        }

        if (unresolvedCurveCount > 0
            || (openCurveCount > 0 && (!toleranceIsUsable || graph.CurveCount != openCurveCount)))
        {
            return TopologyKind.Unresolved;
        }

        if (curveCount == 0)
        {
            if (pointCount > 0)
            {
                return TopologyKind.PointSet;
            }

            return contextObjectCount > 0
                ? TopologyKind.SurfaceContextOnly
                : TopologyKind.Unsupported;
        }

        if (pointCount > 0)
        {
            return TopologyKind.PointGuidedFrame;
        }

        if (openCurveCount == 0)
        {
            return closedCurveCount == 1
                ? TopologyKind.SingleClosedBoundary
                : TopologyKind.SectionSet;
        }

        if (closedCurveCount > 0)
        {
            return TopologyKind.HybridFrame;
        }

        if (graph.JunctionNodeCount > 0)
        {
            return TopologyKind.BranchedFrame;
        }

        if (graph.ComponentCount == 1
            && graph.NodeCount > 0
            && graph.EndNodeCount == 0
            && graph.ThroughNodeCount == graph.NodeCount
            && openCurveCount >= 2)
        {
            return TopologyKind.ClosedBoundaryLoop;
        }

        if (graph.ComponentCount == 1
            && graph.EndNodeCount == 2
            && graph.EndNodeCount + graph.ThroughNodeCount == graph.NodeCount)
        {
            return TopologyKind.OpenChain;
        }

        if (graph.ComponentCount == openCurveCount
            && graph.EndNodeCount == openCurveCount * 2)
        {
            return TopologyKind.SectionSet;
        }

        return TopologyKind.HybridFrame;
    }

    private static bool IsSurfaceContext(GeometrySnapshot snapshot)
    {
        return snapshot.Kind == GeometryKind.Surface
            || snapshot.Kind == GeometryKind.Brep
            || snapshot.Kind == GeometryKind.Extrusion;
    }

    private static EndpointGraph BuildEndpointGraph(
        IReadOnlyList<GeometrySnapshot> openCurves,
        double absoluteTolerance)
    {
        var endpoints = new List<Point3Value>(openCurves.Count * 2);
        foreach (var curve in openCurves)
        {
            if (!curve.StartPoint.HasValue
                || !curve.EndPoint.HasValue
                || !curve.StartPoint.Value.IsFinite
                || !curve.EndPoint.Value.IsFinite)
            {
                return EndpointGraph.Empty;
            }

            endpoints.Add(curve.StartPoint.Value);
            endpoints.Add(curve.EndPoint.Value);
        }

        var sets = new DisjointSet(endpoints.Count);
        for (var first = 0; first < endpoints.Count; first++)
        {
            for (var second = first + 1; second < endpoints.Count; second++)
            {
                if (endpoints[first].DistanceTo(endpoints[second]) <= absoluteTolerance)
                {
                    sets.Union(first, second);
                }
            }
        }

        var rootToNode = new Dictionary<int, int>();
        var endpointNodes = new int[endpoints.Count];
        for (var index = 0; index < endpoints.Count; index++)
        {
            var root = sets.Find(index);
            if (!rootToNode.TryGetValue(root, out var node))
            {
                node = rootToNode.Count;
                rootToNode.Add(root, node);
            }

            endpointNodes[index] = node;
        }

        var degrees = new int[rootToNode.Count];
        var adjacency = Enumerable
            .Range(0, rootToNode.Count)
            .Select(_ => new HashSet<int>())
            .ToArray();
        for (var curveIndex = 0; curveIndex < openCurves.Count; curveIndex++)
        {
            var startNode = endpointNodes[curveIndex * 2];
            var endNode = endpointNodes[(curveIndex * 2) + 1];
            degrees[startNode]++;
            degrees[endNode]++;
            adjacency[startNode].Add(endNode);
            adjacency[endNode].Add(startNode);
        }

        var componentCount = CountComponents(adjacency);
        return new EndpointGraph(
            openCurves.Count,
            degrees.Length,
            componentCount,
            degrees.Count(degree => degree == 1),
            degrees.Count(degree => degree == 2),
            degrees.Count(degree => degree > 2));
    }

    private static int CountComponents(IReadOnlyList<HashSet<int>> adjacency)
    {
        var visited = new bool[adjacency.Count];
        var components = 0;
        var stack = new Stack<int>();

        for (var start = 0; start < adjacency.Count; start++)
        {
            if (visited[start])
            {
                continue;
            }

            components++;
            stack.Push(start);
            while (stack.Count > 0)
            {
                var node = stack.Pop();
                if (visited[node])
                {
                    continue;
                }

                visited[node] = true;
                foreach (var neighbor in adjacency[node])
                {
                    if (!visited[neighbor])
                    {
                        stack.Push(neighbor);
                    }
                }
            }
        }

        return components;
    }

    private sealed class DisjointSet
    {
        private readonly int[] _parents;
        private readonly byte[] _ranks;

        public DisjointSet(int count)
        {
            _parents = Enumerable.Range(0, count).ToArray();
            _ranks = new byte[count];
        }

        public int Find(int item)
        {
            if (_parents[item] != item)
            {
                _parents[item] = Find(_parents[item]);
            }

            return _parents[item];
        }

        public void Union(int first, int second)
        {
            var firstRoot = Find(first);
            var secondRoot = Find(second);
            if (firstRoot == secondRoot)
            {
                return;
            }

            if (_ranks[firstRoot] < _ranks[secondRoot])
            {
                _parents[firstRoot] = secondRoot;
            }
            else if (_ranks[firstRoot] > _ranks[secondRoot])
            {
                _parents[secondRoot] = firstRoot;
            }
            else
            {
                _parents[secondRoot] = firstRoot;
                _ranks[firstRoot]++;
            }
        }
    }

    private sealed class EndpointGraph
    {
        public static readonly EndpointGraph Empty = new EndpointGraph(0, 0, 0, 0, 0, 0);

        public EndpointGraph(
            int curveCount,
            int nodeCount,
            int componentCount,
            int endNodeCount,
            int throughNodeCount,
            int junctionNodeCount)
        {
            CurveCount = curveCount;
            NodeCount = nodeCount;
            ComponentCount = componentCount;
            EndNodeCount = endNodeCount;
            ThroughNodeCount = throughNodeCount;
            JunctionNodeCount = junctionNodeCount;
        }

        public int CurveCount { get; }

        public int NodeCount { get; }

        public int ComponentCount { get; }

        public int EndNodeCount { get; }

        public int ThroughNodeCount { get; }

        public int JunctionNodeCount { get; }
    }
}
