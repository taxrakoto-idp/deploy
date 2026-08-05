# Portfolio deployments

This repository contains the desired Kubernetes state for portfolio
applications and platform tools. Argo CD watches the `main` branch and
automatically reconciles matching Helm charts with the cluster.

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
└── tools/
    ├── jenkins/
    │   ├── Chart.yaml
    │   ├── values.yaml
    │   └── templates/
    └── backstage/
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

## Platform tools

Every immediate directory under `tools/` must be a complete and valid Helm
chart:

```text
tools/<tool>/Chart.yaml
```

The directory name becomes both the Argo CD Application name and Kubernetes
namespace. For example, `tools/jenkins` is deployed as Application `jenkins`
into namespace `jenkins`.

Validate a tool before pushing it:

```bash
helm lint tools/jenkins
helm template jenkins tools/jenkins --namespace jenkins
```

## Synchronization behavior

The ApplicationSets enable:

- Automatic synchronization
- Self-healing when cluster resources drift from Git
- Automatic namespace creation
- Pruning of resources removed from Git
- Detection of resources managed by more than one Application

Removing a discovered `values.yaml` or a tool directory from `main` removes
its generated Argo CD Application and managed Kubernetes resources. Review
deletions carefully before pushing them.

## Secrets and cluster prerequisites

Do not commit credentials, private keys, tokens, or plain-text production
secrets. Reference an external secret manager or pre-created Kubernetes Secret
from Helm values instead.

Applications are responsible for declaring their runtime prerequisites. Before
enabling an optional chart feature, ensure its operator or cluster API exists;
examples include External Secrets, Gateway API, certificate management, and
PostgreSQL operators.

Namespace-scoped prerequisites, including image-pull Secrets and `SecretStore`
resources, must exist in each generated `<application>-<environment>` namespace.

## Check deployments

```bash
kubectl get applications --namespace argocd
kubectl get applicationsets --namespace argocd
```

Application health, synchronization history, rendered resources, and errors are
also available in the Argo CD UI.
