"""Two-stage orchestration tests with real receipt binding and mocked Rhino API.

This is not licensed Rhino execution or a numerical atlas certification.
"""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
from attachment_proof_fixtures import source_model, full_attachment_result, mock_verify_atlas, add_test_descriptors
from test_native_owner_separation import n, Adapter, Geometry
from test_preview_state import FakeDoc, FakeAttributes

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_pipeline_preview_test', ROOT / 'src/SmartSkin.Rhino8/Python/preview.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class NativePreviewPipelineTests(unittest.TestCase):
    def setUp(self):
        self.adapter = Adapter()
        self.owner = Geometry('owner')
        self.patch = Geometry('patch')
        self.patch.IsValid = True
        self.patch.MemoryEstimate = lambda: 1024
        self.guide = Geometry('guide')
        self.guide.IsValid = True
        self.guide.MemoryEstimate = lambda: 256
        self.model = source_model()
        self.result = full_attachment_result()
        add_test_descriptors(self.result, [self.patch], [self.guide])
        self.context = n.NativeOwnerContext([n.OwnerSnapshot('owner', self.owner,
            (n.SelectedSpan('owner:0', 0, (0., 1.)),))], {'source': 'synthetic'}, .001, self.adapter)
        self.state = p.NativeScreenState(self.model, self.context)
        self.capture = SimpleNamespace(model=self.model, verify_sources=lambda doc: (True, 'unchanged'))
        self.rhino = SimpleNamespace(DocObjects=SimpleNamespace(ObjectAttributes=FakeAttributes))
        self.system = SimpleNamespace(Guid=SimpleNamespace(Empty=0))
        self.addCleanup(self.state.close)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(p, '_native_owner_api', return_value=n).start()
        mock.patch.object(p, '_verify_atlas_separation', side_effect=mock_verify_atlas).start()

    def screen(self):
        binding = p._issue_checked_conversion(self.result, [self.patch], [self.guide], self.context)
        return self.state.screen([self.patch], self.result, guides=[self.guide], conversion=binding)

    def verify(self):
        return self.state.verify([self.patch], self.result, guides=[self.guide])

    def commit(self, doc, screen=True):
        return p.commit_new_geometry(doc, self.capture, [self.patch], [self.guide], 1., self.rhino, self.system,
                                     attachment_result=self.result, native_screen=self.state if screen else None)

    def test_only_explicit_numerical_pending_disposition_allows_screening(self):
        self.assertTrue(p.geometry_commit_acceptance(self.result)[0])
        receipt = self.screen()
        self.assertTrue(receipt.report['checked'])
        self.assertIs(self.state.receipt, receipt)
        self.assertFalse(self.result['experimental_commit_allowed'])
        self.assertNotIn('separation_receipt', self.result)
        self.assertTrue(self.verify())

    def test_real_numerical_failures_never_reach_native_calls(self):
        for changes in ({'valid': False}, {'geometry_valid': False}, {'fatal': True},
                        {'disposition': 'blocked'}, {'disposition': 'ready', 'experimental_commit_allowed': True},
                        {'native_screen_pending': False}, {'commit_disposition': 'inspection_only'}):
            result = copy.deepcopy(self.result)
            result.update(changes)
            with self.assertRaisesRegex(RuntimeError, 'Numerical readiness blocked'):
                self.state.screen([self.patch], result)
            self.assertIsNone(self.state.receipt)
        self.assertEqual(self.adapter.calls, [])

    def test_atlas_missing_failed_or_stale_blocks_native_screen(self):
        for atlas in (None, {'checked': True, 'passed': False, 'request': None},
                      {'checked': True, 'passed': True, 'request': {'stale': True}}):
            result = copy.deepcopy(self.result)
            result['atlas_separation'] = atlas or {}
            with self.assertRaisesRegex(RuntimeError, 'atlas'):
                self.state.screen([self.patch], result)
            self.assertIsNone(self.state.receipt)
        self.assertEqual(self.adapter.calls, [])

    def test_result_side_native_pass_flags_cannot_replace_receipt(self):
        self.result['native_owner_screen'] = {'checked': True, 'passed': True}
        doc = FakeDoc()
        with self.assertRaisesRegex(RuntimeError, 'separately held native separation receipt'):
            self.commit(doc, screen=False)
        self.assertEqual(doc.Objects.add_calls, 0)

    def test_pending_result_can_commit_only_after_native_receipt(self):
        doc = FakeDoc()
        with self.assertRaisesRegex(RuntimeError, 'fresh native owner-separation receipt'):
            self.commit(doc)
        self.assertEqual(doc.Objects.add_calls, 0)
        self.screen()
        self.assertEqual(self.commit(doc), (1, 1))
        self.assertFalse(self.result['experimental_commit_allowed'])
        self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_same_values_restored_after_invalidation_require_new_receipt(self):
        old = self.screen()
        self.state.invalidate()
        with self.assertRaisesRegex(RuntimeError, 'screened again'):
            self.verify()
        fresh = self.screen()
        self.assertIsNot(old, fresh)
        self.assertTrue(self.verify())

    def test_failed_screen_discards_old_receipt_and_restoration_cannot_reuse_it(self):
        self.screen()
        self.adapter.distances[((1., 1., 1.), 'owner')] = 0.
        with self.assertRaises(n.SeparationError):
            self.screen()
        self.assertIsNone(self.state.receipt)
        self.adapter.distances.clear()
        with self.assertRaisesRegex(RuntimeError, 'fresh native'):
            self.verify()
        self.screen()
        self.assertTrue(self.verify())

    def test_new_request_or_cancel_during_native_screen_cannot_publish_receipt(self):
        self.adapter.after_events = self.state.invalidate
        with self.assertRaises(n.SeparationError):
            self.screen()
        self.assertIsNone(self.state.receipt)
        self.adapter.after_events = None
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            self.state.screen([self.patch], self.result, cancelled=lambda: True)
        self.assertIsNone(self.state.receipt)

    def test_atlas_must_still_pass_after_long_native_screen(self):
        self.adapter.after_events = lambda: self.result['atlas_separation'].update(passed=False)
        with self.assertRaisesRegex(RuntimeError, 'atlas'):
            self.screen()
        self.assertIsNone(self.state.receipt)

    def test_native_geometry_change_invalidates_receipt_even_after_value_restore(self):
        self.screen()
        self.patch.version += 1
        with self.assertRaisesRegex(RuntimeError, 'changed after exact readback'):
            self.verify()
        self.patch.version -= 1
        self.assertIsNone(self.state.receipt)
        with self.assertRaisesRegex(RuntimeError, 'fresh native'):
            self.verify()

    def test_wrong_request_or_ledger_invalidates_receipt(self):
        self.screen()
        self.result['native_contact_ledger']['geometry_digest'] = 'changed'
        with self.assertRaises(n.SeparationError):
            self.verify()
        self.assertIsNone(self.state.receipt)

    def test_receipt_rechecked_before_each_add_and_after_batch(self):
        for event_point in ('first', 'last'):
            self.screen()
            doc = FakeDoc()
            method = 'AddBrep' if event_point == 'first' else 'AddCurve'
            original = getattr(doc.Objects, method)
            def invalidate_after_add(geometry, attributes):
                identifier = original(geometry, attributes)
                self.state.invalidate()
                return identifier
            setattr(doc.Objects, method, invalidate_after_add)
            with self.assertRaisesRegex(RuntimeError, 'fresh native'):
                self.commit(doc)
            self.assertEqual(doc.Objects.add_calls, 1 if event_point == 'first' else 2)
            self.assertEqual(doc.Objects.deleted, [101] if event_point == 'first' else [102, 101])
            self.assertFalse(doc.Objects.objects[1].IsDeleted)

    def test_closing_disposes_context_and_revokes_receipt(self):
        self.screen()
        self.state.close()
        self.assertTrue(self.owner.disposed)
        self.assertIsNone(self.state.context)
        self.assertIsNone(self.state.receipt)
        self.assertIsNone(self.state.conversion)
        with self.assertRaisesRegex(RuntimeError, 'fresh native'):
            self.verify()

    def test_separate_cold_cached_and_native_stage_budgets_are_explicit(self):
        self.assertEqual(p.COLD_BUILD_SECONDS, 180.)
        self.assertEqual(p.CACHED_BUILD_SECONDS, 60.)
        self.assertEqual(p.NATIVE_SCREEN_SECONDS, 15.)

    def test_checked_conversion_rejects_stale_same_count_native_lists(self):
        binding = p._issue_checked_conversion(self.result, [self.patch], [self.guide], self.context)
        replacement = Geometry('guide')  # Same fingerprint, different unchecked object.
        replacement.MemoryEstimate = lambda: 256
        with self.assertRaisesRegex(RuntimeError, 'converter-issued'):
            self.state.screen([self.patch], self.result, guides=[replacement], conversion=binding)
        replacement = Geometry('patch')
        replacement.MemoryEstimate = lambda: 1024
        with self.assertRaisesRegex(RuntimeError, 'converter-issued'):
            self.state.screen([replacement], self.result, guides=[self.guide], conversion=binding)
        self.assertIsNone(self.state.receipt)

    def test_conversion_is_bound_to_initial_numeric_surfaces_and_guides(self):
        binding = p._issue_checked_conversion(self.result, [self.patch], [self.guide], self.context)
        for key in ('surfaces', 'guides'):
            changed = copy.deepcopy(self.result)
            changed[key][0]['different_descriptor'] = True
            with self.assertRaisesRegex(RuntimeError, 'different surface|descriptors disagree'):
                self.state.screen([self.patch], changed, guides=[self.guide], conversion=binding)

    def test_guide_mutation_before_first_screen_cannot_be_rebound(self):
        binding = p._issue_checked_conversion(self.result, [self.patch], [self.guide], self.context)
        self.guide.version += 1
        with self.assertRaisesRegex(RuntimeError, 'changed after exact readback'):
            self.state.screen([self.patch], self.result, guides=[self.guide], conversion=binding)

    def test_conversion_drift_names_only_changed_generated_component_indices(self):
        binding = p._issue_checked_conversion(self.result, [self.patch], [self.guide], self.context)
        for geometry, expected in ((self.patch, 'Brep indices=[0]; guide indices=[]'),
                                   (self.guide, 'Brep indices=[]; guide indices=[0]')):
            geometry.version += 1
            with self.assertRaises(RuntimeError) as caught:
                p._verify_checked_conversion(binding, self.result, [self.patch], [self.guide], self.context)
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn('owner', str(caught.exception).lower())
            geometry.version -= 1

    def test_result_side_conversion_flag_is_not_provenance(self):
        self.result['conversion_binding'] = {'checked': True}
        with self.assertRaisesRegex(RuntimeError, 'converter-issued'):
            self.state.screen([self.patch], self.result, guides=[self.guide])

    def test_fingerprint_memory_is_bounded_before_serialization(self):
        self.guide.MemoryEstimate = lambda: self.context.limits.max_snapshot_bytes + 1
        with self.assertRaisesRegex(RuntimeError, 'fingerprint memory'):
            p._issue_checked_conversion(self.result, [self.patch], [self.guide], self.context)

    def test_native_guide_mutation_during_add_rolls_back_only_our_additions(self):
        for event_point in ('first', 'last'):
            self.screen()
            doc = FakeDoc()
            method = 'AddBrep' if event_point == 'first' else 'AddCurve'
            original = getattr(doc.Objects, method)
            def mutate_guide_after_add(geometry, attributes):
                identifier = original(geometry, attributes)
                self.guide.version += 1
                return identifier
            setattr(doc.Objects, method, mutate_guide_after_add)
            with self.assertRaisesRegex(RuntimeError, 'changed after exact readback'):
                self.commit(doc)
            self.assertEqual(doc.Objects.deleted, [101] if event_point == 'first' else [102, 101])
            self.assertFalse(doc.Objects.objects[1].IsDeleted)


