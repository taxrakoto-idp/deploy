# Backstage

This wrapper deploys the custom TaxRakoto IDP Backstage application through
the official Backstage Helm chart. Argo CD discovers `tools/backstage` through
the `platform-components` ApplicationSet and deploys it into the `backstage`
namespace after the `postgres` Application is Healthy.

## Pinned artifacts

- Upstream chart repository: `https://backstage.github.io/charts`
- Upstream chart: `backstage`
- Chart version: `2.10.0`
- Backstage application version: `1.54.0`
- Image: `ghcr.io/taxrakoto-idp/backstage`
- Multi-architecture image digest:
  `sha256:ee726cee4df120049c2381a18d49e2962908526447502834f663fdca0d8c0379`

`Chart.lock` records the resolved dependency and
`charts/backstage-2.10.0.tgz` makes the Git revision self-contained for Argo
CD. The image digest selects the same AMD64 or ARM64 build on every cluster.

## PostgreSQL connection

The bundled PostgreSQL chart is disabled. Backstage reads its connection from
the PGO-generated `backstage-postgres-pguser-backstage` Secret in the same
namespace. The Deployment maps only these keys:

| Backstage environment variable | PGO Secret key |
| --- | --- |
| `POSTGRES_HOST` | `host` |
| `POSTGRES_PORT` | `port` |
| `POSTGRES_USER` | `user` |
| `POSTGRES_PASSWORD` | `password` |
| `POSTGRES_DB` | `dbname` |

TLS is requested with `PGSSLMODE=require`. No database credentials are stored
in Git.

## Access

Ingress is deliberately disabled. Access the local demonstration through a
port forward:

```bash
kubectl --namespace backstage port-forward service/backstage 7007:7007
```

Then open `http://localhost:7007`.

Guest authentication is enabled by the custom application's production
configuration for this local demonstration. Do not expose this deployment
publicly without replacing guest authentication.

## Validate

```bash
helm dependency build tools/backstage
helm lint tools/backstage
helm template backstage tools/backstage --namespace backstage
```

After Argo CD synchronizes the package:

```bash
kubectl get deployment,pod,service --namespace backstage
kubectl get secret backstage-postgres-pguser-backstage --namespace backstage
kubectl logs deployment/backstage --namespace backstage
```

## Upgrade

1. Publish and verify a new multi-architecture Backstage image.
2. Replace `backstage.backstage.image.digest` in `values.yaml` with the new
   top-level manifest digest.
3. If upgrading the upstream chart, update its dependency version in
   `Chart.yaml` and run `helm dependency update tools/backstage`.
4. Review `Chart.lock`, the packaged dependency, and rendered manifests.
