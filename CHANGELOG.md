# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- `daf-okn stack-health --roster FILE [--member NAME] [--checkout DIR]` and
  `daf_okn.core.stack_roster`: an offline, read-only consumer of the
  `daf-stack-doctor roster` JSON. It validates the roster shape and compares the
  named member's declared path, branch, required files, gate command, board and
  Sidecar manifest with a checkout. No gate is executed, nothing is written and no
  network is used; the payload keeps `native_gate: not_run`.
- `tests/core/test_stack_roster.py` (roster parsing, malformed/duplicate/absent
  members, path/branch/file/gate/board/Sidecar negative controls, this checkout
  against the requirements the daf-stack manifest declares) and CLI coverage for
  the new subcommand.

## [0.2.0] - 2026-10-12

First public release. Earlier version numbers (such as 2.5.2) came from a project template and
carry no meaning.

### Added

- `daf-okn` command line (also `python -m daf_okn`) with `pull`, `export`, `analyze`,
  `visualize`, `package`, `join`, `explain-join`, `bundle-rdf` and `status` subcommands.
- `daf_okn.core.rdf`: RDF serialization using SKOS, Dublin Core Terms and schema.org, aligned
  with the `cognitive` repository's reference exporter. Entity IRIs sit under
  `https://purl.org/okn/frink/kg/<shortname>/` and the named graph is
  `https://purl.org/okn/frink/kg/<shortname>`; relations no standard term covers become terms
  under `<base>relation/` declared `rdfs:subPropertyOf skos:semanticRelation`; other node
  attributes stay available under `<base>vocab/`. N-Triples and N-Quads output is sorted and
  byte-stable.
- Registry entries are written to `registry/docs/registry/kgs/<shortname>.md` with exactly the fields
  the registry documents (`template`, `shortname`, `title`, `description`, `stats`, `homepage`,
  `funding` when supplied, `frink-options`, `contacts`).
- Vault adapter: `[[links]]` resolve through frontmatter `aliases:` as well as paths and file
  names; repeated names resolve alphabetically; any Obsidian-style vault can be read, and more
  frontmatter fields (`description`, `aliases`, `authors`, `year`, `doi`, ...) are kept.
- Manuscript chapters are resolved into `output/manuscript/` by
  `scripts/z_generate_manuscript_variables.py`.
- `ruff` configuration, GitHub Actions CI (Python 3.12 and 3.14, coverage gate of 90%),
  `CONTRIBUTING.md`, `SECURITY.md`.

### Changed

- RDF output no longer uses `daf-okn:Node` / `nodeType` terms or the
  `https://purl.org/okn/daf-okn/` namespace.
- `registry_entry()` and `daf-okn package` no longer accept `sparql`, `tpf` or `license`
  frontmatter; the registry asks contributors to leave the endpoints out until RENCI sets them
  up, and the licence is stated in the entry body.
- The package layout is `<shortname>.<fmt>`, `registry/docs/registry/kgs/<shortname>.md` and
  `checklist.md`.
- Exported graph JSON records `vault_name` instead of an absolute `source_root` path.
- Template leftovers (references to an `infrastructure/` layer, vendoring and a template
  renderer) were removed from the documentation and scripts.

### Removed

- `drafts/` and the template export descriptor.
