# local-stack bootstrap — installs Argo CD + the root App-of-Apps via helm.
# Argo CD then reconciles platform/, apps/, pipelines/ from the git repo.

KUBE_CONTEXT         ?= local-stack
NAMESPACE            ?= argocd
ARGOCD_CHART_VERSION ?= 9.5.14
ARGOCD_APPS_VERSION  ?= 2.0.5
REPO_URL             ?=
TARGET_REVISION      ?= main
RETRIES              ?= 5
RETRY_DELAY          ?= 4

HELM    := helm --kube-context $(KUBE_CONTEXT)
KUBECTL := kubectl --context $(KUBE_CONTEXT)

# Retry an arbitrary command up to RETRIES times with RETRY_DELAY between attempts.
# Usage: $(call retry,<command>)
define retry
	for i in $$(seq 1 $(RETRIES)); do \
	  echo ">>> attempt $$i/$(RETRIES): $(1)"; \
	  $(1) && exit 0; \
	  echo ">>> attempt $$i failed, sleeping $(RETRY_DELAY)s"; \
	  sleep $(RETRY_DELAY); \
	done; \
	echo "!!! gave up after $(RETRIES) attempts"; exit 1
endef

.PHONY: help up repos argo-cd root-app down password port-forward check-repo-url status

help:
	@echo "Targets:"
	@echo "  make up REPO_URL=https://github.com/you/local-stack.git"
	@echo "                    install Argo CD + root App-of-Apps"
	@echo "  make password     print the Argo CD admin password"
	@echo "  make port-forward open Argo CD UI on http://localhost:8080"
	@echo "  make status       list helm releases + the root Application"
	@echo "  make down         uninstall both helm releases"
	@echo ""
	@echo "Vars (with defaults): KUBE_CONTEXT=$(KUBE_CONTEXT) NAMESPACE=$(NAMESPACE)"
	@echo "                     ARGOCD_CHART_VERSION=$(ARGOCD_CHART_VERSION)"
	@echo "                     ARGOCD_APPS_VERSION=$(ARGOCD_APPS_VERSION)"
	@echo "                     TARGET_REVISION=$(TARGET_REVISION)"
	@echo "                     RETRIES=$(RETRIES) RETRY_DELAY=$(RETRY_DELAY)"

up: check-repo-url repos argo-cd root-app
	@echo ""
	@echo "Bootstrap complete."
	@echo "  make password         # admin password"
	@echo "  make port-forward     # UI on http://localhost:8080"

repos:
	@$(HELM) repo add argo https://argoproj.github.io/argo-helm 2>/dev/null || true
	@$(call retry,$(HELM) repo update argo)

argo-cd:
	@$(KUBECTL) get ns $(NAMESPACE) >/dev/null 2>&1 || \
	  $(KUBECTL) create namespace $(NAMESPACE)
	@$(call retry,$(HELM) upgrade --install argo-cd argo/argo-cd \
	  --namespace $(NAMESPACE) \
	  --version $(ARGOCD_CHART_VERSION) \
	  --values bootstrap/values/argocd.yaml \
	  --wait --timeout 10m)

root-app: check-repo-url
	@$(call retry,$(HELM) upgrade --install root-app argo/argocd-apps \
	  --namespace $(NAMESPACE) \
	  --version $(ARGOCD_APPS_VERSION) \
	  --values bootstrap/values/root-app.yaml \
	  --set "applications[0].source.repoURL=$(REPO_URL)" \
	  --set "applications[0].source.targetRevision=$(TARGET_REVISION)" \
	  --wait)

check-repo-url:
	@if [ -z "$(REPO_URL)" ]; then \
	  echo "ERROR: REPO_URL is required. Example:"; \
	  echo "  make up REPO_URL=https://github.com/you/local-stack.git"; \
	  exit 1; \
	fi

password:
	@$(KUBECTL) -n $(NAMESPACE) get secret argocd-initial-admin-secret \
	  -o jsonpath='{.data.password}' | base64 -d; echo

port-forward:
	@echo "Argo CD UI -> http://localhost:8080  (user: admin)"
	@$(KUBECTL) port-forward -n $(NAMESPACE) svc/argo-cd-argocd-server 8080:80

status:
	@$(HELM) list -n $(NAMESPACE)
	@echo ""
	@$(KUBECTL) get applications.argoproj.io -n $(NAMESPACE)

down:
	-$(HELM) uninstall root-app -n $(NAMESPACE)
	-$(HELM) uninstall argo-cd  -n $(NAMESPACE)
