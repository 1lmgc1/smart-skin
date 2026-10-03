using System.Collections.ObjectModel;

namespace SmartSkin.P08B;

// POLICY ONLY. No Rhino reference, no geometry generation and no document writes.
// Native integration must supply measured evidence from ONE immutable candidate.
public enum Grade { G0, G1, G2 }
public enum BoundaryRole { ContinueSmooth, PreserveFeature }
public enum Proof { Unknown, Failed, Passed }
public enum CandidateState { Rejected, PreviewOnly, ReviewRequired, Ready }

public sealed record EdgeRule(string EdgeKey, Grade Preferred, Grade Minimum,
    BoundaryRole Role = BoundaryRole.ContinueSmooth)
{
    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(EdgeKey)
            || !Enum.IsDefined(Preferred) || !Enum.IsDefined(Minimum)
            || !Enum.IsDefined(Role) || Minimum > Preferred)
            throw new ArgumentException("Invalid boundary rule.");
        if (Role == BoundaryRole.PreserveFeature && (Preferred != Grade.G0 || Minimum != Grade.G0))
            throw new ArgumentException("A positional feature boundary cannot be implicitly upgraded to a smooth target.");
    }
}

public sealed record Limits(double Gap, double NormalDegrees, double CurvaturePercent)
{
    public void Validate()
    {
        if (!Positive(Gap) || !Positive(NormalDegrees) || !Positive(CurvaturePercent)
            || NormalDegrees > 90 || CurvaturePercent > 100)
            throw new ArgumentException("Invalid verification limits.");
    }
    private static bool Positive(double value) => double.IsFinite(value) && value > 0;
}

// Coverage flags refer to the entire assigned edge interval under a declared
// native/sampling protocol, never just a successful point or a requested setting.
public sealed record EdgeEvidence(string CandidateId, string EdgeKey,
    double? MaximumGap, bool PositionCoverageComplete,
    double? MaximumNormalDegrees = null, bool NormalCoverageComplete = false,
    double? MaximumCurvaturePercent = null, bool CurvatureCoverageComplete = false);

public sealed record GlobalEvidence(string CandidateId,
    Proof ValidBrep = Proof.Unknown,
    Proof FullBoundaryCoverage = Proof.Unknown,
    Proof EveryTargetJoined = Proof.Unknown,
    Proof NoExtraCapBoundaries = Proof.Unknown,
    Proof ParentsPreserved = Proof.Unknown,
    Proof EdgeFaceMapping = Proof.Unknown,
    Proof ShapeAndFeatureChecks = Proof.Unknown)
{
    public IEnumerable<(string Name, Proof Value)> Gates()
    {
        yield return (nameof(ValidBrep), ValidBrep);
        yield return (nameof(FullBoundaryCoverage), FullBoundaryCoverage);
        yield return (nameof(EveryTargetJoined), EveryTargetJoined);
        yield return (nameof(NoExtraCapBoundaries), NoExtraCapBoundaries);
        yield return (nameof(ParentsPreserved), ParentsPreserved);
        yield return (nameof(EdgeFaceMapping), EdgeFaceMapping);
        yield return (nameof(ShapeAndFeatureChecks), ShapeAndFeatureChecks);
    }
}

public sealed record EdgeFinding(string EdgeKey, Grade Preferred, Grade Minimum,
    Grade? HighestSupported, string Reason)
{
    public bool MeetsMinimum => HighestSupported.HasValue && HighestSupported.Value >= Minimum;
    public bool MeetsPreferred => HighestSupported.HasValue && HighestSupported.Value >= Preferred;
}

// Both IDs must change when their respective geometry or contract changes.
// Native integration must show the adjustments BEFORE setting ReviewedAdjustments.
public sealed record Confirmation(string CandidateId, string ContractId,
    bool AcceptRequested, bool ReviewedAdjustments);

public sealed class Assessment
{
    internal Assessment(string candidateId, string contractId, CandidateState state,
        IEnumerable<EdgeFinding> edges, IEnumerable<string> reasons)
    {
        CandidateId = candidateId;
        ContractId = contractId;
        State = state;
        Edges = Array.AsReadOnly(edges.ToArray());
        Reasons = Array.AsReadOnly(reasons.ToArray());
    }
    public string CandidateId { get; }
    public string ContractId { get; }
    public CandidateState State { get; }
    public ReadOnlyCollection<EdgeFinding> Edges { get; }
    public ReadOnlyCollection<string> Reasons { get; }
    public bool HasClosedVerifiedBaseline => State != CandidateState.Rejected;
    public bool UniformRequestedG2 => Edges.Count > 0 && Edges.All(e => e.Preferred == Grade.G2);
    public bool UniformSupportedG2 => Edges.Count > 0 && Edges.All(e => e.HighestSupported == Grade.G2);
    public bool CanCommit(Confirmation confirmation) =>
        confirmation.AcceptRequested
        && confirmation.CandidateId == CandidateId
        && confirmation.ContractId == ContractId
        && (State == CandidateState.Ready
            || (State == CandidateState.ReviewRequired && confirmation.ReviewedAdjustments));
}

