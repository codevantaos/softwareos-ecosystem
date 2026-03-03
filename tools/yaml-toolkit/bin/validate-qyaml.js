#!/usr/bin/env node
/**
 * softwareos-base YAML Toolkit v8
 * Schema Validator — validate-qyaml.js
 *
 * Usage:
 *   node validate-qyaml.js [file.qyaml]            # validate single file
 *   node validate-qyaml.js --dir backend/k8s        # validate directory recursively
 *   node validate-qyaml.js --stdin                  # read from stdin
 *   node validate-qyaml.js --json                   # output JSON report
 *   node validate-qyaml.js --strict                 # exit 1 on warnings too
 *
 * Exit codes:
 *   0 — all checks passed
 *   1 — one or more ERRORS found
 *   2 — configuration / usage error
 */

"use strict";

const fs   = require("fs");
const path = require("path");
const yaml = require("js-yaml");

// ── CLI args ────────────────────────────────────────────────────────────────
const args       = process.argv.slice(2);
const outputJson = args.includes("--json");
const strict     = args.includes("--strict");
const fromStdin  = args.includes("--stdin");
const dirIndex   = args.indexOf("--dir");
const dirTarget  = dirIndex !== -1 ? args[dirIndex + 1] : null;
const fileTarget = args.find(a => !a.startsWith("--"));

// ── Colors ──────────────────────────────────────────────────────────────────
const C = {
  red:    s => outputJson ? s : `\x1b[91m${s}\x1b[0m`,
  yellow: s => outputJson ? s : `\x1b[93m${s}\x1b[0m`,
  green:  s => outputJson ? s : `\x1b[92m${s}\x1b[0m`,
  teal:   s => outputJson ? s : `\x1b[96m${s}\x1b[0m`,
  dim:    s => outputJson ? s : `\x1b[2m${s}\x1b[0m`,
  bold:   s => outputJson ? s : `\x1b[1m${s}\x1b[0m`,
};

// ── Result builders ─────────────────────────────────────────────────────────
const err  = (code, msg, field = null) => ({ level: "ERROR",   code, message: msg, field });
const warn = (code, msg, field = null) => ({ level: "WARNING", code, message: msg, field });
const info = (code, msg, field = null) => ({ level: "INFO",    code, message: msg, field });

// ── UUID v4 regex ────────────────────────────────────────────────────────────
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ISO8601 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/;

