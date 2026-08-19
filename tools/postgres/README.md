# Backstage PostgreSQL cluster

This package creates the PostgreSQL cluster used by Backstage. Argo CD
discovers `tools/postgres` as the `postgres` Application, while the resources
themselves are deployed into the `backstage` namespace so Backstage can consume
the PGO-generated connection Secret directly.

The platform ApplicationSet routes both the `postgres` and `backstage`
Applications to this shared namespace. Argo CD creates it when PostgreSQL is
first synchronized but deliberately does not assign either Application
ownership of the Namespace object.

PGO creates a `backstage` database and user. The generated Secret is named
`backstage-postgres-pguser-backstage` and contains the connection values that
the Backstage deployment will reference; no database password is stored in Git.

The database requests 5 Gi from the `nfs-csi` StorageClass. The pgBackRest
configuration is retained as commented YAML in `postgrescluster.yaml`, but it
is disabled for the local demonstration so an additional 5 Gi repository PVC
is not allocated. Uncomment it when backup and restore testing is required.

## Validate

```bash
kubectl kustomize tools/postgres
```

After Argo CD synchronizes the package:

```bash
kubectl get postgrescluster,pods,pvc --namespace backstage
kubectl get secret backstage-postgres-pguser-backstage --namespace backstage
```
