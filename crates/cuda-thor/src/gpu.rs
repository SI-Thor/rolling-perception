//! Thin direct FFI to `libcuda` (driver API) + `libnvrtc`.
//! No cudarc: FEASIBILITY §6 — cudarc vs CUDA 13.2 / sm_110 compatibility is
//! unverified; this surface is ~25 functions and every one is exercised by
//! the spikes below. Thor-only; gated behind `--features cuda-thor`.
//!
//! Safety posture: all raw handles live inside structs with `Drop` impls
//! that unload/free/destroy. Epoch retirement in [`spike3`] follows the
//! PLAN §6 rule — a module is unloaded only after the event recorded
//! after its last launch has synchronised (see the retirement loop).
//! Every `unsafe` block in this module carries a `// SAFETY:` comment
//! stating the invariant it relies on; public functions that take raw
//! handles from the caller ([`Event::record`], [`Module::launch`]) are
//! `unsafe fn`s with a `# Safety` contract instead.

use std::ffi::{c_char, c_void, CStr, CString};
use std::time::{Duration, Instant};

use crate::{max_abs_err, reference, test_input, Variant, TOL};

// ---------------------------------------------------------------- FFI types
type CUresult = i32;
type CUdevice = i32;
type CUcontext = *mut c_void;
type CUmodule = *mut c_void;
type CUfunction = *mut c_void;
type CUevent = *mut c_void;
type CUstream = *mut c_void;
type CUdeviceptr = u64;
type NvrtcResult = i32;
type NvrtcProgram = *mut c_void;

const CUDA_SUCCESS: CUresult = 0;

extern "C" {
    fn cuInit(flags: u32) -> CUresult;
    fn cuDeviceGet(dev: *mut CUdevice, ordinal: i32) -> CUresult;
    fn cuDevicePrimaryCtxRetain(ctx: *mut CUcontext, dev: CUdevice) -> CUresult;
    #[link_name = "cuDevicePrimaryCtxRelease_v2"]
    fn cuDevicePrimaryCtxRelease(dev: CUdevice) -> CUresult;
    fn cuCtxSetCurrent(ctx: CUcontext) -> CUresult;
    fn cuCtxSynchronize() -> CUresult;
    fn cuGetErrorString(err: CUresult, out: *mut *const c_char) -> CUresult;
    // TRAP (found the hard way on the Thor, 2026-11-01): cuda.h silently
    // #defines a dozen driver entry points to their _v2 symbols. The legacy
    // plain symbols still exist in libcuda but reject a modern (primary /
    // v4) context with CUDA_ERROR_INVALID_CONTEXT (201) — while the C
    // headers, and any C shim, quietly bind the _v2 names and work. Every
    // _v2 link_name below is one of those remaps; do not "simplify" them.
    #[link_name = "cuMemAlloc_v2"]
    fn cuMemAlloc(ptr: *mut CUdeviceptr, bytes: usize) -> CUresult;
    #[link_name = "cuMemFree_v2"]
    fn cuMemFree(ptr: CUdeviceptr) -> CUresult;
    #[link_name = "cuMemAllocHost_v2"]
    fn cuMemAllocHost(ptr: *mut *mut c_void, bytes: usize) -> CUresult;
    fn cuMemFreeHost(ptr: *mut c_void) -> CUresult;
    #[link_name = "cuMemcpyHtoD_v2"]
    fn cuMemcpyHtoD(dst: CUdeviceptr, src: *const c_void, bytes: usize) -> CUresult;
    #[allow(dead_code)] // part of the FFI surface; spikes use the async form
    #[link_name = "cuMemcpyDtoH_v2"]
    fn cuMemcpyDtoH(dst: *mut c_void, src: CUdeviceptr, bytes: usize) -> CUresult;
    #[link_name = "cuMemcpyDtoHAsync_v2"]
    fn cuMemcpyDtoHAsync(
        dst: *mut c_void,
        src: CUdeviceptr,
        bytes: usize,
        stream: CUstream,
    ) -> CUresult;
    fn cuStreamCreate(stream: *mut CUstream, flags: u32) -> CUresult;
    #[link_name = "cuStreamDestroy_v2"]
    fn cuStreamDestroy(stream: CUstream) -> CUresult;
    fn cuModuleLoadData(module: *mut CUmodule, image: *const c_void) -> CUresult;
    fn cuModuleGetFunction(
        func: *mut CUfunction,
        module: CUmodule,
        name: *const c_char,
    ) -> CUresult;
    fn cuModuleUnload(module: CUmodule) -> CUresult;
    fn cuLaunchKernel(
        func: CUfunction,
        gx: u32,
        gy: u32,
        gz: u32,
        bx: u32,
        by: u32,
        bz: u32,
        shared: u32,
        stream: CUstream,
        args: *mut *mut c_void,
        extra: *mut *mut c_void,
    ) -> CUresult;
    fn cuEventCreate(event: *mut CUevent, flags: u32) -> CUresult;
    fn cuEventRecord(event: CUevent, stream: CUstream) -> CUresult;
    fn cuEventQuery(event: CUevent) -> CUresult;
    fn cuEventSynchronize(event: CUevent) -> CUresult;
    #[link_name = "cuEventDestroy_v2"]
    fn cuEventDestroy(event: CUevent) -> CUresult;
    #[link_name = "cuMemGetInfo_v2"]
    fn cuMemGetInfo(free: *mut usize, total: *mut usize) -> CUresult;

    fn nvrtcCreateProgram(
        prog: *mut NvrtcProgram,
        src: *const c_char,
        name: *const c_char,
        num_headers: i32,
        headers: *const *const c_char,
        include_names: *const *const c_char,
    ) -> NvrtcResult;
    fn nvrtcCompileProgram(
        prog: NvrtcProgram,
        num_options: i32,
        options: *const *const c_char,
    ) -> NvrtcResult;
    fn nvrtcGetProgramLogSize(prog: NvrtcProgram, size: *mut usize) -> NvrtcResult;
    fn nvrtcGetProgramLog(prog: NvrtcProgram, log: *mut c_char) -> NvrtcResult;
    fn nvrtcGetPTXSize(prog: NvrtcProgram, size: *mut usize) -> NvrtcResult;
    fn nvrtcGetPTX(prog: NvrtcProgram, ptx: *mut c_char) -> NvrtcResult;
    fn nvrtcGetCUBINSize(prog: NvrtcProgram, size: *mut usize) -> NvrtcResult;
    fn nvrtcGetCUBIN(prog: NvrtcProgram, cubin: *mut c_char) -> NvrtcResult;
    fn nvrtcDestroyProgram(prog: *mut NvrtcProgram) -> NvrtcResult;
    fn nvrtcGetErrorString(err: NvrtcResult) -> *const c_char;
    fn nvrtcVersion(major: *mut i32, minor: *mut i32) -> NvrtcResult;
}

