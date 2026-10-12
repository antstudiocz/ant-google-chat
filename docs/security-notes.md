# Packaging security notes

As of 2026-10-12, `npm audit` reports vulnerabilities in the development-only dependency tree of the pinned `@anthropic-ai/mcpb@2.1.2` bundle CLI. It identifies `node-forge` through that CLI (GHSA-86w9-cpqp-85rv, high) and `tmp` through `external-editor` (GHSA-52f5-9888-hmc6, low; GHSA-ph9p-34f9-6g65, high), plus three transitive low-severity advisories. npm reports no available fix for the dependency tree. `npm audit --omit=dev` reports no production dependencies because the package has no npm runtime dependencies.

The MCPB CLI is only used for validation and archive creation. The archive staging script copies an explicit allowlist of seven files and never copies `node_modules`; end-user execution uses the separately locked Python project. Build the bundle in a trusted, isolated CI runner and avoid using the MCPB CLI on untrusted input until upstream resolves the advisories.
