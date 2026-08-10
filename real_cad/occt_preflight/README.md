# OpenCascade STEP preflight

This standalone checker intentionally links no OpenCascade DRAW library.  It
imports one STEP file, validates its B-rep, checks shell closure and per-solid
positive volume, triangulates it, and independently checks the derived mesh for
boundary and non-manifold edges.

The batch driver runs one process per model.  A crash, timeout, non-zero exit,
or invalid JSON remains an explicit failed row in the frozen aggregate rather
than silently disappearing from the denominator.

The checker does not heal, sew, fuse, or otherwise modify the imported model.
Consequently its admission result describes the model as received.

