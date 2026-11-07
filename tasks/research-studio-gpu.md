# Research: can GPU support make Vertical Studio faster?

Researched 2026-11-07 by request. **Report only — nothing here is implemented.**
Every number below is measured on this laptop (i7 + GeForce MX250, driver 582.78)
with the ffmpeg the app actually ships (`release/portable/bin/ffmpeg.exe`,
9.0-full_build gyan.dev), on a 20 s synthetic 4K H.264 clip.

## Short answer

No, not where it was hoped. GPU **decode** is measurably *slower* than the
software path we already use, and the one GPU trick that would cut the render
time — a GPU-side crop — does not exist in ffmpeg. The only credible GPU win is
**encoding**, and on this app's only Windows-NVIDIA users that is ~1.6-3.1×, at
a quality change, with no fallback when the driver is missing.

Three **CPU-side** changes found on the way are worth more than any GPU work,
need no GPU, and are already measured: 5-13× on the dominant detection pass,
7.3× on the cropdetect pass, and one full 4K decode removed. Those are the
recommendation.

## Where the time actually goes

`engine.py:1113` prices **7 full reads of the source** per film with both
features on — `reframe.ANALYSIS_PASSES = 3` (`reframe.py:61`) plus 1 render,
and 3 passes for the shorts leg:

| # | Pass | Where | What it really costs |
|---|---|---|---|
| 1 | silence | `shorts.py:286` `silencedetect` | audio-only, cheap |
| 2 | scene | `shorts.py:314` `select='gt(scene,…)'` | **full-res decode** |
| 3 | shorts encode | `shorts.py:333` `libx264 -preset veryfast -crf 20` | encode |
| 4 | cropdetect | `reframe.py:294` `cropdetect=24:2:0` | **full-res decode** |
| 5 | proxy encode | `reframe.py:569` | encode, to 1920-wide @ 5 fps |
| 6 | tracking | `reframe.py:580-615` `cv2.VideoCapture` | **the real hog** |
| 7 | render | `reframe.py:346` `sendcmd,crop,scale` + `libx264` | decode + CPU crop + encode |

Two premises in the original question were wrong:

- The detectors are **DNN ONNX models** (YuNet + NanoDet, `reframe.py:732-735`),
  not Haar cascades — so "GPU the classifier" was never an OpenCV-Cascade issue.
