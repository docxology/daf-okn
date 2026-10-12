# Security policy

If you find a security problem in daf-okn, please report it privately by email to
daniel@activeinference.institute rather than opening a public issue. Include the version
(`daf-okn --version`), what you observed and, if you can, a minimal way to reproduce it.

You can expect an acknowledgement within a week. Only the latest release is supported.

daf-okn reads local files and talks to public OKN endpoints (okn.us, registry.okn.us,
apps.okn.us). It never needs credentials; the lakeFS upload commands it prints contain
placeholders for your own keys, which you should keep out of version control.
