# Gitea

This wrapper deploys the official Gitea Helm chart. Argo CD discovers
`tools/gitea` through the `platform-components` ApplicationSet and deploys it
into the `gitea` namespace only after `gitea-postgres` is Healthy.

## Upstream dependency

- Chart repository: `https://dl.gitea.com/charts/`
- Chart: `gitea`
- Chart version: `12.7.0`
- Gitea version: `1.27.0`
- Installation mode: one rootless replica

`Chart.lock` records the resolved dependency and `charts/gitea-12.7.0.tgz`
makes the Git revision self-contained for Argo CD.

The chart's PostgreSQL and Valkey dependencies are disabled. Gitea uses the PGO
database at `gitea-postgres-primary.gitea.svc:5432`; only its password is read
from the generated `gitea-postgres-pguser-gitea` Secret. For this local
single-replica demonstration, Gitea uses its memory session/cache providers and
the level queue stored on its persistent data volume.

The repository data volume requests 2 Gi from `nfs-csi` and is retained when
the Helm release is removed. Public registration and ingress are disabled.
Users access the UI through port forwarding:

```bash
kubectl --namespace gitea port-forward service/gitea-http 3000:3000
```

An idempotent Argo CD Sync hook creates `gitea-admin-secret` with a random
password before the Gitea Deployment is synchronized. The Secret is reused on
later syncs and is not stored in Git. Retrieve the credentials with:

```bash
kubectl --namespace gitea get secret gitea-admin-secret \
  --output=jsonpath='{.data.username}' | base64 --decode
printf '\n'
kubectl --namespace gitea get secret gitea-admin-secret \
  --output=jsonpath='{.data.password}' | base64 --decode
printf '\n'
```

Gitea Actions is enabled in the application configuration, but no runner is
installed by this package. The runner remains a separate platform component.

## Validate

```bash
helm dependency build tools/gitea
helm lint tools/gitea
helm template gitea tools/gitea --namespace gitea
```

## Upgrade

1. Review the official chart release and upgrade notes.
2. Change the dependency version and `appVersion` in `Chart.yaml`.
3. Pin the corresponding Gitea image tag in `values.yaml`.
4. Run `helm dependency update tools/gitea`.
5. Review `Chart.lock`, the packaged dependency, and rendered manifests.