// ------------------------------------------------------------------- errors
fn cu_err_string(code: CUresult) -> String {
    // SAFETY: `cuGetErrorString` writes a pointer to a static,
    // NUL-terminated string (or leaves it untouched on failure). The
    // pointer is null-checked before `CStr::from_ptr`, and the string
    // outlives the call (driver-owned static storage).
    unsafe {
        let mut p: *const c_char = std::ptr::null();
        if cuGetErrorString(code, &mut p) == CUDA_SUCCESS && !p.is_null() {
            return CStr::from_ptr(p).to_string_lossy().into_owned();
        }
        format!("CUresult {code}")
    }
}
fn nv_err_string(code: NvrtcResult) -> String {
    // SAFETY: `nvrtcGetErrorString` returns a pointer to a static,
    // NUL-terminated string; null-checked before `CStr::from_ptr`.
    unsafe {
        let p = nvrtcGetErrorString(code);
        if !p.is_null() {
            return CStr::from_ptr(p).to_string_lossy().into_owned();
        }
        format!("nvrtcResult {code}")
    }
}

/// `CString::new` without a panic path: kernel sources and names in
/// this crate are compile-time literals (NUL-free by inspection), but
/// a library function returns errors, it does not unwrap.
fn cstring(s: &str, what: &str) -> Result<CString, String> {
    CString::new(s).map_err(|_| format!("{what} contains an interior NUL byte"))
}
fn cu_check(code: CUresult, what: &str) -> Result<(), String> {
    if code == CUDA_SUCCESS {
        Ok(())
    } else {
        Err(format!("{what}: {} ({code})", cu_err_string(code)))
    }
}

/// Returns a human-readable probe of a driver result WITHOUT failing:
/// used for the known-wrong `sm_100` control, where an error (or a
/// surprising success) is itself the datum.
fn cu_outcome(code: CUresult) -> String {
    if code == CUDA_SUCCESS {
        "SUCCESS".to_string()
    } else {
        format!("error {} ({})", code, cu_err_string(code))
    }
}

// ------------------------------------------------------------------ context
/// An initialised driver, device 0's retained primary context (made
/// current), and one stream. `Drop` destroys the stream and releases
/// the context. Not `Sync`: the driver context is thread-affine, so
/// use one `Gpu` per thread.
pub struct Gpu {
    dev: CUdevice,
    stream: CUstream,
}

impl Gpu {
    /// Initialise the driver and retain device 0's primary context.
    pub fn new() -> Result<Gpu, String> {
        // SAFETY: each call is a driver entry point used per its
        // documented contract — out-parameters point at live locals,
        // every result is checked before the handle it produced is
        // used, and the retained primary context is released on every
        // failure path after the retain succeeds.
        unsafe {
            cu_check(cuInit(0), "cuInit")?;
            let mut dev: CUdevice = 0;
            cu_check(cuDeviceGet(&mut dev, 0), "cuDeviceGet")?;
            let mut ctx: CUcontext = std::ptr::null_mut();
            cu_check(
                cuDevicePrimaryCtxRetain(&mut ctx, dev),
                "cuDevicePrimaryCtxRetain",
            )?;
            if let Err(e) = cu_check(cuCtxSetCurrent(ctx), "cuCtxSetCurrent") {
                let _ = cuDevicePrimaryCtxRelease(dev);
                return Err(e);
            }
            let mut stream: CUstream = std::ptr::null_mut();
            let r = cuStreamCreate(&mut stream, 0);
            if r != CUDA_SUCCESS {
                let _ = cuDevicePrimaryCtxRelease(dev);
                return Err(format!("cuStreamCreate: {}", cu_err_string(r)));
            }
            Ok(Gpu { dev, stream })
        }
    }

