# PreFer changelog

## AWS hosted-model preset expansion

Image: `ghcr.io/cvalusek/prefer:sha-53b2f31@sha256:3bb7b4bbeddeff0441a91cf0d0074541895423c26503db213b3b1989762254d2`

Runtime: llama.cpp `server-cuda-b10362`

- AWS `general.ini` presets are now cumulative by instance size. Use a family
  or single-model preset when you do not want every supported model prestaged.
- G6 adds Muse Q4 at 1×128K and raises Gemma E4B from 2×128K to 4×128K.
- G6e adds a cumulative general preset plus Qwen3.6 27B and 35B-A3B Q6 family
  and single-model presets at 1×192K. Gemma 26B changes from 4×128K to 2×256K;
  Gemma 31B remains 1×256K.
- G7e general now includes all lower-tier models. New Gemma family and
  single-model presets run 26B at 4×256K and 31B at 2×256K. Qwen3.6 27B/35B
  increase to 4×256K, GLM-4.7-Flash to 4×202,752, and Muse Q6 uses 4×128K.
- DeepSeek V4 Flash 0731 increases from 1×256K to the verified 4×384K shape,
  retaining its Q4 target, Q8 DSpark companion, and f16 K/V cache.
- Prestaging manifests were regenerated for every changed and new preset.
  Model artifacts, aliases, the v1 client contract, `models-max=1`, and the
  llama.cpp runtime pin are unchanged.
