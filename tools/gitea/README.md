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

## Platform initialization

After Gitea becomes Healthy, an idempotent Argo CD `PostSync` hook initializes
the installation-local platform resources through the Gitea API:

- public `taxrakoto-idp` organization;
- restricted `backstage-bot` and `gitops-bot` service accounts;
- `scaffolders` and `gitops-writers` teams;
- private `taxrakoto-idp/application-gitops` repository initialized on `main`;
- narrowly scoped API tokens for the two service accounts; and
- an organization-level Gitea Actions runner registration token.

The Job reads the bootstrap administrator account only while it runs. It
stores generated credentials in `gitea-backstage-bot`, `gitea-gitops-bot`, and
`gitea-actions-runner-token` Kubernetes Secrets. Existing resources and Secret
values are reused on later syncs, and credential values are never logged or
stored in Git.

The future Actions runner release must read the `runner-token` key from
`gitea-actions-runner-token`. That Secret currently lives in the `gitea`
namespace, so the runner release should use the same namespace unless a
deliberate cross-namespace Secret distribution mechanism is added.

Verify initialization without displaying credentials:

```bash
kubectl --namespace gitea get secret \
  gitea-backstage-bot gitea-gitops-bot gitea-actions-runner-token
kubectl --namespace gitea get job gitea-platform-initializer
```

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