public static class BoundaryAcceptance
{
    // This function ASSESSES supplied evidence. It does not produce it, prove
    // analytic G2, repair geometry or relax a locked rule after a failed solve.
    public static Assessment Evaluate(string candidateId, string contractId,
        IEnumerable<EdgeRule> rules, IEnumerable<EdgeEvidence> observations,
        GlobalEvidence global, Limits limits)
    {
        if (string.IsNullOrWhiteSpace(candidateId) || string.IsNullOrWhiteSpace(contractId))
            throw new ArgumentException("Candidate and contract revision identities are required.");
        ArgumentNullException.ThrowIfNull(rules);
        ArgumentNullException.ThrowIfNull(observations);
        ArgumentNullException.ThrowIfNull(global);
        ArgumentNullException.ThrowIfNull(limits);
        limits.Validate();
        var requested = rules.ToArray();
        var measured = observations.ToArray();
        if (requested.Length == 0) throw new ArgumentException("No boundary conditions.");
        foreach (var rule in requested) rule.Validate();
        if (requested.Select(r => r.EdgeKey).Distinct(StringComparer.Ordinal).Count() != requested.Length)
            throw new ArgumentException("Duplicate boundary rule identity.");
        var errors = new List<string>();
        if (global.CandidateId != candidateId || measured.Any(m => m.CandidateId != candidateId))
            errors.Add("STALE_OR_MIXED_CANDIDATE_EVIDENCE");
        foreach (var gate in global.Gates())
            if (gate.Value != Proof.Passed)
                errors.Add(gate.Name + (gate.Value == Proof.Failed ? "_FAILED" : "_UNAVAILABLE"));
        if (measured.Select(m => m.EdgeKey).Distinct(StringComparer.Ordinal).Count() != measured.Length)
            errors.Add("DUPLICATE_EDGE_EVIDENCE");
        var expectedKeys = requested.Select(r => r.EdgeKey).ToHashSet(StringComparer.Ordinal);
        if (measured.Length != requested.Length || !expectedKeys.SetEquals(measured.Select(m => m.EdgeKey)))
            errors.Add("MISSING_OR_UNEXPECTED_EDGE_EVIDENCE");
        if (errors.Count > 0)
            return new Assessment(candidateId, contractId, CandidateState.Rejected,
                Array.Empty<EdgeFinding>(), errors);

        var byKey = measured.ToDictionary(m => m.EdgeKey, StringComparer.Ordinal);
        var findings = requested.Select(r => AssessEdge(r, byKey[r.EdgeKey], limits)).ToArray();
        // G0 is a non-negotiable baseline for EVERY edge, including a sharp one.
        if (findings.Any(f => !f.HighestSupported.HasValue))
            return new Assessment(candidateId, contractId, CandidateState.Rejected, findings,
                findings.Where(f => !f.HighestSupported.HasValue).Select(f => f.EdgeKey + ":" + f.Reason));
        // Preserve a good closed candidate for review even when locked smoothness
        // remains unsatisfied; never label it committable or discard other edges.
        if (findings.Any(f => !f.MeetsMinimum))
            return new Assessment(candidateId, contractId, CandidateState.PreviewOnly, findings,
                findings.Where(f => !f.MeetsMinimum).Select(f => f.EdgeKey + ":BELOW_LOCKED_MINIMUM"));
        if (findings.Any(f => !f.MeetsPreferred))
            return new Assessment(candidateId, contractId, CandidateState.ReviewRequired, findings,
                findings.Where(f => !f.MeetsPreferred).Select(f => f.EdgeKey + ":" + f.Reason));
        return new Assessment(candidateId, contractId, CandidateState.Ready, findings, Array.Empty<string>());
    }

    private static bool Known(double? value, bool complete) => complete
        && value.HasValue && double.IsFinite(value.Value) && value.Value >= 0;

    private static EdgeFinding AssessEdge(EdgeRule rule, EdgeEvidence observation, Limits limits)
    {
        EdgeFinding Result(Grade? grade, string reason) =>
            new(rule.EdgeKey, rule.Preferred, rule.Minimum, grade, reason);
        if (!Known(observation.MaximumGap, observation.PositionCoverageComplete))
            return Result(null, "POSITION_UNAVAILABLE");
        if (observation.MaximumGap!.Value > limits.Gap)
            return Result(null, "POSITION_OUT_OF_TOLERANCE");
        if (!Known(observation.MaximumNormalDegrees, observation.NormalCoverageComplete))
            return Result(Grade.G0, "HIGHER_CONTINUITY_UNAVAILABLE");
        if (observation.MaximumNormalDegrees!.Value > limits.NormalDegrees)
            return Result(Grade.G0, "NORMAL_OUT_OF_TOLERANCE");
        if (!Known(observation.MaximumCurvaturePercent, observation.CurvatureCoverageComplete))
            return Result(Grade.G1, "CURVATURE_UNAVAILABLE");
        if (observation.MaximumCurvaturePercent!.Value > limits.CurvaturePercent)
            return Result(Grade.G1, "CURVATURE_OUT_OF_TOLERANCE");
        return Result(Grade.G2, "G2_SUPPORTED_BY_SUPPLIED_EVIDENCE");
    }
}
