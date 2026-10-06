"""Synthetic metadata for transaction tests, not native-evidence certification."""
import copy


def shared_tolerances():
    return {'position': 1e-6, 'normal_angle_degrees': .1, 'shape_operator': 1e-5}


def edit_result(request, positions=None):
    result = full_attachment_result()
    result.update(edit_request=copy.deepcopy(request), handle_positions_request=copy.deepcopy(request),
                  handle_positions=copy.deepcopy(positions if positions is not None else
                                                 {key: [0., 0., 1.] for key in request['values']}),
                  edit_proof={'schema': 'smartskin.edit-proof.v2', 'checked': True,
                              'source_2jets_unchanged': True, 'shared_2jets_compatible': True,
                              'symmetry_checked': True, 'symmetry_compatible': True,
                              'symmetry_residual': 1e-9, 'symmetry_tolerance': 1e-6,
                              'shared_residuals': {'position': 1e-9, 'normal_angle_degrees': .01, 'shape_operator': 1e-7},
                              'shared_tolerances': shared_tolerances()})
    result['atlas_separation']['request'] = copy.deepcopy(request)
    return result


def source_model():
    def edge(key, domain, points, reverse=False):
        return {'source_key': key, 'original_curve_domain': list(domain),
                'traversal_domain': list(reversed(domain)) if reverse else list(domain),
                'reference_corners': [{'edge_end': index, 'edge_parameter': domain[index],
                                       'point': list(points[index])} for index in (0, 1)]}
    roles = {'upper': [edge('synthetic-upper-edge', (10.0, 20.0), ((0, 0, 0), (2, 0, 0)))],
             'side0': [edge('synthetic-side0-edge', (-2.0, 4.0), ((0, 0, 0), (0, 2, 0)))],
             'side1': [edge('synthetic-side1-edge', (8.0, 12.0), ((2, 2, 0), (2, 0, 0)), reverse=True)],
             'lower': [edge('synthetic-lower-edge', (0.0, 1.0), ((0, 2, 0), (2, 2, 0)))]}
    return {'absolute_tolerance': 1e-6,
            'source_boundaries': {'schema': 'native-boundaries-v1', 'complete': True,
                                  'status': 'validated', 'source_edge_count': 4, 'roles': roles}}


def full_attachment_result(schema='smartskin.attachments.v2'):
    return {'valid': True, 'geometry_valid': True, 'fatal': False, 'experimental_commit_allowed': False,
            'disposition': 'native_screen_pending', 'native_screen_pending': True,
            'atlas_separation': {'checked': True, 'passed': True, 'request': None},
            'native_contact_ledger': {'schema': 'smartskin.native-contact-ledger.v1', 'checked': True,
                'source_digest': 'synthetic-source', 'geometry_digest': 'synthetic-geometry',
                'contacts': [], 'point_contacts': [],
                'interval_units': 'actual generated varying-axis and original selected source-curve parameters',
                'internal_seams_are_allowed_contacts': False},
            'attachment_proof': {'schema': schema, 'checked': True,
                                 'source_full_finite_boundary_pass': True,
                                 'shared_full_finite_boundary_pass': True,
                                 'corner_policy': 'hard_upper_source_corners',
                                 'excluded_intervals': [], 'excluded_points': []}}


def mock_verify_atlas(result, source, request):
    """Contract stub only. Real atlas hashing/screening has separate tests."""
    proof = result.get('atlas_separation', {})
    if proof.get('checked') is not True or proof.get('passed') is not True or proof.get('request') != request:
        raise RuntimeError('Synthetic atlas receipt is missing, failed, or stale.')
    return True


def add_test_descriptors(result, breps, guides):
    """Mock-converter descriptor placeholders; no native geometry claim."""
    result.setdefault('surfaces', [{'synthetic_patch': i} for i in range(len(breps))])
    result.setdefault('patches', result['surfaces'])
    result.setdefault('guides', [{'synthetic_guide': i} for i in range(len(guides))])


def native_screen_fixture(preview, capture, breps, result, request=None, guides=()):
    """Use real receipt issuance/binding with the native worker's mock adapter."""
    from test_native_owner_separation import n, Adapter, Geometry
    for index, brep in enumerate(tuple(breps) + tuple(guides)):
        if not hasattr(brep, 'name'): brep.name = 'synthetic-preview-patch-' + str(index)
        if not hasattr(brep, 'version'): brep.version = 0
        brep.disposed = False
        brep.bbox = ((0., 0., 0.), (2., 2., 2.))
        brep.witnesses = ((1., 1., 1.),)
        brep.MemoryEstimate = lambda: 1024
    context = n.NativeOwnerContext([n.OwnerSnapshot('owner', Geometry('owner'),
        (n.SelectedSpan('owner:0', 0, (0., 1.)),))], {'source': 'synthetic'}, .001, Adapter())
    state = preview.NativeScreenState(capture.model, context)
    add_test_descriptors(result, breps, guides)
    binding = preview._issue_checked_conversion(result, breps, guides, context)
    state.screen(breps, result, request=request, guides=guides, conversion=binding)
    return state
