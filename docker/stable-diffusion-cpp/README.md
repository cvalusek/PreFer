# PreFer image runtime

This sibling runtime wraps a pinned
[stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) CUDA
server with PreFer's generated model catalog, immutable artifact validation,
deployment inventory, and one-model lazy router. It is intentionally much
narrower than ComfyUI: clients get stable HTTP endpoints and curated model
choices without owning workflow graphs.

## API

The public service listens on container port 8080 and exposes:

- `GET /health`
- `GET /v1/models`
- `POST /v1/images/generations`
- `POST /v1/images/edits`

Discovery is side-effect free. `GET /v1/models` reports every configured model,
its capabilities, precision, staging state, and active state without downloading
or loading it. Prestaging runs in the background. The first generation or edit
request for a model waits for that model's files, starts a private
stable-diffusion.cpp worker, and then proxies the request. One worker remains
resident at a time and unloads after 30 idle minutes.

Generate an image:

```bash
curl http://localhost:8082/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{"model":"z-image-turbo","prompt":"a cinematic photograph of a lighthouse in a thunderstorm","size":"1024x1024","response_format":"b64_json"}'
```

Edit an image:

```bash
curl http://localhost:8082/v1/images/edits \
  -F "model=qwen-image-edit-2511" \
  -F "image=@input.png" \
  -F "prompt=replace the daytime sky with a realistic star field" \
  -F "size=1024x1024" \
  -F "response_format=b64_json"
```

`X-Prefer-Model` or a `model` query parameter can select a model for clients
that cannot include `model` in a multipart body. If no model is supplied, the
first model in the selected config is used. Unsupported model/capability pairs
fail before a worker is started.

The upstream native async `/sdcpp/v1` and WebUI `/sdapi/v1` surfaces are not
routed in this first release because their jobs outlive a single request and
would make safe model swapping ambiguous.

## Models

| Request model | Capabilities | Curated lanes | Role |
| --- | --- | --- | --- |
| `flux-2-klein-4b` | generation, edit | Q4, Q8, and official BF16 | Fast four-step generation and instruction editing |
| `z-image-turbo` | generation | Q4, Q6, and Q8 | Fast eight-step generation |
| `qwen-image` | generation | Q4, Q6, and Q8 | Higher-quality generation and text rendering |
| `qwen-image-edit-2511` | edit | Q4, Q6, and Q8 | Dedicated instruction editing with its required BF16 encoder |
| `sdxl-1.0` | generation, edit | FP16 | Lightweight fallback for generation and maskless img2img |

Every target, text encoder, VAE, and other companion artifact is pinned to an immutable
Hugging Face revision, byte size, and SHA-256. Qwen Image Edit 2511 always adds
`qwen_image_zero_cond_t=true`; omitting it is a documented quality regression.
SDXL does not advertise masks, inpainting, or ControlNet. stable-diffusion.cpp
documents its current ControlNet path for SD 1.5, so adding that capability
requires a separate exact runtime/model smoke.

Artifact staging uses Hugging Face's `hf` CLI and Xet. Downloads land in stable
hidden paths on the image model volume, so stopping the container preserves
resumable `.incomplete` state. Exact size and SHA-256 are checked before a
same-volume atomic rename publishes a component. Stat-bound completion markers
avoid hashing unchanged multi-gigabyte files on every restart; legacy files are
hashed once when their selected lane is first staged. Shared encoders and VAEs
are deduplicated across model keys before bounded parallel work begins.

The catalog is configuration-complete but the hardware routes remain
`configuration-only` until their first exact-card load, generation/edit,
memory, and output-quality smoke. FLUX.2 Klein also retains a VERIFY item for
an open upstream metadata-validation report on a Vulkan path; CUDA promotion
requires the same pinned tuple to load and produce a non-corrupt image.

## Deployment configs

Generated configs live under `server-configs/<provider>/<gpu>/<count>/` and
always have a sibling `.prestage` manifest. Each supported machine gets:

- `general.json` for all capabilities available on that machine;
- `fast.json`, `generation.json`, `edit.json`, and `quality.json` where useful;
- one JSON config per model.

The initial lane matrix is:

