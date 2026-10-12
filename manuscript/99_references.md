# References {#sec:references}

Bibliography lives in [`manuscript/references.bib`](references.bib) and is the bibliography for the `[@key]` citations in the manuscript. A Pandoc run that passes `--natbib` rewrites each citation to the appropriate `\cite{}`/`\citep{}`/`\citet{}` LaTeX command and resolves it against the bib file; this repository does not run Pandoc.

Cited sources fall into three groups:

- **Methodology**: reproducible computational research [@peng2011reproducible]; knowledge-graph foundations [@hogan2021knowledge]; the semantic-web vision behind RDF interchange [@bernerslee2001semantic].
- **Query interfaces**: SPARQL 1.1 [@sparql2013], the QLever engine behind the OKN per-graph endpoints [@bast2017qlever], and Triple Pattern Fragments [@verborgh2014tpf].
- **Primary subject**: the OKN registry itself [@oknregistry2026], whose documented endpoints and metadata file are pinned in [`docs/okn/api-notes.md`](../docs/okn/api-notes.md).

To check that `references.bib` parses and that every `[@key]` used in the chapters resolves:

```bash
python -c "print(open('manuscript/references.bib').read()[:200])"  # sanity open
grep -oE '\[@[a-z0-9]+' manuscript/*.md | sort -u
```
