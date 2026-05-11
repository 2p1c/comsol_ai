#!/usr/bin/env node
/**
 * Post-install: registers the comsol skill in Claude Code's skill directory.
 *
 * Copies (or symlinks) the bundled skill/ folder to:
 *   Windows:  %USERPROFILE%/.claude/skills/comsol
 *   Linux/macOS: ~/.claude/skills/comsol
 *
 * If the target already exists, it is left untouched (the user may have
 * customised it).  Set env FORCE_INSTALL=1 to overwrite.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const SKILL_NAME = 'comsol';

function skillSource() {
  // When installed as an npm package, the skill/ folder is at the package root.
  // When running from the repo clone, it's also at the repo root.
  return path.resolve(__dirname, '..', 'skills', 'comsol');
}

function skillTarget() {
  const home = os.homedir();
  return path.join(home, '.claude', 'skills', SKILL_NAME);
}

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const ent of entries) {
    const srcPath = path.join(src, ent.name);
    const dstPath = path.join(dst, ent.name);
    if (ent.isDirectory()) {
      copyDir(srcPath, dstPath);
    } else {
      fs.copyFileSync(srcPath, dstPath);
    }
  }
}

function main() {
  const src = skillSource();
  const dst = skillTarget();

  if (!fs.existsSync(src)) {
    console.warn(`[comsol-ai] Skill source not found at ${src} — skipping install.`);
    return;
  }

  if (fs.existsSync(dst)) {
    if (process.env.FORCE_INSTALL === '1') {
      console.log(`[comsol-ai] FORCE_INSTALL=1 — overwriting ${dst}`);
      fs.rmSync(dst, { recursive: true, force: true });
    } else {
      console.log(`[comsol-ai] Skill already exists at ${dst} — skipping (set FORCE_INSTALL=1 to overwrite).`);
      return;
    }
  }

  copyDir(src, dst);
  console.log(`[comsol-ai] Skill installed to ${dst}`);
}

main();
