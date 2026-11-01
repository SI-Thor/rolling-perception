// exp4: Viewport gating (FluidAttn, honest version).
// Full-frame kernel computes every element of a 4096x4096 field.
// Gated kernel launches the same grid but blocks whose tile lies wholly
// outside the ROI return immediately — no loads, no math.
// Verify: gated output equals full output INSIDE the ROI, and elements
// OUTSIDE the ROI are untouched (sentinel preserved). Time both.
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cuda_runtime.h>
#define CK(x) do{cudaError_t e=(x); if(e){printf("CUDA err %s @%d\n",cudaGetErrorString(e),__LINE__); exit(1);}}while(0)

__global__ void full(const float* __restrict__ in, float* __restrict__ out, int W){
    int x = blockIdx.x*blockDim.x + threadIdx.x, y = blockIdx.y*blockDim.y + threadIdx.y;
    if(x<W && y<W){ int i=y*W+x; out[i]=in[i]*2.0f+1.0f; }
}
__global__ void gated(const float* __restrict__ in, float* __restrict__ out, int W,
                      int x0,int y0,int x1,int y1){
    int bx0 = blockIdx.x*blockDim.x, by0 = blockIdx.y*blockDim.y;
    if(bx0+blockDim.x<=x0 || bx0>=x1 || by0+blockDim.y<=y0 || by0>=y1) return; // whole tile outside ROI
    int x = bx0+threadIdx.x, y = by0+threadIdx.y;
    if(x<W && y<W && x>=x0 && x<x1 && y>=y0 && y<y1){ int i=y*W+x; out[i]=in[i]*2.0f+1.0f; }
}

static float bench(cudaStream_t s, int which, const float* in, float* out, int W, dim3 g, dim3 b, int roi[4]){
    cudaEvent_t a,c; cudaEventCreate(&a); cudaEventCreate(&c);
    for(int w=0;w<3;w++){ if(which==0) full<<<g,b,0,s>>>(in,out,W); else gated<<<g,b,0,s>>>(in,out,W,roi[0],roi[1],roi[2],roi[3]); }
    cudaEventRecord(a,s);
    const int R=20;
    for(int r=0;r<R;r++){ if(which==0) full<<<g,b,0,s>>>(in,out,W); else gated<<<g,b,0,s>>>(in,out,W,roi[0],roi[1],roi[2],roi[3]); }
    cudaEventRecord(c,s); cudaEventSynchronize(c);
    float ms; cudaEventElapsedTime(&ms,a,c); return ms/R;
}

int main(){
    const int W=4096; const size_t N=(size_t)W*W;
    float *in,*of,*og; CK(cudaMalloc(&in,N*4)); CK(cudaMalloc(&of,N*4)); CK(cudaMalloc(&og,N*4));
    CK(cudaMemset(in,0x40,N*4));
    CK(cudaMemset(og,0xEE,N*4)); // sentinel outside ROI must survive in gated output
    dim3 b(16,16), g(W/16,W/16);
    int roi[4]={1024,1024,1536,1536}; // 512x512 = 1/64 of the field
    float tf = bench(nullptr,0,in,of,W,g,b,roi);
    float tg = bench(nullptr,1,in,og,W,g,b,roi);
    CK(cudaDeviceSynchronize());
    // verify
    float *hf=(float*)malloc(N*4), *hg=(float*)malloc(N*4);
    CK(cudaMemcpy(hf,of,N*4,cudaMemcpyDeviceToHost)); CK(cudaMemcpy(hg,og,N*4,cudaMemcpyDeviceToHost));
    long inside_diff=0; long outside_touched=0;
    unsigned char sent[4]; memset(sent,0xEE,4); float sentinel; memcpy(&sentinel,sent,4);
    for(int y=0;y<W;y++) for(int x=0;x<W;x++){ size_t i=(size_t)y*W+x;
        bool ins = (x>=roi[0]&&x<roi[2]&&y>=roi[1]&&y<roi[3]);
        if(ins){ if(fabsf(hf[i]-hg[i])>1e-4) inside_diff++; }
        else { if(hg[i]!=sentinel) outside_touched++; }
    }
    double frac = (512.0*512.0)/(double)N;
    printf("GATING field %dx%d (%.1fM elems), ROI 512x512 (%.2f%% of field)\n", W,W,N/1e6, frac*100);
    printf("  full-frame: %.3f ms/frame   gated: %.3f ms/frame   speedup %.1fx\n", tf, tg, tf/tg);
    printf("  inside-ROI mismatches vs full: %ld   outside-ROI elements touched: %ld  %s\n",
           inside_diff, outside_touched, (inside_diff==0&&outside_touched==0)?"CLEAN":"DIRTY");
    free(hf); free(hg); cudaFree(in); cudaFree(of); cudaFree(og);
    return 0;
}
