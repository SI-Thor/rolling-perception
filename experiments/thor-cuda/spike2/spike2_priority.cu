// spike2_priority: do stream priorities restore the rolling staircase when
// BIG lane kernels saturate the GPU and all arrive at once?
// 4 lanes, exp1's big config (N=1M, reps=60). All 4 kernels launched
// back-to-back on 4 streams (simultaneous arrival). Completion times read
// from CUDA events' own GPU timestamps (the exp1 lesson).
// Configs, interleaved over TRIALS trials:
//   default : cudaStreamCreate
//   prio    : cudaStreamCreateWithPriority, lane0 = greatest priority,
//             decreasing by lane (priorities clamped to the device range)
// Report: per-lane median completion (ms), spread (last-first) per config.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
#include <cuda_runtime.h>
#define CK(x) do{cudaError_t e=(x); if(e){printf("CUDA err %s @%d\n",cudaGetErrorString(e),__LINE__); exit(1);}}while(0)

__global__ void lane_work(const float* __restrict__ in, float* __restrict__ out, int n, int reps){
    int i = blockIdx.x*blockDim.x + threadIdx.x;
    if(i>=n) return;
    float v = in[i];
    for(int r=0;r<reps;r++) v = v*1.000001f + 0.0000001f;
    out[i]=v;
}
static double med(std::vector<double> v){ std::sort(v.begin(), v.end()); return v[v.size()/2]; }

int main(){
    const int LANES=4, N=1<<20, REPS=60, TRIALS=5;
    float *din[LANES], *dout[LANES];
    for(int l=0;l<LANES;l++){ CK(cudaMalloc(&din[l], N*sizeof(float))); CK(cudaMalloc(&dout[l], N*sizeof(float)));
        CK(cudaMemset(din[l], 0x3f, N*sizeof(float))); }
    dim3 grid((N+255)/256), block(256);
    int greatest, least; CK(cudaDeviceGetStreamPriorityRange(&least, &greatest));
    printf("stream priority range: greatest=%d least=%d\n", greatest, least);

    std::vector<double> comp[2][LANES]; double spread[2][64]; int spn[2]={0,0};
    for(int t=0;t<TRIALS;t++){
        for(int cfg=0; cfg<2; cfg++){           // 0=default, 1=prio (interleaved)
            cudaStream_t st[LANES]; cudaEvent_t done[LANES], start;
            for(int l=0;l<LANES;l++){
                if(cfg==0){ CK(cudaStreamCreate(&st[l])); }
                else { int p = greatest + l; if(p>least) p=least;
                       CK(cudaStreamCreateWithPriority(&st[l], cudaStreamNonBlocking, p)); }
                CK(cudaEventCreate(&done[l]));
            }
            CK(cudaEventCreate(&start)); CK(cudaEventRecord(start, st[0])); CK(cudaStreamSynchronize(st[0]));
            for(int l=0;l<LANES;l++){ lane_work<<<grid,block,0,st[l]>>>(din[l],dout[l],N,REPS);
                                      CK(cudaEventRecord(done[l], st[l])); }
            double times[LANES];
            for(int l=0;l<LANES;l++){ CK(cudaEventSynchronize(done[l])); float ems; CK(cudaEventElapsedTime(&ems, start, done[l]));
                                      times[l]=ems; comp[cfg][l].push_back(ems); }
            double mx=*std::max_element(times,times+LANES), mn=*std::min_element(times,times+LANES);
            spread[cfg][spn[cfg]++] = mx-mn;
            for(int l=0;l<LANES;l++){ cudaStreamDestroy(st[l]); cudaEventDestroy(done[l]); }
            cudaEventDestroy(start);
        }
    }
    for(int cfg=0; cfg<2; cfg++){
        printf("%s per-lane median completion ms:", cfg==0?"DEFAULT  ":"PRIORITY ");
        double mn=1e9, mx=0;
        for(int l=0;l<LANES;l++){ double m=med(comp[cfg][l]); printf(" L%d=%.2f", l, m); mn=std::min(mn,m); mx=std::max(mx,m); }
        std::vector<double> sp(spread[cfg], spread[cfg]+spn[cfg]);
        printf(" | median spread(last-first)=%.2f ms\n", med(sp));
    }
    for(int l=0;l<LANES;l++){ cudaFree(din[l]); cudaFree(dout[l]); }
    return 0;
}
