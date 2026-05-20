variable "kube_config_path" {
  description = "Path to kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Kube context name (the minikube profile)"
  type        = string
  default     = "local-stack"
}

variable "argocd_chart_version" {
  description = "argo/argo-cd Helm chart version"
  type        = string
  default     = "9.5.14"
}

variable "argocd_namespace" {
  description = "Namespace Argo CD is installed into"
  type        = string
  default     = "argocd"
}

variable "repo_url" {
  description = "Git URL where the local-stack repo is pushed; Argo CD pulls manifests from here"
  type        = string
}

variable "target_revision" {
  description = "Git revision Argo CD tracks (branch, tag, or commit SHA)"
  type        = string
  default     = "HEAD"
}
