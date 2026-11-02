## What breaks first

**1. NVENC instance count, not SMs — and it is unmeasured.** Thor's encode path is fixed-function; the 20 SMs are irrelevant to it. But Jetson-class parts have historically shipped 