    /// The raw stream handle, for the FFI calls in this module that
    /// take one ([`Module::launch`], [`Event::record`]).
    pub fn stream(&self) -> CUstream {
        self.stream
    }

    /// `(free, total)` device memory in bytes, per `cuMemGetInfo`.
    pub fn mem_info(&self) -> Result<(usize, usize), String> {
        // SAFETY: both out-parameters point at live locals; the result
        // is checked before they are read.
        unsafe {
            let (mut free, mut total) = (0usize, 0usize);
            cu_check(cuMemGetInfo(&mut free, &mut total), "cuMemGetInfo")?;
            Ok((free, total))
        }
    }

    /// Block until the current context's work completes.
    pub fn sync(&self) -> Result<(), String> {
        // SAFETY: `cuCtxSynchronize` takes no pointers; a context is
        // current on this thread by construction (`Gpu::new`).
        unsafe { cu_check(cuCtxSynchronize(), "cuCtxSynchronize") }
    }
}

impl Drop for Gpu {
    fn drop(&mut self) {
        // SAFETY: `self.stream` and the retained primary context for
        // `self.dev` were created by `Gpu::new` and are released
        // exactly once, here. Errors are ignored deliberately: there
        // is no recovery available during drop.
        unsafe {
            let _ = cuStreamDestroy(self.stream);
            let _ = cuCtxSynchronize();
            let _ = cuDevicePrimaryCtxRelease(self.dev);
        }
    }
}

// -------------------------------------------------------------- device bufs
/// A device allocation of the stored byte size, freed on `Drop`.
pub struct DevBuf(CUdeviceptr, usize);
impl DevBuf {
    /// Allocate `bytes` of device memory.
    pub fn new(bytes: usize) -> Result<DevBuf, String> {
        // SAFETY: the out-parameter points at a live local; the result
        // is checked before the pointer it produced is stored.
        unsafe {
            let mut p: CUdeviceptr = 0;
            cu_check(cuMemAlloc(&mut p, bytes), "cuMemAlloc")?;
            Ok(DevBuf(p, bytes))
        }
    }

    /// Copy `data` into the allocation, synchronously.
    ///
    /// The slice must fill the buffer *exactly* (`data.len() * 4 ==
    /// bytes`). This is a hard check returning `Err`, not a
    /// `debug_assert`: this is a safe function, and in a release
    /// build a debug-only check would let a short slice through to
    /// `cuMemcpyHtoD`, which would copy the buffer's full byte count
    /// out of a smaller host allocation — an out-of-bounds read
    /// behind a safe signature.
    pub fn upload(&self, data: &[f32]) -> Result<(), String> {
        match data.len().checked_mul(4) {
            Some(b) if b == self.1 => {}
            _ => {
                return Err(format!(
                    "upload length mismatch: {} f32 elements for a {} B device buffer",
                    data.len(),
                    self.1
                ))
            }
        }
        // SAFETY: `self.0` is a live allocation of `self.1` bytes, and
        // the check above proves `data` is exactly `self.1` bytes, so
        // the copy is in-bounds on both sides.
        unsafe {
            cu_check(
                cuMemcpyHtoD(self.0, data.as_ptr() as *const c_void, self.1),
                "cuMemcpyHtoD",
            )
        }
    }

    /// The raw device pointer, for kernel arguments.
    pub fn ptr(&self) -> CUdeviceptr {
        self.0
    }
}
impl Drop for DevBuf {
    fn drop(&mut self) {
        // SAFETY: `self.0` came from `cuMemAlloc` in `DevBuf::new` and
        // is freed exactly once, here.
        unsafe {
            let _ = cuMemFree(self.0);
        }
    }
}

/// A pinned (page-locked) host allocation of the stored byte size,
/// freed on `Drop`. Pinned memory is what the async copy APIs can
/// actually stream against without staging.
pub struct PinnedBuf(*mut c_void, usize);
impl PinnedBuf {
    /// Allocate `bytes` of pinned host memory.
    pub fn new(bytes: usize) -> Result<PinnedBuf, String> {
        // SAFETY: the out-parameter points at a live local; the result
        // is checked before the pointer it produced is stored.
        unsafe {
            let mut p: *mut c_void = std::ptr::null_mut();
            cu_check(cuMemAllocHost(&mut p, bytes), "cuMemAllocHost")?;
            Ok(PinnedBuf(p, bytes))
        }
    }

