// spike2_arrangements: SAME kernel, SAME slice sizes, three arrangements.
//   (a) launch      : per-slice kernel launch on one stream, host waits each slice
//   (b) shadow      : two streams, host stays 2 slices ahead (slice i+1 staged on B
//                     while slice i computes on A), completions collected in order
//   (c) persistent  : ONE resident kernel (2 blocks x 256 thr) polling a flag in
//                     host-pinned mapped memory; host raises request_seq, kernel
//                     writes started_seq when it picks the slice up, done_seq when
//                     finished. Pickup = flag-set -> started_seq visible (host clock,
//                     includes the mapped-memory round trip).
// For (a)/(b) pickup = GPU-event elapsed from a submit event (recorded on an idle
// timing stream at the moment of submission) to a begin event recorded on the work
// stream immediately before the kernel. Work = begin -> end event.
// CPU cost = getrusage(user+sys) over the run, reported per slice and as % of wall.
// Correctness: one extra slice is run at the end of each mode and out[k] is
// compared against the host-computed reference for the same input/reps.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <sys/resource.h>
#include <cuda_runtime.h>
#define CK(x) do{cudaError_t e=(x); if(e){printf("CUDA err %s @%d\n",cudaGetErrorString(e),__LINE__); exit(1);}}while(0)

__global__ void slice_work(const float* __restrict__ in, float* __restrict__ out, int n, int reps){
    int i = blockIdx.x*blockDim.x + threadIdx.x;
    if(i>=n) return;
    float v = in[i];
    for(int r=0;r<reps;r++) v = v*1.000001f + 0.0000001f;
    out[i]=v;
}

// ---- persistent arrangement: control struct in host-pinned mapped memory ----
struct Control{ volatile unsigned long long request_seq, started_seq, done_seq;
                volatile int reps; volatile int stop; volatile int n; volatile int pad[9]; };

__global__ void persistent_kernel(Control* ctl, const float* __restrict__ in, float* __restrict__ out){
    unsigned long long seen = 0;
    const int n = ctl->n;
    while(true){
        if(ctl->stop) return;
        unsigned long long req = ctl->request_seq;
        if(req != seen){
            seen = req;
            if(threadIdx.x==0 && blockIdx.x==0){ __threadfence_system(); ctl->started_seq = seen; }
            int reps = ctl->reps;
            for(int i = threadIdx.x + blockIdx.x*blockDim.x; i < n; i += gridDim.x*blockDim.x){
                float v = in[i];
                for(int r=0;r<reps;r++) v = v*1.000001f + 0.0000001f;
                out[i]=v;
            }
            __threadfence_system();
            if(threadIdx.x==0 && blockIdx.x==0) ctl->done_seq = seen;
        }
    }
}

static double cpu_now_s(){ struct rusage ru; getrusage(RUSAGE_SELF,&ru);
    return ru.ru_utime.tv_sec + ru.ru_utime.tv_usec/1e6 + ru.ru_stime.tv_sec + ru.ru_stime.tv_usec/1e6; }
static double pct(std::vector<double> v, double q){ std::sort(v.begin(), v.end());
    return v[std::min(v.size()-1, (size_t)(q*v.size()))]; }
static void report(const char* mode, int n, int reps, int reqs,
                     std::vector<double> pickup_us, std::vector<double> work_us,
                     double wall_ms, double cpu_ms){
    printf("%-10s N=%7d reps=%3d slices=%3d | pickup us p50=%.1f p95=%.1f p99=%.1f | work us p50=%.1f p95=%.1f | total=%.1f ms | host CPU=%.1f ms (%.2f ms/slice, %.0f%% of wall)\n",
        mode, n, reps, reqs, pct(pickup_us,.5), pct(pickup_us,.95), pct(pickup_us,.99),
        pct(work_us,.5), pct(work_us,.95), wall_ms, cpu_ms, cpu_ms/reqs, 100.0*cpu_ms/wall_ms);
}
static float reference(float v, int reps){ for(int r=0;r<reps;r++) v = v*1.000001f + 0.0000001f; return v; }

