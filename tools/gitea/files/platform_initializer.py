import base64
import json
import os
import secrets
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request


GITEA_URL = os.environ["GITEA_URL"].rstrip("/")
GITEA_API = f"{GITEA_URL}/api/v1"
ADMIN_USERNAME = os.environ["GITEA_ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["GITEA_ADMIN_PASSWORD"]
ORGANIZATION = os.environ["ORGANIZATION"]
ORGANIZATION_FULL_NAME = os.environ["ORGANIZATION_FULL_NAME"]
ORGANIZATION_DESCRIPTION = os.environ["ORGANIZATION_DESCRIPTION"]
ORGANIZATION_VISIBILITY = os.environ["ORGANIZATION_VISIBILITY"]
GITOPS_REPOSITORY = os.environ["GITOPS_REPOSITORY"]
GITOPS_REPOSITORY_DESCRIPTION = os.environ["GITOPS_REPOSITORY_DESCRIPTION"]
GITOPS_REPOSITORY_PRIVATE = os.environ["GITOPS_REPOSITORY_PRIVATE"].lower() == "true"
BACKSTAGE_USERNAME = os.environ["BACKSTAGE_USERNAME"]
BACKSTAGE_EMAIL = os.environ["BACKSTAGE_EMAIL"]
BACKSTAGE_SECRET = os.environ["BACKSTAGE_SECRET"]
GITOPS_USERNAME = os.environ["GITOPS_USERNAME"]
GITOPS_EMAIL = os.environ["GITOPS_EMAIL"]
GITOPS_SECRET = os.environ["GITOPS_SECRET"]
RUNNER_SECRET = os.environ["RUNNER_SECRET"]
RUNNER_SECRET_KEY = os.environ["RUNNER_SECRET_KEY"]

SERVICE_ACCOUNT_DIRECTORY = "/var/run/secrets/kubernetes.io/serviceaccount"
with open(f"{SERVICE_ACCOUNT_DIRECTORY}/namespace", encoding="utf-8") as namespace_file:
    NAMESPACE = namespace_file.read().strip()
with open(f"{SERVICE_ACCOUNT_DIRECTORY}/token", encoding="utf-8") as token_file:
    KUBERNETES_TOKEN = token_file.read().strip()

KUBERNETES_API = (
    f"https://{os.environ['KUBERNETES_SERVICE_HOST']}:"
    f"{os.environ['KUBERNETES_SERVICE_PORT_HTTPS']}"
)
KUBERNETES_CONTEXT = ssl.create_default_context(
    cafile=f"{SERVICE_ACCOUNT_DIRECTORY}/ca.crt"
)


def request(
    url,
    method="GET",
    payload=None,
    expected=(200,),
    basic_auth=None,
    bearer_token=None,
    ssl_context=None,
    content_type="application/json",
):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = content_type
    if basic_auth:
        raw_credentials = f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")
        encoded_credentials = base64.b64encode(raw_credentials).decode("ascii")
        headers["Authorization"] = f"Basic {encoded_credentials}"
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    api_request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(
            api_request,
            context=ssl_context,
            timeout=20,
        ) as response:
            status = response.status
            response_body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        response_body = error.read()
    except urllib.error.URLError as error:
        raise RuntimeError(f"request to {url} failed: {error.reason}") from error

    if status not in expected:
        message = ""
        try:
            error_payload = json.loads(response_body.decode("utf-8"))
            message = error_payload.get("message", "")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            pass
        detail = f": {message}" if message else ""
        raise RuntimeError(f"{method} {url} returned HTTP {status}{detail}")

    if not response_body:
        return status, None
    return status, json.loads(response_body.decode("utf-8"))


def quoted(value):
    return urllib.parse.quote(value, safe="")


def gitea_request(path, **kwargs):
    kwargs.setdefault("basic_auth", (ADMIN_USERNAME, ADMIN_PASSWORD))
    return request(f"{GITEA_API}{path}", **kwargs)


def kubernetes_request(path, **kwargs):
    kwargs.setdefault("bearer_token", KUBERNETES_TOKEN)
    kwargs.setdefault("ssl_context", KUBERNETES_CONTEXT)
    return request(f"{KUBERNETES_API}{path}", **kwargs)


def wait_for_gitea():
    health_url = f"{GITEA_URL}/api/healthz"
    for _ in range(60):
        try:
            request(health_url, expected=(200,))
            print("Gitea health endpoint is ready")
            return
        except RuntimeError:
            time.sleep(5)
    raise RuntimeError("Gitea did not become healthy within five minutes")


def get_kubernetes_secret(name):
    path = f"/api/v1/namespaces/{quoted(NAMESPACE)}/secrets/{quoted(name)}"
    status, secret = kubernetes_request(path, expected=(200, 404))
    if status == 404:
        raise RuntimeError(f"required Kubernetes Secret {name} does not exist")

    decoded = {}
    for key, value in secret.get("data", {}).items():
        decoded[key] = base64.b64decode(value).decode("utf-8")
    return decoded


def patch_kubernetes_secret(name, values):
    path = f"/api/v1/namespaces/{quoted(NAMESPACE)}/secrets/{quoted(name)}"
    encoded_values = {
        key: base64.b64encode(value.encode("utf-8")).decode("ascii")
        for key, value in values.items()
    }
    kubernetes_request(
        path,
        method="PATCH",
        payload={"data": encoded_values},
        expected=(200,),
        content_type="application/merge-patch+json",
    )


def ensure_service_account_credentials(username, secret_name):
    values = get_kubernetes_secret(secret_name)
    updates = {}
    if values.get("username") != username:
        updates["username"] = username
    password = values.get("password")
    if not password:
        password = secrets.token_urlsafe(36)
        updates["password"] = password
    if updates:
        patch_kubernetes_secret(secret_name, updates)
        print(f"Reconciled credentials for {username}")
    return password, values.get("token")


def ensure_gitea_user(username, email, password):
    user_path = f"/users/{quoted(username)}"
    status, _ = gitea_request(user_path, expected=(200, 404))
    if status == 404:
        gitea_request(
            "/admin/users",
            method="POST",
            payload={
                "username": username,
                "email": email,
                "password": password,
                "full_name": username,
                "must_change_password": False,
                "restricted": True,
                "send_notify": False,
                "visibility": "private",
            },
            expected=(201,),
        )
        print(f"Created Gitea service account {username}")
        return

    gitea_request(
        f"/admin/users/{quoted(username)}",
        method="PATCH",
        payload={
            "active": True,
            "email": email,
            "login_name": username,
            "must_change_password": False,
            "password": password,
            "prohibit_login": False,
            "restricted": True,
            "source_id": 0,
            "visibility": "private",
        },
        expected=(200,),
    )
    print(f"Reconciled Gitea service account {username}")


def ensure_organization():
    status, _ = gitea_request(
        f"/orgs/{quoted(ORGANIZATION)}",
        expected=(200, 404),
    )
    if status == 200:
        print(f"Organization {ORGANIZATION} already exists")
        return

    gitea_request(
        f"/admin/users/{quoted(ADMIN_USERNAME)}/orgs",
        method="POST",
        payload={
            "username": ORGANIZATION,
            "full_name": ORGANIZATION_FULL_NAME,
            "description": ORGANIZATION_DESCRIPTION,
            "visibility": ORGANIZATION_VISIBILITY,
            "repo_admin_change_team_access": False,
        },
        expected=(201,),
    )
    print(f"Created organization {ORGANIZATION}")


def ensure_team(name, description, can_create_repositories, includes_all_repositories):
    _, teams = gitea_request(f"/orgs/{quoted(ORGANIZATION)}/teams?limit=50")
    for team in teams:
        if team["name"] == name:
            print(f"Team {name} already exists")
            return team["id"]

    _, team = gitea_request(
        f"/orgs/{quoted(ORGANIZATION)}/teams",
        method="POST",
        payload={
            "name": name,
            "description": description,
            "permission": "write",
            "can_create_org_repo": can_create_repositories,
            "includes_all_repositories": includes_all_repositories,
            "units": ["repo.code", "repo.actions", "repo.pulls", "repo.releases"],
        },
        expected=(201,),
    )
    print(f"Created team {name}")
    return team["id"]


def ensure_team_member(team_id, username):
    gitea_request(
        f"/teams/{team_id}/members/{quoted(username)}",
        method="PUT",
        expected=(204,),
    )
    print(f"Ensured {username} is a team member")


def ensure_repository():
    path = f"/repos/{quoted(ORGANIZATION)}/{quoted(GITOPS_REPOSITORY)}"
    status, _ = gitea_request(path, expected=(200, 404))
    if status == 200:
        print(f"Repository {ORGANIZATION}/{GITOPS_REPOSITORY} already exists")
        return

    gitea_request(
        f"/orgs/{quoted(ORGANIZATION)}/repos",
        method="POST",
        payload={
            "name": GITOPS_REPOSITORY,
            "description": GITOPS_REPOSITORY_DESCRIPTION,
            "private": GITOPS_REPOSITORY_PRIVATE,
            "auto_init": True,
            "default_branch": "main",
            "readme": "Default",
        },
        expected=(201,),
    )
    print(f"Created repository {ORGANIZATION}/{GITOPS_REPOSITORY}")


def ensure_team_repository(team_id):
    gitea_request(
        f"/teams/{team_id}/repos/{quoted(ORGANIZATION)}/{quoted(GITOPS_REPOSITORY)}",
        method="PUT",
        expected=(204,),
    )
    print(f"Granted team access to {ORGANIZATION}/{GITOPS_REPOSITORY}")


def ensure_access_token(username, password, secret_name, existing_token, scopes):
    if existing_token:
        print(f"Access token for {username} already exists in Kubernetes")
        return

    _, token_response = gitea_request(
        f"/users/{quoted(username)}/tokens",
        method="POST",
        payload={
            "name": "taxrakoto-idp-bootstrap",
            "scopes": scopes,
        },
        expected=(201,),
        basic_auth=(username, password),
    )
    token = token_response.get("sha1")
    if not token:
        raise RuntimeError(f"Gitea did not return the new token for {username}")
    patch_kubernetes_secret(secret_name, {"token": token})
    print(f"Stored access token for {username} in Kubernetes")


def ensure_runner_token():
    values = get_kubernetes_secret(RUNNER_SECRET)
    if values.get(RUNNER_SECRET_KEY):
        print("Organization runner registration token already exists in Kubernetes")
        return

    _, token_response = gitea_request(
        f"/orgs/{quoted(ORGANIZATION)}/actions/runners/registration-token",
        method="POST",
        expected=(200,),
    )
    token = token_response.get("token")
    if not token:
        raise RuntimeError("Gitea did not return an organization runner token")
    patch_kubernetes_secret(RUNNER_SECRET, {RUNNER_SECRET_KEY: token})
    print("Stored organization runner registration token in Kubernetes")


def main():
    wait_for_gitea()

    backstage_password, backstage_token = ensure_service_account_credentials(
        BACKSTAGE_USERNAME,
        BACKSTAGE_SECRET,
    )
    gitops_password, gitops_token = ensure_service_account_credentials(
        GITOPS_USERNAME,
        GITOPS_SECRET,
    )
    ensure_gitea_user(BACKSTAGE_USERNAME, BACKSTAGE_EMAIL, backstage_password)
    ensure_gitea_user(GITOPS_USERNAME, GITOPS_EMAIL, gitops_password)

    ensure_organization()
    scaffolders_team = ensure_team(
        "scaffolders",
        "Backstage repository publishers",
        can_create_repositories=True,
        includes_all_repositories=True,
    )
    gitops_team = ensure_team(
        "gitops-writers",
        "Writers for installation-local desired state",
        can_create_repositories=False,
        includes_all_repositories=False,
    )
    ensure_team_member(scaffolders_team, BACKSTAGE_USERNAME)
    ensure_team_member(gitops_team, GITOPS_USERNAME)

    ensure_repository()
    ensure_team_repository(gitops_team)

    ensure_access_token(
        BACKSTAGE_USERNAME,
        backstage_password,
        BACKSTAGE_SECRET,
        backstage_token,
        ["write:organization", "write:repository", "read:user"],
    )
    ensure_access_token(
        GITOPS_USERNAME,
        gitops_password,
        GITOPS_SECRET,
        gitops_token,
        ["read:organization", "write:repository", "read:user"],
    )
    ensure_runner_token()
    print("Gitea platform initialization completed successfully")


if __name__ == "__main__":
    main()
