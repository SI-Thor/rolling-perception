//! FluidAttn — viewport / ROI gating (Pillar 3).
//!
//! ## Email claim kept
//! Work outside the region of interest should be skipped, not done
//! and discarded, so compute concentrates where attention points.
//! The ROI is an axis-aligned rectangle (`CacheAlignedMask` in the
//! email; a plain struct here — alignment of a 16-byte bounds value
//! buys nothing measurable, so it isn't dressed up as 64).
//!
//! ## Email claims fixed / stated honestly
//! * The email's gate was a 1-D check (`xmin <= x <= xmax`) returning
//!   a `bool` — in Rust source that is a branch like any other.
//!   "Branchless" below means the *source* combines comparisons
//!   arithmetically (`bool as u32`, bitwise AND) with no `if` on the
//!   data path. Whether LLVM emits a branch for any given target is
//!   the compiler's decision and is not promised.
//! * The email's implementation returned the gate but never showed
//!   skipped work being counted or results being preserved.
//!   [`gated_apply`] returns exact processed/skipped counts, and its
//!   contract — inside the ROI the result is identical to ungated
//!   compute, outside it the input is untouched — is tested.

/// Axis-aligned region of interest, half-open:
/// `x in [xmin, xmax)`, `y in [ymin, ymax)`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Viewport {
    pub xmin: u32,
    pub xmax: u32,
    pub ymin: u32,
    pub ymax: u32,
}

impl Viewport {
    pub fn new(xmin: u32, xmax: u32, ymin: u32, ymax: u32) -> Self {
        assert!(xmin <= xmax && ymin <= ymax, "inverted viewport");
        Self { xmin, xmax, ymin, ymax }
    }

    /// Whole-frame viewport.
    pub fn full(width: u32, height: u32) -> Self {
        Self { xmin: 0, xmax: width, ymin: 0, ymax: height }
    }

    pub fn area(&self) -> u64 {
        (self.xmax - self.xmin) as u64 * (self.ymax - self.ymin) as u64
    }

    /// 1 if `(x, y)` is inside, 0 otherwise — computed as arithmetic
    /// on comparison results, no data-dependent branch in the source.
    #[inline(always)]
    pub fn mask(&self, x: u32, y: u32) -> u32 {
        let in_x = ((x >= self.xmin) & (x < self.xmax)) as u32;
        let in_y = ((y >= self.ymin) & (y < self.ymax)) as u32;
        in_x & in_y
    }

    #[inline(always)]
    pub fn contains(&self, x: u32, y: u32) -> bool {
        self.mask(x, y) == 1
    }
}

/// Outcome counts from [`gated_apply`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct GateStats {
    pub processed: usize,
    pub skipped: usize,
}

/// Apply `f` to every element of a row-major `width × height` grid
/// that lies inside `vp`; leave all other elements untouched and
/// *do not call `f` on them at all* — the skip is the saving.
///
/// Returns exact counts: `processed == vp.area()` (clipped to the
/// grid) and `processed + skipped == width * height`.
pub fn gated_apply<T, F: FnMut(&mut T)>(
    data: &mut [T],
    width: usize,
    height: usize,
    vp: &Viewport,
    mut f: F,
) -> GateStats {
    assert_eq!(data.len(), width * height, "grid size mismatch");
    let mut stats = GateStats { processed: 0, skipped: 0 };
    for y in 0..height {
        for x in 0..width {
            let idx = y * width + x;
            // The mask decides; outside-ROI elements are not touched
            // by `f`. (This loop's branch is the dispatch, not the
            // per-element math the email's claim was about.)
            if vp.mask(x as u32, y as u32) == 1 {
                f(&mut data[idx]);
                stats.processed += 1;
            } else {
                stats.skipped += 1;
            }
        }
    }
    stats
}

/// Iterator over the `(x, y)` coordinates inside `vp`, clipped to a
/// `width × height` grid — for callers that drive their own kernels.
pub fn roi_coords(
    width: usize,
    height: usize,
    vp: &Viewport,
) -> impl Iterator<Item = (usize, usize)> {
    let xs = (vp.xmin as usize).min(width)..(vp.xmax as usize).min(width);
    let ys = (vp.ymin as usize).min(height)..(vp.ymax as usize).min(height);
    ys.flat_map(move |y| xs.clone().map(move |x| (x, y)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mask_matches_bounds() {
        let vp = Viewport::new(2, 5, 1, 3);
        assert_eq!(vp.mask(2, 1), 1);
        assert_eq!(vp.mask(4, 2), 1);
        assert_eq!(vp.mask(5, 2), 0, "xmax is exclusive");
        assert_eq!(vp.mask(1, 1), 0);
        assert_eq!(vp.mask(3, 3), 0, "ymax is exclusive");
        assert!(vp.contains(3, 2));
        assert!(!vp.contains(0, 0));
    }

    #[test]
    fn gated_result_identical_on_roi_and_untouched_outside() {
        let (w, h) = (8usize, 6usize);
        let original: Vec<f64> = (0..w * h).map(|i| i as f64 * 0.5).collect();
        let vp = Viewport::new(2, 6, 1, 5);

        let mut gated = original.clone();
        let calls = std::cell::Cell::new(0usize);
        let stats = gated_apply(&mut gated, w, h, &vp, |v| {
            calls.set(calls.get() + 1);
            *v = v.mul_add(3.0, 1.0);
        });

        // Reference: same function applied only inside the ROI.
        let mut reference = original.clone();
        for y in 0..h {
            for x in 0..w {
                if vp.contains(x as u32, y as u32) {
                    let v = &mut reference[y * w + x];
                    *v = v.mul_add(3.0, 1.0);
                } else {
                    assert_eq!(gated[y * w + x], original[y * w + x], "outside ROI must be untouched");
                }
            }
        }
        assert_eq!(gated, reference);
        assert_eq!(calls.get(), stats.processed, "f must not be called for skipped elements");
    }

    #[test]
    fn skipped_counts_are_exact() {
        let (w, h) = (10usize, 10usize);
        let mut data = vec![0u32; w * h];
        let vp = Viewport::new(2, 5, 0, 4); // 3 * 4 = 12 inside
        let stats = gated_apply(&mut data, w, h, &vp, |v| *v += 1);
        assert_eq!(stats.processed, 12);
        assert_eq!(stats.skipped, 100 - 12);
        assert_eq!(stats.processed, vp.area() as usize);
    }

    #[test]
    fn full_viewport_skips_nothing_empty_skips_everything() {
        let mut data = vec![1i32; 16];
        let s = gated_apply(&mut data, 4, 4, &Viewport::full(4, 4), |v| *v *= 2);
        assert_eq!((s.processed, s.skipped), (16, 0));
        let mut data = vec![1i32; 16];
        let s = gated_apply(&mut data, 4, 4, &Viewport::new(2, 2, 0, 4), |v| *v *= 2);
        assert_eq!((s.processed, s.skipped), (0, 16));
        assert!(data.iter().all(|&v| v == 1));
    }

    #[test]
    fn roi_coords_match_viewport() {
        let coords: Vec<_> = roi_coords(8, 8, &Viewport::new(6, 20, 0, 2)).collect();
        // Clipped to the 8-wide grid: x in 6..8, y in 0..2.
        assert_eq!(coords.len(), 4);
        assert!(coords.iter().all(|&(x, y)| x >= 6 && x < 8 && y < 2));
    }
}
