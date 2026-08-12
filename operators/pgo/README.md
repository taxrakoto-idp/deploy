# Crunchy PGO operator

This wrapper deploys the official Crunchy Postgres for Kubernetes Helm chart.
Argo CD discovers this directory through the `platform-components`
ApplicationSet and deploys it as Application `pgo` in namespace `pgo`.

## Upstream dependency

- Chart: `oci://registry.developers.crunchydata.com/crunchydata/pgo`
- Chart and application version: `6.0.2`
- Upstream OCI digest: `sha256:161c722234b0824771e36773f279f2cf228c5314b094736419a0d57e15f3d710`
- Installation mode: cluster-wide
- Operator replicas: one
- Debug logging: disabled

`Chart.lock` records the resolved dependency and `charts/pgo-6.0.2.tgz` makes
the Git revision self-contained for Argo CD.

PGO includes a multi-megabyte `PostgresCluster` CRD. The coordinating Argo CD
ApplicationSet enables server-side apply so Kubernetes does not try to store
the full CRD in the client-side `last-applied-configuration` annotation.

## Validate

```bash
helm dependency build operators/pgo
helm lint operators/pgo
helm template pgo operators/pgo \
  --namespace pgo \
  --include-crds
```

## Upgrade

1. Change the dependency version and `appVersion` in `Chart.yaml`.
2. Review the upstream release notes and default values.
3. Run `helm dependency update operators/pgo`.
4. Review the changed `Chart.lock` and packaged dependency.
5. Lint and render the wrapper before pushing it.

The upstream chart retains its CRDs during Helm uninstall. Before removing PGO,
delete or deliberately preserve every managed `PostgresCluster`, then review
the remaining `postgres-operator.crunchydata.com` CRDs separately.