class ImportFallbackTests(unittest.TestCase):
    def test_missing_versioned_module_uses_only_its_matching_fallback(self):
        import builtins
        original = builtins.__import__
        for alias, fallback, call in (
            ('_smartskin_p08e1_native_owner_separation', 'native_owner_separation', p._native_owner_api),
            ('_smartskin_p08e1_atlas_separation', 'atlas_separation', lambda: p._verify_atlas_separation({}, {}, None))):
            seen = []
            def importing(name, *args, **kwargs):
                seen.append(name)
                if name == alias: raise ModuleNotFoundError('alias unavailable', name=alias)
                if name == fallback: return SimpleNamespace(verify_atlas_separation=lambda *a, **k: True)
                return original(name, *args, **kwargs)
            with mock.patch('builtins.__import__', side_effect=importing):
                call()
            self.assertEqual(seen[:2], [alias, fallback])

    def test_transitive_dependency_failure_never_imports_generic_fallback(self):
        import builtins
        original = builtins.__import__
        for alias, fallback, call in (
            ('_smartskin_p08e1_native_owner_separation', 'native_owner_separation', p._native_owner_api),
            ('_smartskin_p08e1_atlas_separation', 'atlas_separation', lambda: p._verify_atlas_separation({}, {}, None))):
            seen = []
            def importing(name, *args, **kwargs):
                seen.append(name)
                if name == alias: raise ModuleNotFoundError('dependency unavailable', name='missing_installed_dependency')
                return original(name, *args, **kwargs)
            with mock.patch('builtins.__import__', side_effect=importing):
                with self.assertRaises(ModuleNotFoundError) as caught:
                    call()
            self.assertEqual(caught.exception.name, 'missing_installed_dependency')
            self.assertNotIn(fallback, seen)


if __name__ == '__main__':
    unittest.main()
