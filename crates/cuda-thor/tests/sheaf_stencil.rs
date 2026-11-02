//! Thor-gated proof for the generic kernel surface (the five
//! cuda-thor additions rolling-pipeline's executor seam specified:
//! public `compile`, `Module::load_named`, `Module::launch_args`,
//! byte-level `DevBuf` copies, `Gpu::new_stream`).
//!
//! A sheaf stencil — graph-Laplacian apply plus one smoothing
//! step, the pipeline's refine stage (ARCHITECTURE claim D13) — is
//! compiled from source at test time, loaded by name, launched
//! with typed argument descriptors on the *second* stream, and
//! compared against the CPU reference.
//!
//! CPU reference: copied from `rolling-substrate-core`'s
//! `SheafGraph::laplacian_apply_into` (this crate does not depend
//! on the substrate crate, so the math is restated here verbatim:
//! zero the output, then per edge `(i, j)` accumulate
//! `out[i] += s[i] - s[j]` and `out[j] += s[j] - s[i]`). If the
//! substrate's rule ever changes, this copy must change with it —
//! the comparison is only meaningful against the real definition.
//!
//! Precision: **f64 end to end**, because the pipeline's stencil
//! is f64 and a f32 proof would not unblock it. The one honest
//! divergence source is accumulation *order*: the CPU accumulates
//! each node's contributions in edge-list order, the GPU kernel is
//! edge-parallel and accumulates with `atomicAdd`, in whatever
//! order the edges land. That is reassociation rounding only —
//! with |s| < 1 and max degree 4, the bound is a handful of ulps of
//! partial sums below ~8, i.e. ~1e-14. The tolerance is 1e-9: five
//! orders above the reassociation bound, seven below the signal
//! scale. Anything larger is a real bug, not rounding.
//!
//! `#[ignore]`d AND feature-gated, like the spike tests. Run on
//! the Thor with:
//!   cargo test --release --features cuda-thor --test sheaf_stencil -- --ignored --nocapture

#[cfg(feature = "cuda-thor")]
use cuda_thor::gpu::{compile, DevBuf, Gpu, Module, PinnedBuf};
#[cfg(feature = "cuda-thor")]
use cuda_thor::{test_input, KernelArg};

/// The two stencil kernels. `laplacian_apply` is edge-parallel:
/// one thread per edge, both endpoint contributions atomically
/// accumulated (this is the scatter form of the CPU reference's
/// per-edge loop). `smooth_axpy` is the node-parallel second half
/// of one refine step, `s -= alpha * (L s)`, and exists here to
/// exercise an f64 scalar argument through `launch_args`.
#[cfg(feature = "cuda-thor")]
const STENCIL_SRC: &str = r#"
extern "C" __global__ void laplacian_apply(const double* __restrict__ s,
                                           const int* __restrict__ ei,
                                           const int* __restrict__ ej,
                                           double* __restrict__ out,
                                           int m) {
    int e = blockIdx.x * blockDim.x + threadIdx.x;
    if (e >= m) return;
    int i = ei[e];
    int j = ej[e];
    double d = s[i] - s[j];
    atomicAdd(&out[i], d);
    atomicAdd(&out[j], -d);
}
extern "C" __global__ void smooth_axpy(double* __restrict__ s,
                                       const double* __restrict__ ls,
                                       double alpha, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    s[i] -= alpha * ls[i];
}"#;

/// Stated tolerance for the GPU-vs-CPU comparison (see the module
/// docs for the reassociation bound it sits above).
#[cfg(feature = "cuda-thor")]
const TOL_F64: f64 = 1e-9;

/// The graph: a 64-node line plus four chords (max degree 4).
#[cfg(feature = "cuda-thor")]
fn graph() -> (usize, Vec<(i32, i32)>) {
    let n = 64usize;
    let mut edges: Vec<(i32, i32)> = (0..n - 1).map(|i| (i as i32, i as i32 + 1)).collect();
    edges.extend([(0, 32), (16, 48), (8, 40), (24, 56)]);
    (n, edges)
}

/// CPU reference Laplacian apply — copied (see module docs) from
/// `rolling-substrate-core`'s `laplacian_apply_into`.
#[cfg(feature = "cuda-thor")]
fn reference_laplacian(n: usize, edges: &[(i32, i32)], s: &[f64]) -> Vec<f64> {
    let mut out = vec![0.0f64; n];
    for &(i, j) in edges {
        let (i, j) = (i as usize, j as usize);
        out[i] += s[i] - s[j];
        out[j] += s[j] - s[i];
    }
    out
}

#[cfg(feature = "cuda-thor")]
fn f64_bytes(v: &[f64]) -> Vec<u8> {
    v.iter().flat_map(|x| x.to_le_bytes()).collect()
}

#[cfg(feature = "cuda-thor")]
fn i32_bytes(v: &[i32]) -> Vec<u8> {
    v.iter().flat_map(|x| x.to_le_bytes()).collect()
}

#[cfg(feature = "cuda-thor")]
fn bytes_f64(b: &[u8]) -> Vec<f64> {
    // `b` is a whole number of f64s by construction (a pinned
    // buffer of n * 8 bytes), so the as_chunks remainder is empty.
    b.as_chunks::<8>()
        .0
        .iter()
        .map(|c| f64::from_le_bytes(*c))
        .collect()
}

#[cfg(feature = "cuda-thor")]
fn max_abs_err_f64(a: &[f64], b: &[f64]) -> f64 {
    assert_eq!(a.len(), b.len(), "comparison lengths must match");
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).abs())
        .fold(0.0f64, f64::max)
}

