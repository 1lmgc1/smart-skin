# -*- coding: utf-8 -*-
"""P08D1B-FIELD01. Pure Python 2.7/3 helpers; not a geometry solver."""
from __future__ import print_function
import os, json, math, hashlib, uuid, time
try:
    TEXT = unicode
except NameError:
    TEXT = str
PACKAGE = 'P08D1B-FIELD01'

def text(value):
    if isinstance(value, TEXT): return value
    if isinstance(value, bytes): return value.decode('utf-8', 'replace')
    return TEXT(value)

def finite(value):
    return not (math.isnan(float(value)) or math.isinf(float(value)))

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(65536)
            if not b: break
            h.update(b)
    return h.hexdigest()

def safe_child(root, relative):
    if not isinstance(relative, TEXT) or not relative or '\\' in relative:
        raise ValueError('INVALID_RELATIVE_PATH')
    parts = relative.split('/')
    if any(p in ('', '.', '..') or ':' in p for p in parts):
        raise ValueError('UNSAFE_RELATIVE_PATH')
    out = os.path.abspath(os.path.join(root, *parts))
    prefix = os.path.abspath(root) + os.sep
    if not out.startswith(prefix): raise ValueError('PATH_ESCAPES_PACKAGE')
    return out

def read_manifest(root):
    with open(os.path.join(root, 'cases.json'), 'rb') as f:
        raw = f.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024: raise ValueError('MANIFEST_TOO_LARGE')
    m = json.loads(raw.decode('utf-8-sig'))
    validate_manifest(m)
    return m

def validate_manifest(m):
    if m.get('schema') != 1 or m.get('package') != PACKAGE:
        raise ValueError('WRONG_FIELD_PACKAGE')
    cases = m.get('cases', [])
    if not 1 <= len(cases) <= 5: raise ValueError('CASE_COUNT')
    if len(set(c['id'] for c in cases)) != len(cases): raise ValueError('DUPLICATE_CASE')
    all_caps, all_layers = [], []
    for c in cases:
        if c.get('form_status') != 'REJECTED_RESEARCH_ONLY': raise ValueError('DO_NOT_PROMOTE_REJECTED_FORM')
        if c.get('geometry_commit') is not False: raise ValueError('COMMIT_NOT_ALLOWED')
        caps = c.get('caps', [])
        if len(caps) not in (1, 3): raise ValueError('CAP_FACE_COUNT')
        for cap in caps:
            uuid.UUID(cap['object_id']); all_caps.append(cap['object_id'])
            if any(s not in ('left','right','bottom','top') for s in cap['exterior_sides']):
                raise ValueError('UNKNOWN_CAP_SIDE')
        all_layers.append(c['layer'])
        if not finite(c['relief_bound_mm']) or not 0 <= c['relief_bound_mm'] <= .0025:
            raise ValueError('RELIEF_BUDGET')
    if len(set(all_caps)) != len(all_caps): raise ValueError('DUPLICATE_CAP_ID')
    if len(set(all_layers)) != len(all_layers): raise ValueError('SHARED_CASE_LAYER')
    sources = m.get('source_edges', [])
    if len(sources) != 6 or len(set((s['object_id'],s['edge']) for s in sources)) != 6:
        raise ValueError('SIX_UNIQUE_SOURCE_INTERVALS_REQUIRED')
    for s in sources:
        uuid.UUID(s['object_id'])
        if s['edge'] < 0 or s['face'] < 0: raise ValueError('SOURCE_INDEX')
    if set(all_caps).intersection(s['object_id'] for s in sources): raise ValueError('CAP_IS_SOURCE')
    if m.get('default_case') not in [c['id'] for c in cases]: raise ValueError('DEFAULT_CASE')
    if m.get('maximum_doc_tolerance') != .01: raise ValueError('TOLERANCE_CONTRACT')
    return True

class Report(object):
    """Exactly one new file. Flush each record; finish once; verify bytes."""
    def __init__(self, folder, console=None):
        if not os.path.isdir(folder): os.makedirs(folder)
        self.path = os.path.join(folder, 'SmartSkin_Field_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8] + '.txt')
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        self.handle = os.fdopen(fd, 'wb'); self.rows = []; self.closed = False
        self.console = console or (lambda unused: None)
        try:
            self.handle.write(b'\xef\xbb\xbf'); self.handle.flush()
        except BaseException:
            self.handle.close(); self.closed = True; raise
    def emit(self, event, **fields):
        if self.closed: raise ValueError('REPORT_ALREADY_CLOSED')
        line = u'SMARTSKIN_FIELD_' + event + u' | seq=' + text(len(self.rows)+1)
        for key in sorted(fields):
            value = fields[key]
            if isinstance(value, (dict,list,tuple)):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
            line += u' | ' + text(key) + u'=' + text(value).replace(u'\r',u' ').replace(u'\n',u' ')
        raw = (line + u'\r\n').encode('utf-8')
        self.handle.write(raw); self.handle.flush(); self.rows.append(raw)
    def finish(self):
        if self.closed: return self.path
        try:
            self.emit('INTEGRITY', preceding_records=len(self.rows), preceding_sha256=hashlib.sha256(b''.join(self.rows)).hexdigest())
        finally:
            self.handle.close(); self.closed = True
        with open(self.path, 'rb') as f: data = f.read()
        if data != b'\xef\xbb\xbf' + b''.join(self.rows): raise IOError('REPORT_READBACK_MISMATCH')
        self.console('SMARTSKIN_FIELD_SAVED | ' + self.path)
        return self.path


def interval_coverage(intervals, start=0., end=1., tolerance=1e-9):
    """No omitted or multiply owned source intervals; finite coordinates only."""
    if not intervals: return False
    pieces = sorted((min(a,b), max(a,b)) for a,b in intervals)
    current = start
    for a,b in pieces:
        if not finite(a) or not finite(b) or b-a <= tolerance: return False
        if abs(a-current) > tolerance: return False
        current = b
    return abs(current-end) <= tolerance