    /// The allocation viewed as `f32`s (`bytes / 4` elements; a
    /// trailing partial element is not exposed). Aliasing caveat:
    /// while this slice is alive, do not write through
    /// [`Self::as_mut_ptr`] — the raw-pointer copy path is for the
    /// caller to sequence *between* borrows, as the spikes do
    /// (copy, synchronise, then read).
    pub fn as_f32_slice(&self) -> &[f32] {
        // SAFETY: `self.0` is a live allocation of `self.1` bytes,
        // owned by `self`, so it outlives the returned borrow. Pinned
        // host allocations from the driver are aligned for any
        // fundamental type (certainly `f32`), and `self.1 / 4`
        // elements span at most `self.1` bytes.
        unsafe { std::slice::from_raw_parts(self.0 as *const f32, self.1 / 4) }
    }

    /// The raw pointer, for the async copy APIs.
    pub fn as_mut_ptr(&self) -> *mut c_void {
        self.0
    }
}
impl Drop for PinnedBuf {
    fn drop(&mut self) {
        // SAFETY: `self.0` came from `cuMemAllocHost` in
        // `PinnedBuf::new` and is freed exactly once, here.
        unsafe {
            let _ = cuMemFreeHost(self.0);
        }
    }
}

// ------------------------------------------------------------------- events
/// A driver event, destroyed on `Drop`. Spike 3's retirement rule is
/// built on these: an event is recorded after an epoch's last launch,
/// and the epoch's module is unloaded only after the event reports
/// completion.
pub struct Event(CUevent);
impl Event {
    /// Create an event in the current context.
    pub fn new() -> Result<Event, String> {
        // SAFETY: the out-parameter points at a live local; the result
        // is checked before the handle it produced is stored.
        unsafe {
            let mut e: CUevent = std::ptr::null_mut();
            cu_check(cuEventCreate(&mut e, 0), "cuEventCreate")?;
            Ok(Event(e))
        }
    }

    /// Record the event on `stream`.
    ///
    /// # Safety
    /// `stream` must be a valid stream in the current context (e.g.
    /// [`Gpu::stream`]). This is an `unsafe fn`, not a safe one with
    /// an unchecked pointer argument (clippy's
    /// `not_unsafe_ptr_arg_deref` is a deny-level lint for a reason):
    /// the driver dereferences the handle, and nothing on this side
    /// can validate it.
    pub unsafe fn record(&self, stream: CUstream) -> Result<(), String> {
        // SAFETY: `self.0` is a live event from `Event::new`; `stream`
        // is valid by the caller contract above.
        cu_check(cuEventRecord(self.0, stream), "cuEventRecord")
    }

    /// Raw query code: 0 = complete, 600 = not ready, else an error.
    pub fn query(&self) -> CUresult {
        // SAFETY: `self.0` is a live event from `Event::new`; the call
        // takes the handle by value and writes nothing through it.
        unsafe { cuEventQuery(self.0) }
    }

    /// Block until the event's recorded work completes.
    pub fn synchronize(&self) -> Result<(), String> {
        // SAFETY: `self.0` is a live event from `Event::new`.
        unsafe { cu_check(cuEventSynchronize(self.0), "cuEventSynchronize") }
    }
}
impl Drop for Event {
    fn drop(&mut self) {
        // SAFETY: `self.0` came from `cuEventCreate` in `Event::new`
        // and is destroyed exactly once, here.
        unsafe {
            let _ = cuEventDestroy(self.0);
        }
    }
}

// ------------------------------------------------------------------- nvrtc
/// The result of one NVRTC compilation.
pub struct Compiled {
    /// PTX (NUL-terminated text) or CUBIN (binary), per the request.
    pub image: Vec<u8>,
    /// Wall time of the NVRTC compile call.
    pub compile_time: Duration,
    /// The compiler log, trimmed (empty for a clean compile).
    pub log: String,
}

