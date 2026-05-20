# local-stack

A minikube-hosted demo of a modern, GitOps-driven cloud-native platform: **Argo CD + Istio + Keycloak + Tekton** with a UI-bearing sample app that rides the full pipeline (build → deploy → mTLS → SSO).

## Prerequisites

- Docker
- minikube (>= 1.38)
- kubectl, helm, make
- A git repo you can push this directory to (GitHub/GitLab/etc.) — Argo CD pulls manifests from it.

## Bootstrap

1. **Start the cluster** (you control this — automation doesn't touch the cluster lifecycle):

   ```bash
   minikube start \
     --profile=local-stack \
     --cpus=3 --memory=5500m \
     --driver=docker \
     --addons=metrics-server,registry
   ```

2. **Push this repo somewhere Argo can read it** (GitHub/GitLab/etc.).

3. **Install Argo CD + the root App-of-Apps**:

   ```bash
   make up REPO_URL=https://github.com/you/local-stack.git
   ```

   Two `helm upgrade --install` calls behind the scenes (`argo-cd` chart, then `argocd-apps` chart for the root App). Both wrapped in a retry loop because GitHub Pages can be flaky from some networks.

4. **Open the Argo UI**:

   ```bash
   make port-forward            # in one shell
   make password                # in another, copy the output
   # browse http://localhost:8080  (user: admin)
   ```

The root App points at `bootstrap/root/`. It'll be Synced with 0 resources until Phase 2 fills that directory.

## Other Make targets

```bash
make status         # helm releases + Argo Applications
make down           # uninstall both helm releases (cluster stays up)
make help           # list everything
```

`minikube delete -p local-stack` is yours to run when you want a fully clean slate.

## Layout

```text
Makefile           Bootstrap entry point (helm + kubectl)
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
