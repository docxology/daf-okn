# Standalone Guide

<!-- BEGIN:PUBLICATION_INDEX -->
<!-- No DOIs or platform identifiers are assigned yet; leave fields empty rather
     than fabricating them. -->

## Publication identity

- Standalone repository: [docxology/daf-okn](https://github.com/docxology/daf-okn)
- Metadata source: [`docs/manuscript/config.yaml`](manuscript/config.yaml); citation sidecars live at the project root.

<!-- END:PUBLICATION_INDEX -->

## Purpose

`daf-okn` pulls, analyzes, visualizes, and contributes to the Open Knowledge
Network (okn.us / registry.okn.us), including exporting the Active Inference
Institute `cognitive` knowledge graph to the registry.

## Post-Fork Edits

- Update `docs/manuscript/config.yaml`, `domain_profile.yaml`, `experiment_plan.yaml`,
  `CITATION.cff`, `.zenodo.json`, `codemeta.json`, and `pyproject.toml` if you
  fork this project again.
- Assign Zenodo DOIs and platform identifiers only on first public release;
  leave fields empty rather than fabricating identifiers.

## Validation Commands

```bash
bash scripts/gate.sh
```

## Dependencies

Package dependencies are declared in [`pyproject.toml`](../pyproject.toml).
Registry pulls, live queries, connector search, and live joins use OKN services.
The [rendering guide](rendering_pipeline.md) covers the separate template checkout.

## What Not To Claim

Do not claim OKN registry results (pulls, analyses, contributions) until the
corresponding modules have been implemented and their outputs regenerated from
live source data.
