# Independent tablet screening validation plan

Freeze the two model SHA-256 values, Experiment 2 preprocessing, and the 0.30 defective probability threshold before opening the independent set. Use the Pi's existing image workflow. Image acquisition can be performed by a data provider and delivered as JPEG or PNG files.

1. Request a labeled tablet set from a collection with documented provenance independent of PharmaVision. Record the collection, capture conditions, batch or specimen identifier, defect category if available, and labeling procedure. Keep multiple photos of one tablet in the same split. Agree on release and reuse permissions with the provider.
2. Have two reviewers label each tablet using a shared definition of visible defect. Resolve disagreements before unblinding predictions. Document exclusions, uncertain labels, and changes. Keep the independent images out of training and threshold selection.
3. Hash the files and compare with accessible training and tuning images. Screen near-duplicate candidates and adjudicate them against original images. Report coverage limits when only reduced images or partial source data are available. Preserve the original manifests and splits.
4. Run the exact Pi preprocessing and Experiment 2 executable against the locked images. Save one row per specimen with label, predicted class, both probabilities, threshold, provenance group, and forward time. Keep full-pipeline upload checks on a subset to verify the correct QC actions and export format.
5. Report the confusion matrix, defect recall and precision with uncertainty, failure examples, and performance by capture condition. If specimens share batches, account for clustering when reporting uncertainty. Agree on sample counts and acceptance criteria before the run, with emphasis on false negatives and review workload. Any threshold or model adjustment requires another held-out set.

Current status: the two demo cases establish system behavior. The 260 earlier tensors establish performance parity between wrappers. The prior 200-image accuracy result is provisional because probable split overlap was found. Independent performance remains unmeasured.

## Procedure on the Pi

Create a locked CSV with columns `image,sha256,label,specimen_id,batch_id,collection`. Paths are relative to the CSV, labels are `normal` or `defective`, and specimen identifiers must be globally unique in the evaluation file. Keep the adjudication and near-duplicate audit alongside the manifest. An explicit human provenance review remains necessary.

Run the recorded Pi vision wrapper on each locked file in a separate test deployment. Preserve the per-specimen CSV, label adjudication and manifest hash. Evaluate once against the frozen 0.30 decision threshold. The later manifest CLI is in the separate development copy. Its promotion is outside this submission reference.
