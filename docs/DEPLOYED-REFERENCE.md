# Deployment map and rollback

This is a review archive. Recovery instructions refer to existing files on the owner's Pi, including model binaries omitted here.

| Service | Loopback port | Pi directory | Launch from Pi |
|---|---:|---|---|
| Protected baseline | 8765 | `~/PillGuard_Integration.a3llKg` | `cd ~/PillGuard_Integration.a3llKg && sh run_pi.sh` |
| Optimized candidate | 8766 | `~/PillGuard_Performance.ltsFKI` | `sh ~/PillGuard_Performance.ltsFKI/run_candidate.sh` |
| Isolated asynchronous test | 18770/18771 during tests | `~/PillGuard_PS5_Prototype.y0DOfN` | Evidence only. The tests used a separate database and temporary server. |

The baseline and optimized candidate use separate histories. For rollback from 8766, direct the browser to the separately preserved service on 8765. If the baseline is stopped, start it using the recorded command. The original baseline archive, SQLite snapshot, and dependency copies are in `~/PillGuard_Baseline.TBSXF8`. Restore into a new directory and use a spare port. The rollback drill used port 18767, confirmed byte-for-byte history export equality, and ran normal and defective inspections against restored model files and copied libraries. If needed, recover the optimized service by keeping the single-pass runner and compact app in their separate deployment directory and using its launch script and checksums.

Replace the redacted account and host placeholders with your actual Pi values if using SSH. [Original rollback procedure](ROLLBACK-original.md) · [Rollback drill](../evidence/rollback/rollback-test.log) · [Service reachability from the prior run](../evidence/upload-acceptance/service-check.log)
