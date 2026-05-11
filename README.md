# COMSOL AI

COMSOL Multiphysics automation skills — programmatic simulation via Python.

## Install

```bash
# Register this marketplace (one time)
/plugin marketplace add 2p1c/comsol_ai

# Install the COMSOL skill
/plugin install comsol@comsol-skills
```

## What's included

| Skill | Description |
|-------|-------------|
| `comsol` | COMSOL model creation, physics setup, meshing, parametric/time-domain studies, and result extraction via mph + COMSOL Java API. Verified against COMSOL 6.2. |

## Prerequisites

- COMSOL Multiphysics 6.0–6.3
- Python 3.x with `mph`, `numpy`, `pandas`

## Repository structure

```
skills/comsol/          # The skill
├── SKILL.md            # Skill instructions
├── scripts/            # Simulation scripts
├── references/         # API reference, debugging log, examples
.claude-plugin/
└── marketplace.json    # Plugin registry manifest
```
