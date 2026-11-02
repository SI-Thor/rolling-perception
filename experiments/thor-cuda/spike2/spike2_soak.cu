// spike2_soak: bounded soak of the persistent kernel.
// Exactly DURATION_S seconds (argv[1], default 600). 2 blocks x 256 threads.
// Host issues a tiny work request every 100 ms (1024-elem buffer, exp3 shape)
// and busy-polls the ack; between requests it sleeps (it is not the load).
// Logs every 30 s: elapsed, requests served, ack p50/p95 so far.
// At the end: stop via flag, device sync, verify final buffer, print summary.
// Telemetry (tegrastats) is collected by the wrapper script, not here.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
#include <chrono>
#include <thread>
#include <cuda_runtime.h>
#define CK(x) do{cudaError_t e=(x); if(e){printf("CUDA err %s @%d\n",cudaGetErrorString(e),__LINE__); exit(1);}}while(0)

struct Control{ volatile unsigned long long request_seq, done_seq;
                volatile float scale; volatile int stop; volatile int pad[13]; };

__global__ void persistent(Control* ctl, float* buf, int n){
    unsigned long long seen = 0;
    while(true){
        if(ctl->stop) return;
        unsigned long long req = ctl->request_seq;
        if(req != seen){
            seen = req; float s = ctl->scale;
            for(int i = threadIdx.x + blockIdx.x*blockDim.x; i < n; i += gridDim.x*blockDim.x) buf[i] += s;
            __threadfence_system();
            if(threadIdx.x==0 && blockIdx.x==0) ctl->done_seq = seen;
        }
    }
}

int main(int argc, char** argv){
    const int DURATION_S = argc>1 ? atoi(argv[1]) : 600;
    const int N = 1024;
    Control* h; Control* d;
    CK(cudaHostAlloc((void**)&h, sizeof(Control), cudaHostAllocMapped));
    CK(cudaHostGetDevicePointer((void**)&d, h, 0));
    h->request_seq=0; h->done_seq=0; h->scale=1.0f; h->stop=0;
    float* buf; CK(cudaMalloc(&buf, N*sizeof(float))); CK(cudaMemset(buf, 0, N*sizeof(float)));
    auto t0 = std::chrono::steady_clock::now();
    persistent<<<2,256>>>(d, buf, N);
    CK(cudaGetLastError());
    printf("SOAK start duration=%ds pid-visible-name=spike2_soak\n", DURATION_S); fflush(stdout);
    std::vector<double> lat; unsigned long long req=0; double last_log=0;
    while(true){
        double el = std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();
        if(el >= DURATION_S) break;
        req++;
        auto s = std::chrono::steady_clock::now();
        h->request_seq = req;
        while(h->done_seq != req){ }
        lat.push_back(std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-s).count());
        if(el - last_log >= 30.0){ last_log = el;
            std::vector<double> v=lat; std::sort(v.begin(), v.end());
            printf("SOAK t=%.0fs requests=%llu ack p50=%.1f us p95=%.1f us\n", el, req,
                   v[v.size()/2], v[(size_t)(v.size()*0.95)]); fflush(stdout); }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    h->stop = 1; CK(cudaDeviceSynchronize());
    double wall = std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();
    float first; CK(cudaMemcpy(&first, buf, sizeof(float), cudaMemcpyDeviceToHost));
    std::sort(lat.begin(), lat.end()); double mean=0; for(double x:lat) mean+=x; mean/=std::max<size_t>(1,lat.size());
    printf("SOAK done wall=%.1fs requests=%llu ack mean=%.1f us p50=%.1f us p95=%.1f us p99=%.1f us max=%.1f us buf[0]=%.1f expected=%.1f %s STOPPED-CLEAN\n",
           wall, req, mean, lat[lat.size()/2], lat[(size_t)(lat.size()*0.95)], lat[(size_t)(lat.size()*0.99)], lat.back(),
           first, (float)req, fabsf(first-(float)req)<0.5f?"MATCH":"MISMATCH");
    cudaFree(buf); cudaFreeHost(h);
    return 0;
}