fn nvrtc_compile(source: &str, arch_flag: &str, want_cubin: bool) -> Result<Compiled, String> {
    // No unwraps: these strings are crate-internal literals today,
    // but a library function returns its failures as errors.
    let src = cstring(source, "kernel source")?;
    let name = cstring("perceive.cu", "program name")?;
    let opt = cstring(&format!("-arch={arch_flag}"), "arch option")?;
    let opts: [*const c_char; 1] = [opt.as_ptr()];
    // SAFETY: for the whole block — `prog` is an out-parameter
    // pointing at a live local; `src`/`name`/`opts` are live
    // `CString`s for the duration of each call; the log and image
    // buffers are sized from the driver's own reported sizes before
    // being filled; the program is destroyed exactly once on every
    // path out of the block (each error return destroys it first).
    unsafe {
        let t0 = Instant::now();
        let mut prog: NvrtcProgram = std::ptr::null_mut();
        let r = nvrtcCreateProgram(
            &mut prog,
            src.as_ptr(),
            name.as_ptr(),
            0,
            std::ptr::null(),
            std::ptr::null(),
        );
        if r != 0 {
            return Err(format!("nvrtcCreateProgram: {}", nv_err_string(r)));
        }
        let cr = nvrtcCompileProgram(prog, 1, opts.as_ptr());
        let mut logsz = 0usize;
        let _ = nvrtcGetProgramLogSize(prog, &mut logsz);
        let mut log = String::new();
        if logsz > 1 {
            let mut buf = vec![0u8; logsz];
            let _ = nvrtcGetProgramLog(prog, buf.as_mut_ptr() as *mut c_char);
            log = String::from_utf8_lossy(&buf)
                .trim_end_matches('\0')
                .trim()
                .to_string();
        }
        if cr != 0 {
            let _ = nvrtcDestroyProgram(&mut prog);
            return Err(format!(
                "nvrtcCompileProgram(-arch={arch_flag}): {} ({cr}) log: {log}",
                nv_err_string(cr)
            ));
        }
        let mut image: Vec<u8>;
        if want_cubin {
            let mut sz = 0usize;
            let r = nvrtcGetCUBINSize(prog, &mut sz);
            if r != 0 {
                let _ = nvrtcDestroyProgram(&mut prog);
                return Err(format!("nvrtcGetCUBINSize: {}", nv_err_string(r)));
            }
            image = vec![0u8; sz];
            let r = nvrtcGetCUBIN(prog, image.as_mut_ptr() as *mut c_char);
            if r != 0 {
                let _ = nvrtcDestroyProgram(&mut prog);
                return Err(format!("nvrtcGetCUBIN: {}", nv_err_string(r)));
            }
        } else {
            let mut sz = 0usize;
            let r = nvrtcGetPTXSize(prog, &mut sz);
            if r != 0 {
                let _ = nvrtcDestroyProgram(&mut prog);
                return Err(format!("nvrtcGetPTXSize: {}", nv_err_string(r)));
            }
            image = vec![0u8; sz];
            let r = nvrtcGetPTX(prog, image.as_mut_ptr() as *mut c_char);
            if r != 0 {
                let _ = nvrtcDestroyProgram(&mut prog);
                return Err(format!("nvrtcGetPTX: {}", nv_err_string(r)));
            }
            if *image.last().unwrap_or(&1) != 0 {
                image.push(0);
            }
        }
        let dt = t0.elapsed();
        let _ = nvrtcDestroyProgram(&mut prog);
        Ok(Compiled {
            image,
            compile_time: dt,
            log,
        })
    }
}

/// The linked NVRTC's `(major, minor)` version.
pub fn nvrtc_version() -> (i32, i32) {
    // SAFETY: both out-parameters point at live locals; a failed call
    // leaves the zeros, which the caller reports as-is.
    unsafe {
        let (mut a, mut b) = (0, 0);
        let _ = nvrtcVersion(&mut a, &mut b);
        (a, b)
    }
}

// ------------------------------------------------------------------ modules
/// A loaded module and its `perceive` function handle. There is no
/// `Drop` impl on purpose: unloading is an explicit, error-returning
/// act ([`Module::unload`], consuming) because spike 3's retirement
/// rule needs to *know* when an unload happened relative to its
/// event. Forgetting to unload leaks the module until context
/// teardown — visible in `cuMemGetInfo`, which spike 3 accounts.
pub struct Module {
    module: CUmodule,
    func: CUfunction,
    /// Wall time of the `cuModuleLoadData` call.
    pub load_time: Duration,
}

impl Module {
    /// Load a PTX or CUBIN image and resolve its `perceive` kernel.
    pub fn load(image: &[u8]) -> Result<Module, String> {
        // No unwrap on the kernel name either (see `cstring`).
        let fname = cstring("perceive", "kernel name")?;
        // SAFETY: the out-parameters point at live locals; `image`
        // outlives the load call; if function resolution fails the
        // just-loaded module is unloaded before returning, so no
        // handle leaks on the error path.
        unsafe {
            let t0 = Instant::now();
            let mut module: CUmodule = std::ptr::null_mut();
            cu_check(
                cuModuleLoadData(&mut module, image.as_ptr() as *const c_void),
                "cuModuleLoadData",
            )?;
            let dt = t0.elapsed();
            let mut func: CUfunction = std::ptr::null_mut();
            if let Err(e) = cu_check(
                cuModuleGetFunction(&mut func, module, fname.as_ptr()),
                "cuModuleGetFunction",
            ) {
                let _ = cuModuleUnload(module);
                return Err(e);
            }
            Ok(Module {
                module,
                func,
                load_time: dt,
            })
        }
    }

    /// Attempt a load and report the raw driver outcome — control-path only.
    pub fn try_load_outcome(image: &[u8]) -> String {
        // SAFETY: same contract as `Module::load`; a successful
        // control load is unloaded immediately so the control leaves
        // no state behind.
        unsafe {
            let mut module: CUmodule = std::ptr::null_mut();
            let r = cuModuleLoadData(&mut module, image.as_ptr() as *const c_void);
            if r == CUDA_SUCCESS {
                let _ = cuModuleUnload(module);
            }
            cu_outcome(r)
        }
    }