| Hardware | FLUX.2 Klein | Z-Image | Qwen Image / Edit | SDXL |
| --- | --- | --- | --- | --- |
| 8 GB local | Q4 + Q4 encoder, CPU offload | Q4 + Q4 encoder, CPU offload | Not included | FP16, CPU offload |
| 12 GB local | Q8 + Q4 encoder, CPU offload | Q6 + Q4 encoder, CPU offload | Not included | FP16, CPU offload |
| 24–32 GB | Official BF16 + Q8 encoder | Q8 + Q8 encoder | Q4 generation; dedicated Qwen Edit omitted | FP16 |
| 48 GB | Official BF16 + Q8 encoder | Q8 + Q8 encoder | Q6 + BF16 encoder | FP16 |
| 80–288 GB | Official BF16 + Q8 encoder | Q8 + Q8 encoder | Q8 + BF16 encoder | FP16 |

AWS configs cover `g6.xlarge`, `g6e.xlarge`, and `g7e.2xlarge`. Generic local
configs cover RTX 4060 8 GB, RTX A2000 8 GB, GTX 1070 Ti, and TITAN X Pascal.
RunPod configs cover every checked-in one-card 24–288 GB NVIDIA inventory
choice using the exact API `provider_gpu_type_id`. RunPod prices and bundled
host resources are dated observations, not stable provisioning constraints.
Pascal and every generated provider route require an exact smoke; the pinned
upstream CUDA image is published for Linux AMD64 only.

## Local Compose

The image service is part of the default application:

```bash
docker compose up --build image
curl http://localhost:8082/v1/models
```

The default config contains the primary lane for all five models and stages
them in the background. Select a smaller generated config when only one model
or bundle is wanted:

```dotenv
IMAGE_SERVER_CONFIG=/server-configs/local/titan-x-pascal/1x/fast.json
IMAGE_PRESTAGE_MODELS=
```

Environment variables:

- `IMAGE_PORT` changes the host port from 8082.
- `PREFER_IMAGE_MODEL_VOLUME` names the persistent `/models` volume.
- `IMAGE_SERVER_CONFIG` selects a generated config; blank uses the general
  default.
- `IMAGE_PRESTAGE_MODELS` overrides the sibling prestage manifest. Blank uses
  the selected config; `none` skips downloads.
- `IMAGE_DOWNLOAD_JOBS` accepts 1 through 8 independent artifact transfers and
  defaults to 4.
- `HF_TOKEN`, `HF_HUB_DISABLE_XET`, and the `HF_XET_*` controls are passed to
  Hugging Face staging. Xet high-performance mode is enabled by default.

The local Compose path is Hugging Face-only and does not configure S3. Image
discovery still starts immediately and does not wait for background staging.
Requests wait only for their selected files and verification markers. An
explicit `none` remains a no-download choice; pre-existing exact-size files
without markers become usable after that empty background pass completes.

## Generated inventory

Source ownership is split so no giant hand-edited catalog is required:

- `runtime.json` owns the pinned stable-diffusion.cpp image and source.
- `models/<family>/<model>/model.json` owns model-wide facts and quant lanes.
- `deployment-bundles.json` owns related capability bundles.
- `deployment-scenarios/` owns hardware lane selection.
- `download-artifacts.sh` owns the checked-in resumable transfer behavior.
- `generate.py` emits configs, prestage manifests, the artifact resolver/map
  in `model-downloads.generated.sh`, and `deployment-inventory.generated.json`.

Regenerate and verify with:

```bash
python docker/stable-diffusion-cpp/generate.py
python docker/stable-diffusion-cpp/generate.py --check
python -m unittest discover -s docker/stable-diffusion-cpp/tests -v
python -m unittest benchmark.tests.test_artifact_downloads -v
```

The image embeds the NeurOn provisioning contract at
`/deployment-inventory.json`. The grouped PreFer release includes the same
bytes as `prefer-image-deployment-inventory.json`. It includes runtime identity,
platform, exact artifacts, configured request IDs, capabilities, provider GPU
IDs, staged bytes, config paths, prestaging, residency, and verification state.

## Release and operating boundary

The published tags are `image-cuda12` and
`image-cuda12-sha-<commit>`. The base image is an immutable digest of upstream's
moving `master-cuda` publication at source
`be0e34480dada95f8ce9a021bbb95c5de85d67c7`. Unlike llama.cpp and audio.cpp,
this upstream CUDA artifact currently provides Linux AMD64 only, so the PreFer
image deliberately does not claim ARM64.

The service has no built-in authentication. Keep it behind NeurOn or another
trusted authenticated boundary rather than exposing it directly to the public
Internet.
