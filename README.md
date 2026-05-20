# local-stack

A minikube-hosted demo of a modern, GitOps-driven cloud-native platform: **Argo CD + Istio + Keycloak + Tekton** with a UI-bearing sample app that rides the full pipeline (build → deploy → mTLS → SSO).

## Prerequisites

- Docker
- minikube (>= 1.38)
- kubectl, helm
- terraform (>= 1.6)
- A git repo you can push this directory to (GitHub, GitLab, etc.) — Argo CD pulls manifests from it.

## Bootstrap

1. **Start the cluster** (you control this — Terraform doesn't):

   ```bash
   minikube start \
     --profile=local-stack \
     --cpus=3 --memory=5500m \
     --driver=docker \
     --addons=metrics-server,registry
   ```

2. **Push this repo somewhere Argo can read it** (GitHub/GitLab/etc.).

3. **Configure Terraform** with your repo URL:

   ```bash
   cd bootstrap
   cp terraform.tfvars.example terraform.tfvars
   $EDITOR terraform.tfvars   # set repo_url
   ```

4. **Apply**:

   ```bash
   terraform init
   terraform apply
   ```

   This installs Argo CD and applies the root App-of-Apps. After it exits, Argo owns the cluster.

5. **Open the Argo UI**:

   ```bash
   kubectl port-forward -n argocd svc/argo-cd-argocd-server 8080:80
   # http://localhost:8080  (user: admin)
   terraform -chdir=bootstrap output -raw argocd_admin_password
   ```

## Layout

```text
bootstrap/   Terraform: installs Argo CD + applies root App-of-Apps
  root/      Child Applications discovered by the root App (Phase 2+)
platform/    Argo Applications for Istio, Keycloak, Tekton, Postgres
apps/        Argo Application + manifests for the sample app (taskboard)
pipelines/   Tekton tasks + pipeline definitions
src/         Sample app source (Go + React)
```

Once the platform Applications are in place, the demo flow is:
**code change → Tekton pipeline builds & pushes image → Argo detects manifest change → redeploys behind Istio gateway with mTLS, fronted by Keycloak SSO.**

## Tear down

```bash
terraform -chdir=bootstrap destroy   # removes Argo + everything Argo manages
minikube delete -p local-stack       # nukes the cluster (your call)
```
