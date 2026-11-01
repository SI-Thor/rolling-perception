// exp1: Rolling (phase-interleaved) vs Batched perception on the GPU.
// Same lanes, same work, same arrival pattern. Only the scheduling differs.
// Arrivals are modelled with a host sleep = sensor period (labelled, not compute).
// Measured with CUDA events / host clock: time-to-first-output, per-output times.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <thread>
#include <chrono>
#include <vector>
#include <cuda_runtime.h>
#define CK(x) do{cudaError_t e=(x); if(e){printf("CUDA err %s @%d\n",cudaGetErrorString(e),__LINE__); exit(1);}}while(0)

__global__ void lane_work(const float* __restrict__ in, float* __restrict__ out, int n, int reps){
    int i = blockIdx.x*blockDim.x + threadIdx.x;
    if(i>=n) return;
    float v = in[i];
    for(int r=0;r<reps;r++) v = v*1.000001f + 0.0000001f;
    out[i]=v;
}

int main(int argc,char**argv){
    const int LANES=4;
    const int N=1<<20;          // per lane
    const int REPS=60;          // compute per element
    const int STAGGER_MS=5;     // modelled sensor period between lane arrivals
    float *din[LANES], *dout[LANES];
    cudaStream_t st[LANES];
    for(int l=0;l<LANES;l++){
        CK(cudaMalloc(&din[l], N*sizeof(float))); CK(cudaMalloc(&dout[l], N*sizeof(float)));
        CK(cudaMemset(din[l], 0x3f, N*sizeof(float))); // ~0.75-ish bit pattern, finite
        CK(cudaStreamCreate(&st[l]));
    }
    dim3 grid((N+255)/256), block(256);
    auto t0 = std::chrono::steady_clock::now();
    auto now_ms = [&](){ return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-t0).count(); };

    // ---- BATCHED: wait for ALL arrivals, process, emit ONE output at the end ----
    t0 = std::chrono::steady_clock::now();
    std::this_thread::sleep_for(std::chrono::milliseconds(STAGGER_MS*LANES)); // last arrival
    double batched_ready = now_ms();
    for(int l=0;l<LANES;l++) lane_work<<<grid,block,0,st[l]>>>(din[l],dout[l],N,REPS);
    for(int l=0;l<LANES;l++) CK(cudaStreamSynchronize(st[l]));
    double batched_first = now_ms();
    printf("BATCHED  all-inputs-ready=%.2f ms  time-to-first(only)-output=%.2f ms  outputs=1\n", batched_ready, batched_first);

    // ---- ROLLING: each lane launches on its own stream the moment it arrives ----
    // Timing is read from the EVENTS' OWN GPU timestamps, not from when the host
    // gets around to observing completion (v1 of this bench had that bug: the
    // observation loop only started after the last launch, so every output
    // appeared to land at ~20 ms).
    t0 = std::chrono::steady_clock::now();
    cudaEvent_t done[LANES], ev_start;
    CK(cudaEventCreate(&ev_start));
    CK(cudaEventRecord(ev_start, st[0])); // GPU-clock zero, before any arrival wait
    for(int l=0;l<LANES;l++){
        CK(cudaEventCreate(&done[l]));
        std::this_thread::sleep_for(std::chrono::milliseconds(STAGGER_MS)); // this lane arrives
        lane_work<<<grid,block,0,st[l]>>>(din[l],dout[l],N,REPS);
        CK(cudaEventRecord(done[l], st[l]));
    }
    std::vector<double> out_times;
    for(int l=0;l<LANES;l++){ CK(cudaEventSynchronize(done[l])); float ems; CK(cudaEventElapsedTime(&ems, ev_start, done[l])); out_times.push_back(ems); }
    printf("ROLLING  time-to-first-output=%.2f ms  outputs=%d at:", out_times[0], LANES);
    for(double t: out_times) printf(" %.2f", t);
    printf(" ms\n");
    printf("VERDICT  rolling first output is %.1fx earlier; rolling emits %d usable outputs in the window where batched emits 1\n",
           batched_first/out_times[0], LANES);
    for(int l=0;l<LANES;l++){ cudaFree(din[l]); cudaFree(dout[l]); cudaStreamDestroy(st[l]); }
    return 0;
}