// ════════════════════════════════════════════════════════════════════════════
// RULE DEFINITIONS  (55 rules across 8 groups)
// ════════════════════════════════════════════════════════════════════════════
function runRules(raw, doc, filename) {
  const results = [];
  const push    = r => results.push(r);

  // ── GROUP 1: File-level / structural ──────────────────────────────────────
  if (raw.includes("%YAML")) {
    push(err("S001", "%YAML directive found — not GKE-compatible. Remove it and start with ---", "file"));
  }
  if (!raw.trimStart().startsWith("---")) {
    push(err("S002", "Document must start with --- (YAML document marker)", "file"));
  }
  if (raw.includes("<<:")) {
    push(warn("S003", "YAML merge key (<<:) found — not supported in all parsers. Expand inline.", "file"));
  }
  const boolBad = /\b(yes|no|on|off|True|False|TRUE|FALSE)\b/;
  if (boolBad.test(raw)) {
    push(warn("S004", "Non-standard boolean found (yes/no/on/off/True etc.). Use true/false only.", "file"));
  }
  const tabLine = raw.split("\n").findIndex(l => l.match(/^\t/));
  if (tabLine !== -1) {
    push(err("S005", `Tab character used for indentation at line ${tabLine + 1}. Use 2 spaces.`, "file"));
  }
  if (!raw.includes("governance_companion") && !raw.includes("document_metadata")) {
    push(err("S006", "No governance_companion / document_metadata block found. All .qyaml files must include the four governance blocks.", "file"));
  }

  // ── GROUP 2: document_metadata ────────────────────────────────────────────
  // Find metadata — may be nested under governance_companion or top-level
  const dm = doc?.governance_companion?.document_metadata ?? doc?.document_metadata;

  if (!dm) {
    push(err("M001", "document_metadata block is missing", "document_metadata"));
  } else {
    if (!dm.unique_id) {
      push(err("M002", "unique_id is missing", "document_metadata.unique_id"));
    } else if (!UUID_V4.test(dm.unique_id)) {
      push(err("M003", `unique_id '${dm.unique_id}' is not a valid UUID v4`, "document_metadata.unique_id"));
    }

    if (!dm.target_system) {
      push(err("M004", "target_system is missing", "document_metadata.target_system"));
    }

    if (!Array.isArray(dm.cross_layer_binding)) {
      push(err("M005", "cross_layer_binding must be an array (use [] if empty)", "document_metadata.cross_layer_binding"));
    }

    if (dm.schema_version !== "v8") {
      push(err("M006", `schema_version must be exactly "v8", got "${dm.schema_version}"`, "document_metadata.schema_version"));
    }

    if (dm.generated_by !== "yaml-toolkit-v8") {
      push(err("M007", `generated_by must be "yaml-toolkit-v8", got "${dm.generated_by}"`, "document_metadata.generated_by"));
    }

    if (!dm.created_at) {
      push(err("M008", "created_at is missing", "document_metadata.created_at"));
    } else if (!ISO8601.test(dm.created_at)) {
      push(warn("M009", `created_at '${dm.created_at}' is not ISO 8601 UTC (should end with Z)`, "document_metadata.created_at"));
    }

    // Extra fields check
    const allowedDm = ["unique_id","target_system","cross_layer_binding","schema_version","generated_by","created_at"];
    Object.keys(dm).filter(k => !allowedDm.includes(k)).forEach(k => {
      push(warn("M010", `Unknown field '${k}' in document_metadata — extra fields are not allowed`, `document_metadata.${k}`));
    });
  }

  // ── GROUP 3: governance_info ──────────────────────────────────────────────
  const gi = doc?.governance_companion?.governance_info ?? doc?.governance_info;

  if (!gi) {
    push(err("G001", "governance_info block is missing", "governance_info"));
  } else {
    if (!gi.owner) push(err("G002", "owner is missing", "governance_info.owner"));

    if (!Array.isArray(gi.approval_chain)) {
      push(err("G003", "approval_chain must be an array", "governance_info.approval_chain"));
    } else if (gi.approval_chain.length === 0) {
      push(warn("G004", "approval_chain is empty — should contain at least one approver", "governance_info.approval_chain"));
    }

    if (!Array.isArray(gi.compliance_tags)) {
      push(err("G005", "compliance_tags must be an array", "governance_info.compliance_tags"));
    } else if (!gi.compliance_tags.includes("yaml-toolkit-v8")) {
      push(warn("G006", "compliance_tags should include 'yaml-toolkit-v8'", "governance_info.compliance_tags"));
    }

    if (!gi.lifecycle_policy) {
      push(err("G007", "lifecycle_policy is missing", "governance_info.lifecycle_policy"));
    } else if (!["standard","strict","experimental"].includes(gi.lifecycle_policy)) {
      push(warn("G008", `lifecycle_policy '${gi.lifecycle_policy}' is not a recognised value (standard|strict|experimental)`, "governance_info.lifecycle_policy"));
    }

    const allowedGi = ["owner","approval_chain","compliance_tags","lifecycle_policy"];
    Object.keys(gi).filter(k => !allowedGi.includes(k)).forEach(k => {
      push(warn("G009", `Unknown field '${k}' in governance_info`, `governance_info.${k}`));
    });
  }

  // ── GROUP 4: registry_binding ─────────────────────────────────────────────
  const rb = doc?.governance_companion?.registry_binding ?? doc?.registry_binding;

  if (!rb) {
    push(err("R001", "registry_binding block is missing", "registry_binding"));
  } else {
    if (!rb.service_endpoint) {
      push(err("R002", "service_endpoint is missing", "registry_binding.service_endpoint"));
    } else if (!/^https?:\/\//.test(rb.service_endpoint)) {
      push(err("R003", `service_endpoint must start with http:// or https://, got '${rb.service_endpoint}'`, "registry_binding.service_endpoint"));
    }

    const validProtocols = ["consul","etcd","eureka"];
    if (!rb.discovery_protocol) {
      push(err("R004", "discovery_protocol is missing", "registry_binding.discovery_protocol"));
    } else if (!validProtocols.includes(rb.discovery_protocol)) {
      push(err("R005", `discovery_protocol must be one of [${validProtocols.join(", ")}], got '${rb.discovery_protocol}'`, "registry_binding.discovery_protocol"));
    }

    if (!rb.health_check_path) {
      push(err("R006", "health_check_path is missing", "registry_binding.health_check_path"));
    } else if (!rb.health_check_path.startsWith("/")) {
      push(err("R007", `health_check_path must start with /, got '${rb.health_check_path}'`, "registry_binding.health_check_path"));
    }

    if (rb.registry_ttl === undefined || rb.registry_ttl === null) {
      push(err("R008", "registry_ttl is missing", "registry_binding.registry_ttl"));
    } else if (typeof rb.registry_ttl !== "number" || rb.registry_ttl <= 0) {
      push(err("R009", `registry_ttl must be a positive integer (seconds), got '${rb.registry_ttl}'`, "registry_binding.registry_ttl"));
    }

    const allowedRb = ["service_endpoint","discovery_protocol","health_check_path","registry_ttl"];
    Object.keys(rb).filter(k => !allowedRb.includes(k)).forEach(k => {
      push(warn("R010", `Unknown field '${k}' in registry_binding`, `registry_binding.${k}`));
    });
  }

  // ── GROUP 5: vector_alignment_map ─────────────────────────────────────────
  const vm = doc?.governance_companion?.vector_alignment_map ?? doc?.vector_alignment_map;

  if (!vm) {
    push(err("V001", "vector_alignment_map block is missing", "vector_alignment_map"));
  } else {
    if (vm.alignment_model !== "quantum-bert-xxl-v1") {
      push(err("V002", `alignment_model must be "quantum-bert-xxl-v1", got "${vm.alignment_model}"`, "vector_alignment_map.alignment_model"));
    }

    const validDims = [1024, 2048, 4096];
    if (!vm.dim) {
      push(warn("V003", "dim is missing — expected 1024, 2048, or 4096", "vector_alignment_map.dim"));
    } else if (!validDims.includes(vm.dim)) {
      push(err("V004", `dim must be one of [${validDims.join(", ")}], got ${vm.dim}`, "vector_alignment_map.dim"));
    }

    if (vm.tolerance === undefined) {
      push(warn("V005", "tolerance is missing — expected float between 0.0001 and 0.005", "vector_alignment_map.tolerance"));
    } else if (vm.tolerance < 0.0001 || vm.tolerance > 0.005) {
      push(err("V006", `tolerance ${vm.tolerance} is outside allowed range [0.0001, 0.005]`, "vector_alignment_map.tolerance"));
    }

    if (!Array.isArray(vm.coherence_vector)) {
      push(err("V007", "coherence_vector must be an array of floats", "vector_alignment_map.coherence_vector"));
    } else if (vm.coherence_vector.length < 8) {
      push(err("V008", `coherence_vector must contain at least 8 values, got ${vm.coherence_vector.length}`, "vector_alignment_map.coherence_vector"));
    } else {
      const nonFloat = vm.coherence_vector.find(v => typeof v !== "number");
      if (nonFloat !== undefined) {
        push(err("V009", `coherence_vector contains non-numeric value: ${nonFloat}`, "vector_alignment_map.coherence_vector"));
      }
      const outOfRange = vm.coherence_vector.find(v => v < 0 || v > 1);
      if (outOfRange !== undefined) {
        push(warn("V010", `coherence_vector value ${outOfRange} is outside normalised range [0, 1]`, "vector_alignment_map.coherence_vector"));
      }
    }

    if (!Array.isArray(vm.function_keyword) || vm.function_keyword.length === 0) {
      push(err("V011", "function_keyword must be a non-empty array of strings", "vector_alignment_map.function_keyword"));
    }

    if (!vm.contextual_binding) {
      push(err("V012", "contextual_binding is missing", "vector_alignment_map.contextual_binding"));
    } else if (!/^.+ -> \[.*\]$/.test(vm.contextual_binding)) {
      push(warn("V013", `contextual_binding '${vm.contextual_binding}' should follow pattern: "service -> [dep1, dep2]"`, "vector_alignment_map.contextual_binding"));
    }

    const allowedVm = ["alignment_model","dim","tolerance","coherence_vector","function_keyword","contextual_binding"];
    Object.keys(vm).filter(k => !allowedVm.includes(k)).forEach(k => {
      push(warn("V014", `Unknown field '${k}' in vector_alignment_map`, `vector_alignment_map.${k}`));
    });
  }

  // ── GROUP 6: K8s payload rules ────────────────────────────────────────────
  if (doc?.kind === "Deployment") {
    const meta  = doc.metadata;
    const spec  = doc.spec;
    const tpl   = spec?.template;
    const cntrs = tpl?.spec?.containers ?? [];

    if (!meta?.labels?.["generated-by"]) {
      push(err("K001", "Deployment metadata.labels must include 'generated-by: yaml-toolkit-v8'", "metadata.labels.generated-by"));
    } else if (meta.labels["generated-by"] !== "yaml-toolkit-v8") {
      push(err("K002", `generated-by label must be 'yaml-toolkit-v8', got '${meta.labels["generated-by"]}'`, "metadata.labels.generated-by"));
    }

    if (!meta?.namespace) {
      push(warn("K003", "metadata.namespace is missing — will default to 'default' namespace", "metadata.namespace"));
    }

    if (!tpl?.spec?.serviceAccountName) {
      push(warn("K004", "spec.template.spec.serviceAccountName is missing — use a dedicated ServiceAccount per service", "spec.template.spec.serviceAccountName"));
    }

    cntrs.forEach((c, i) => {
      const prefix = `spec.template.spec.containers[${i}]`;
      if (!c.livenessProbe)  push(err("K005", `Container '${c.name}' is missing livenessProbe`, `${prefix}.livenessProbe`));
      if (!c.readinessProbe) push(err("K006", `Container '${c.name}' is missing readinessProbe`, `${prefix}.readinessProbe`));
      if (!c.resources?.requests) push(err("K007", `Container '${c.name}' is missing resources.requests`, `${prefix}.resources.requests`));
      if (!c.resources?.limits)   push(err("K008", `Container '${c.name}' is missing resources.limits`, `${prefix}.resources.limits`));

      if (c.resources?.requests && c.resources?.limits) {
        const parseMem = s => parseInt((s ?? "0").replace(/[^0-9]/g,""));
        const reqMem = parseMem(c.resources.requests.memory);
        const limMem = parseMem(c.resources.limits.memory);
        if (limMem > 0 && limMem < reqMem) {
          push(err("K009", `Container '${c.name}': resources.limits.memory (${c.resources.limits.memory}) < requests.memory (${c.resources.requests.memory})`, `${prefix}.resources`));
        }
      }

      const hasSecretRef = (c.envFrom ?? []).some(e => e.secretRef);
      if (!hasSecretRef) {
        push(warn("K010", `Container '${c.name}' has no envFrom.secretRef — secrets should be injected via Kubernetes Secret`, `${prefix}.envFrom`));
      }

      const secretKeys = (c.env ?? []).filter(e =>
        /_KEY$|_SECRET$|_PASSWORD$|_TOKEN$|_CREDENTIAL$/i.test(e.name)
      );
      if (secretKeys.length > 0) {
        push(err("K011", `Container '${c.name}' has plaintext secret env vars: [${secretKeys.map(e=>e.name).join(", ")}]. Move to Kubernetes Secret.`, `${prefix}.env`));
      }

      if (spec?.replicas !== undefined && spec.replicas < 1) {
        push(err("K012", `spec.replicas is ${spec.replicas} — minimum is 1`, "spec.replicas"));
      }
    });
  }

  // ── GROUP 7: Docker Compose payload ───────────────────────────────────────
  if (doc?.services) {
    Object.entries(doc.services).forEach(([svcName, svc]) => {
      if (!svc.healthcheck) {
        push(warn("D001", `Docker service '${svcName}' is missing healthcheck — add one for production readiness`, `services.${svcName}.healthcheck`));
      }
      if (!svc.image && !svc.build) {
        push(err("D002", `Docker service '${svcName}' has neither image nor build specified`, `services.${svcName}`));
      }
      const secretKeys = Object.keys(svc.environment ?? {}).filter(k =>
        /_KEY$|_SECRET$|_PASSWORD$|_TOKEN$|_CREDENTIAL$/i.test(k)
      );
      if (secretKeys.length > 0) {
        push(warn("D003", `Docker service '${svcName}' has potential secret env vars: [${secretKeys.join(", ")}]. Use Docker Secrets or .env file.`, `services.${svcName}.environment`));
      }
      if (!(svc.labels ?? {})["generated-by"]) {
        push(warn("D004", `Docker service '${svcName}' is missing label 'generated-by: yaml-toolkit-v8'`, `services.${svcName}.labels`));
      }
    });
  }

  // ── GROUP 8: Security / supply-chain ──────────────────────────────────────
  const images = [];
  if (doc?.spec?.template?.spec?.containers) {
    doc.spec.template.spec.containers.forEach(c => { if (c.image) images.push(c.image); });
  }
  if (doc?.services) {
    Object.values(doc.services).forEach(s => { if (s.image) images.push(s.image); });
  }
  images.forEach(img => {
    if (img.endsWith(":latest")) {
      push(warn("SC001", `Image '${img}' uses ':latest' tag — pin to a specific digest or semantic version for reproducible deployments`, "image"));
    }
    if (!img.includes("/")) {
      push(warn("SC002", `Image '${img}' appears to be from Docker Hub (no registry prefix) — use a private registry (e.g. ghcr.io)`, "image"));
    }
  });

  return results;
}

