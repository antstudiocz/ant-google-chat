# Google Chat plugin implementation

User authorizes public GitHub repository under Antstudio, local MCP read/write, and distribution for Codex, Claude Code, Claude Desktop. Verified organization slug: antstudiocz. Planned repository: google-chat-plugin. Endpoint: reviewed initial public repository and installable platform packages; directory submission and remote hosting are outside current scope.

Continuity: isolated sanitized successor of existing local Python MCP. Existing installation and credentials remain intact. Root owns this plan; integration owner owns other project files, independent reviewer reads only.

Acceptance: list spaces/messages/get message remain available, sending text and strict thread replies supported using least-privilege OAuth create scope, safe idempotency, no secrets in Git or releases. Model-neutral MCP stdio server; documented Codex and Claude Code plugin installation and Claude Desktop MCP bundle/config installation. Clearly distinguish packaging validation from actual client UI loading and live Google writes.

Risks: OAuth permission expansion requires human Google consent; public artifacts must exclude tokens, OAuth client files, local chat data, and environment directories. Tests mock Google boundary, not server behavior; protocol smoke checks actual stdio discovery. No live message test without explicit destination/body authorization.

Cadence: early platform feasibility and OAuth contract review, scoped owner implementation, independent security/simplicity/test review, repairs, freeze, full targeted gates, whitelist Git index and archive checks, public push and CI observation.

Status: owner implementation complete, independent review has no blocking findings. Root repeated full 23-test suite, ruff, Claude manifest validation, MCPB manifest validation and required real-archive checks: all pass. Package smoke findings were repaired. Shared Python server, thin manifests and seven-file bundle allowlist satisfy simplicity review. No native Goal requested.

Candidate limits: mocked Google boundary and real stdio discovery verified; live OAuth consent/send and application UI installs unverified. MCPB archive unsigned. Upstream MCPB build-tool dev dependencies have audit advisories; no npm dependency is included in user bundle, production npm audit is clean. Details documented in security notes.

Freeze/publication checkpoint: root will commit the whitelisted reviewed files, request exact-commit review, push main and publish v0.1.0 plus the validated MCPB. GitHub CI will provide clean-host Linux evidence. Publication completion is separately reported with exact commit and run results.

Publication preflight: authenticated GitHub user has active admin membership in antstudiocz, organization display name (ant). Empty public repository created at https://github.com/antstudiocz/google-chat-plugin; no source pushed yet. Native public plugin-directory submission is a separate endpoint requiring remote HTTPS hosting and provider review; local GitHub marketplace distribution satisfies the requested clients.

Official references inspected: [OpenAI packaging](https://developers.openai.com/plugins/build/plugins), [OpenAI Claude migration](https://developers.openai.com/plugins/guides/submit-claude-plugin), [Claude manifest](https://code.claude.com/docs/en/plugins-reference), [MCP bundles](https://github.com/modelcontextprotocol/mcpb), [Google message creation](https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create), [MCP safety](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices).

Next: exact-candidate review, public push, GitHub CI and release. User-owned pending action for live sends: interactive Google OAuth consent with the additional create scope; local host installation follows the documented workflow and is not silently changed.
