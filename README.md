# IDP deployments

This repository contains the desired Kubernetes state for IDP
applications, privileged Kubernetes operators, and platform tools. Argo CD
watches the `main` branch and automatically reconciles matching deployment
packages with the cluster.

The Argo CD installation and ApplicationSet definitions are maintained in the
separate `argo` repository.

## Repository structure

```text
.
├── apps/
│   └── react-chart/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── templates/
│       └── envs/
│           └── <environment>/
│               └── <application>/
│                   └── values.yaml
├── operators/
│   └── pgo/
│       ├── Chart.yaml
│       ├── Chart.lock
│       ├── values.yaml
│       └── charts/
└── tools/
    ├── postgres/
    │   └── <PostgresCluster manifests or chart>
    ├── backstage/
    │   ├── Chart.yaml
    │   ├── values.yaml
    │   └── templates/
    └── jenkins/
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
```

## Applications

`apps/react-chart` is a reusable Helm chart. Each application supplies its own
environment-specific overrides using this exact path convention:

```text
apps/react-chart/envs/<environment>/<application>/values.yaml
```

For example:

```text
apps/react-chart/envs/staging/my-first-react-app/values.yaml
```

Argo CD derives the deployment configuration from that path:

| Setting | Generated value |
| --- | --- |
| Argo CD Application | `my-first-react-app-staging` |
| Helm release name | `my-first-react-app` |
| Kubernetes namespace | `my-first-react-app-staging` |
| Environment label | `staging` |

The filename must be `values.yaml`. Files with other names are not discovered
by the applications ApplicationSet.

### Add an application

1. Create the environment and application directory.
2. Add a `values.yaml` containing only that application's overrides.
3. Validate the chart locally.
4. Commit and push the change to `main`.

Example validation:

```bash
helm lint apps/react-chart \
  --values apps/react-chart/envs/staging/my-first-react-app/values.yaml

helm template my-first-react-app apps/react-chart \
  --namespace my-first-react-app-staging \
  --values apps/react-chart/envs/staging/my-first-react-app/values.yaml
```

Adding a matching values file creates the Argo CD Application automatically.
Changing the file updates the deployment.

## Kubernetes operators

Every immediate directory under `operators/` is discovered by the
`platform-components` ApplicationSet:

```text
operators/<operator>/
```

Operator packages may contain Helm, Kustomize, or plain Kubernetes manifests
that Argo CD can render. The directory name becomes the Argo CD Application
name and Kubernetes namespace. For example, `operators/pgo` becomes
Application `pgo` in namespace `pgo`.

Operators use the privileged `operators` AppProject because they may need to
install CRDs and cluster-wide RBAC. Do not place ordinary workloads or
namespace-scoped tools in this directory.

PGO uses a wrapper chart around the pinned official Crunchy OCI chart. Validate
the wrapper and its CRDs before pushing it:

```bash
helm dependency build operators/pgo
helm lint operators/pgo
helm template pgo operators/pgo --namespace pgo --include-crds
```

## Platform tools

Every immediate directory under `tools/` must be a complete package that Argo
CD can render. Most tools use Helm:

```text
tools/<tool>/Chart.yaml
```

The directory name becomes both the Argo CD Application name and Kubernetes
namespace. For example, `tools/jenkins` is deployed as Application `jenkins`
into namespace `jenkins`. Operator and tool directory names must be unique
because both are managed by the same ApplicationSet.

Validate a Helm-based tool before pushing it:

```bash
helm lint tools/jenkins
helm template jenkins tools/jenkins --namespace jenkins
```

## Synchronization behavior

The application workloads ApplicationSet enables automatic synchronization.
The `platform-components` ApplicationSet uses Argo CD Progressive Syncs with a
`RollingSync` strategy. It reconciles components in this order:

1. Everything under `operators/`
2. `tools/postgres`
3. `tools/backstage`
4. All remaining directories under `tools/`

Each stage must become Healthy before the next stage begins. This ensures PGO
is available before the `PostgresCluster` is applied, and PostgreSQL is healthy
before Backstage is deployed. A PostgreSQL package must expose meaningful Argo
CD health, using a custom health check or a validation resource, before it is
added to this sequence.

Both ApplicationSets provide:

- Automatic Git reconciliation
- Correction when cluster resources drift from Git
- Automatic namespace creation
- Pruning of resources removed from Git
- Detection of resources managed by more than one Application

Platform components are deleted in reverse order so dependants are removed
before their operators. Removing a discovered `values.yaml`, operator
directory, or tool directory from `main` removes its generated Argo CD
Application and managed Kubernetes resources. Review deletions carefully
before pushing them.

## Label conventions

Generated Applications and namespaces use standard Kubernetes application
labels where possible:

| Label | Purpose |
| --- | --- |
| `app.kubernetes.io/managed-by` | Identifies Argo CD as the reconciler |
| `app.kubernetes.io/part-of` | Groups resources under `taxrakoto-idp` |
| `app.kubernetes.io/name` | Identifies an application workload |
| `app.kubernetes.io/component` | Identifies an operator or platform tool |
| `taxrakoto-idp.github.io/environment` | Identifies the deployment environment |
| `taxrakoto-idp.github.io/layer` | Separates operators from tools for ordered synchronization |

The `taxrakoto-idp.github.io` prefix is the project-specific label namespace.
It prevents generic custom labels from colliding with labels owned by other
controllers or public projects.

## Secrets and cluster prerequisites

Do not commit credentials, private keys, tokens, or plain-text production
secrets. Reference an external secret manager or pre-created Kubernetes Secret
from Helm values instead.

Applications are responsible for declaring their runtime prerequisites. Put
cluster-wide controllers such as External Secrets, Gateway API implementations,
certificate management, and PostgreSQL operators under `operators/`. Put the
namespace-scoped custom resources or consumers under `tools/`.

Namespace-scoped prerequisites, including image-pull Secrets and `SecretStore`
resources, must exist in each generated `<application>-<environment>` namespace.

## Check deployments

```bash
kubectl get applications --namespace argocd
kubectl get applicationsets --namespace argocd
```

Application health, synchronization history, rendered resources, and errors are
also available in the Argo CD UI.
