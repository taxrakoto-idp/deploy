# Gitea Actions runner

This wrapper deploys one organization-level runner with the official Gitea
Actions Helm chart. Argo CD discovers `tools/gitea-actions`, deploys it in the
`gitea` namespace after Gitea is Healthy, and supplies the registration token
created by the Gitea `PostSync` initializer.

## Pinned dependency

- Chart: `actions`
- Chart repository: `https://dl.gitea.com/charts/`
- Chart version: `0.1.2`
- Runner image: `docker.gitea.com/runner:2.0.1`
- Docker-in-Docker image: `docker.io/docker:29.5.2-dind-rootless`

`Chart.lock` and `charts/actions-0.1.2.tgz` make the Argo CD revision
self-contained.

## Runtime contract

The runner connects to `http://gitea-http.gitea.svc:3000` and reads the
`runner-token` key from `gitea-actions-runner-token`. Both the runner and the
Secret are in the `gitea` namespace; the credential is never stored in Git.

The installation intentionally runs one runner with one concurrent job and a
30-minute job timeout. The runner requests 50m CPU and 128 MiB memory; its
Docker-in-Docker sidecar requests 250m CPU and 512 MiB memory. Explicit limits
bound both containers and each job container. A 1 Gi `nfs-csi` volume retains
runner registration data.

The Docker daemon uses the chart's rootless mode. Its Kubernetes container is
still privileged as required by this official chart, but it uses an isolated
`emptyDir` socket rather than the Kubernetes node's Docker socket. The pod's
dedicated ServiceAccount does not mount a Kubernetes API token and has no RBAC
permissions.

## Validate

```bash
helm dependency build tools/gitea-actions
helm lint tools/gitea-actions
helm template gitea-actions tools/gitea-actions --namespace gitea
```

After Argo CD deploys the component:

```bash
kubectl --namespace gitea rollout status statefulset/gitea-actions-runner
kubectl --namespace gitea get pod,pvc
```