#[test]
#[ignore = "needs the Thor GPU"]
#[cfg(feature = "cuda-thor")]
fn sheaf_stencil_through_the_generic_api_matches_cpu_reference() {
    let (n, edges) = graph();
    let m = edges.len();
    let alpha = 0.05f64;
    // Deterministic input in [-1, 1), from the crate's own fixture
    // generator, widened to f64.
    let s: Vec<f64> = test_input(n).iter().map(|&v| v as f64).collect();
    let expected_ls = reference_laplacian(n, &edges, &s);
    let expected_s: Vec<f64> = s
        .iter()
        .zip(expected_ls.iter())
        .map(|(v, l)| v - alpha * l)
        .collect();

    let gpu = Gpu::new().expect("Gpu::new on the Thor");
    let (free0, total) = gpu.mem_info().expect("cuMemGetInfo");
    // Addition 5: the second stream (the shadow stream).
    let shadow = gpu.new_stream().expect("Gpu::new_stream");
    let stream = shadow.handle();
    assert!(!stream.is_null(), "second stream handle must be real");

    // Addition 1: public NVRTC compile of a non-perceive kernel.
    let compiled = compile(STENCIL_SRC, "compute_110", false).expect("compile stencil");
    assert!(compiled.log.is_empty(), "compile log: {}", compiled.log);
    // Addition 2: load by arbitrary kernel name, twice (one Module
    // resolves one function, as the struct has always been shaped).
    let apply = Module::load_named(&compiled.image, "laplacian_apply").expect("load apply");
    let axpy = Module::load_named(&compiled.image, "smooth_axpy").expect("load axpy");

    // Addition 4: byte-level upload of f64 sections and i32 edge
    // lists (the old upload() could not stage either).
    let d_s = DevBuf::new(n * 8).expect("alloc s");
    d_s.upload_bytes(&f64_bytes(&s)).expect("upload s");
    let d_out = DevBuf::new(n * 8).expect("alloc out");
    d_out
        .upload_bytes(&vec![0u8; n * 8])
        .expect("zero the output buffer");
    let (ei, ej): (Vec<i32>, Vec<i32>) = edges.iter().copied().unzip();
    let d_ei = DevBuf::new(m * 4).expect("alloc ei");
    d_ei.upload_bytes(&i32_bytes(&ei)).expect("upload ei");
    let d_ej = DevBuf::new(m * 4).expect("alloc ej");
    d_ej.upload_bytes(&i32_bytes(&ej)).expect("upload ej");

    // Addition 3: typed-descriptor launches, both on the shadow
    // stream. Grid covers the edge list / the node list.
    let grid_e = ((m as u32).div_ceil(256), 1, 1);
    let grid_n = ((n as u32).div_ceil(256), 1, 1);
    // SAFETY: the stream is the live shadow stream; both modules
    // stay loaded until after the synchronisation below; the
    // argument lists match the kernel signatures in STENCIL_SRC
    // (pointer, pointer, pointer, pointer, i32) and
    // (pointer, pointer, f64, i32); every DevPtr names one of the
    // live buffers above, sized for the kernel's accesses (s/out:
    // n f64 indexed by node id < n; ei/ej: m i32 indexed by the
    // thread's edge id < m).
    unsafe {
        apply
            .launch_args(
                stream,
                &[
                    KernelArg::from_devbuf(&d_s),
                    KernelArg::from_devbuf(&d_ei),
                    KernelArg::from_devbuf(&d_ej),
                    KernelArg::from_devbuf(&d_out),
                    KernelArg::I32(m as i32),
                ],
                grid_e,
                (256, 1, 1),
            )
            .expect("launch laplacian_apply");
        axpy.launch_args(
            stream,
            &[
                KernelArg::from_devbuf(&d_s),
                KernelArg::from_devbuf(&d_out),
                KernelArg::F64(alpha),
                KernelArg::I32(n as i32),
            ],
            grid_n,
            (256, 1, 1),
        )
        .expect("launch smooth_axpy");
    }

    // Addition 4 (download half): async copy-back into pinned host
    // memory on the same stream, then synchronise that stream only.
    let host_ls = PinnedBuf::new(n * 8).expect("pinned ls");
    let host_s = PinnedBuf::new(n * 8).expect("pinned s");
    // SAFETY: the stream is the live shadow stream; both pinned
    // buffers are exactly the device buffers' size (checked inside
    // download_to_pinned), and the reads below happen only after
    // `shadow.synchronize()`.
    unsafe {
        d_out
            .download_to_pinned(&host_ls, stream)
            .expect("download Ls");
        d_s.download_to_pinned(&host_s, stream).expect("download s");
    }
    shadow.synchronize().expect("synchronise shadow stream");

    let got_ls = bytes_f64(host_ls.as_bytes());
    let got_s = bytes_f64(host_s.as_bytes());
    let err_ls = max_abs_err_f64(&got_ls, &expected_ls);
    let err_s = max_abs_err_f64(&got_s, &expected_s);
    println!(
        "device: total {total} B ({:.1} GiB), free at start {free0} B; nvrtc {:?}",
        total as f64 / (1u64 << 30) as f64,
        cuda_thor::gpu::nvrtc_version(),
    );
    println!(
        "stencil: n={n} nodes, m={m} edges, compile {:.1} ms; \
         laplacian max_err {err_ls:.3e}, smooth-step max_err {err_s:.3e} (tol {TOL_F64:.0e})",
        compiled.compile_time.as_secs_f64() * 1e3,
    );
    assert!(
        err_ls <= TOL_F64,
        "laplacian_apply GPU vs CPU max_err {err_ls} exceeds tol {TOL_F64}"
    );
    assert!(
        err_s <= TOL_F64,
        "smooth step GPU vs CPU max_err {err_s} exceeds tol {TOL_F64}"
    );

    apply.unload().expect("unload apply");
    axpy.unload().expect("unload axpy");
}