    /// Launch `perceive` over `n` elements: `din` -> `dout`.
    ///
    /// The size relationship a caller could get wrong is checked, not
    /// assumed: `n` must be positive and `4 * n` must fit *both*
    /// buffers — before this check existed, an oversized `n` in a
    /// safe-looking call would have the kernel write past the output
    /// allocation on the device.
    ///
    /// # Safety
    /// `stream` must be a valid stream in the current context (e.g.
    /// [`Gpu::stream`]), and this module must not be unloaded until
    /// the launched work has completed on that stream.
    pub unsafe fn launch(
        &self,
        stream: CUstream,
        din: &DevBuf,
        dout: &DevBuf,
        n: i32,
    ) -> Result<(), String> {
        if n <= 0 {
            return Err(format!("launch n must be positive, got {n}"));
        }
        // n <= i32::MAX, so this cannot overflow usize on a 64-bit host.
        let need = (n as usize) * 4;
        if need > din.1 || need > dout.1 {
            return Err(format!(
                "launch n={n} needs {need} B; buffers are {} B in / {} B out",
                din.1, dout.1
            ));
        }
        let mut dptr_in = din.ptr();
        let mut dptr_out = dout.ptr();
        let mut nn = n;
        let mut args: [*mut c_void; 3] = [
            &mut dptr_in as *mut CUdeviceptr as *mut c_void,
            &mut dptr_out as *mut CUdeviceptr as *mut c_void,
            &mut nn as *mut i32 as *mut c_void,
        ];
        let grid = (n as u32).div_ceil(256);
        // SAFETY: `self.func` is a live function handle from
        // `Module::load`; the argument array points at the three
        // locals above, which outlive the (synchronous, enqueue-only)
        // driver call — the driver copies the argument values at
        // launch. Buffer extents were validated against `n` above,
        // and `stream` is valid by the caller contract.
        cu_check(
            cuLaunchKernel(
                self.func,
                grid,
                1,
                1,
                256,
                1,
                1,
                0,
                stream,
                args.as_mut_ptr(),
                std::ptr::null_mut(),
            ),
            "cuLaunchKernel",
        )
    }

    /// Unload the module, consuming it — call only once the module's
    /// last launch has completed (spike 3's retirement rule).
    pub fn unload(self) -> Result<(), String> {
        // SAFETY: `self.module` came from `cuModuleLoadData` in
        // `Module::load`; consuming `self` makes a second unload
        // unrepresentable.
        unsafe { cu_check(cuModuleUnload(self.module), "cuModuleUnload") }
    }
}

// ------------------------------------------------------------------ spike 1
/// Spike 1's measurements and control outcomes (see [`spike1`]).
pub struct Spike1Report {
    /// Linked NVRTC `(major, minor)`.
    pub nvrtc_version: (i32, i32),
    /// Compile time for `-arch=compute_110`, milliseconds.
    pub compile_110_ms: f64,
    /// Size of the `compute_110` PTX image, bytes.
    pub ptx_bytes: usize,
    /// `cuModuleLoadData` time for the PTX image, milliseconds.
    pub load_110_ms: f64,
    /// Observed max abs error, GPU output vs CPU reference.
    pub max_err: f32,
    /// Whether `max_err <= TOL`.
    pub ok_within_tol: bool,
    // Known-wrong controls (the email's sm_100 family):
    /// Control: compiling PTX for `compute_100` — raw outcome text.
    pub control_compute100_ptx_compile: String,
    /// Control: loading + running the `compute_100` PTX — raw outcome text.
    pub control_compute100_ptx_load_and_run: String,
    /// Control: compiling a native `sm_100` CUBIN — raw outcome text.
    pub control_sm100_cubin_compile: String,
    /// Control: loading the `sm_100` CUBIN on the sm_110 device — raw outcome text.
    pub control_sm100_cubin_load: String,
}

