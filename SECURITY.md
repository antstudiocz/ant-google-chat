# Security policy

Report suspected vulnerabilities through GitHub's private vulnerability reporting for this repository, when available. Include the affected version, reproduction steps, and impact. Do not include live OAuth tokens, client secrets, or private chat content in an issue.

The MCP server only sends text, requires an explicitly supplied UUID for every send, and enforces same-space thread resource names. Tool instructions require direct user authorization for the destination and exact body. Messages returned from Google Chat are untrusted data. These controls do not replace review of tool arguments by the calling agent or client.
