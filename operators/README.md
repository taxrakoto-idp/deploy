# Kubernetes operators

Each immediate child directory is a deployable operator package discovered by
the Argo CD `platform-components` ApplicationSet:

```text
operators/<operator>/
```

Operators are deployed through the privileged `operators` AppProject before
platform tools. Keep ordinary applications and namespace-scoped tools out of
this directory.

PGO will be added at `operators/pgo`.
