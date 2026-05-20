data "kubernetes_secret" "argocd_admin" {
  metadata {
    name      = "argocd-initial-admin-secret"
    namespace = var.argocd_namespace
  }

  depends_on = [helm_release.argocd]
}

output "argocd_admin_password" {
  description = "Argo CD admin password (auto-generated on first install)"
  value       = data.kubernetes_secret.argocd_admin.data["password"]
  sensitive   = true
}

output "argocd_port_forward" {
  description = "Run this to open the Argo CD UI on http://localhost:8080"
  value       = "kubectl port-forward -n ${var.argocd_namespace} svc/argo-cd-argocd-server 8080:80"
}

output "next_steps" {
  description = "What to do after `terraform apply` succeeds"
  value       = <<-EOT

    Argo CD is installed and the 'root' Application has been applied.

    1. Open the UI:
       $ ${"kubectl port-forward -n ${var.argocd_namespace} svc/argo-cd-argocd-server 8080:80"}
       Then browse http://localhost:8080  (user: admin, password: see `terraform output -raw argocd_admin_password`)

    2. The root App points at:
         repo: ${var.repo_url}
         rev:  ${var.target_revision}
         path: bootstrap/root/

       Until you populate that directory with child Application manifests (Phase 2),
       the root App will report Synced with 0 resources -- that's expected.
  EOT
}
