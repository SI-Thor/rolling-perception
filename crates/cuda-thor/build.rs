//! Links libcuda + libnvrtc ONLY when the `cuda-thor` feature is on.
//! Thor-only: paths are the JetPack / CUDA 13.2 layout verified on the box
//! (docs/FEASIBILITY.md). On any other machine, build without the feature.
fn main() {
    println!("cargo:rerun-if-env-changed=CARGO_FEATURE_CUDA_THOR");
    if std::env::var_os("CARGO_FEATURE_CUDA_THOR").is_some() {
        // libcuda lives in the system lib dir on the Thor; libnvrtc in the
        // CUDA target lib dir. rpath is baked so binaries run without
        // LD_LIBRARY_PATH gymnastics.
        for dir in [
            "/usr/lib/aarch64-linux-gnu",
            "/usr/local/cuda/targets/sbsa-linux/lib",
            "/usr/local/cuda/lib64",
        ] {
            println!("cargo:rustc-link-search=native={dir}");
            println!("cargo:rustc-link-arg=-Wl,-rpath,{dir}");
        }
        println!("cargo:rustc-link-lib=dylib=cuda");
        println!("cargo:rustc-link-lib=dylib=nvrtc");
    }
}
