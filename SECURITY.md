# Security policy

If you find a security problem in daf-okn, please report it privately by email to
daniel@activeinference.institute rather than opening a public issue. Include the version
(`daf-okn --version`), what you observed and, if you can, a minimal way to reproduce it.

You can expect an acknowledgement within a week. Only the latest release is supported.

daf-okn reads local files and talks to public OKN endpoints (okn.us, registry.okn.us,
apps.okn.us). Pulling registry data needs no credentials. The optional `lakefs-cognitive`
command reads a lakectl configuration file that you supply, which holds your lakeFS access
keys. The tool uses those keys only to authenticate its requests to the OKN lakeFS endpoint
and does not store or log them. Keep that file, and the keys in the upload commands the tool
prints, out of version control.