// ════════════════════════════════════════════════════════════════════════════
// VALIDATE ONE FILE
// ════════════════════════════════════════════════════════════════════════════
function validateContent(raw, filename) {
  let doc;
  try {
    // Parse first document only (governance companion may be a second document)
    doc = yaml.load(raw);
  } catch (e) {
    return {
      file:    filename,
      valid:   false,
      errors:  1,
      warnings:0,
      results: [err("PARSE", `YAML parse error: ${e.message}`, "file")],
    };
  }

  const results  = runRules(raw, doc, filename);
  const errors   = results.filter(r => r.level === "ERROR").length;
  const warnings = results.filter(r => r.level === "WARNING").length;

  return {
    file:     filename,
    valid:    errors === 0 && (!strict || warnings === 0),
    errors,
    warnings,
    results,
  };
}

// ════════════════════════════════════════════════════════════════════════════
// RENDER REPORT
// ════════════════════════════════════════════════════════════════════════════
function renderReport(reports) {
  if (outputJson) {
    console.log(JSON.stringify({ reports, summary: buildSummary(reports) }, null, 2));
    return;
  }

  const totalErrors   = reports.reduce((s,r) => s + r.errors,   0);
  const totalWarnings = reports.reduce((s,r) => s + r.warnings, 0);
  const totalFiles    = reports.length;
  const failedFiles   = reports.filter(r => !r.valid).length;

  console.log(`\n${C.bold("softwareos-base YAML Toolkit v8 — Schema Validator")}`);
  console.log(C.dim("─".repeat(62)));

  reports.forEach(report => {
    const icon = report.valid ? C.green("✓") : C.red("✗");
    console.log(`\n${icon}  ${C.bold(report.file)}`);

    if (report.results.length === 0) {
      console.log(`   ${C.dim("All 55 rules passed")}`);
      return;
    }

    report.results.forEach(r => {
      const prefix =
        r.level === "ERROR"   ? C.red(`   [ERR  ${r.code}]`) :
        r.level === "WARNING" ? C.yellow(`   [WARN ${r.code}]`) :
                                C.teal(`   [INFO ${r.code}]`);
      const field = r.field ? C.dim(` · ${r.field}`) : "";
      console.log(`${prefix}  ${r.message}${field}`);
    });
  });

  console.log(`\n${C.dim("─".repeat(62))}`);
  console.log(`  Files checked : ${C.bold(String(totalFiles))}`);
  console.log(`  Failed files  : ${failedFiles > 0 ? C.red(String(failedFiles)) : C.green(String(failedFiles))}`);
  console.log(`  Errors        : ${totalErrors   > 0 ? C.red(String(totalErrors))   : C.green(String(totalErrors))}`);
  console.log(`  Warnings      : ${totalWarnings > 0 ? C.yellow(String(totalWarnings)) : C.green(String(totalWarnings))}`);

  if (totalErrors === 0 && totalWarnings === 0) {
    console.log(`\n  ${C.green(C.bold("✓ All checks passed"))}\n`);
  } else if (totalErrors === 0) {
    console.log(`\n  ${C.yellow(C.bold(`⚠ Passed with ${totalWarnings} warning(s)`))}\n`);
  } else {
    console.log(`\n  ${C.red(C.bold(`✗ Validation FAILED — ${totalErrors} error(s) found`))}\n`);
  }
}

