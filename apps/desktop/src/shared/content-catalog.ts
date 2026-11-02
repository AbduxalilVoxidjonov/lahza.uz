// The app-managed content catalog: every artifact the app can download for
// the user, pinned to immutable versioned URLs with byte counts and SHA-256
// digests (supply-chain rule, docs/licensing.md — never a rolling "latest").
//
// Values are verbatim from ADR 0039 (CPU-only whisper.cpp v1.9.1 +
// multilingual Base), ADR 0043 (sherpa-onnx v1.13.4 + Paraformer-zh for the
// FunASR backend), ADR 0055 (llama.cpp b10103 Vulkan + Qwen3-VL-4B-Instruct
// Q4_K_M for the video-understanding backend), and ADR 0073 (the Linux x64
// artifacts of all three, at those same upstream versions), ADR 0075 (the
// macOS arm64 artifacts of sherpa-onnx and llama.cpp), and ADR 0076 (the macOS
// arm64 whisper-cli, which whisper.cpp does not publish — this repo builds it
// from the pinned upstream commit and releases it). Do not re-derive
// or "refresh" them — a new upstream release is a NEW catalog entry with its
// own pinned url/bytes/sha, decided through an ADR update, not an edit here.
//
// content-catalog.test.ts enforces the pinning invariants over every entry.

import type { ContentArtifact, ContentItem, ContentPlatformKey } from "./content-download";

