# Third-party components and release limits

## TRIBE v2

The curated `tribev2/` source is based on facebookresearch/tribev2 revision
`0492da249c6a90a1aaa35ea243ea6c1b802c3586`.
Keep its copyright headers, [license](tribev2/LICENSE), and upstream README.
Its license is Creative Commons Attribution-NonCommercial 4.0 International;
this project does not remove the non-commercial restriction.

The existing local change to `tribev2/tribev2/eventstransforms.py` uses in-process
WhisperX transcription/alignment and `int8` transcription on non-CUDA devices,
instead of launching an unpinned `uvx whisperx` subprocess. The release copy
preserves that change without including the nested Git repository.

The version-checked installer `backend/scripts/apply_neuralset_mps.py` extends
neuralset 0.0.2 device validation and automatic selection to support Apple MPS.
It does not distribute a virtual environment or change model weights.

## Models and assets

Model weights are not included. Users must obtain models through their own
accounts and comply with each model's terms, including gated LLaMA access.
Never publish Hugging Face credentials, converted checkpoints, or model caches.

The atlas generator uses MNE's HCP-MMP parcellation fetcher. HCP's Open Access
Data Use Terms allow redistribution of derived data under the same terms and
require acknowledgment; preserve those terms before distributing the atlas.
The public repository does not distribute this atlas; users generate it locally
only after explicitly confirming review of the source data terms.
See https://www.humanconnectome.org/study/hcp-young-adult/data-use-terms.

The four base mesh arrays match the fsaverage5 assets packaged with Nilearn;
the open-book variants are local geometric transformations. Nilearn's installed
fsaverage5 description labels the asset license as "unknown". This is not
license clearance: confirm the underlying FreeSurfer/asset redistribution
terms before publishing those files or a container image containing them.
Atlas and mesh files are excluded from the public source allowlist and Docker
build contexts. `backend/scripts/prepare_assets.py` obtains the base meshes from
the user's installed Nilearn and prepares them locally; its confirmation flag
does not establish redistribution rights.

FreeSurfer terms: https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSoftwareLicense

Uploaded media, transcripts, job results, and local insight references are
not release assets. Only use media you have permission to process.

Original first-party application code is licensed under Apache-2.0;
see the root [LICENSE](LICENSE) and [NOTICE](NOTICE). This grant does not
relicense upstream code, weights, or visualization assets.

## Known dependency boundary

The vendored model currently requires PyTorch below 2.7. The reproducible
runtime specification retains PyTorch 2.6 and Transformers 4.57 for compatibility;
these versions have known dependency advisories. Upgrading the full model stack
requires separate upstream compatibility and numerical-output validation.
This release is not a claim that the inference dependency tree is vulnerability-free.
Do not process untrusted downloaded checkpoints or expose this service publicly.
