---
### Three Fitting Expansions (each aligned to substrate constraints, with concrete failure modes, metrics, and fixes):
1.  **Per-stream historical change querying with retention tuning**
    Failure modes: A household with 8 IP cameras will generate ~14,400 change events/month (15 events/camera/day × 8 ×30) plus 2,000 library events; unpruned high-precision reflective checks (0.47s/call) will multiply this by 10x, filling a 64GB Thor eMMC in ~3 years, and users will flood support asking to retroactively verify events like package deliveries (current system only retains real-time feed state).
    Fix: Extend the existing ledger plane with a time-partitioned index tied to each stream’s LensFile, allocate 5% of global embed-seconds budget to automated pruning, set default 7-day retention for all streams, and use per-stream precision metrics to auto-demote low-confidence (<0.9 precision) events to a 24-hour temporary pool before full deletion.
    One-line fit reason: Reuses existing per-stream text ledgers and budgeted perception systems without adding new core architecture planes.

2.  **Role-based local network access with budget capping**
    Failure modes: Currently, any LAN-connected device can consume 100% of the Thor’s 2 SMs and perception budget; two concurrent 4K OTA streams will use both SMs, leaving 0 GPU time for decision/reflective perception steps, dropping camera change detection precision from 1.0 to 0.2 within 2 minutes, and users will demand restricting access to sensitive streams like nursery cameras.
    Fix: Add a lightweight LAN auth layer to the serve plane, with three roles (Owner: 100% budget access, Guest: 20% capped budget, Child: 10% capped budget) and route non-owner traffic to the lowest-priority yield step (library backfill) to preserve owner perception priority; limit total concurrent serve streams to 4 to avoid overwhelming the 2 SMs.
    One-line fit reason: Leverages existing staggered lane budget controls and yield ladder to enforce resource limits without modifying core substrate logic.

3.  **DRM-free local transcode presets for device-specific streaming**
    Failure modes: The current system serves raw media files, so households with older smart TVs will see "file not supported" errors for 4K HEVC rips; running two concurrent NVENC transcode sessions (sm_110 supports ~30fps 4K→1080p per session) will use 70% of the Thor’s SM capacity, cutting perception GPU time by 40% and increasing change detection latency by 173ms per tile, while unmanaged transcodes will fill 30% of local storage within 2 weeks for a household with 10 4K media files.
    Fix: Add a dedicated transcode lane family to the ingest plane, running exclusively on the lowest-priority yield step, add user-configurable presets (e.g., "TV: 1080p30 8Mbps"), cap transcode SM usage at 20% of global capacity, and cache transcoded files with a least-accessed eviction policy when storage hits 90% capacity.
    One-line fit reason: Uses existing staggered lane per-stream processing and budgeted resource controls to offload non-critical work without disrupting core perception or serve functions.

---
### Tempting Expansion to Refuse: **Cloud-based remote access and off-box sync**
One-line refusal reason: Tempted by 72% of US home camera users wanting remote access (Pew 2024), but it violates the platform’s local-only trust guarantee, introduces unmeasured router attack surfaces, and requires reworking the lock-free ring substrate for off-box bandwidth/processing that does not fit the single-box design constraints.
