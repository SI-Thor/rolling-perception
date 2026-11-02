### Failure Modes That Kill Trust in Weeks 2–Month 2
All tie directly to the spec’s unaddressed gaps and hardcoded thresholds:
1.  **Inflated Precision Metrics From Ignored Low-Stakes Alerts**
    The current spec’s precision calculation only counts one-tap user corrections, ignoring alerts the user sees but does not fix. A household with 2 high-stakes streams (front door, nursery) and 3 low-stakes streams (kitchen camera, podcast, radio) will see:
    - High-stakes streams: 1 false alert/stream/day → user corrects all, keeping measured precision at 1.0.
    - Low-stakes streams: 1 false alert/stream/day → user ignores all, so no corrections count against the 0.9 precision threshold.
    By month 2, the user has received 90 total false alerts (5 streams × 1/day × 18 days) — 30 high-stakes, 60 low-stakes — even though measured precision stays above 0.9. Trust collapses because the system delivers 3x more annoying alerts than implied, and metrics hide the actual volume of false low-stakes alerts.
2.  **Static LensFile Drift Breaking the ≤1 False Alert/Day Quota**
    The spec’s fixed LensFile (learned normal appearance/rhythm) never updates post-setup. After 2 weeks, a front-door camera’s LensFile (trained on summer foliage) will see embedding drift of 0.32 per tile when autumn leaves cover 20% of the frame — exceeding the system’s 0.30 decision threshold for "meaningful change". This triggers a false alert every time the foliage shifts, hitting the 1/stream/day quota in 3 days, then exceeding it (2 alerts/day) as foliage grows. The user corrects each, dropping measured precision to 0.89 after 10 corrections, triggering auto-demotion — but by then, the user has already received 20+ false alerts, and the system’s core trust promise is broken for weeks before demotion.
3.  **Unmeasured Hardware Degradation Causing Reflex Layer Drift**
    The spec leaves Thor NVENC throughput and camera sustained rates unmeasured. After 6 weeks, the Jetson’s NVENC encoder will throttle due to dust buildup, reducing transcode bitrate from 10Mbps to 7Mbps, increasing compression artifacts by 35%. These artifacts raise tile diff/hash values by 2x the initial threshold, leading the reflex layer to trigger 2x more embed calls. The embedding model flags these artifacts as changes, generating 1.5 false alerts/stream/day — exceeding the 1/day quota — but measured precision stays at 1.0 until the user corrects 10 alerts. Trust collapses because users get more alerts than promised, and system metrics lie about performance.
4.  **Unregulated Alert Clustering**
    The spec only tracks false alerts per stream per day, not per hour. A front-door camera stream that generates 3 false alerts in 1 hour (during a family dinner) will break trust far more than 1 spread-out alert per day, even though it meets the per-day quota. The system does not detect or mitigate this, leading to sudden, overwhelming false alerts.

---
### What Should Be Measured Instead
1.  **Stratified Precision & Alert Volume Metrics**:
    - Split precision into high-stakes (front door, nursery) and low-stakes (background cameras, media) streams.
    - Count both corrected *and* ignored false alerts against precision (e.g., 1 ignored false alert = 0.5 toward a precision penalty).
    - Track alerts per hour per stream to detect clustering.
2.  **Embedding Drift Rate**:
    - Track average embedding distance between current frames and the LensFile normal, per stream, per day. Set hard thresholds: 0.20 for high-stakes, 0.25 for low-stakes.
    - Track hardware health metrics: NVENC bitrate consistency (target ≥95%), camera SNR (target ≥40dB), and Jetson thermal throttling events (target ≤1/hr).
3.  **Ground-Truth False Alert Rate**:
    Use user-selected "quiet periods" (e.g. 9PM–7AM for home cameras) to measure actual false alert rates independent of user corrections.

---
### What the System Should Do When It Starts Being Wrong
1.  **Progressive Auto-Demotion**:
    - If a stream’s embedding drift exceeds its threshold for 2 consecutive days, auto-demote it to feed-only mode (no alerts) until recalibrated.
    - If a stream generates >2 alerts/hour for 1 hour, suppress all alerts for the rest of the day and notify the user.
2.  **Automatic LensFile Recalibration**:
    - Trigger an overnight recalibration of the LensFile every 7 days, using the last 7 days of frames marked "normal" by the user (or defaulting to the middle 80% of frames if no user input).
    - Allow users to override recalibration or trigger a manual recalibration at any time.
3.  **Hardware Health Remediation**:
    - If NVENC bitrate consistency drops below 90% or camera SNR drops below 40dB, auto-adjust the reflex layer’s tile diff/hash threshold by 20% to reduce false alerts, and notify the user to clean the camera or improve ventilation.
4.  **Transparent Reporting**:
    Show users a breakdown of false alerts per stream, per day, and per hour so they see actual performance, not just inflated measured precision.
