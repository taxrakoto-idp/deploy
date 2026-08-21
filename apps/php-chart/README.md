# Generic PHP application chart

This chart runs unbuilt PHP source from an installation-local Gitea repository
using an official public PHP image. An init container fetches the configured Git
revision into an `emptyDir`, and the PHP container mounts that source at
`/var/www/html` by default.

Backstage generates an application-specific values file; it does not generate
or copy this reusable chart. A minimal generated file is:

```yaml
image:
  tag: "8.4-apache"

source:
  repository: http://gitea-http.gitea.svc:3000/demo-idp/my-app.git
  revision: 0123456789abcdef0123456789abcdef01234567

env:
  APP_ENV: demo
  APP_MESSAGE: Hello from Backstage

containerPort: 80
service:
  port: 80
```

Use a supported Apache image tag for the zero-build golden path. Quote image
tags in YAML so values such as `8.0` are not parsed as numbers. A mutable major
tag such as `7` or `8` is not reproducible and may select an unsupported or
unexpected runtime; the Backstage form should offer a reviewed allow-list of
explicit tags.

Set `source.revision` to the commit SHA returned when the source repository is
created or updated. A mutable branch is accepted for experimentation, but a Pod
will not automatically restart when that branch moves.

Public Gitea repositories clone anonymously. For a private repository, set
`source.credentials.existingSecret` to a Secret in the application namespace
with `username` and `token` keys. Do not put credentials in a repository URL or
generated values file.

The default `php:<version>-apache` image listens on port 80. For a CLI image,
override the port and pass command arguments separately:

```yaml
image:
  tag: "8.4-cli"
command: ["php"]
args: ["-S", "0.0.0.0:8080", "-t", "/var/www/html"]
containerPort: 8080
service:
  port: 80
```

Validate changes from the `deploy` repository root:

```bash
helm lint apps/php-chart
helm template php-demo apps/php-chart --namespace php-demo
```
