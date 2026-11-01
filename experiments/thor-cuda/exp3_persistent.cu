// exp3: Persistent kernel + behaviour swap via pinned mapped memory.
// One kernel launches ONCE and stays resident, polling a control struct in
// host-pinned mapped memory (the feasibility finding: control slots belong in
// mapped pinned memory, NOT managed memory, because
// directManagedMemAccessFromHost=0 on Thor).
// Host sends work requests (seq + scale); kernel does the work on a device
// buffer and acks by writing done_seq back through the same mapped struct.
// Host measures request->ack round-trip latency. Changing `scale` mid-run is
// the honest miniature of "hot-swap": behaviour changes at iteration
// granularity, no relaunch. A stop flag ends the kernel cleanly.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <chrono>
#include <vector>
#include <algorithm>
#include <cuda_runtime.h>
#define CK(x) do{cudaError_t e=(x); if(e){printf("CUDA err %s @%d\n",cudaGetErrorString(e),__LINE__); exit(1);}}while(0)

struct Control {
    volatile unsigned long long request_seq;
    volatile unsigned long long done_seq;
    volatile float scale;
    volatile int stop;
    volatile int pad[13]; // keep it simple, single cache-ish struct
};

__global__ void persistent(Control* ctl, float* buf, int n){
    unsigned long long seen = 0;
    while(true){
        if(ctl->stop) return;
        unsigned long long req = ctl->request_seq;
        if(req != seen){
            seen = req;
            float s = ctl->scale;
            for(int i = threadIdx.x + blockIdx.x*blockDim.x; i < n; i += gridDim.x*blockDim.x){
                buf[i] += s;
            }
            __threadfence_system();
            if(threadIdx.x==0 && blockIdx.x==0) ctl->done_seq = seen;
        }
    }
}

int main(){
    const int N = 1024;
    Control* hctl; Control* dctl;
    CK(cudaHostAlloc((void**)&hctl, sizeof(Control), cudaHostAllocMapped));
    CK(cudaHostGetDevicePointer((void**)&dctl, hctl, 0));
    hctl->request_seq = 0; hctl->done_seq = 0; hctl->scale = 1.0f; hctl->stop = 0;
    float* dbuf; CK(cudaMalloc(&dbuf, N*sizeof(float))); CK(cudaMemset(dbuf, 0, N*sizeof(float)));

    auto launch_t0 = std::chrono::steady_clock::now();
    persistent<<<2,128>>>(dctl, dbuf, N);   // resident: 2 blocks only, leaves 18 SMs free
    CK(cudaGetLastError());

    const int REQS = 300;
    std::vector<double> lat_us;
    for(int r=1;r<=REQS;r++){
        if(r==REQS/2) hctl->scale = 10.0f;
        auto s = std::chrono::steady_clock::now();
        hctl->request_seq = (unsigned long long)r;
        while(hctl->done_seq != (unsigned long long)r){ }
        auto e = std::chrono::steady_clock::now();
        lat_us.push_back(std::chrono::duration<double,std::micro>(e-s).count());
    }
    hctl->stop = 1;
    CK(cudaDeviceSynchronize());
    double join_ms = std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-launch_t0).count();

    float first=0; CK(cudaMemcpy(&first, dbuf, sizeof(float), cudaMemcpyDeviceToHost));
    // expected: 149 reqs * 1.0 + 151 reqs * 10.0 = 149 + 1510 = 1659
    float expected = 149*1.0f + 151*10.0f;
    std::sort(lat_us.begin(), lat_us.end());
    double mean=0; for(double v:lat_us) mean+=v; mean/=lat_us.size();
    printf("PERSISTENT resident kernel: %d requests served by ONE launch\n", REQS);
    printf("  request->ack latency: mean=%.1f us  p50=%.1f us  p95=%.1f us  max=%.1f us\n",
           mean, lat_us[lat_us.size()/2], lat_us[(size_t)(lat_us.size()*0.95)], lat_us.back());
    printf("  buffer[0]=%.1f expected=%.1f  %s  (scale swapped 1.0 -> 10.0 at request %d, no relaunch)\n",
           first, expected, (fabsf(first-expected)<0.5f?"MATCH":"MISMATCH"), REQS/2);
    printf("  clean stop via flag: device synchronized, total wall=%.1f ms\n", join_ms);
    cudaFree(dbuf); cudaFreeHost(hctl);
    return 0;
}
