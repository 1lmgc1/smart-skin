from pathlib import Path
import os
root=Path(__file__).parent
names=('mixed_kernel.py','adaptive_boundary.py','shape_guard.py','stable_refinement.py','rhino_stable_adapter.py')
parts=[]
for index,name in enumerate(names):
    source=(root/name).read_text(encoding='utf-8')
    if index:
        source='\n'.join(line for line in source.split('\n') if not line.startswith((
            'from __future__ import division','from mixed_kernel import ',
            'from adaptive_boundary import ','from shape_guard import ',
            'from stable_refinement import ')))
    source=source.replace("CODE_COMMIT = 'WORKTREE'", "CODE_COMMIT = "+repr(os.environ.get('GITHUB_SHA','WORKTREE')))
    parts.append(source)
out=Path(os.environ.get('ARTIFACT_DIR','construction-artifact'));out.mkdir(exist_ok=True,parents=True)
(out/'SmartSkin_MixedBoundary_Prototype.py').write_text('\n\n'.join(parts),encoding='utf-8')
print(out/'SmartSkin_MixedBoundary_Prototype.py')
