# Gitea PostgreSQL cluster

This package creates the PostgreSQL cluster that Gitea will use. Argo CD
discovers `tools/gitea-postgres` as the `gitea-postgres` Application and deploys
its resources into the shared `gitea` namespace before the future `gitea`
Application is allowed to synchronize.

PGO creates a `gitea` database owned by a dedicated `gitea` login role. The
generated Secret is named `gitea-postgres-pguser-gitea` and will provide the
host, port, database name, username, password, and connection URI consumed by
the Gitea chart. No database password is stored in Git.

The database requests 2 Gi from the `nfs-csi` StorageClass. A pgBackRest backup
configuration is retained as commented YAML in `postgrescluster.yaml`, but it
is disabled for the local demonstration so an additional repository PVC is not
allocated. Uncomment it when backup and restore testing is required.

## Validate

```bash
kubectl kustomize tools/gitea-postgres
```

After Argo CD synchronizes the package:

```bash
kubectl get postgrescluster,pods,pvc --namespace gitea
kubectl get secret gitea-postgres-pguser-gitea --namespace gitea
```
