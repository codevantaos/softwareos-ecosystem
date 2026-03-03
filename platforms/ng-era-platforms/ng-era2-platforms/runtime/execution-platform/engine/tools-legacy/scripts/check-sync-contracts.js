//# @GL-governed
//# @GL-layer: GL90-99
//# @GL-semantic: archive-tools
//# @GL-audit-trail: ../../engine/governance/GL_SEMANTIC_ANCHOR.json
//#
//# GL Unified Charter Activated
// @GL-status: active

/**
 * SynergyMesh Sync Contract Checker
 * 
 * Validates that sync_softwareos-contracts between config files are maintained.
 * Ensures referential integrity across the configuration hierarchy.
 */

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

// Config dependency order (lower depends on higher)
const CONFIG_HIERARCHY = [
  'config/environment.yaml',
  'config/dependencies.yaml',
  'config/ai-constitution.yaml',
  'config/agents/team/virtual-experts.yaml',
  'config/safety-mechanisms.yaml'
];

// Sync softwareos-contracts define what each config can reference
const SYNC_CONTRACTS = {
  'dependencies.yaml': {
    can_reference: ['environment.yaml'],
    reference_fields: {
      'tools[].allowed_environments': 'environments[].id',
      'models[].environments': 'environments[].id',
      'services[].environments': 'environments[].id'
    }
  },
  'ai-constitution.yaml': {
    can_reference: ['environment.yaml', 'dependencies.yaml'],
    reference_fields: {
      'principles[].applies_to_environments': 'environments[].id',
      'principles[].restricted_tools': 'tools[].id'
    }
  },
  'virtual-experts.yaml': {
    can_reference: ['environment.yaml', 'dependencies.yaml', 'ai-constitution.yaml'],
    reference_fields: {
      'experts[].environments': 'environments[].id',
      'experts[].allowed_tools': 'tools[].id',
      'experts[].governed_by': 'principles[].id'
    }
  },
  'safety-mechanisms.yaml': {
    can_reference: ['environment.yaml', 'ai-constitution.yaml', 'virtual-experts.yaml'],
    reference_fields: {
      'mechanisms[].environments': 'environments[].id',
      'mechanisms[].constitution_refs': 'principles[].id',
      'mechanisms[].reviewers': 'experts[].id'
    }
  }
};

const colors = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function loadYaml(filePath) {
  try {
    const fullPath = path.join(process.cwd(), filePath);
    if (!fs.existsSync(fullPath)) return null;
    const content = fs.readFileSync(fullPath, 'utf8');
    return yaml.load(content);
  } catch (error) {
    return null;
  }
}

function extractIds(config, pathStr) {
  const ids = new Set();
  const parts = pathStr.split('[].');
  
  if (parts.length === 2) {
    const [arrayName, idField] = parts;
    const array = config[arrayName];
    if (Array.isArray(array)) {
      array.forEach(item => {
        if (item[idField]) ids.add(item[idField]);
      });
    }
  }
  
  return ids;
}

function extractReferences(config, pathStr) {
  const refs = new Set();
  const parts = pathStr.split('[].');
  
  if (parts.length === 2) {
    const [arrayName, fieldPath] = parts;
    const array = config[arrayName];
    if (Array.isArray(array)) {
      array.forEach(item => {
        const value = item[fieldPath];
        if (Array.isArray(value)) {
          value.forEach(v => refs.add(v));
        } else if (value) {
          refs.add(value);
        }
      });
    }
  }
  
  return refs;
}

function checkSyncContracts() {
  log('\n🔗 SynergyMesh Sync Contract Checker\n', 'blue');
  
  const configs = {};
  const errors = [];
  const warnings = [];
  
  // Load all configs
  for (const configPath of CONFIG_HIERARCHY) {
    const config = loadYaml(configPath);
    const name = path.basename(configPath);
    if (config) {
      configs[name] = config;
      log(`  ✅ Loaded: ${configPath}`, 'green');
    } else {
      log(`  ⚠️  Not found: ${configPath}`, 'yellow');
    }
  }
  
  log('\n📋 Checking Sync Contracts:', 'blue');
  
  // Check each contract
  for (const [configName, contract] of Object.entries(SYNC_CONTRACTS)) {
    const config = configs[configName];
    if (!config) continue;
    
    log(`\n  ${configName}:`, 'blue');
    
    for (const [refField, targetPath] of Object.entries(contract.reference_fields)) {
      // Determine which config the target is in
      let targetConfig = null;
      let targetConfigName = '';
      
      if (targetPath.startsWith('environments')) {
        targetConfig = configs['environment.yaml'];
        targetConfigName = 'environment.yaml';
      } else if (targetPath.startsWith('tools') || targetPath.startsWith('models')) {
        targetConfig = configs['dependencies.yaml'];
        targetConfigName = 'dependencies.yaml';
      } else if (targetPath.startsWith('principles')) {
        targetConfig = configs['ai-constitution.yaml'];
        targetConfigName = 'ai-constitution.yaml';
      } else if (targetPath.startsWith('experts')) {
        targetConfig = configs['virtual-experts.yaml'];
        targetConfigName = 'virtual-experts.yaml';
      }
      
      if (!targetConfig) {
        warnings.push(`${configName}: Cannot find target config for ${targetPath}`);
        continue;
      }
      
      // Check if this reference is allowed
      if (!contract.can_reference.includes(targetConfigName)) {
        errors.push(`${configName}: Not allowed to reference ${targetConfigName}`);
        continue;
      }
      
      // Get valid IDs from target
      const validIds = extractIds(targetConfig, targetPath);
      
      // Get references from source
      const refs = extractReferences(config, refField);
      
      // Check for invalid references
      let hasInvalid = false;
      for (const ref of refs) {
        if (!validIds.has(ref)) {
          errors.push(`${configName}: Invalid reference '${ref}' in ${refField} (not found in ${targetConfigName})`);
          hasInvalid = true;
        }
      }
      
      if (!hasInvalid && refs.size > 0) {
        log(`    ✅ ${refField} → ${targetConfigName}`, 'green');
      }
    }
  }
  
  // Summary
  log('\n' + '='.repeat(50), 'blue');
  
  if (warnings.length > 0) {
    log('\n⚠️  Warnings:', 'yellow');
    warnings.forEach(w => log(`  ${w}`, 'yellow'));
  }
  
  if (errors.length > 0) {
    log('\n❌ Errors:', 'red');
    errors.forEach(e => log(`  ${e}`, 'red'));
    log('\n❌ Sync contract check failed', 'red');
    process.exit(1);
  } else {
    log('\n✅ All sync softwareos-contracts valid', 'green');
    process.exit(0);
  }
}

checkSyncContracts();
