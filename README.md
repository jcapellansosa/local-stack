# local-stack

A minikube-hosted demo of a modern, GitOps-driven cloud-native platform: **Argo CD + Istio + Keycloak + Tekton** with a UI-bearing sample app that rides the full pipeline (build → deploy → mTLS → SSO).

## Prerequisites

- Docker
- minikube (>= 1.38)
- kubectl, helm
- A git repo you can push this directory to (GitHub/GitLab/etc.) — Argo CD pulls manifests from it.

## Bootstrap

Every step is a command you run yourself. Nothing is hidden in a script.

### 1. Start the cluster

You control the cluster lifecycle. Automation only touches what runs *inside* it.

```bash
minikube start \
  --profile=local-stack \
  --cpus=3 --memory=5500m \
  --driver=docker \
  --addons=metrics-server,registry
```

### 2. Push this repo somewhere Argo CD can read it

GitHub, GitLab, or any HTTPS git URL. Note the URL — you'll pass it in step 4.

### 3. Install Argo CD

Adds the Argo Helm repo, then installs the `argo-cd` chart into the `argocd` namespace using the values file at [bootstrap/values/argocd.yaml](bootstrap/values/argocd.yaml). `--wait` blocks until pods are ready.

```bash
helm --kube-context local-stack repo add argo https://argoproj.github.io/argo-helm
helm --kube-context local-stack repo update argo

kubectl --context local-stack get ns argocd >/dev/null 2>&1 \
  || kubectl --context local-stack create namespace argocd

helm --kube-context local-stack upgrade --install argo-cd argo/argo-cd \
  --namespace argocd \
  --version 9.5.14 \
  --values bootstrap/values/argocd.yaml \
  --wait --timeout 10m
```

If the helm download fails with `connection reset` (the Argo Helm repo is sometimes flaky), just re-run the `helm upgrade --install` command. It's idempotent.

**Behind a TLS-intercepting proxy?** If Argo's repo-server later errors with `x509: certificate signed by unknown authority` when fetching from a chart/git host, your network is presenting MITM'd certs and Argo doesn't trust your corporate CA. Copy [bootstrap/values/argocd-tls.local.yaml.example](bootstrap/values/argocd-tls.local.yaml.example) (if present) — or create `bootstrap/values/argocd-tls.local.yaml` (gitignored) — listing each intercepted hostname with your CA's PEM, then add `--values bootstrap/values/argocd-tls.local.yaml` to the `helm upgrade` above and re-run it. Add a new entry to that file every time you encounter the error from a new hostname.

### 4. Install the root App-of-Apps

Installs the `argocd-apps` chart with one Argo `Application` that points back at this repo's [bootstrap/root/](bootstrap/root/) directory. From this point on, Argo CD reconciles everything else from Git.

Replace `https://github.com/you/local-stack.git` with your repo URL from step 2.

```bash
helm --kube-context local-stack upgrade --install root-app argo/argocd-apps \
  --namespace argocd \
  --version 2.0.5 \
  --values bootstrap/values/root-app.yaml \
  --set applications.root.source.repoURL=https://github.com/you/local-stack.git \
  --set applications.root.source.targetRevision=main \
  --wait
```

### 5. Open the Argo CD UI

```bash
# in one shell — port-forward the Argo server
kubectl --context local-stack port-forward -n argocd svc/argo-cd-argocd-server 8080:80

# in another shell — print the admin password
kubectl --context local-stack -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

Browse to <http://localhost:8080> and log in as `admin` with the password from above.

The root App points at `bootstrap/root/`. Until Phase 2 fills that directory, it'll be Synced with 0 resources — that's expected.

## Useful commands

```bash
# list helm releases + all Argo Applications
helm --kube-context local-stack list -n argocd
kubectl --context local-stack get applications.argoproj.io -n argocd

# uninstall the bootstrap (cluster stays up; Argo cleans up child apps via finalizers)
helm --kube-context local-stack uninstall root-app -n argocd
helm --kube-context local-stack uninstall argo-cd  -n argocd
```

`minikube delete -p local-stack` is yours to run when you want a fully clean slate.

## Layout

```text
bootstrap/
  values/          Helm values files (argocd.yaml, root-app.yaml)
  root/            Child Applications discovered by the root App (Phase 2+)
platform/          Argo Applications for Istio, Keycloak, Tekton, Postgres
apps/              Argo Application + manifests for the sample app (taskboard)
pipelines/         Tekton tasks + pipeline definitions
src/               Sample app source (Go + React)
```

The end-to-end demo flow once everything is in place:
**code change → Tekton pipeline builds & pushes image → Argo detects manifest change → redeploys behind Istio gateway with mTLS, fronted by Keycloak SSO.**