export const CONTENT_CATALOG: readonly ContentItem[] = [
  {
    id: "whisper-cpp-runtime",
    kind: "speech-runtime",
    version: "1.9.1",
    labelKey: "content_whisper_runtime",
    license: { name: "MIT", upstreamUrl: "https://github.com/ggml-org/whisper.cpp" },
    speech: { backend: "whisper_cpp" },
    platforms: {
      "win32-x64": {
        url: "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-bin-x64.zip",
        sha256:
          "7d8be46ecd31828e1eb7a2ecdd0d6b314feafd82163038ab6092594b0a063539",
        bytes: 7982101,
        archive: "zip",
        // The runtime is the archive's complete Release/ directory (the
        // dynamically selected CPU backend DLLs must stay beside the exe).
        entryPath: "Release/whisper-cli.exe",
        fields: { binary: "Release/whisper-cli.exe" },
        // The official Windows build dynamically imports the Microsoft Visual
        // C++ v14 x64 runtime (MSVCP140, VCRUNTIME140[_1], VCOMP140) — ADR 0039
        // makes that an explicit prerequisite rather than an unrecorded
        // assumption.
        prerequisiteKey: "content_prereq_msvc14",
      },
      // CPU-only like the Windows artifact, and for the same reason: the
      // upstream Linux tarball ships the libggml-cpu-*.so set and no GPU
      // backend at all (ADR 0073). The runtime is its whole extracted
      // directory — whisper-cli's RUNPATH is $ORIGIN, so libwhisper.so.1 and
      // the ggml backends it dlopens must keep sitting beside it, SYMLINKS
      // INCLUDED (libwhisper.so.1 is a link to libwhisper.so.1.9.1): an
      // extractor that flattens links installs a binary that cannot start.
      "linux-x64": {
        url: "https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.1/whisper-bin-ubuntu-x64.tar.gz",
        sha256:
          "f3bf3b4369a99b54665b0f19b88483b30de27f25963b0414235dea03198515c5",
        bytes: 9379235,
        archive: "tar.gz",
        entryPath: "whisper-bin-ubuntu-x64/whisper-cli",
        fields: { binary: "whisper-bin-ubuntu-x64/whisper-cli" },
      },
      // whisper.cpp publishes no macOS CLI (its only Apple asset is an
      // xcframework), so this is Lahza's own release asset: whisper-cli
      // v1.9.1 built from the pinned upstream commit by
      // scripts/build-whisper-cli-macos.mjs in the content-whisper-cli
      // workflow (ADR 0076). One static binary with Metal and its shader
      // library embedded — it links only system frameworks, so nothing needs
      // to sit beside it. The pin is the CI-published asset, not a local build.
      "darwin-arm64": {
        url: "https://api.github.com/repositories/1246738326/releases/assets/583933461",
        sha256:
          "cda72d4951aa2adbcf4b109151fbfaa071be7fab0297acbf002f3cf5d007b8d1",
        bytes: 1169176,
        archive: "tar.gz",
        entryPath: "whisper-cli-v1.9.1-macos-arm64/whisper-cli",
        fields: { binary: "whisper-cli-v1.9.1-macos-arm64/whisper-cli" },
      },
    },
  },
  {
    id: "whisper-model-base",
    kind: "speech-model",
    // Hugging Face revision — the model file is platform-independent, but it
    // still installs under <id>/<version>/ like everything else.
    version: "5359861c739e955e79d9a303bcbc70fb988958b1",
    labelKey: "content_whisper_model_base",
    license: {
      name: "MIT",
      upstreamUrl: "https://huggingface.co/ggerganov/whisper.cpp",
    },
    speech: { backend: "whisper_cpp" },
    platforms: {
      // Multilingual Base — neither ggml-base.en.bin nor a quantized variant
      // (ADR 0039). Byte-identical on every platform; listed per-platform so
      // coverage stays an explicit decision as other OSes phase in.
      "win32-x64": {
        url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base.bin?download=true",
        sha256:
          "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
        bytes: 147951465,
        archive: "none",
        entryPath: "ggml-base.bin",
        fields: { model: "ggml-base.bin" },
      },
      "linux-x64": {
        url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base.bin?download=true",
        sha256:
          "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
        bytes: 147951465,
        archive: "none",
        entryPath: "ggml-base.bin",
        fields: { model: "ggml-base.bin" },
      },
      "darwin-arm64": {
        url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base.bin?download=true",
        sha256:
          "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
        bytes: 147951465,
        archive: "none",
        entryPath: "ggml-base.bin",
        fields: { model: "ggml-base.bin" },
      },
    },
  },
  {
    id: "funasr-runtime",
    kind: "speech-runtime",
    version: "1.13.4",
    labelKey: "content_funasr_runtime",
    license: { name: "Apache-2.0", upstreamUrl: "https://github.com/k2-fsa/sherpa-onnx" },
    speech: { backend: "funasr" },
    platforms: {
      "win32-x64": {
        url: "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.4/sherpa-onnx-v1.13.4-win-x64-shared-MD-Release.tar.bz2",
        // Double-confirmed: GitHub's release-asset digest and the locally
        // validated archive agree (ADR 0043).
        sha256:
          "d4dacc8be5afe03f22ade4d50cfd587c03a625eaca8c41f2d99a24d3db463eab",
        bytes: 20034576,
        archive: "tar.bz2",
        entryPath:
          "sherpa-onnx-v1.13.4-win-x64-shared-MD-Release/bin/sherpa-onnx-offline.exe",
        fields: {
          binary:
            "sherpa-onnx-v1.13.4-win-x64-shared-MD-Release/bin/sherpa-onnx-offline.exe",
        },
        // The shared-MD build dynamically links the MSVC v14 x64 runtime, same
        // as the whisper.cpp runtime above (ADR 0043).
        prerequisiteKey: "content_prereq_msvc14",
      },
      // The `shared` build, the Linux twin of the Windows shared-MD choice —
      // not `static` (385 MB) and not the CUDA/GPU variants, which would pin a
      // toolkit the app does not ship. sherpa-onnx-offline's RPATH is
      // $ORIGIN:$ORIGIN/../lib, so bin/ and lib/ must stay in one tree.
      "linux-x64": {
        url: "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.4/sherpa-onnx-v1.13.4-linux-x64-shared.tar.bz2",
        sha256:
          "18887dc13c7d313d0e0f6c164ed31715c27c1c2c4f71acd7c0147dc84cf02514",
        bytes: 27801563,
        archive: "tar.bz2",
        entryPath: "sherpa-onnx-v1.13.4-linux-x64-shared/bin/sherpa-onnx-offline",
        fields: {
          binary: "sherpa-onnx-v1.13.4-linux-x64-shared/bin/sherpa-onnx-offline",
        },
      },
      // The osx-arm64 `shared` build — the macOS twin of the Linux choice. Its
      // bin/sherpa-onnx-offline resolves libonnxruntime through @loader_path
      // and @loader_path/../lib, so bin/ and lib/ stay in one tree. ⚠️ Upstream
      // ships lib/libonnxruntime*.dylib with a signature that no longer covers
      // the file, which Apple Silicon answers with SIGKILL at load — the
      // install's macOS seal step re-signs it ad hoc (contentSign.ts, ADR 0075).
      "darwin-arm64": {
        url: "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.4/sherpa-onnx-v1.13.4-osx-arm64-shared.tar.bz2",
        sha256:
          "809ab5d0c77bd8f358364a244e6ab17f2afecf9779eb9fd436fa469c3ff5375c",
        bytes: 27044587,
        archive: "tar.bz2",
        entryPath: "sherpa-onnx-v1.13.4-osx-arm64-shared/bin/sherpa-onnx-offline",
        fields: {
          binary: "sherpa-onnx-v1.13.4-osx-arm64-shared/bin/sherpa-onnx-offline",
        },
      },
    },
  },
  {
    id: "funasr-model-paraformer-zh",
    kind: "speech-model",
    version: "2023-09-14",
    labelKey: "content_funasr_model_paraformer",
    // Apache-2.0 per the official FunASR org's Hugging Face model card; the
    // FunASR repo's bespoke MODEL_LICENSE is the second recorded signal — both
    // in ADR 0043. The manifest's name + upstream record satisfies its
    // attribution requirement.
    license: {
      name: "Apache-2.0",
      upstreamUrl: "https://huggingface.co/funasr/paraformer-zh",
    },
    // One archive fills two config fields — model AND tokens ride together.
    speech: { backend: "funasr" },
    platforms: {
      // Platform-independent data, listed per-platform like the whisper model
      // so coverage stays an explicit decision as other OSes phase in.
      "win32-x64": {
        // ⚠️ Rolling `asr-models` release tag, not a version tag — the pinned
        // sha256 below is what carries the trust (ADR 0043): a swapped asset
        // fails verification loudly instead of installing.
        url: "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-paraformer-zh-2023-09-14.tar.bz2",
        sha256:
          "9c49fd9c6fb63de8e18c1054cf3d100f804741b7e608e187923cd8ff09fa9f03",
        bytes: 234051698,
        archive: "tar.bz2",
        entryPath: "sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx",
        fields: {
          model: "sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx",
          tokens: "sherpa-onnx-paraformer-zh-2023-09-14/tokens.txt",
        },
      },
      "linux-x64": {
        url: "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-paraformer-zh-2023-09-14.tar.bz2",
        sha256:
          "9c49fd9c6fb63de8e18c1054cf3d100f804741b7e608e187923cd8ff09fa9f03",
        bytes: 234051698,
        archive: "tar.bz2",
        entryPath: "sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx",
        fields: {
          model: "sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx",
          tokens: "sherpa-onnx-paraformer-zh-2023-09-14/tokens.txt",
        },
      },
      "darwin-arm64": {
        url: "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-paraformer-zh-2023-09-14.tar.bz2",
        sha256:
          "9c49fd9c6fb63de8e18c1054cf3d100f804741b7e608e187923cd8ff09fa9f03",
        bytes: 234051698,
        archive: "tar.bz2",
        entryPath: "sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx",
        fields: {
          model: "sherpa-onnx-paraformer-zh-2023-09-14/model.int8.onnx",
          tokens: "sherpa-onnx-paraformer-zh-2023-09-14/tokens.txt",
        },
      },
    },
  },
  {
    id: "llama-mtmd-runtime",
    kind: "vlm-runtime",
    // llama.cpp build tag — the build both VLM engines are validated against.
    version: "b10103",
    labelKey: "content_llama_mtmd_runtime",
    license: { name: "MIT", upstreamUrl: "https://github.com/ggml-org/llama.cpp" },
    // The BINARY is engine-agnostic — one llama-mtmd-cli drives Qwen3-VL and
    // MiniCPM-V alike, which is why `backends` is a list at all. It claims only
    // qwen3_vl today on purpose: the catalog carries no MiniCPM model, so
    // claiming that engine here would leave its Settings row offering a
    // "download" that installs a runtime and then reports the whole set
    // present. `"minicpm_v"` joins this list in the same change that adds its
    // model + mmproj entries, never before.
    vlm: { backends: ["qwen3_vl"] },
    platforms: {
      // The VULKAN build, not the CPU-only one, and not a tradeoff: this
      // archive ships ggml-vulkan.dll AND the full ggml-cpu-*.dll set, so it
      // is a strict superset — it uses the GPU where a Vulkan driver exists
      // (every current NVIDIA / AMD / Intel Windows driver ships one) and
      // falls back to the same CPU backends the CPU archive would have given.
      // 33 MB against the CPU archive's 18 MB buys that (ADR 0055).
      "win32-x64": {
        url: "https://github.com/ggml-org/llama.cpp/releases/download/b10103/llama-b10103-bin-win-vulkan-x64.zip",
        sha256:
          "3e3aa22631fa7d6cded90219e6e0d4d929b035280f5a9f209e535662e60eb33f",
        bytes: 33479917,
        archive: "zip",
        // The archive is FLAT (no Release/ prefix, unlike whisper.cpp's), and
        // the runtime is its whole extracted directory — the dynamically
        // selected ggml backend DLLs must stay beside the exe.
        entryPath: "llama-mtmd-cli.exe",
        fields: { binary: "llama-mtmd-cli.exe" },
        // Same MSVC v14 x64 dependency as the whisper.cpp Windows runtime:
        // llama-mtmd-cli.exe and llama.dll both dynamically import MSVCP140 +
        // VCRUNTIME140 (verified against the pinned archive).
        prerequisiteKey: "content_prereq_msvc14",
      },
      // The Vulkan build here too, for the same superset reason — and with the
      // same shape as its Windows twin: one top-level directory whose whole
      // contents are the runtime (llama-mtmd-cli's RUNPATH is $ORIGIN). A
      // machine with no Vulkan driver loads the libggml-cpu-*.so this archive
      // also carries (ADR 0073).
      "linux-x64": {
        url: "https://github.com/ggml-org/llama.cpp/releases/download/b10103/llama-b10103-bin-ubuntu-vulkan-x64.tar.gz",
        sha256:
          "ca2c3db8aa2787b2e49655460787190d0619caeeff259ffa1bf909fe5133264d",
        bytes: 32238620,
        archive: "tar.gz",
        entryPath: "llama-b10103/llama-mtmd-cli",
        fields: { binary: "llama-b10103/llama-mtmd-cli" },
      },
      // The macos-arm64 build, which is the Metal build — upstream publishes no
      // other macOS arm64 variant, and it carries the CPU and BLAS backends
      // beside libggml-metal, so it is the same superset shape as the Vulkan
      // archives. Same one-directory layout (RPATH @loader_path, versioned
      // dylibs behind symlinks the tar lane recreates); its signatures are
      // valid as shipped (ADR 0075).
      "darwin-arm64": {
        url: "https://github.com/ggml-org/llama.cpp/releases/download/b10103/llama-b10103-bin-macos-arm64.tar.gz",
        sha256:
          "1c07a23cf98d80b6349860b6d30f9e15548a7fd91a4b44b15e749f377b6f6246",
        bytes: 10803401,
        archive: "tar.gz",
        entryPath: "llama-b10103/llama-mtmd-cli",
        fields: { binary: "llama-b10103/llama-mtmd-cli" },
      },
    },
  },
  {
    id: "qwen3-vl-4b-model",
    kind: "vlm-model",
    // Hugging Face revision — platform-independent data, still installed under
    // <id>/<version>/ like everything else.
    version: "1cd86afb9a95c410a6038ab3b40d8b578c892266",
    labelKey: "content_qwen3vl_model",
    license: {
      name: "Apache-2.0",
      upstreamUrl: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF",
    },
    vlm: { backends: ["qwen3_vl"] },
    platforms: {
      // Q4_K_M, the quantization the spike measured (~20 s for 8 frames on a
      // Vulkan RTX 3050) — not F16 (8.0 GB) or Q8_0 (4.3 GB).
      "win32-x64": {
        url: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/1cd86afb9a95c410a6038ab3b40d8b578c892266/Qwen3VL-4B-Instruct-Q4_K_M.gguf?download=true",
        sha256:
          "66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a",
        bytes: 2497281664,
        archive: "none",
        entryPath: "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
        fields: { model: "Qwen3VL-4B-Instruct-Q4_K_M.gguf" },
      },
      "linux-x64": {
        url: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/1cd86afb9a95c410a6038ab3b40d8b578c892266/Qwen3VL-4B-Instruct-Q4_K_M.gguf?download=true",
        sha256:
          "66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a",
        bytes: 2497281664,
        archive: "none",
        entryPath: "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
        fields: { model: "Qwen3VL-4B-Instruct-Q4_K_M.gguf" },
      },
      "darwin-arm64": {
        url: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/1cd86afb9a95c410a6038ab3b40d8b578c892266/Qwen3VL-4B-Instruct-Q4_K_M.gguf?download=true",
        sha256:
          "66358cb18bb6b3b1b6675aa412c7a88ef01d228f481184d13668e5201c730a0a",
        bytes: 2497281664,
        archive: "none",
        entryPath: "Qwen3VL-4B-Instruct-Q4_K_M.gguf",
        fields: { model: "Qwen3VL-4B-Instruct-Q4_K_M.gguf" },
      },
    },
  },
  {
    id: "qwen3-vl-4b-mmproj",
    kind: "vlm-model",
    version: "1cd86afb9a95c410a6038ab3b40d8b578c892266",
    labelKey: "content_qwen3vl_mmproj",
    license: {
      name: "Apache-2.0",
      upstreamUrl: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF",
    },
    // The vision projector is a SEPARATE download from the model (two URLs, so
    // two entries — unlike the Paraformer bundle, where one archive filled two
    // fields). Without it the GGUF is text-only and the availability probe
    // reports NeedsModel, which is why it is a first-class catalog entry rather
    // than an afterthought on the model row.
    vlm: { backends: ["qwen3_vl"] },
    platforms: {
      // F16 projector, not the Q8_0 one: the projector is small next to the
      // model (797 MB vs 2.4 GB) and quantizing it is where vision quality goes.
      "win32-x64": {
        url: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/1cd86afb9a95c410a6038ab3b40d8b578c892266/mmproj-Qwen3VL-4B-Instruct-F16.gguf?download=true",
        sha256:
          "256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331",
        bytes: 836180256,
        archive: "none",
        entryPath: "mmproj-Qwen3VL-4B-Instruct-F16.gguf",
        fields: { mmproj: "mmproj-Qwen3VL-4B-Instruct-F16.gguf" },
      },
      "linux-x64": {
        url: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/1cd86afb9a95c410a6038ab3b40d8b578c892266/mmproj-Qwen3VL-4B-Instruct-F16.gguf?download=true",
        sha256:
          "256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331",
        bytes: 836180256,
        archive: "none",
        entryPath: "mmproj-Qwen3VL-4B-Instruct-F16.gguf",
        fields: { mmproj: "mmproj-Qwen3VL-4B-Instruct-F16.gguf" },
      },
      "darwin-arm64": {
        url: "https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF/resolve/1cd86afb9a95c410a6038ab3b40d8b578c892266/mmproj-Qwen3VL-4B-Instruct-F16.gguf?download=true",
        sha256:
          "256f3a43bd4205ffef48d6b92715e1e70b5b0e9aef06522584967513a9985331",
        bytes: 836180256,
        archive: "none",
        entryPath: "mmproj-Qwen3VL-4B-Instruct-F16.gguf",
        fields: { mmproj: "mmproj-Qwen3VL-4B-Instruct-F16.gguf" },
      },
    },
  },

  // ---------------------------------------------------------------------------
  // First-run components (kind tool / package / skill-pack, autoInstall).
  // Fetched at app start when missing and the machine is online — nothing here
  // ships in the repo or the installer. Every digest below was computed from
  // the very bytes at the URL (or is the upstream's own published digest that
  // was re-checked against the download), on 2026-11-02:
  //   shasum -a 256 <downloaded file>
  // To bump one: download the new immutable URL, recompute sha256 + `wc -c`,
  // and add it as a NEW pinned entry (see the header rule above).
  // ---------------------------------------------------------------------------
  {
    // Downloader for the "import from a URL" flow. The upstream release
    // publishes one single-file binary per OS; the digests are GitHub's own
    // release-asset digests (the macOS one re-verified by hashing the download).
    // The macOS binary is a universal2 build, hence the same asset for both
    // darwin keys. Unlicense, so redistribution of the pinned bytes is fine.
    id: "yt-dlp",
    kind: "tool",
    version: "2026.10.26",
    labelKey: "content_ytdlp",
    autoInstall: true,
    license: { name: "Unlicense", upstreamUrl: "https://github.com/yt-dlp/yt-dlp" },
    platforms: {
      "win32-x64": {
        url: "https://github.com/yt-dlp/yt-dlp/releases/download/2026.10.26/yt-dlp.exe",
        sha256: "f5389d3698ecde4ef06f4e6b1ce0294fe9ac1396228c8990b8d3416d6d177a7d",
        bytes: 23575744,
        archive: "none",
        entryPath: "yt-dlp.exe",
        fields: { binary: "yt-dlp.exe", entry: "yt-dlp.exe" },
        executable: true,
      },
      "linux-x64": {
        url: "https://github.com/yt-dlp/yt-dlp/releases/download/2026.10.26/yt-dlp_linux",
        sha256: "767ba9dce7052aa196f8b12652f433d76de128ba168966fa84b6394d5e6c6795",
        bytes: 41166968,
        archive: "none",
        entryPath: "yt-dlp",
        fields: { binary: "yt-dlp", entry: "yt-dlp" },
        executable: true,
      },
      "darwin-arm64": ytDlpMac(),
      "darwin-x64": ytDlpMac(),
    },
  },
  {
    // The npm tarball of Remotion's core package at an exact version (the
    // registry's own `dist.shasum` sha1 was cross-checked against the download).
    // Remotion is source-available under its own company license, NOT OSI open
    // source: teams above the free-tier size need a paid license to USE it.
    // Fetching the package is not using it, but surface the license to the user.
    id: "remotion-core",
    kind: "package",
    version: "4.0.540",
    labelKey: "content_remotion",
    autoInstall: true,
    license: { name: "Remotion License", upstreamUrl: "https://github.com/remotion-dev/remotion/blob/main/LICENSE.md" },
    platforms: everywhere({
      url: "https://registry.npmjs.org/remotion/-/remotion-4.0.540.tgz",
      sha256: "b4516b6f9d585cb31fcd6d44597b9373874b9f4ad7c169282459a82d424e7f1f",
      bytes: 432249,
      archive: "tar.gz",
      entryPath: "package/package.json",
      fields: { entry: "package/package.json" },
    }),
  },
  {
    // HeyGen's HyperFrames CLI/runtime, npm tarball at an exact version
    // (registry shasum 6c5e8081... matched the download). Apache-2.0.
    id: "hyperframes",
    kind: "package",
    version: "0.9.3",
    labelKey: "content_hyperframes",
    autoInstall: true,
    license: { name: "Apache-2.0", upstreamUrl: "https://github.com/heygen-com/hyperframes" },
    platforms: everywhere({
      url: "https://registry.npmjs.org/hyperframes/-/hyperframes-0.9.3.tgz",
      sha256: "e1b050f2228fc919726455c6b9cfe48157b607bb8b577b418a6e1f52d38ff12c",
      bytes: 7867851,
      archive: "tar.gz",
      entryPath: "package/package.json",
      fields: { entry: "package/package.json" },
    }),
  },
  {
    // Remotion's agent skills, pinned to a commit (not a branch). The archive
    // is GitHub's generated codeload tarball for that commit; GitHub does not
    // promise byte-stable generated archives, so a digest mismatch here means
    // "re-pin", never "ignore".
    id: "remotion-skills",
    kind: "skill-pack",
    version: "c7cb2fdcacd134fb2ccb9b7a44f9ffa44e467271",
    labelKey: "content_remotion_skills",
    autoInstall: true,
    license: { name: "See upstream (no SPDX declared)", upstreamUrl: "https://github.com/remotion-dev/skills" },
    platforms: everywhere({
      url: "https://codeload.github.com/remotion-dev/skills/tar.gz/c7cb2fdcacd134fb2ccb9b7a44f9ffa44e467271",
      sha256: "a626ec482b4f686cda123b04b34e34fb4e08f28471ac3d98f7d2b07bcb3666cc",
      bytes: 752738,
      archive: "tar.gz",
      entryPath: "skills-c7cb2fdcacd134fb2ccb9b7a44f9ffa44e467271/package.json",
      fields: { entry: "skills-c7cb2fdcacd134fb2ccb9b7a44f9ffa44e467271/package.json" },
    }),
  },
  {
    // OpenMontage, pinned to a commit. LICENSE IS AGPL-3.0: it is downloaded
    // as a separate user-run tool beside the app (never linked into or shipped
    // with it), and the license is shown in the component row. Same
    // codeload-stability caveat as remotion-skills.
    id: "openmontage",
    kind: "skill-pack",
    version: "195eab24478dc9363326aec437aefc3701635ddf",
    labelKey: "content_openmontage",
    autoInstall: false,
    license: { name: "AGPL-3.0", upstreamUrl: "https://github.com/calesthio/OpenMontage" },
    platforms: everywhere({
      url: "https://codeload.github.com/calesthio/OpenMontage/tar.gz/195eab24478dc9363326aec437aefc3701635ddf",
      sha256: "171a1c456f12759606bb4a81483b2153cebc4b9779be38e2df7072af9222ff6f",
      bytes: 76028900,
      archive: "tar.gz",
      entryPath: "OpenMontage-195eab24478dc9363326aec437aefc3701635ddf/README.md",
      fields: { entry: "OpenMontage-195eab24478dc9363326aec437aefc3701635ddf/README.md" },
    }),
  },
  // NavaiST v2 medium (Uzbek ASR), CTranslate2 / faster-whisper layout, from
  // https://huggingface.co/abduaziz/navaistt_v2_medium_ct2 (the earlier
  // "abduaziz/navaistt" name answered 401). Pinned to HF commit e4e78fef714aa13d1e8581cb8816ea362586d543;
  // size and sha256 read from the HF tree API (LFS oid for model.bin) or
  // computed with shasum -a 256 on the downloaded file (the small files).
  // A catalog item carries ONE file, so the five files of the model directory
  // are five sibling items sharing this revision (same approach as the Qwen3-VL
  // model + mmproj pair). Each installs under <id>/<revision>/; there is no
  // CTranslate2 speech backend yet, so they are kind "package" (components
  // lane, manual opt-in) and no engine config consumes them.
  // The model card declares NO license: usage is not granted, hence
  // autoInstall false and an explicit license string the UI row shows.
  {
    id: "asr-navaistt",
    kind: "package",
    version: "e4e78fef714aa13d1e8581cb8816ea362586d543",
    labelKey: "content_navaistt",
    autoInstall: false,
    license: { name: "Unspecified upstream — written permission required", upstreamUrl: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2" },
    platforms: everywhere({
      url: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2/resolve/e4e78fef714aa13d1e8581cb8816ea362586d543/model.bin?download=true",
      sha256: "7c247983182b6eee58ab48e94183e6079fdb68d5a621ab50e69a714b45b191f0",
      bytes: 1527906453,
      archive: "none",
      entryPath: "model.bin",
      fields: { entry: "model.bin" },
    }),
  },
  {
    id: "asr-navaistt-config",
    kind: "package",
    version: "e4e78fef714aa13d1e8581cb8816ea362586d543",
    labelKey: "content_navaistt_config",
    autoInstall: false,
    license: { name: "Unspecified upstream — written permission required", upstreamUrl: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2" },
    platforms: everywhere({
      url: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2/resolve/e4e78fef714aa13d1e8581cb8816ea362586d543/config.json?download=true",
      sha256: "3622a2ddc41ec0e0fd4e68c13c6830f03b90c38d89aaad184de02c8c642cf807",
      bytes: 2257,
      archive: "none",
      entryPath: "config.json",
      fields: { entry: "config.json" },
    }),
  },
  {
    id: "asr-navaistt-preprocessor",
    kind: "package",
    version: "e4e78fef714aa13d1e8581cb8816ea362586d543",
    labelKey: "content_navaistt_preprocessor",
    autoInstall: false,
    license: { name: "Unspecified upstream — written permission required", upstreamUrl: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2" },
    platforms: everywhere({
      url: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2/resolve/e4e78fef714aa13d1e8581cb8816ea362586d543/preprocessor_config.json?download=true",
      sha256: "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
      bytes: 339,
      archive: "none",
      entryPath: "preprocessor_config.json",
      fields: { entry: "preprocessor_config.json" },
    }),
  },
  {
    id: "asr-navaistt-tokenizer",
    kind: "package",
    version: "e4e78fef714aa13d1e8581cb8816ea362586d543",
    labelKey: "content_navaistt_tokenizer",
    autoInstall: false,
    license: { name: "Unspecified upstream — written permission required", upstreamUrl: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2" },
    platforms: everywhere({
      url: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2/resolve/e4e78fef714aa13d1e8581cb8816ea362586d543/tokenizer.json?download=true",
      sha256: "27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566",
      bytes: 2480466,
      archive: "none",
      entryPath: "tokenizer.json",
      fields: { entry: "tokenizer.json" },
    }),
  },
  {
    id: "asr-navaistt-vocabulary",
    kind: "package",
    version: "e4e78fef714aa13d1e8581cb8816ea362586d543",
    labelKey: "content_navaistt_vocabulary",
    autoInstall: false,
    license: { name: "Unspecified upstream — written permission required", upstreamUrl: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2" },
    platforms: everywhere({
      url: "https://huggingface.co/abduaziz/navaistt_v2_medium_ct2/resolve/e4e78fef714aa13d1e8581cb8816ea362586d543/vocabulary.json?download=true",
      sha256: "5ad28279db5e546349708b9a74736e2c018737ac5a600f1048f1f26c99b85b47",
      bytes: 1068103,
      archive: "none",
      entryPath: "vocabulary.json",
      fields: { entry: "vocabulary.json" },
    }),
  },
];

/** The same platform-independent payload on every platform key, so coverage
 *  stays an explicit per-platform entry like the rest of the catalog. */
function everywhere(artifact: ContentArtifact): Partial<Record<ContentPlatformKey, ContentArtifact>> {
  return {
    "win32-x64": artifact,
    "linux-x64": artifact,
    "darwin-arm64": artifact,
    "darwin-x64": artifact,
  };
}

function ytDlpMac(): ContentArtifact {
  return {
    url: "https://github.com/yt-dlp/yt-dlp/releases/download/2026.10.26/yt-dlp_macos",
    sha256: "0f922c15ccc0b83eefa1c8bc9104e434318c4bf16e408e1ee93b7745a6efe0aa",
    bytes: 37466304,
    archive: "none",
    entryPath: "yt-dlp",
    fields: { binary: "yt-dlp", entry: "yt-dlp" },
    executable: true,
  };
}