/// Spike 1 (PLAN §6): NVRTC compile of the perceive filter for
/// `compute_110`, driver-load, launch, compare against the CPU reference.
/// Controls: what the driver actually does with the email's `sm_100`.
pub fn spike1() -> Result<Spike1Report, String> {
    let gpu = Gpu::new()?;
    let n = 1usize << 16;
    let input = test_input(n);
    let expected = reference(Variant::A, &input);
    let din = DevBuf::new(n * 4)?;
    let dout = DevBuf::new(n * 4)?;
    din.upload(&input)?;
    let host_out = PinnedBuf::new(n * 4)?;

    // Main path: PTX for compute_110.
    let compiled = nvrtc_compile(Variant::A.source(), "compute_110", false)?;
    let ptx_bytes = compiled.image.len();
    let module = Module::load(&compiled.image)?;
    let load_110_ms = module.load_time.as_secs_f64() * 1e3;
    // SAFETY: the stream is the live `Gpu`'s; the module is not
    // unloaded until after `gpu.sync()` below; both buffers are
    // `n * 4` bytes (which `launch` also re-validates itself).
    unsafe { module.launch(gpu.stream(), &din, &dout, n as i32)? };
    // SAFETY: `host_out` is a live `PinnedBuf` of `n * 4` bytes and
    // `dout` a live `DevBuf` of `n * 4` bytes, so the async copy is
    // in-bounds on both sides; `gpu.sync()` completes it before the
    // readback below.
    unsafe {
        cu_check(
            cuMemcpyDtoHAsync(host_out.as_mut_ptr(), dout.ptr(), n * 4, gpu.stream()),
            "cuMemcpyDtoHAsync",
        )?;
    }
    gpu.sync()?;
    let got = host_out.as_f32_slice().to_vec();
    let max_err = max_abs_err(&got, &expected);
    module.unload()?;

    // Control 1: PTX for compute_100 (an sm_100-family *virtual* arch).
    let c_ptx_compile: String;
    let c_ptx_run: String;
    match nvrtc_compile(Variant::A.source(), "compute_100", false) {
        Ok(c) => {
            c_ptx_compile = format!("compiled OK ({} B PTX)", c.image.len());
            match Module::load(&c.image) {
                Ok(m) => {
                    let ran: String;
                    // SAFETY: same conditions as the main-path launch
                    // above (live stream, loaded module, n*4 buffers).
                    match unsafe { m.launch(gpu.stream(), &din, &dout, n as i32) } {
                        Ok(()) => match gpu.sync() {
                            Ok(()) => {
                                // SAFETY: control readback — same
                                // in-bounds argument as the main path;
                                // the result is intentionally ignored
                                // (a control outcome is reported, not
                                // propagated).
                                unsafe {
                                    let _ = cuMemcpyDtoHAsync(
                                        host_out.as_mut_ptr(),
                                        dout.ptr(),
                                        n * 4,
                                        gpu.stream(),
                                    );
                                }
                                let _ = gpu.sync();
                                let e = max_abs_err(host_out.as_f32_slice(), &expected);
                                ran = format!("loaded+ran OK, max_err vs reference = {e:.3e} (PTX is forward-compatible: the driver JITs it for sm_110; sm_100 is a wrong *target choice*, not a fatal one, on the PTX path)");
                            }
                            Err(e) => ran = format!("loaded, sync failed: {e}"),
                        },
                        Err(e) => ran = format!("loaded, launch failed: {e}"),
                    }
                    let _ = m.unload();
                    c_ptx_run = ran;
                }
                Err(e) => c_ptx_run = format!("load failed: {e}"),
            }
        }
        Err(e) => {
            c_ptx_compile = format!("compile failed: {e}");
            c_ptx_run = "not attempted (no PTX)".to_string();
        }
    }

    // Control 2: native CUBIN for sm_100 — a binary for the wrong device.
    let c_cubin_compile: String;
    let c_cubin_load: String;
    match nvrtc_compile(Variant::A.source(), "sm_100", true) {
        Ok(c) => {
            c_cubin_compile = format!("compiled OK ({} B CUBIN)", c.image.len());
            c_cubin_load = Module::try_load_outcome(&c.image);
        }
        Err(e) => {
            c_cubin_compile = format!("compile failed: {e}");
            c_cubin_load = "not attempted (no CUBIN)".to_string();
        }
    }

    Ok(Spike1Report {
        nvrtc_version: nvrtc_version(),
        compile_110_ms: compiled.compile_time.as_secs_f64() * 1e3,
        ptx_bytes,
        load_110_ms,
        max_err,
        ok_within_tol: max_err <= TOL,
        control_compute100_ptx_compile: c_ptx_compile,
        control_compute100_ptx_load_and_run: c_ptx_run,
        control_sm100_cubin_compile: c_cubin_compile,
        control_sm100_cubin_load: c_cubin_load,
    })
}

// ------------------------------------------------------------------ spike 3
/// Spike 3's measurements (see [`spike3`]).
pub struct Spike3Report {
    /// Module swaps performed (one epoch each).
    pub swaps: usize,
    /// Kernel launches per epoch.
    pub launches_per_epoch: usize,
    /// Epochs whose readback was compared against the CPU reference.
    pub epochs_verified: usize,
    /// Worst max-abs-error across all verified epochs.
    pub max_err: f32,
    /// Whether every verified epoch was within `TOL`.
    pub all_within_tol: bool,
    /// One-time compile time per variant (A, B), milliseconds.
    pub compile_ms_per_variant: (f64, f64),
    /// Mean `cuModuleLoadData` time across the swap loop, milliseconds.
    pub mean_load_ms: f64,
    /// Modules retired (unloaded after their event synchronised).
    pub retirements: usize,
    /// Retirements whose event had *already* completed at the
    /// retirement check (the rest had to wait in `synchronize`).
    pub retirements_where_event_already_done: usize,
    /// `cuMemGetInfo` free bytes before the swap loop.
    pub free_before_bytes: usize,
    /// `cuMemGetInfo` free bytes after the loop and all retirements.
    pub free_after_bytes: usize,
    /// free_after - free_before (negative would suggest a leak; noise band
    /// is whatever the driver does with its own caches — reported raw).
    pub free_delta_bytes: i64,
    /// Total wall time of the spike.
    pub wall: Duration,
}

/// One live epoch: a loaded module plus the event recorded after its last
/// launch. It may only be unloaded via [`Swapper::retire_oldest`].
struct Epoch {
    module: Option<Module>,
    event: Event,
    variant: Variant,
}

