# PreFer audio.cpp runtime

This sibling runtime adds local speech recognition, speech synthesis, music
generation, and full-duplex speech-to-speech without mixing audio model
lifecycle or API behavior into the llama.cpp router. It uses
[audio.cpp](https://github.com/0xShug0/audio.cpp), whose server provides
OpenAI-style audio routes, native GGUF loading, CUDA/CPU backends, lazy model
loading, and bounded LRU residency.

## Images

Both images are published in the same `ghcr.io/cvalusek/prefer` repository as
the llama runtime:

| Variant | Moving tag | Immutable release tag |
| --- | --- | --- |
| CUDA 12 | `audio-cuda12` | `audio-cuda12-sha-<commit>` |
| CPU | `audio-cpu` | `audio-cpu-sha-<commit>` |

They wrap the upstream dual-architecture `full-cuda12` and `full-cpu` images
at source revision `6d530f4052ca93b5cd84ef6124406dcf85542a6f` and immutable OCI indexes.
Exact base indexes and per-platform manifests live in `runtime.json` and the
generated deployment inventory. `latest` remains a llama.cpp compatibility
tag and never points at audio.cpp.

The audio deployment inventory includes the two backend-level images plus
generated CUDA deployment choices for AWS G6/G6e, the supported local cards,
and RunPod's current 24-48 GB card inventory. The image still retains only one
model at a time; a multi-model config controls what can be explored and what is
prestaged, not simultaneous GPU residency. Exact device fit, latency, and
quality remain target-specific verification gates where the inventory says
`configuration-only`.

## Deployment bundles

Every supported CUDA target exposes the relevant bundles and a single-model
alternative for each included route:

| Config | Included capabilities |
| --- | --- |
| `general` | All seven speech, voice, conversation, and music routes. |
| `speech` | ASR, TTS Base, CustomVoice, and VoiceDesign. |
| `assistant` | ASR, TTS Base, and CustomVoice. |
| `voice-lab` | TTS Base, CustomVoice, and VoiceDesign. |
| `conversation` | PersonaPlex full-duplex speech-to-speech. |
| `music` | ACE-Step and MiniMax Music. |

`general` is the exploration surface. The smaller bundles are useful when two
or more related capabilities belong on one host without staging unrelated
artifacts. Single-model configs are the lowest-overhead provisioning choice
when a controller already knows the desired capability.

Generated config paths mirror the provider and hardware, for example
`/server-configs/aws/g6/xlarge/general.json` and
`/server-configs/runpod/l40s/1x/music.json`. Set `AUDIO_SERVER_CONFIG` to the
chosen path. With `AUDIO_PRESTAGE_MODELS` blank, the entrypoint reads the
config's sibling `.prestage` manifest; an explicit comma-separated value still
overrides it, and `none` skips staging.

AWS provides `g6.xlarge` (L4 24 GB) and `g6e.xlarge` (L40S 48 GB) choices.
RunPod provides exact one-card inventory entries for L4, RTX 3090/4090/5090,
RTX A5000/A6000, A40, L40/L40S, RTX 6000 Ada, and the 24/48 GB RTX PRO 6000
MIG offers. Local profiles cover RTX 4060 8 GB, RTX A2000 8 GB, GTX 1070 Ti,
and TITAN X Pascal. The 8 GB and GTX 1070 Ti profiles intentionally expose
only the Qwen speech/voice routes; the owner-smoked TITAN X profile exposes the
complete exploration set.

## Model set

| Request model id | Prestage key | Task | Artifact | Why this lane |
| --- | --- | --- | --- | --- |
| `qwen3-tts-0.6b` | `qwen3-tts-0.6b-bf16` | TTS / voice cloning | Qwen3 TTS 0.6B Base BF16, 2.52 GB | TTS fidelity is more sensitive to quantization, and BF16 is only about 525 MB larger than Q8 here. |
| `qwen3-tts-1.7b-customvoice` | `qwen3-tts-1.7b-customvoice-bf16` | TTS / packaged voices / style control | Qwen3 TTS 1.7B CustomVoice BF16, 4.18 GB | Provides stable built-in voices and instruction-driven delivery without a reference recording. |
| `qwen3-tts-1.7b-voicedesign` | `qwen3-tts-1.7b-voicedesign-bf16` | voice design | Qwen3 TTS 1.7B VoiceDesign BF16, 4.18 GB | Creates a voice from a written instruction without a reference recording. |
| `qwen3-asr-0.6b` | `qwen3-asr-0.6b-q8` | offline or live STT | Qwen3 ASR 0.6B Q8_0, 1.15 GB | Compact primary transcription lane with upstream streaming support. |
| `ace-step-1.5` | `ace-step-1.5-turbo-q8` | music generation / editing | ACE-Step 1.5 Turbo Q8_0, 6.19 GB | Preserves a high-quality local lane with substantially more memory headroom than BF16. |
| `minimax-music-3` | `minimax-music-3-q4` | music generation | MiniMax Music 3 mixed Q4_0/Q8_0 package, 8.45 GB | Upstream's balanced package; the route remains experimental in audio.cpp. |
| `personaplex-7b` | `personaplex-7b-q4` | speech-to-speech conversation | PersonaPlex 7B Q4_K, 7.86 GB | Practical English conversational lane with a 512 MiB graph arena for 12 GB cards. |

The inventory uses audio.cpp's framework task code `gen` for both music
routes; `music` above is the user-facing capability.

Artifacts are downloaded at immutable revisions, checked by exact byte size
and SHA-256, and stored under `/models`. MiniMax is a 13-file package whose
configs, tokenizer, and component GGUFs are all pinned and checked. Official
base revisions and licenses are recorded in the per-model catalogs. No Git LFS
objects are added to this repository.

Staging uses Hugging Face's `hf` CLI and Xet rather than direct `curl` URLs.
Each artifact has a stable hidden staging path on the audio model volume, so a
container stop retains Hugging Face's resumable `.incomplete` state. The final
path is replaced only after exact size and SHA-256 validation, using a
same-volume atomic rename. Unchanged artifacts then use a stat-bound completion
marker; an existing pre-marker installation is hashed once after upgrade and
does not pay that cost on later starts. `AUDIO_DOWNLOAD_JOBS` defaults to four
independent artifact paths and accepts 1 through 8. Shared paths are
deduplicated before jobs launch, and failures are joined and reported in stable
catalog order.

The container stages as root because RunPod and other external mounts replace
the image-layer ownership of `/models`. This matches the llama.cpp container
and keeps lock files, Hugging Face resume state, verified staging files, final
artifacts, and completion markers on the persistent volume. Do not replace this
with a build-time `chown`: it is hidden as soon as an external volume is mounted.

The default config registers all seven ids lazily, retains only one model at a
time, and unloads an idle resident model after 30 minutes. Requests for another
id evict the least-recently-used idle model and reload it. audio.cpp serializes
requests per model, so this deployment is for bounded assistant audio, not
high-concurrency serving.

The CUDA config deliberately disables audio.cpp's generic pre-load memory
guard. Its fixed `1.5x` file-size estimate rejects the pinned PersonaPlex Q4
artifact on a 12 GB card before considering the model's supported 512 MiB graph
arena, while a direct load and inference fits. The curated one-model residency
limit still prevents aggregate model residency; an undersized device may report
an allocator/OOM error when a selected route itself does not fit.

## Local CUDA start

The audio service starts with the default Compose application on port 8081 and
uses separate model/voice volumes:

```bash
docker compose up --build
curl http://localhost:8081/health
curl http://localhost:8081/v1/models
```

Use `docker compose up audio` to run only audio.cpp, or
`docker compose up prefer` to run only llama.cpp.

With both `AUDIO_SERVER_CONFIG` and `AUDIO_PRESTAGE_MODELS` blank or unset,
first start uses the all-capabilities default and stages every primary package.
Set a generated server config to stage its matching sidecar, set
`AUDIO_PRESTAGE_MODELS=none` to skip downloads, or provide a comma-separated
subset of the prestage keys in the table above. The full default set is about
34.5 GB. Both audio variants' health checks allow four hours for this one-time staging; the
service becomes healthy immediately once the server is ready.

Compose passes `HF_TOKEN` plus the same `HF_HUB_DISABLE_XET` and `HF_XET_*`
controls as the llama service. Xet high-performance mode is enabled by default
for audio staging and can be overridden for a constrained host.

The CPU image is intentionally separate rather than pretending that CPU and
CUDA are interchangeable performance tiers:

```bash
docker build -f docker/audio-cpp/Dockerfile.cpu -t prefer:audio-cpu-local docker/audio-cpp
docker run --rm -p 8081:8080 -v prefer-audio-model-cache:/models prefer:audio-cpu-local
```

## Requests

Transcribe an uploaded WAV using the OpenAI-compatible multipart route:

```bash
curl http://localhost:8081/v1/audio/transcriptions \
  -F model=qwen3-asr-0.6b \
  -F language=en \
  -F file=@sample.wav
```

`qwen3-asr-0.6b` is configured in streaming mode, so native clients can also
use `POST /v1/audio/transcriptions/live` with raw PCM for partial results.

The 0.6B TTS Base model is a voice-cloning model. Supply a reference WAV and
its transcript:

```bash
curl http://localhost:8081/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -o speech.wav \
  -d '{
    "model": "qwen3-tts-0.6b",
    "input": "PreFer is serving this sentence through audio.cpp.",
    "voice_ref": "/voices/reference.wav",
    "reference_text": "The exact transcript of the reference recording."
  }'
```

Place server-side reference files in the `prefer-audio-voices` volume, or use
audio.cpp's base64 `voice_ref` request form. A managed voice catalog is a later
product decision; this release does not bake a voice or enable the upstream
download-management UI.

The 1.7B CustomVoice model uses Qwen's packaged speakers and accepts an
optional style instruction. The 1.7B VoiceDesign model creates a voice from an
instruction and does not need reference audio. Both are offline generation
routes in audio.cpp; CustomVoice uses `tts`, while VoiceDesign uses the
framework's `vdes` task. Use `/v1/tasks/run` when sending the complete native
request fields, especially for VoiceDesign.

```bash
curl http://localhost:8081/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -o customvoice.wav \
  -d '{
    "model": "qwen3-tts-1.7b-customvoice",
    "input": "A stable packaged assistant voice.",
    "options": {
      "speaker": "Vivian",
      "instruct": "Warm, clear, and confident."
    }
  }'
```

```bash
curl http://localhost:8081/v1/tasks/run \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3-tts-1.7b-voicedesign",
    "request": {
      "text": "A voice created from a written instruction.",
      "instruct": "A warm adult narrator with calm, articulate delivery."
    }
  }'
```

The generic task response is JSON with the WAV in its base64 `audio` field.

ACE-Step and MiniMax use audio.cpp's generic task endpoint. For example:

```bash
curl http://localhost:8081/v1/tasks/run \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "ace-step-1.5",
    "request": {
      "text": "bright electronic instrumental with a steady pulse",
      "task_route": "text2music",
      "duration_seconds": 10,
      "num_inference_steps": 4,
      "seed": 42
    }
  }'
```

Use the same endpoint with `"model": "minimax-music-3"`, a music description
in `request.text`, and required lyrics in `request.options.lyrics`. Its adapter
remains experimental in audio.cpp.

PersonaPlex uses `POST /v1/audio/speech/live` for native full-duplex audio. It
includes the packaged NATF/NATM/VARF/VARM voices and defaults to `NATF2`.
PersonaPlex is English-only and supplies its own 7B conversational model, so it
does not call the llama.cpp service. Native clients can stream directly; a web
client still needs a backend WebSocket/stream adapter rather than exposing this
HTTP endpoint directly to browser microphone code.

The live request body is raw interleaved PCM with chunked transfer encoding;
`model`, `input` (the system/persona prompt), `sample_rate`, `channels`, and
`sample_format` are query parameters. `voice_id` selects a packaged voice.

```bash
curl -N -X POST -H 'Expect:' -H 'Accept: text/event-stream' \
  -H 'Transfer-Encoding: chunked' -T input-24khz-mono-s16le.pcm \
  'http://localhost:8081/v1/audio/speech/live?model=personaplex-7b&input=You%20are%20a%20concise%20voice%20assistant.&sample_rate=24000&channels=1&sample_format=s16le&voice_id=NATF2'
```

For a live microphone, pipe the capture to `curl -T -`; uploading a finite PCM
file as above validates the same model and SSE response path but is not a true
full-duplex client.

## Generated contract

`models/<family>/<model>/model.json` owns each model's lineage, primary quant,
immutable file or multi-file package, sizes, hashes, and server path.
`runtime.json` owns the upstream image identity. `deployment-bundles.json`
owns related capability groups, while
`deployment-scenarios/<provider>/<hardware>.json` owns provider/card identity,
compatibility, and which bundles or single models are exposed. Generated files
under `server-configs/` must not be hand-edited.
Run:

```bash
python docker/audio-cpp/generate.py
python docker/audio-cpp/generate.py --check
python -m unittest benchmark.tests.test_artifact_downloads -v
```

The generator emits locked CUDA/CPU defaults, every scenario config and its
paired prestage manifest, the exact downloader, and
`deployment-inventory.generated.json`. The inventory includes image/runtime
identity, bundle definitions, exact model artifacts and precision, provider
hardware IDs and observations, config/prestage paths, effective residency,
staged bytes, and verification state. It is copied to
`/deployment-inventory.json`, identified by OCI labels, and published as the
commit-named `prefer-audio-deployment-inventory-<commit-sha>` workflow artifact
for NeurOn or another provisioning controller.
