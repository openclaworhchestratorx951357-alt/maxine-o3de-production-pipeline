# Architecture

The target system is a two-tier production pipeline:

- **Draft lane**: fast iteration for idea-to-preview velocity. This lane can use TripoSR or local reconstruction flows, spawn mesh entities, and capture smoke proof quickly.
- **Release lane**: canonical packaging and publication. This lane resolves O3DE products by source identity and product type, runs QC, writes evidence bundles, and publishes prefab/actor outputs with rollback support.

The success condition must move from:

- "spawn succeeded"

to:

- "release package published with manifest, evidence, validation, and rollback."

This change prevents fragile one-off outputs from being mistaken for production-ready deliveries.

```mermaid
flowchart LR
    A[Inbox job or operator command] --> B[Normalize job and assign IDs]
    B --> C{Lane selection}
    C -->|Draft mesh| D[Fast reconstruction]
    C -->|Release character| E[DCC conform and rig validation]
    C -->|External rig import| F[Rigged FBX intake]
    D --> G[Preflight QC]
    E --> G
    F --> G
    G -->|Fail| H[Quarantine plus evidence]
    G -->|Pass| I[Canonical source package]
    I --> J[O3DE Asset Processor]
    J --> K[Resolve products by source UUID]
    K --> L[Generate actor or prefab package]
    L --> M[Editor automation smoke tests]
    M --> N[Manifest plus screenshots plus logs]
    N --> O{Policy decision}
    O -->|Pass| P[Publish package]
    O -->|Warn| Q[Pending manual review]
    O -->|Fail| R[Undo plus cleanup]
```
