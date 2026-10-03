using SmartSkin.P08B;

// Synthetic records only. These tests DO NOT run a Rhino solver or measure a surface.
internal static class Program
{
    private const string Candidate = "synthetic-candidate-r1";
    private const string Contract = "synthetic-contract-r1";
    private static readonly Limits Tolerances = new(0.01, 1.0, 5.0);
    private static int _cases;
    private static int _failures;
    private static EdgeRule[] Rules() => new[]
    {
        new EdgeRule("A", Grade.G2, Grade.G0), new EdgeRule("B", Grade.G2, Grade.G0),
        new EdgeRule("C", Grade.G2, Grade.G0), new EdgeRule("D", Grade.G2, Grade.G0),
        new EdgeRule("E", Grade.G0, Grade.G0, BoundaryRole.PreserveFeature),
        new EdgeRule("F", Grade.G0, Grade.G0, BoundaryRole.PreserveFeature),
    };
    private static EdgeEvidence[] Observations() => new[] { "A", "B", "C", "D", "E", "F" }
        .Select((key, i) => new EdgeEvidence(Candidate, key, 0.001, true,
            i < 4 ? 0.1 : 45, true, i < 4 ? 1.0 : null, i < 4)).ToArray();
    private static GlobalEvidence Proofs() => new(Candidate,
        Proof.Passed, Proof.Passed, Proof.Passed, Proof.Passed, Proof.Passed, Proof.Passed, Proof.Passed);
    private static Assessment Assess(EdgeRule[]? rules = null, EdgeEvidence[]? observations = null,
        GlobalEvidence? proof = null, Limits? limits = null) => BoundaryAcceptance.Evaluate(
            Candidate, Contract, rules ?? Rules(), observations ?? Observations(), proof ?? Proofs(), limits ?? Tolerances);
    private static Confirmation Confirm(bool reviewed = true) => new(Candidate, Contract, true, reviewed);
    private static void Check(bool condition) { if (!condition) throw new Exception("Assertion failed."); }
    private static void Throws(Action action)
    {
        try { action(); } catch (ArgumentException) { return; }
        throw new Exception("Expected an explicit argument failure.");
    }
    private static void Test(string name, Action body)
    {
        _cases++;
        try { body(); Console.WriteLine("P08B_POLICY_TEST PASS | " + name); }
        catch (Exception e) { _failures++; Console.WriteLine("P08B_POLICY_TEST FAIL | " + name + " | " + e.Message); }
    }
    public static int Main()
    {
        Test("mixed_4G2_2G0_is_ready_not_uniform_G2", () =>
        {
            var a = Assess(); Check(a.State == CandidateState.Ready && a.CanCommit(Confirm()));
            Check(!a.UniformRequestedG2 && !a.UniformSupportedG2);
            Check(a.Edges.Count(e => e.HighestSupported == Grade.G2) == 4);
        });
        Test("G0_feature_does_not_need_smoothness", () =>
        {
            var o = Observations(); o[4] = o[4] with { MaximumNormalDegrees = null, NormalCoverageComplete = false };
            Check(Assess(observations: o).State == CandidateState.Ready);
        });
        Test("one_curvature_failure_keeps_other_edges_and_needs_review", () =>
        {
            var o = Observations(); o[0] = o[0] with { MaximumCurvaturePercent = 20 };
            var a = Assess(observations: o);
            Check(a.State == CandidateState.ReviewRequired && a.Edges[0].HighestSupported == Grade.G1);
            Check(a.Edges.Skip(1).Take(3).All(e => e.HighestSupported == Grade.G2));
            Check(!a.CanCommit(Confirm(false)) && a.CanCommit(Confirm(true)));
        });
        Test("one_normal_failure_can_be_local_G0_with_review", () =>
        {
            var o = Observations(); o[1] = o[1] with { MaximumNormalDegrees = 10 };
            var a = Assess(observations: o);
            Check(a.State == CandidateState.ReviewRequired && a.Edges[1].HighestSupported == Grade.G0);
        });
        Test("missing_curvature_is_unknown_not_impossible", () =>
        {
            var o = Observations(); o[0] = o[0] with { MaximumCurvaturePercent = null };
            var a = Assess(observations: o);
            Check(a.State == CandidateState.ReviewRequired && a.Edges[0].Reason == "CURVATURE_UNAVAILABLE");
        });
        Test("incomplete_curvature_coverage_cannot_claim_G2", () =>
        {
            var o = Observations(); o[0] = o[0] with { CurvatureCoverageComplete = false };
            Check(Assess(observations: o).Edges[0].HighestSupported == Grade.G1);
        });
        Test("locked_G2_failure_keeps_baseline_but_cannot_commit", () =>
        {
            var r = Rules(); r[0] = r[0] with { Minimum = Grade.G2 };
            var o = Observations(); o[0] = o[0] with { MaximumCurvaturePercent = 20 };
            var a = Assess(r, o);
            Check(a.State == CandidateState.PreviewOnly && a.HasClosedVerifiedBaseline && !a.CanCommit(Confirm()));
        });
        Test("gap_failure_never_becomes_G0_success", () =>
        {
            var o = Observations(); o[4] = o[4] with { MaximumGap = 0.02 };
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("missing_G0_is_not_zero_gap", () =>
        {
            var o = Observations(); o[0] = o[0] with { MaximumGap = null };
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("NaN_gap_rejected", () =>
        {
            var o = Observations(); o[0] = o[0] with { MaximumGap = double.NaN };
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("negative_gap_rejected", () =>
        {
            var o = Observations(); o[0] = o[0] with { MaximumGap = -1 };
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("incomplete_position_coverage_rejected", () =>
        {
            var o = Observations(); o[0] = o[0] with { PositionCoverageComplete = false };
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("G2_metric_without_G1_does_not_claim_G2", () =>
        {
            var o = Observations(); o[0] = o[0] with { NormalCoverageComplete = false };
            Check(Assess(observations: o).Edges[0].HighestSupported == Grade.G0);
        });
        Test("nonfinite_higher_metric_is_unavailable", () =>
        {
            var o = Observations(); o[0] = o[0] with { MaximumNormalDegrees = double.PositiveInfinity };
            Check(Assess(observations: o).Edges[0].Reason == "HIGHER_CONTINUITY_UNAVAILABLE");
        });
        Test("all_targets_required_even_on_sharp_side", () => Check(
            Assess(observations: Observations().Take(5).ToArray()).State == CandidateState.Rejected));
        Test("duplicate_edge_measurements_rejected", () =>
        {
            var o = Observations(); o[1] = o[0];
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("unexpected_edge_measurement_rejected", () =>
        {
            var o = Observations(); o[0] = o[0] with { EdgeKey = "not-requested" };
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("selection_order_does_not_assign_continuity", () =>
        {
            var a = Assess(observations: Observations().Reverse().ToArray());
            Check(a.State == CandidateState.Ready && a.Edges[0].EdgeKey == "A");
        });
        Test("no_Frankenstein_candidate_measurements", () =>
        {
            var o = Observations(); o[0] = o[0] with { CandidateId = "different-geometry" };
            Check(Assess(observations: o).State == CandidateState.Rejected);
        });
        Test("stale_global_proof_rejected", () => Check(
            Assess(proof: Proofs() with { CandidateId = "old" }).State == CandidateState.Rejected));
        Test("failed_join_rejected", () => Check(
            Assess(proof: Proofs() with { EveryTargetJoined = Proof.Failed }).State == CandidateState.Rejected));
        Test("unmeasured_join_rejected", () => Check(
            Assess(proof: Proofs() with { EveryTargetJoined = Proof.Unknown }).State == CandidateState.Rejected));
        Test("invalid_Brep_rejected", () => Check(
            Assess(proof: Proofs() with { ValidBrep = Proof.Failed }).State == CandidateState.Rejected));
        Test("extra_boundary_rejected", () => Check(
            Assess(proof: Proofs() with { NoExtraCapBoundaries = Proof.Failed }).State == CandidateState.Rejected));
        Test("source_edit_not_authorized_by_fallback", () => Check(
            Assess(proof: Proofs() with { ParentsPreserved = Proof.Failed }).State == CandidateState.Rejected));
        Test("mapping_unknown_rejected", () => Check(
            Assess(proof: Proofs() with { EdgeFaceMapping = Proof.Unknown }).State == CandidateState.Rejected));
        Test("coverage_unknown_rejected", () => Check(
            Assess(proof: Proofs() with { FullBoundaryCoverage = Proof.Unknown }).State == CandidateState.Rejected));
        Test("shape_and_feature_checks_cannot_be_skipped", () => Check(
            Assess(proof: Proofs() with { ShapeAndFeatureChecks = Proof.Unknown }).State == CandidateState.Rejected));
        Test("explicit_accept_required", () => Check(!Assess().CanCommit(Confirm() with { AcceptRequested = false })));
        Test("stale_candidate_acceptance_rejected", () => Check(!Assess().CanCommit(Confirm() with { CandidateId = "old" })));
        Test("stale_contract_acceptance_rejected", () => Check(!Assess().CanCommit(Confirm() with { ContractId = "old" })));
        Test("duplicate_rule_identity_invalid", () =>
        {
            var r = Rules(); r[1] = r[0]; Throws(() => Assess(r));
        });
        Test("cannot_raise_minimum_above_preferred", () =>
        {
            var r = Rules(); r[0] = r[0] with { Minimum = Grade.G2, Preferred = Grade.G1 }; Throws(() => Assess(r));
        });
        Test("positional_feature_not_implicitly_smooth", () =>
        {
            var r = Rules(); r[4] = r[4] with { Preferred = Grade.G2 }; Throws(() => Assess(r));
        });
        Test("nonfinite_limits_rejected", () => Throws(() => Assess(limits: Tolerances with { Gap = double.NaN })));
        Test("evidence_snapshot_cannot_be_changed_by_callers_array", () =>
        {
            var o = Observations(); var a = Assess(observations: o);
            o[0] = o[0] with { MaximumGap = 500 };
            Check(a.State == CandidateState.Ready && a.Edges[0].HighestSupported == Grade.G2);
        });
        Console.WriteLine($"P08B_POLICY_SUMMARY | cases={_cases} | failed={_failures} | scope=SYNTHETIC_POLICY_ONLY | rhino_native=NOT_RUN");
        return _failures == 0 ? 0 : 1;
    }
}