/// Spike 3 (PLAN §6): 1,000 host-side module swaps at launch boundaries,
/// alternating kernel variants A/B, under load (multiple launches per
/// epoch), every epoch's output verified against the CPU reference, retired
/// modules unloaded only after their completion event has synchronised.
pub fn spike3(swaps: usize) -> Result<Spike3Report, String> {
    let t_start = Instant::now();
    let gpu = Gpu::new()?;
    let n = 1usize << 16;
    let launches_per_epoch = 4usize;
    let input = test_input(n);
    let expected = [reference(Variant::A, &input), reference(Variant::B, &input)];
    let din = DevBuf::new(n * 4)?;
    let dout = DevBuf::new(n * 4)?;
    din.upload(&input)?;
    let host_out = PinnedBuf::new(n * 4)?;

    // Compile both variants ONCE as native sm_110 CUBINs: spike 3 tests the
    // swap/retirement machinery, not the compiler. (CUBIN loads are also
    // the honest swap currency on a fixed box — a PTX load re-JITs every
    // time; that cost is spike 1's number, not hidden here.)
    let cub_a = nvrtc_compile(Variant::A.source(), "sm_110", true)?;
    let cub_b = nvrtc_compile(Variant::B.source(), "sm_110", true)?;
    let compile_ms = (
        cub_a.compile_time.as_secs_f64() * 1e3,
        cub_b.compile_time.as_secs_f64() * 1e3,
    );

    // Baseline AFTER context + buffers exist, BEFORE the swap loop.
    gpu.sync()?;
    let (free_before, _) = gpu.mem_info()?;

    let mut load_time_total = Duration::ZERO;
    let mut live: Vec<Epoch> = Vec::new(); // at most 2: current + retiring
    let mut retirements = 0usize;
    let mut retirements_already_done = 0usize;
    let mut verified = 0usize;
    let mut worst_err = 0.0f32;
    let mut all_ok = true;

    for i in 0..swaps {
        let variant = if i % 2 == 0 { Variant::A } else { Variant::B };
        let image = if i % 2 == 0 {
            &cub_a.image
        } else {
            &cub_b.image
        };
        let module = Module::load(image)?;
        load_time_total += module.load_time;
        for _ in 0..launches_per_epoch {
            // SAFETY: the stream is the live `Gpu`'s; this epoch's
            // module is unloaded only in the retirement path below,
            // after its event synchronises — so it outlives all work
            // launched here. Buffers are `n * 4` bytes (re-validated
            // inside `launch`).
            unsafe { module.launch(gpu.stream(), &din, &dout, n as i32)? };
        }
        let event = Event::new()?;
        // SAFETY: the stream is the live `Gpu`'s and the event was
        // just created in this context.
        unsafe { event.record(gpu.stream())? };
        live.push(Epoch {
            module: Some(module),
            event,
            variant,
        });

        // Verify the epoch we just launched (async copy + event sync).
        // SAFETY: `host_out` is a live `PinnedBuf` of `n * 4` bytes
        // and `dout` a live `DevBuf` of `n * 4` bytes; `gpu.sync()`
        // below completes the copy before the readback.
        unsafe {
            cu_check(
                cuMemcpyDtoHAsync(host_out.as_mut_ptr(), dout.ptr(), n * 4, gpu.stream()),
                "cuMemcpyDtoHAsync",
            )?;
        }
        // The copy was queued after this epoch's launches on the same
        // stream; sync the context to know it landed. (This also completes
        // the epoch's event, which the retirement below will observe.)
        gpu.sync()?;
        let exp = &expected[i % 2];
        let err = max_abs_err(host_out.as_f32_slice(), exp);
        if err > worst_err {
            worst_err = err;
        }
        if err > TOL {
            all_ok = false;
        }
        verified += 1;

        // Retire the OLDEST epoch once we hold more than one: event first,
        // unload only after it reports completion. Never the reverse.
        while live.len() > 1 {
            let epoch = live.remove(0);
            let q = epoch.event.query();
            if q == CUDA_SUCCESS {
                retirements_already_done += 1;
            }
            epoch.event.synchronize()?; // hard gate: no unload before this returns
                                        // Structural invariant, stated rather than unwrapped
                                        // silently: an epoch's module is `Some` from the push in
                                        // this loop until exactly this retirement takes it. The
                                        // expect can only fire if a future edit breaks that
                                        // structure — in which case failing loudly is correct.
            let module = epoch
                .module
                .expect("epoch holds its module from push to retirement");
            module.unload()?;
            retirements += 1;
            let _ = epoch.variant;
        }
    }
    // Retire the final epoch the same way.
    for epoch in live.drain(..) {
        epoch.event.synchronize()?;
        epoch
            .module
            .expect("epoch holds its module from push to retirement")
            .unload()?;
        retirements += 1;
    }

    gpu.sync()?;
    let (free_after, _) = gpu.mem_info()?;
    Ok(Spike3Report {
        swaps,
        launches_per_epoch,
        epochs_verified: verified,
        max_err: worst_err,
        all_within_tol: all_ok,
        compile_ms_per_variant: compile_ms,
        mean_load_ms: load_time_total.as_secs_f64() * 1e3 / swaps.max(1) as f64,
        retirements,
        retirements_where_event_already_done: retirements_already_done,
        free_before_bytes: free_before,
        free_after_bytes: free_after,
        free_delta_bytes: free_after as i64 - free_before as i64,
        wall: t_start.elapsed(),
    })
}
