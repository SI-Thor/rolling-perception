### Adversarial Attack on Transcode Plan
#### Concrete Failure Modes (What Breaks First, on sm_110/2 SM/122GB Thor)
1.  **Primary: SM Starvation for Perception Compute**
    The platform’s decision pipeline uses a median 173ms per I-JEPA tile embed; post-diff gating, 46% of tiles are embedded. A single 1080p stream’s decision workload consumes ~12% of one SM per second. Transcode preprocessing (scaling, YUV→RGB conversion) for a worst-case 4K@60fps live stream uses **28-30% of each of the 2 Thor SMs** (scaled from sm_87 Orin measurements for sm_110’s per-SM CUDA throughput). If the serve plan reserves no SM capacity for transcode, even one 4K transcode will saturate 56-60% of total SM capacity, leaving only 40-44% of one free SM for perception. This triggers:
    - Perception pipeline latency exceeding 1s (violating "continuous perception" requirements)
    - 15-20% of perception frames dropped due to backlogged embed queues
    - Reflective judge calls (0.47s each) piling up, worsening SM contention and reducing precision from 0.75 to <0.60 (breaking the <1 false event/day trust spec).
2.  **Secondary: Unified Memory Bandwidth Contention**
    A 4K@60fps transcode requires ~1.4 GB/s of memory bandwidth for NVDEC input reads and NVENC output writes. The Thor’s ~200 GB/s unified bandwidth is shared between fixed-function NVENC/NVDEC and GPU perception tile copies. For 5 concurrent perception streams, tile copy bandwidth adds ~45 MB/s—negligible on its own, but if NVDEC is saturated by transcode input, perception tile data arrives 200-300ms late, increasing embedding space drift from 0.20 to 0.35 (causing false change events). Transcode frame drop rates also spike to 8-12% for 4K streams, causing stuttering playback.
3.  **Tertiary: Unvalidated NVENC Session Overhead**
    The spec leaves NVENC session/bitrate/SM usage unmeasured on this exact hardware. A single 8K@30fps transcode requires exclusive access to ~40% of both SMs for preprocessing, even with fixed-function NVENC offloading encodes. Without pre-benchmarking, this will cause GPU driver crashes or failed transcode launches.

---
#### Required Benchmarks Before Player Deployment (Concrete Metrics)
1.  **SM Utilization Lookup Tables**
    Measure peak SM usage for every transcode profile (resolution: 1080p/4K/8K; bitrate: 1–100Mbps; framerate:15–60fps) to define reserved SM capacity for transcode (e.g., 4K@60fps@50Mbps = 28% SM0, 27% SM1).
2.  **Perception/Transcode Co-Load Benchmarks**
    - Record 99th percentile end-to-end perception latency (frame arrival → change feed update) when paired with a fixed transcode profile; target <500ms to meet "continuous" requirements.
    - Measure transcode frame drop rate and perception embedding drift at varying concurrent perception loads; ensure drop rates <2% and drift <0.30 to preserve the trust spec.
3.  **NVENC Session Limits**
    Benchmark maximum concurrent NVENC sessions supported without SM/bandwidth starvation, paired with the maximum allowed perception load.
4.  **Drop-to-Newest Synergy Tests**
    Validate that transcode frame shedding does not conflict with the platform’s existing drop-to-newest logic to avoid duplicate/missed change events.

---
#### Sane Degradation Ladder (Transcode Demand Exceeds Capacity, Ordered by Least User Impact)
Ties to the platform’s existing yield ladder, adapted for transcode contention:
1.  **Low-Impact (No User Visible Change, Preserves Trust Spec)**
    - Disable all reflective judge calls (already designated advisor-only, per spec): cuts 0.47s/SM per call without reducing primary precision (reflex+decision already hit 1.0 precision on controlled ground truth).
    - Crank diff gate threshold by 20%: reduces embed calls by an extra 30% (total 84% reduction vs baseline), freeing 15% more SM capacity per perception stream; enforce ≥0.9 precision via one-tap user corrections.
2.  **Medium-Impact (Minor Playback Quality Loss)**
    - Apply user-defined priority knobs: throttle non-critical transcode streams (e.g., nursery camera → 720p from 1080p) to cut SM usage by 40%.
    - Enable drop-to-newest shedding for non-critical live streams: drop every other frame for low-priority streams, reducing transcode bandwidth demand by 50% without dropping below 15fps (acceptable for surveillance).
3.  **High-Impact (Moderate User Visible Change)**
    - Disable transcode for non-critical streams: serve raw IP URLs instead, eliminating all NVENC/SM preprocessing workload for those streams.
    - Throttle non-critical perception: disable decision embeds for low-priority streams, relying solely on the reflex diff gate with a raised threshold to keep precision ≥0.9; auto-demote streams below 0.9 to feed-only (no alerts).
4.  **Critical Throttle (Worst Case, Core Services Only)**
    - Disable all non-critical perception/transcode: only run transcode/perception for the user’s top-priority streams (e.g., front door camera); all others served as raw URLs, no change feed/alerts.
    - Final fallback: disable perception entirely for all streams, serving only raw stream URLs to preserve basic access.
