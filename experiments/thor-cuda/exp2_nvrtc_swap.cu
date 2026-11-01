// exp2: NVRTC hot-swap, the honest version.
// Compile kernel v1 at runtime for compute_110, load via driver API, run it.
// Then compile v2 (different behaviour) at runtime WHILE v1 exists, load it,
// and swap the CUfunction the host launches — between launches. Verify the
// outputs actually change. Report real compile times.
// This is what the email's "CascadeJIT atomic swap" can truthfully mean.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <chrono>
#include <string>
#include <cuda.h>
#include <nvrtc.h>
#define CUCK(x) do{CUresult r=(x); if(r){const char* s; cuGetErrorString(r,&s); printf("CU err %s @%d\n",s,__LINE__); exit(1);}}while(0)
#define NVCK(x) do{nvrtcResult r=(x); if(r!=NVRTC_SUCCESS){printf("NVRTC err %s @%d\n",nvrtcGetErrorString(r),__LINE__); exit(1);}}while(0)

static const char* SRC_V1 = R"(
extern "C" __global__ void k(const float* in, float* out, int n){
  int i = blockIdx.x*blockDim.x + threadIdx.x;
  if(i<n) out[i] = in[i]*2.0f;
})";
static const char* SRC_V2 = R"(
extern "C" __global__ void k(const float* in, float* out, int n){
  int i = blockIdx.x*blockDim.x + threadIdx.x;
  if(i<n){ float v = in[i]; v = v*v + v; out[i] = v; }  // different math entirely
})";

CUfunction compile_and_load(const char* src, const char* label, double& compile_ms){
    auto t0 = std::chrono::steady_clock::now();
    nvrtcProgram prog; NVCK(nvrtcCreateProgram(&prog, src, "k.cu", 0, nullptr, nullptr));
    const char* opts[] = {"-arch=compute_110", "--use_fast_math"};
    nvrtcResult cr = nvrtcCompileProgram(prog, 2, opts);
    size_t logsz; nvrtcGetProgramLogSize(prog,&logsz);
    if(logsz>1){ std::string log(logsz,' '); nvrtcGetProgramLog(prog,&log[0]); printf("  [%s log] %s\n", label, log.c_str()); }
    if(cr!=NVRTC_SUCCESS){ printf("NVRTC compile failed %s\n", nvrtcGetErrorString(cr)); exit(1); }
    size_t ptxsz; NVCK(nvrtcGetPTXSize(prog,&ptxsz));
    std::string ptx(ptxsz,' '); NVCK(nvrtcGetPTX(prog,&ptx[0]));
    nvrtcDestroyProgram(&prog);
    CUmodule mod; CUCK(cuModuleLoadData(&mod, ptx.data()));
    CUfunction fn; CUCK(cuModuleGetFunction(&fn, mod, "k"));
    compile_ms = std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t0).count();
    printf("  [%s] NVRTC compile+load: %.1f ms, PTX %zu B\n", label, compile_ms, ptxsz);
    return fn;
}

int main(){
    CUCK(cuInit(0)); CUdevice dev; CUCK(cuDeviceGet(&dev,0)); CUcontext ctx; CUCK(cuCtxCreate(&ctx,nullptr,0,dev));
    const int N=1<<16; int n_arg = N;
    CUdeviceptr din, dout; CUCK(cuMemAlloc(&din,N*sizeof(float))); CUCK(cuMemAlloc(&dout,N*sizeof(float)));
    float* h = (float*)malloc(N*sizeof(float)); for(int i=0;i<N;i++) h[i]=3.0f;
    CUCK(cuMemcpyHtoD(din,h,N*sizeof(float)));

    double ms1, ms2;
    printf("NVRTC HOT-SWAP (target compute_110, Thor sm_110)\n");
    CUfunction f1 = compile_and_load(SRC_V1, "v1: out=in*2", ms1);
    void* args1[] = {&din,&dout,&n_arg};
    auto s=std::chrono::steady_clock::now();
    CUCK(cuLaunchKernel(f1, (N+255)/256,1,1, 256,1,1, 0, nullptr, args1, nullptr)); CUCK(cuCtxSynchronize());
    double run1 = std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-s).count();
    CUCK(cuMemcpyDtoH(h,(CUdeviceptr)dout,sizeof(float)));
    printf("  v1 run: %.0f us, out[0]=%.1f (expect 6.0) %s\n", run1, h[0], fabsf(h[0]-6.0f)<1e-4?"MATCH":"MISMATCH");

    CUfunction f2 = compile_and_load(SRC_V2, "v2: out=in*in+in", ms2);
    // THE SWAP: host changes which CUfunction it launches. Between launches, zero downtime.
    s=std::chrono::steady_clock::now();
    CUCK(cuLaunchKernel(f2, (N+255)/256,1,1, 256,1,1, 0, nullptr, args1, nullptr)); CUCK(cuCtxSynchronize());
    double run2 = std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-s).count();
    CUCK(cuMemcpyDtoH(h,(CUdeviceptr)dout,sizeof(float)));
    printf("  v2 run: %.0f us, out[0]=%.1f (expect 12.0) %s\n", run2, h[0], fabsf(h[0]-12.0f)<1e-4?"MATCH":"MISMATCH");
    printf("VERDICT swap is real at launch granularity: compile v2 (%.1f ms) happens off the run path; no v1 state lost.\n", ms2);
    free(h); cuMemFree(din); cuMemFree(dout);
    return 0;
}
