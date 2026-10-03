from pathlib import Path
import os
root=Path(__file__).parent
kernel=(root/'mixed_kernel.py').read_text(encoding='utf-8')
adaptive=(root/'adaptive_boundary.py').read_text(encoding='utf-8').replace('from __future__ import division\n','').replace('from mixed_kernel import SIDES, Patch, basis, knots, qr_fit, finite, norm, sub, add, mul\n','')
adapter=(root/'rhino_prototype.py').read_text(encoding='utf-8').replace('from __future__ import division\n','').replace('from mixed_kernel import *\n','').replace('from adaptive_boundary import adaptive_coons\n','')
adapter=adapter.replace("CODE_COMMIT = 'WORKTREE'", "CODE_COMMIT = "+repr(os.environ.get('GITHUB_SHA','WORKTREE')))
out=Path(os.environ.get('ARTIFACT_DIR','construction-artifact'));out.mkdir(exist_ok=True,parents=True)
(out/'SmartSkin_MixedBoundary_Prototype.py').write_text(kernel+'\n\n'+adaptive+'\n\n'+adapter,encoding='utf-8')
print(out/'SmartSkin_MixedBoundary_Prototype.py')
