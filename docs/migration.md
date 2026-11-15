# Safe future transition — documentation only

No migration, production connection or legacy profile conversion occurs during
container startup. OSCAR1.x files are **not** OSCAR2 SQL databases. Repointing
an old PVC at the new datadir is not a migration.

Before a separately approved private integration:

1. Discover the actual old release/claims, versions, config/data/SD paths and
   GitOps synchronization behavior. Protect old chart-managed PVCs against
   removal **before replacing the old release**. New v2 claim names alone
   do not stop Helm deleting old managed PVCs.
2. Stop old application writes and make consistent backups of config, data,
   SD input and ownership. Verify restoration, not only snapshot existence.
   Nested config/data/SD mounts require separate backups.
3. Keep originals immutable and disconnected. Use verified clones/working
   copies, an independent configuration, new OSCAR2 data volume and a different
   release name, without taking over production routing. Never attach original
   config/data just because a claim name or release name matches.
4. Use OSCAR2's supported **interactive** legacy importer on a working copy.
   If the importer requires source writes, permit those only on another
   disposable copy, never the original archive or production PVC.
5. Compare every profile/device, history time range, day/session counts,
   enabled/disabled sessions, notes/journal, detailed graphs and representative
   preferences. Account only for documented representation changes.
6. Review **all importer warnings and logs**. Some journal/backup-copy failures
   are warnings and do not prevent a success dialog. Check the new SQLite
   integrity and restart/recreate with the new volumes. A dialog saying
   “success” is not acceptance of data preservation.
7. Obtain separate acceptance and approval before switching traffic.

Incomplete import means **do not switch**. Rollback uses the old application
with its untouched old config/data; never run it over a new SQL folder.
New writes after switching require an explicit rollback/reconciliation
decision: automatic merging of the two histories is not promised.

This public project contains no private values, domains, claim mapping,
credentials, kubeconfig or real medical records. The real integration and
its acceptance remain a separate private task.
