# NeuroLens

Run TRIBE v2 locally on your own audio/video, view predicted cortical responses
over time, and compare two completed analyses. This is a single-user research
tool, not a public upload service.

**Preview release:** visualization assets and model weights are not bundled.
Users prepare them locally under their applicable terms. Audio/video inference
depends on hardware and gated model access; the full inference dependency tree
still has known advisories. This is not a production-security certification.

**These are model predictions, not measured brain activity, emotion readings,
diagnoses, or validated measures of engagement.** Region responses are
normalized within each job; comparisons are descriptive, not calibrated
absolute comparisons between people or clips.

## Architecture

```
backend/         FastAPI + Celery + SQLite + TRIBE v2 inference
frontend/        Next.js + Tailwind CSS + NiiVue/Three.js + Recharts
tribev2/         Curated upstream model source; see THIRD_PARTY_NOTICES.md
```

## Quick Start

### Prerequisites

- Python **3.11** for the documented model stack.
- Node.js **22+**, npm, Redis, and FFmpeg/ffprobe on `PATH`.
- Your own Hugging Face account with access to the gated LLaMA 3.2-3B weights.
- Sufficient disk space for several large model downloads, cached features,
  uploads, and results. First startup is slow and requires network access.
- Apple Silicon: audio-only has worked on a 16 GB Mac; **video does not fit
  reliably on 16 GB**, including with half-precision extractors. Use a machine
  with at least 32 GB for video, and verify available memory before running.
- NVIDIA/CUDA: use a PyTorch 2.6-compatible driver/runtime and ample dedicated
  VRAM. A 16 GB GPU is not a verified video baseline. CPU mode is supported
  by the configuration but can be extremely slow.

Full inference dependencies retain known advisories because the upstream model
requires older PyTorch/Transformers. See [dependency limits](THIRD_PARTY_NOTICES.md).
Do not load untrusted checkpoints or process untrusted media. A clean dependency
resolution is not proof that full audio/video inference works on your hardware.

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements-runtime.txt
python scripts/apply_neuralset_mps.py
python -m pip check
cp .env.example .env
hf auth login
```

Review the HCP Open Access Data Use Terms and FreeSurfer/fsaverage terms linked
in [third-party notices](THIRD_PARTY_NOTICES.md). If your use complies, prepare
the visualization assets locally, from `backend/` with the environment active:

```bash
python scripts/prepare_assets.py --accept-data-terms
```

This writes the atlas and all eight meshes to `backend/static/`. The frontend
fetches them through its backend `/static` proxy, so no public assets need to
be copied into the GitHub repository. Asset preparation may download MNE/HCP
datasets and take additional time/disk space. Do not start the brain viewer
until this command succeeds. The flag confirms your review of the terms; it
does not grant redistribution rights.

Set `NEUROLENS_TRIBE_DEVICE` in `backend/.env` to `mps` (Apple Silicon), `cuda`
(NVIDIA), or `cpu`. The example uses MPS. Text extraction uses CPU on MPS;
audio/video extractors use the configured device. Keep memory guards enabled
and review their thresholds for your machine. Do not reduce sampled video
frames just to make a clip fit without acknowledging that it changes outputs.

On Linux, install the appropriate torch packages **before** the runtime
requirements. For example, for the PyTorch 2.6 CUDA 12.4 distribution:

```bash
python -m pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements-runtime.txt
```

For CPU-only Linux, use `https://download.pytorch.org/whl/cpu` instead.
Run these commands from `backend/` with the virtual environment activated.
Do not upgrade WhisperX independently: recent versions require a PyTorch
version incompatible with this vendored model.

### Start the local application

```bash
# From the project root:
npm ci
cd frontend
npm ci
cd ..
npm run dev
```

Open **http://127.0.0.1:3000** (or http://localhost:3000). Upload a short audio
clip first, wait for completion, then inspect the timeline, brain view, and
exports. Analyze a second clip and select the two completed jobs for comparison.
The worker preloads the audio model; video loads lazily and requires more memory.

`npm run dev` starts loopback-bound Redis, API, worker, and frontend. Do not run
a second Redis or development stack on the same ports. Stop with Ctrl+C.
For separate terminals, from `backend/`:

```bash
redis-server --bind 127.0.0.1 --protected-mode yes --save '' --appendonly no
./venv/bin/uvicorn app.main:app --host 127.0.0.1 --no-proxy-headers --port 8000
./venv/bin/celery -A app.celery_app:celery_app worker --loglevel=info --pool=solo
```

Run `npm run dev` from `frontend/` for the UI when using separate terminals.
Always use `--pool=solo` for Apple MPS; the Metal runtime is not fork-safe.

### Docker (optional, Linux CPU or NVIDIA)

Docker does not provide Apple MPS acceleration. The default Compose file uses
CPU mode. GPU execution requires NVIDIA Container Toolkit and a compatible
CUDA environment; use the CUDA override for the worker.

