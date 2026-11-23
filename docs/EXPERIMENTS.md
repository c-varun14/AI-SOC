# Separate development work

The release preserves the working compact Llama prompt and advisory display gate from the optimized Pi deployment. The later structured advisory experiment used the same Q4 model in WSL. Its final prompt produced zero accepted answers on two prior fixtures. The gate suppressed both answers, and deterministic QC was unaffected. It was never promoted.

The separate development branch also repaired the independent validation import and added fail-closed records for vision errors. Six isolated localhost regression tests passed. A Pi run of those changes remains unverified. Those fixes are outside the submission reference. The earlier, separately tested early-QC prototype is represented by a captured log only.