- The pin is `opencv-python-headless==4.14.0.94` (`requirements.txt:36`), and
  that wheel has **no CUDA module at all** — upstream refuses to ship one: *"Pre-built wheels with CUDA
  support will not be added [to] PyPI"*
  ([opencv-python#398](https://github.com/opencv/opencv-python/issues/398)).
  Using OpenCV's CUDA backend would mean building OpenCV from source
  (`WITH_CUDA=ON`) and shipping that binary ourselves.

The dominant cost is the detector, not ffmpeg: `SubjectDetector.detect` on a
1920-wide proxy measured **250 ms/frame**; at `PROXY_FPS = 5.0`
([reframe.py:57](../src/s_q_ali_media_downloader/core/reframe.py#L57)) that is
1.25 s of work per second of film. `face_centre` calls `setInputSize((width,
height))` (`reframe.py:749`), so YuNet runs at full proxy width — and it scales
hard with input size: 1920×1080 → 127-153 ms, 960×540 → 48 ms, 652×366 → 24 ms,
480×270 → **11 ms/frame**.

## GPU feasibility, stage by stage

| Stage | GPU possible? | Measured / documented verdict |
|---|---|---|
| Decode (passes 2, 4, 7) | yes, technically | **slower than software** on this machine: sw 1.3 s, `-hwaccel cuda` 2.1 s, `auto` 7.3 s, `d3d11va` 9.8 s, `qsv` 3.5 s. ffmpeg's own docs: *"most acceleration methods are intended for playback and will not be faster than software decoding on modern CPUs… ffmpeg will usually need to copy the decoded frames from the GPU memory into the system memory, resulting in further performance loss"* ([ffmpeg(1), `-hwaccel`](https://ffmpeg.org/ffmpeg.html)) |
| Crop on the GPU (pass 7) | **no** | there is no `crop_cuda` / `crop_opencl` / `crop_vaapi`; the CUDA filter set is scale/overlay/pad/bwdif/yadif/colorspace/chromakey/bilateral/thumbnail/transpose and `scale_cuda` is *"Scale (resize) and convert (pixel format)"* only ([vf_crop](https://ffmpeg.org/ffmpeg-filters.html#crop), [scale_cuda](https://ffmpeg.org/ffmpeg-filters.html#scale_cuda)). The shipped build agrees: `-filters | grep crop` → `crop`, `cropdetect`. The only GPU crop is the *static* `*_cuvid` decoder `-crop`/`-resize`, which cannot follow a moving window. `-filter_hw_scale`, as guessed in the question, does not exist in FFmpeg. |
| macOS equivalent | **no** | the whole "VideoToolbox Video Filters" chapter is `scale_vt` + `transpose_vt` ([docs](https://ffmpeg.org/ffmpeg-filters.html#VideoToolbox-Video-Filters)) |
| Encode (passes 3, 5, 7) | yes | NVENC/AMF/QSV/VideoToolbox replace `libx264 veryfast` (reframe.py:343-349, shorts.py:333). NVIDIA documents the offload and the p1-p7 speed/quality presets, 8 concurrent GeForce sessions ([Using FFmpeg with NVIDIA GPU](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/ffmpeg-with-nvidia-gpu/index.html), [NVENC App Note](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvenc-application-note/index.html)). **No official NVENC-vs-x264 speed or quality ratio exists**; the 1.6× (veryfast-equivalent) to 3.1× (fast-equivalent) figures are third-party and unverified. |
| Tracking pass (6) | not from PyPI | OpenCL *is* compiled into our wheel, but every OpenCL path measured **slower**: YuNet 554 ms vs 144 ms CPU, NanoDet forward 467 vs 82 ms, `resize` UMat 2.17 vs Mat 0.5 ms — plus `CL_BUILD_PROGRAM_FAILURE: dnn/activations` on this driver. `DNN_BACKEND_CUDA`/`DNN_TARGET_CUDA` are enum-only in this build; the supported matrix is OPENCV × {CPU, OPENCL, OPENCL_FP16} ([dnn.hpp](https://github.com/opencv/opencv/blob/master/modules/dnn/include/opencv2/dnn/dnn.hpp)). YuNet *can* be retargeted (`FaceDetectorYN.create(..., backend_id, target_id)`, [face.hpp](https://github.com/opencv/opencv/blob/master/modules/objdetect/include/opencv2/objdetect/face.hpp)); the app passes neither today. |

## Why GPU code is hard to keep correct here

1. **GPU encoders do not fall back — they fail the job.** On this machine
   `h264_nvenc` → `Cannot load nvEncodeAPI64.dll` ("minimum required Nvidia
   driver for nvenc is 610.00 or newer"; that DLL is genuinely absent from
   System32), `h264_amf` → `DLL amfrt64.dll failed to open`, `h264_cuvid` →
   "not supported with this chroma format" with all CUVID caps zero. Each exits
   non-zero having written a 0-byte file, so the render leg dies
   (`reframe.py:408-415`). Only `-hwaccel` degrades quietly.
2. **CI can never verify any of it.** Standard GitHub-hosted runner specs list
   CPU/RAM/storage/arch with **no GPU**
   ([github-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners));
   GPUs exist only on paid GPU larger runners (Tesla T4/A10G). So every cell of
   `ci.yml` and `release.yml` would exercise only the failure path, and the
   success path would be verified by nothing but manual runs on owner machines.
3. **A GPU encoder changes the output**, not just its speed, so it is a quality
   decision for the owner, not a performance free lunch.

## The cheaper wins, already measured (no GPU needed)

| | Change | Measured | Cost |
|---|---|---|---|
| A | Detect on a smaller copy: keep `PROXY_WIDTH=1920` for cropping, feed YuNet ~640-960 wide and scale the centre back | 5-13× off the dominant pass | 1-2 lines + a re-check of the accuracy note at `reframe.py:51-57` |
| B | `-skip_frame nokey` on the cropdetect input (`reframe.py:294`) | 0.20 s vs 1.46 s = **7.3×** ([skip_frame](https://ffmpeg.org/ffmpeg-codecs.html)) | one flag |
| C | Merge detection into the proxy pass: `-vf "fps=5,scale=…,cropdetect=24:2:0"` emitted the proxy *and* 98 parseable `crop=` lines in 1.76 s vs 3.59 s as two passes | removes one full 4K decode + one encode | one command, two parsers joined |
| D | Same merge trick for `select='gt(scene,…)'` (`shorts.py:314`) | removes another full-res decode | only if 5 fps scene sampling is acceptable — **product tradeoff** |

Only after A-D, if still wanted: a one-line encoder probe (try
`h264_nvenc` / `hevc_videotoolbox` / `h264_qsv` on a 5-frame throwaway, keep
x264 on any failure). `h264_qsv` was the only GPU encoder that actually worked
on this machine — and Intel iGPU coverage among users is unknown.

## Not checked

No real 4K film was measured. The 20 s 3840x2160 probe clip and the cached
`centres.json` that backed the *older* framing numbers in
`tasks/plan-vertical-reframe.md` are gone — `Downloads\Whisprs\stability-probe\`
no longer exists, only the two real 4K downloads in `Downloads\Whisprs\`. Those
two files are the honest input for experiments A-C; a synthetic `testsrc` clip
ultrafast-encoded, as used here, understates decode cost and would shift the
decode ratios. Also not checked: single-threaded variance; NVENC perceptual
quality at matched bitrate; anything on macOS or Linux. The MX250 is a weak
dGPU: an RTX-class card could move the decode and encode numbers, but not the
two structural blockers (no GPU crop, no CUDA wheel).

## Recommendation

Say no to GPU for now, yes to A-C. They attack the measured bottleneck, work on
every platform we ship, are verifiable in CI, and together remove roughly two of
the seven full reads plus most of the detection time — a bigger realistic gain
than the only GPU path that would ever work.
