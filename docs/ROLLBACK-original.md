# Verified Pi baseline and rollback

The baseline app is under `~/PillGuard_Integration.a3llKg`, listening on Pi loopback port 8765. Performance candidates use separate directories and ports. To return to baseline, close the candidate and open the original service. If the baseline service is stopped, run `cd ~/PillGuard_Integration.a3llKg && sh run_pi.sh`.

The Pi checkpoint at `~/PillGuard_Baseline.TBSXF8` contains the application, runtime, original models, tokenizer, vision code and ExecuTorch wheel in `deployment.tar`. It also contains an SQLite-consistent history snapshot, the history JSON export, runtime dependency inventory and SHA-256 manifests. The original deployment package and historical benchmark evidence remain in the Windows workspace.

For recovery on the Pi:

1. Enter the checkpoint directory and run `sha256sum -c checkpoint.sha256`.
2. Create a new recovery directory. Extract `deployment.tar` into it, then run `sha256sum -c /home/<pi-or-wsl-user>/PillGuard_Baseline.TBSXF8/files.sha256` from the extraction root.
3. Use the recorded system dependency versions and ExecuTorch wheel if recreating the Pi software environment. The checkpoint includes exact vision runtime libraries under `vision-venv-libs/`. Verify them with `sha256sum -c vision-shared.sha256` in the checkpoint directory. For a recovery layout, set `LD_LIBRARY_PATH` to the checkpoint's `vision-venv-libs` directory. Confirm the restored executable's `ldd` output resolves the expected libraries before launching.
4. Copy the checkpoint history database into a new recovery data directory. Start the restored app with `python3 app.py --vision-dir <restored-vision-dir> --llama-runner <restored-llama_main> --tokenizer <restored-tokenizer.model> --data-dir <recovery-data-dir> --port 18767`.
5. Check the recovered service's history and one known normal and defective sample. Switch the browser to it after checking the results. Preserve the original service and its files throughout recovery.
