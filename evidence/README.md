# Recorded demonstration evidence

[PillGuard upload demonstration](PillGuard_Upload_Demo.webm) is the existing captioned walkthrough assembled from actual browser captures of the optimized Pi service. It shows the normal and defective outcomes and stored history. The timings in the standalone and isolated evidence are from their own runs. [Image attribution and license](../notices/RIGHTS.md)

- [Technical addendum](PillGuard_Upload_Addendum.pdf) documents the offline upload acceptance.
- [Raw offline Pi run](pi-offline-uploads.log) and [structured results](offline-acceptance-results.json) contain four cases across the verified baseline and optimized builds.
- [Browser export](browser-export.json) contains the two successful browser upload records.
- [Pi runtime SHA-256 records](pi-sha256.txt) and [optimized executable and pipeline checksum](verified-optimized.sha256) identify the historical artifacts.
- [Cortex-A72 runner log](pi-q4-16-tokens.log), [export log](llama-export.log) and [build configuration](pillguard-release-runner-config.log) document real Llama inference and provenance.
- [Dataset audit](dataset/) contains stored predictions, audit material and metric code. Raw dataset media and model weights are excluded.