```bash
docker compose build
docker compose run --rm worker hf auth login
docker compose run --rm worker python scripts/prepare_assets.py --accept-data-terms
docker compose up

# NVIDIA variant, instead of the last command:
docker compose -f docker-compose.yml -f docker-compose.cuda.yml up
```

Only frontend/API ports are published, both on `127.0.0.1`; Redis is not
published. A named `state` volume shares uploads, results, SQLite, and model
caches and generated visualization assets between API/worker. Never distribute
that volume. Container builds
copy only intentional source paths, not the populated local backend directory.
Frontend rewrites are compiled with `NEUROLENS_BACKEND_URL=http://backend:8000`.

Container execution and full clean-install inference still require verification
on the target system. Configuration validation alone is not an end-to-end test.

## Privacy and local-only boundaries

- This instance has **no multi-user authentication or job ownership isolation**.
  Anyone with access to it can access all its jobs. Never expose it on the
  internet, a shared LAN, a tunnel, or a public reverse proxy.
- Default commands bind to loopback. Host/origin checks also reject foreign
  browser origins and DNS-rebinding hosts; they do not replace authentication
  or protect against another process/user already on your machine.
- Browser access uses the standard ports 3000/8000. Custom browser ports require
  updating both local-access policies, not just CORS settings.
- Media, extracted transcripts, results, and SQLite state stay in local storage.
  Model downloads/authentication contact their providers. No claim is made
  about telemetry in third-party model dependencies.
- Upload limits do not make media decoding safe against every malicious file.
  Only process files you trust and have permission to use.
- Insight references are intentionally excluded from publication. Without an
  appropriate reference corpus the app returns no reference-relative findings.
  Build your own from independent completed jobs, from `backend/`:
  `./venv/bin/python -m scripts.build_insight_reference <job_id> <job_id> ...`.
  These findings remain exploratory and descriptive.

## Assets and licensing

Original first-party application code is licensed under Apache-2.0; see
[LICENSE](LICENSE) and [NOTICE](NOTICE). TRIBE v2 remains CC-BY-NC-4.0,
so the combined model-based workflow is not a commercial-use license grant.

The public release contains **no atlas or mesh data**. Run the local asset
preparation command above after reviewing the source terms. Generated data
is ignored by Git and excluded from Docker build contexts and release copies.
See [third-party notices](THIRD_PARTY_NOTICES.md).
To regenerate only the atlas, run `./venv/bin/python scripts/generate_roi_atlas.py`
from `backend/`. To regenerate backend open-book meshes, run
`backend/venv/bin/python scripts/generate_splayed_meshes.py --mesh-dir backend/static/meshes`
from the root.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/analyze` | Upload video/audio, start analysis |
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/{id}` | Job status + progress |
| GET | `/api/jobs/{id}/result` | Full analysis result |
| GET | `/api/jobs/{id}/timeline` | Region activations over time |
| GET | `/api/jobs/{id}/brain/{t}` | Vertex data for timestep t |
| GET | `/api/jobs/{id}/insights` | Descriptive reference-relative findings |
| GET | `/api/compare/{a}/{b}` | A/B comparison |
| GET | `/api/jobs/{id}/export/report` | Markdown report |
| GET | `/api/jobs/{id}/export/json` | JSON export |

## Verification

```bash
cd backend
./venv/bin/python -m pytest tests/ -v
./venv/bin/python scripts/apply_neuralset_mps.py --check
./venv/bin/python -m pip check
cd ../frontend
npm run lint
npm run test:security
npm run build
npm audit --omit=dev
cd ..
python3 -m unittest discover -s scripts/tests -v
python3 scripts/prepare_release.py
docker compose config --quiet
```

These unit tests do not download model weights or prove real inference.
Before releasing, perform an audio and, on suitable hardware, a video smoke
test from a fresh environment. Verify upload, playback, timestamp scrubbing,
exports, cancellation/retry, and two-job comparison. Do not build in the same
checkout while its Next development server is writing `.next`.

## Preparing a source-only GitHub release

The populated development folder is **not** the release artifact.
The checker uses an explicit allowlist and suppresses credential values in
findings. It does not initialize Git, commit, push, or upload source.

```bash
python3 scripts/prepare_release.py
python3 scripts/prepare_release.py --list
python3 scripts/prepare_release.py --output ../NeuroLens-public
```

The output must be a new directory outside this checkout. It omits personal
activity/agents/emotions/work notes (including case variants), all nested Git
history, environment files except the template, uploads/transcripts/results,
databases, Redis snapshots, local references, models, caches, dependencies,
screenshots, and notebooks. It preserves necessary code, tests, commands,
upstream attribution, and local asset-setup commands. No atlas or meshes are
included, even if they are present in the development folder.

Inspect that copy and keep the preview/dependency limitations visible to users.
Full inference on a fresh environment still requires hardware-specific testing.
Initialize Git only in the clean release copy. Never use an indiscriminate
`git add .` in the populated development
folder. Ignore rules do not remove secrets that were previously committed;
any exposed credential must also be revoked and removed from history.