function buildSummary(reports) {
  return {
    total_files:    reports.length,
    failed_files:   reports.filter(r => !r.valid).length,
    total_errors:   reports.reduce((s,r) => s + r.errors,   0),
    total_warnings: reports.reduce((s,r) => s + r.warnings, 0),
    passed:         reports.every(r => r.valid),
  };
}

// ════════════════════════════════════════════════════════════════════════════
// FILE COLLECTION
// ════════════════════════════════════════════════════════════════════════════
function collectFiles(dir) {
  const files = [];
  function walk(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      if (entry.name === "node_modules") continue;
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) { walk(full); continue; }
      if (entry.name.endsWith(".qyaml") || entry.name.endsWith(".yaml") || entry.name.endsWith(".yml")) {
        files.push(full);
      }
    }
  }
  walk(dir);
  return files;
}

// ════════════════════════════════════════════════════════════════════════════
// MAIN
// ════════════════════════════════════════════════════════════════════════════
function main() {
  // Check js-yaml is available
  try { require.resolve("js-yaml"); } catch {
    console.error("Missing dependency: npm install js-yaml");
    process.exit(2);
  }

  let reports = [];

  if (fromStdin) {
    const raw = fs.readFileSync("/dev/stdin", "utf8");
    reports = [validateContent(raw, "<stdin>")];
  } else if (dirTarget) {
    const files = collectFiles(dirTarget);
    if (files.length === 0) {
      console.error(`No .qyaml/.yaml files found in: ${dirTarget}`);
      process.exit(2);
    }
    reports = files.map(f => validateContent(fs.readFileSync(f, "utf8"), f));
  } else if (fileTarget) {
    if (!fs.existsSync(fileTarget)) {
      console.error(`File not found: ${fileTarget}`);
      process.exit(2);
    }
    reports = [validateContent(fs.readFileSync(fileTarget, "utf8"), fileTarget)];
  } else {
    console.error("Usage: validate-qyaml.js <file.qyaml> | --dir <path> | --stdin");
    process.exit(2);
  }

  renderReport(reports);

  const summary = buildSummary(reports);
  process.exit(summary.passed ? 0 : 1);
}

main();