int main(int argc, char** argv){
    // args: mode N reps reqs
    const char* mode = argv[1]; int N = atoi(argv[2]); int REPS = atoi(argv[3]); int REQS = atoi(argv[4]);
    float *din, *dout;
    CK(cudaMalloc(&din, N*sizeof(float))); CK(cudaMalloc(&dout, N*sizeof(float)));
    CK(cudaMemset(din, 0x3f, N*sizeof(float))); // ~0.75 value pattern
    dim3 grid((N+255)/256), block(256);
    cudaStream_t timing; CK(cudaStreamCreate(&timing));

    if(!strcmp(mode,"launch") || !strcmp(mode,"shadow")){
        cudaStream_t A,B; CK(cudaStreamCreate(&A)); CK(cudaStreamCreate(&B));
        const int DEPTH = !strcmp(mode,"shadow") ? 2 : 1;
        struct Pend{ cudaEvent_t sub,beg,end; };
        std::vector<Pend> inflight; std::vector<double> pickup, work;
        auto submit = [&](int idx){
            Pend p; CK(cudaEventCreate(&p.sub)); CK(cudaEventCreate(&p.beg)); CK(cudaEventCreate(&p.end));
            cudaStream_t s = (idx % 2 == 0) ? A : B; if(DEPTH==1) s = A;
            CK(cudaEventRecord(p.sub, timing));
            CK(cudaEventRecord(p.beg, s));
            slice_work<<<grid,block,0,s>>>(din, dout, N, REPS);
            CK(cudaEventRecord(p.end, s));
            inflight.push_back(p);
        };
        auto collect = [&](bool /*oldest*/){
            Pend p = inflight.front(); inflight.erase(inflight.begin());
            CK(cudaEventSynchronize(p.end));
            float pu, wk; CK(cudaEventElapsedTime(&pu, p.sub, p.beg)); CK(cudaEventElapsedTime(&wk, p.beg, p.end));
            pickup.push_back(pu*1000.0); work.push_back(wk*1000.0);
            cudaEventDestroy(p.sub); cudaEventDestroy(p.beg); cudaEventDestroy(p.end);
        };
        // warm-up slice (not measured)
        slice_work<<<grid,block,0,A>>>(din,dout,N,REPS); CK(cudaStreamSynchronize(A));
        double c0 = cpu_now_s(); auto w0 = std::chrono::steady_clock::now();
        for(int i=0;i<REQS;i++){ submit(i); while((int)inflight.size() >= DEPTH) collect(true); }
        while(!inflight.empty()) collect(true);
        double wall = std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-w0).count();
        report(mode, N, REPS, REQS, pickup, work, wall, (cpu_now_s()-c0)*1000.0);
        cudaStreamDestroy(A); cudaStreamDestroy(B);
    }
    else if(!strcmp(mode,"persistent")){
        Control* h; Control* d;
        CK(cudaHostAlloc((void**)&h, sizeof(Control), cudaHostAllocMapped));
        CK(cudaHostGetDevicePointer((void**)&d, h, 0));
        h->request_seq=0; h->started_seq=0; h->done_seq=0; h->reps=REPS; h->stop=0; h->n=N;
        persistent_kernel<<<2,256>>>(d, din, dout);   // 2 blocks ONLY: 2 of 20 SMs
        CK(cudaGetLastError());
        std::vector<double> pickup, work;
        double c0 = cpu_now_s(); auto w0 = std::chrono::steady_clock::now();
        for(int r=1;r<=REQS;r++){
            auto s = std::chrono::steady_clock::now();
            h->request_seq = (unsigned long long)r;
            while(h->started_seq != (unsigned long long)r){ }
            auto mid = std::chrono::steady_clock::now();
            while(h->done_seq != (unsigned long long)r){ }
            auto e = std::chrono::steady_clock::now();
            pickup.push_back(std::chrono::duration<double,std::micro>(mid-s).count());
            work.push_back(std::chrono::duration<double,std::micro>(e-mid).count());
        }
        double wall = std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-w0).count();
        double cpu = (cpu_now_s()-c0)*1000.0;
        h->stop = 1; CK(cudaDeviceSynchronize());
        report(mode, N, REPS, REQS, pickup, work, wall, cpu);
        float got; CK(cudaMemcpy(&got, dout+123, sizeof(float), cudaMemcpyDeviceToHost));
        float in_v; { unsigned b=0x3f3f3f3f; memcpy(&in_v,&b,4); }
        float want = reference(in_v, REPS);
        printf("  check out[123]=%.6f want=%.6f %s\n", got, want, fabsf(got-want)<1e-3?"MATCH":"MISMATCH");
        cudaFreeHost(h); cudaFree(din); cudaFree(dout); cudaStreamDestroy(timing);
        return 0;
    }
    // correctness spot-check (launch path)
    slice_work<<<grid,block>>>(din,dout,N,REPS); CK(cudaDeviceSynchronize());
    float got; CK(cudaMemcpy(&got, dout+123, sizeof(float), cudaMemcpyDeviceToHost));
    float in_v; { unsigned b=0x3f3f3f3f; memcpy(&in_v,&b,4); }
    float want = reference(in_v, REPS);
    printf("  check out[123]=%.6f want=%.6f %s\n", got, want, fabsf(got-want)<1e-3?"MATCH":"MISMATCH");
    cudaFree(din); cudaFree(dout); cudaStreamDestroy(timing);
    return 0;
}
