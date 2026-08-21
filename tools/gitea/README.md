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

Gitea Actions is enabled in the application configuration. Its runner is
installed separately by `tools/gitea-actions` after this package becomes
Healthy and its `PostSync` initializer has generated the registration token.

## Platform initialization

After Gitea becomes Healthy, an idempotent Argo CD `PostSync` hook initializes
the installation-local platform resources through the Gitea API:

- public `demo-idp` organization;
- purpose-specific `backstage-bot`, `gitops-bot`, and `argocd-reader`
  technical users;
- `scaffolders`, `gitops-writers`, and `gitops-readers` teams;
- private `demo-idp/application-gitops` repository initialized on `main`;
- purpose-scoped API tokens for the three technical users;
- an organization-level Gitea Actions runner registration token.

The Job reads the bootstrap administrator account only while it runs. It
stores generated credentials in `gitea-backstage-bot`, `gitea-gitops-bot`,
`gitea-argocd-reader`, and `gitea-actions-runner-token` Kubernetes Secrets.
Existing resources and Secret values are reused on later syncs, and credential
values are never logged or stored in Git.

These accounts are Gitea technical users, not Kubernetes ServiceAccounts:

- `backstage-bot` publishes the application source repositories created by
  Backstage Software Templates. It belongs to the `scaffolders` team, can
  create repositories in `demo-idp`, and receives an API token with
  `write:organization`, `write:repository`, and `read:user` scopes.
- `gitops-bot` proposes deployment changes in the existing private
  `demo-idp/application-gitops` repository. It belongs to the
  `gitops-writers` team, cannot create organization repositories, and receives
  an API token with `read:organization`, `write:repository`, and `read:user`
  scopes. The planned custom Backstage action will use this identity to create
  a branch, commit `apps/<environment>/<application>/values.yaml`, and open a
  pull request.
- `argocd-reader` belongs to the `gitops-readers` team, which has read-only
  `repo.code` access specifically to `application-gitops`. Its API token has
  only `read:organization`, `read:repository`, and `read:user` scopes.

### Argo CD repository credential

The initializer copies only the `argocd-reader` username and token into the
`application-gitops-repository` Secret in the `argocd` namespace. That Secret
is labeled `argocd.argoproj.io/secret-type: repository`, so the ApplicationSet
controller and repo-server use it for the private internal repository at:

```text
http://gitea-http.gitea.svc:3000/demo-idp/application-gitops.git
```

The initializer ServiceAccount receives `get` and `patch` permission only for
that named Secret in `argocd`; it cannot list Secrets or modify other Argo CD
credentials. Argo CD therefore never receives either write-capable bot token.

### Backstage credential selection

Software Templates must not accept a bot username or token as user input and
must not store credentials in `template.yaml` or its skeleton. The Backstage
backend selects the appropriate technical identity for each action.

The standard Gitea integration is configured with `backstage-bot`:

```yaml
integrations:
  gitea:
    - host: ${GITEA_HOST}
      baseUrl: ${GITEA_BASE_URL}
      username: ${GITEA_BACKSTAGE_USERNAME}
      password: ${GITEA_BACKSTAGE_TOKEN}
```

After `@backstage/plugin-scaffolder-backend-module-gitea` is installed and
registered in the Backstage backend, `publish:gitea` selects this integration
by the host in `repoUrl` and executes as `backstage-bot`:

```yaml
- id: publish
  name: Create application repository
  action: publish:gitea
  input:
    repoUrl: gitea.example?owner=demo-idp&repo=${{ parameters.name }}
    defaultBranch: main
    sourcePath: .
```

The Gitea integration does not switch identities per template step. The
planned GitOps pull-request action therefore needs a separate backend-only
configuration using `GITEA_GITOPS_TOKEN`. A template will pass only safe data
such as the environment, application name, target path, and generated values;
the custom backend action will inject `gitops-bot` credentials internally.

The generated Secrets currently live in the `gitea` namespace, while the
Backstage Pod lives in the `backstage` namespace. A Pod cannot consume a Secret
from another namespace. Before enabling these actions, synchronize only the
required bot usernames and tokens into a dedicated Secret in the `backstage`
namespace and expose them to the backend as environment variables. Do not
expose them to the frontend.

### Permission boundary to enforce

The current `scaffolders` team is created with
`includes_all_repositories=true`. As a result, `backstage-bot` currently also
has write access to `application-gitops`, despite the intended separation from
`gitops-bot`. Before connecting Backstage, change this team to exclude all
repositories by default and explicitly grant it access only to generated
application repositories. `gitops-bot` should be the only automation identity
allowed to modify `application-gitops`.

The Actions runner reads the `runner-token` key from
`gitea-actions-runner-token`. The Secret and runner both live in the `gitea`
namespace, avoiding cross-namespace credential distribution.

Verify initialization without displaying credentials:

```bash
kubectl --namespace gitea get secret \
  gitea-backstage-bot gitea-gitops-bot gitea-argocd-reader \
  gitea-actions-runner-token
kubectl --namespace argocd get secret application-gitops-repository
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
