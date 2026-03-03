package eco_namespace

import data.kubernetes.labels
import data.kubernetes.annotations

# Kubernetes 物件名稱：只允許 a-z0-9-，不得含 _ 或大寫
violation[{"msg": msg}] {
    input.review.object.metadata.name
    not re_match("^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", input.review.object.metadata.name)
    msg := sprintf("Kubernetes object name '%v' is invalid. Must match ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", [input.review.object.metadata.name])
}

# 必填 Labels
violation[{"msg": msg}] {
    mandatory_labels := {
        "app.kubernetes.io/name",
        "app.kubernetes.io/instance",
        "app.kubernetes.io/version",
        "app.kubernetes.io/component",
        "app.kubernetes.io/part-of",
        "softwareos-base/platform",
        "softwareos-base/environment",
        "softwareos-base/owner"
    }
    some i
    label := mandatory_labels[i]
    not input.review.object.metadata.labels[label]
    msg := sprintf("Missing mandatory label: %v", [label])
}

# app.kubernetes.io/part-of 必須是 softwareos-base
violation[{"msg": msg}] {
    input.review.object.metadata.labels["app.kubernetes.io/part-of"]
    input.review.object.metadata.labels["app.kubernetes.io/part-of"] != "softwareos-base"
    msg := sprintf("Label 'app.kubernetes.io/part-of' must be 'softwareos-base', but found '%v'", [input.review.object.metadata.labels["app.kubernetes.io/part-of"]])
}

# 環境值域：softwareos-base/environment 只能是 production|staging|development
violation[{"msg": msg}] {
    env := input.review.object.metadata.labels["softwareos-base/environment"]
    allowed_envs := {"production", "staging", "development"}
    not allowed_envs[env]
    msg := sprintf("Label 'softwareos-base/environment' has invalid value '%v'. Must be one of %v", [env, allowed_envs])
}

# 必填 Annotations
violation[{"msg": msg}] {
    mandatory_annotations := {
        "softwareos-base/uri",
        "softwareos-base/urn",
        "softwareos-base/governance-policy",
        "softwareos-base/audit-log-level"
    }
    some i
    annotation := mandatory_annotations[i]
    not input.review.object.metadata.annotations[annotation]
    msg := sprintf("Missing mandatory annotation: %v", [annotation])
}

# 審計等級值域：softwareos-base/audit-log-level 只能是 full|minimal
violation[{"msg": msg}] {
    audit_level := input.review.object.metadata.annotations["softwareos-base/audit-log-level"]
    allowed_audit_levels := {"full", "minimal"}
    not allowed_audit_levels[audit_level]
    msg := sprintf("Annotation 'softwareos-base/audit-log-level' has invalid value '%v'. Must be one of %v", [audit_level, allowed_audit_levels])
}

# URN 格式：必須匹配定義的語法
violation[{"msg": msg}] {
    urn := input.review.object.metadata.annotations["softwareos-base/urn"]
    not re_match("^urn:softwareos-base:[a-z0-9-]+:[a-z0-9-]+:[a-z0-9-]+:[a-z0-9-]+:((?:[0-9a-f]{8}-[0-9a-f]{4}-1[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12})|(?:sha256-[0-9a-f]{8,}))$", urn)
    msg := sprintf("Annotation 'softwareos-base/urn' has invalid format '%v'. Must match ^urn:softwareos-base:<type>:<platform>:<component>:<resource>:<uuidv1|sha256-...>$", [urn])
}

# URI 格式：必須匹配定義的語法
violation[{"msg": msg}] {
    uri := input.review.object.metadata.annotations["softwareos-base/uri"]
    not re_match("^softwareos-base://[a-z0-9-]+/[a-z0-9-]+/[a-z0-9-]+/.+(\\?.*)?$", uri)
    msg := sprintf("Annotation 'softwareos-base/uri' has invalid format '%v'. Must match ^softwareos-base://<type>/<platform>/<component>/<resource>[?...].$", [uri])
}
