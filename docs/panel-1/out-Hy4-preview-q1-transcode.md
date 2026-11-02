## Attack: “one live transcode + perception on the same GPU” on one Jetson AGX Thor

**Hardware reality to design against:** Thor’s GPU is **20 SMs / 2560 CUDA cores**, with **fixed-function NVENC/NVDEC blocks** and **122 GB unified LPDDR5X**. The 122 GB is not a fix for throughput; it is a fix for *buffering and model residency*. The shared bottleneck is **unified memory bandwidth, NVENC session slots, and SM/VRAM contention** between NVENC’s internal buffers, decode/scale/overlay kernels, and perception kernels.

### 1. What breaks first

**First failure: the player’s decode/scale/overlay path, not NVENC, if you do GPU preprocessing.**  
If the player decodes on NVDEC, then does **GPU colorspace conversion, scaling, deinterlace, overlay, tone mapping, or subtitle burn-in** with CUDA/VIC, those kernels land on the same 20 SMs as perception. A 4K→1080p or 4K→720p pipeline with a few VIC/CUDA passes can eat **10–25% of SM time** before embedding. On a 33 ms 1080p30 budget, that is **3–8 ms of GPU preemption** per frame. Perception then sees **jitter, not just lower throughput**. Your measured **173 ms I-JEPA tile embed** becomes 190–260 ms under contention; the **0.47 s reflective judge** can blow past 0.7 s if it is queued behind a burst of transcode frames.

**Second failure: NVENC session exhaustion / context thrash.**  
Do not assume “one live transcode” means “one session.” A household player that supports **ABR ladder output, multiple qualities, restarts, seek/rebuffer, PiP, or two viewers** can need **2–4 concurrent NVENC sessions**. If Thor exposes only **1–2 hardware encoder contexts**, the second or third session either fails or falls back to software x264. Software 1080p30 x264 on 14 CPU cores is a **different disaster**: it steals CPU from reflex tile-diff/hash and ledger writes, and can push 300–800 ms of CPU time per second of video. That is how you stall ingest and perception at the CPU layer.

**Third failure: memory bandwidth and VIC/NVENC input starvation.**  
Unified memory means perception’s resident embedding model, judge model, tile ring buffers, and NVENC’s reference/reorder buffers all contend for LPDDR5X. A 4K60 live source plus a 1080p ladder plus perception can demand **>100 GB/s** of sustained traffic. Symptoms are not “out of memory”; they are **encode latency spikes, dropped camera frames, and embed queue timeouts**.

**Fourth failure: live ingest drop-to-newest masking a real overload.**  
Camera/live lanes are specified to **drop
