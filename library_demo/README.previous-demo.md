# Historical two-server demo

This document records an earlier `shout`/`edit_summary` comparison. Its commands and `verify.py` expect the former `Reuse_Demo` import and do not reproduce the current paper-tool demo. Use `README.md` and `smoke_paper.py` for the current setup.

# Shared ML tool reuse demo

This external Scala component demonstrates the same existing Isabelle/ML tools
through Kevin Kappelmann's PIDE MCP and the original Isabelle MCP server, using
the extracted verifier-native tool library. It does not copy their ML code.

`Reuse_Demo.thy` imports the original source theory
`/home/edoput/repo/isabelle-mcp/mcp/Tools/MCP_Tools.thy` through its `MCP-Tools`
session. That theory declares `shout` and `edit_summary`, and imports the external
library. The original server also loads that theory. The demo registers only its
Scala adapter with PIDE MCP, not the original server's Scala component.

## Scope

Two fixed demo-local MCP operations:

- `demo_ml_catalogue`, with optional `session`: returns ML names and schemas from
  the prepared root. Existing Scala tools remain available.
- `demo_ml_invoke`, with optional `session`, required `name` and `arguments`:
  invokes a canonical name from that catalogue, such as `MCP_Tools.shout`.

Each call runs synchronously on PIDE MCP's normal separate request thread. The
library supplies typed replies, bounded pending capacity (8), call deadline
(30 seconds), drain deadline (5 seconds), and its configured reply limit. One
completed live root is pinned; normal shutdown drains the bridge and unloads it.
The adapter owns no prover startup/stop code: the existing server owns the session.

Source TODOs explicitly defer MCP cancellation forwarding, catalogue-change
notifications, dynamic individual MCP tool exposure, multi-session handling,
document-edit policies, and comprehensive lifecycle recovery. Only one prepared
session is supported. Do not edit its root/imports during the demo or disable
only `demo_ml_catalogue`: its lifecycle hook owns the shared bridge. These are
demonstration interfaces, not a proposed production contract.

## Reproduce in this checkout

Verified with Isabelle2025-2 and PIDE MCP release baseline
`48dd7804ea6e1857ee767de06ac911b39d7b036c` on branch
`codex/pide-library-adoption` in
`/home/edoput/repo/isabelle-pide-mcp-adoption`.
Library revision: `b169ee50084cae8db200891167e43e6c15807c68`.
The comparison records the current original-server revision and source SHA-256.

This host's existing Flatpak command uses private demo settings; no dependencies
are downloaded or shared component registrations changed. Run the following in
a shell:

```sh
demo_isabelle() {
  /usr/bin/host-spawn --no-pty flatpak run --command=isabelle \
    --env=USER_HOME=/tmp/pide-mcp-adoption-home \
    --env=ISABELLE_IDENTIFIER=PideMcpAdoption \
    de.tum.in.isabelle.Isabelle "$@"
}
demo_isabelle components -u /home/edoput/repo/isabelle-pide-mcp-adoption
demo_isabelle components -u /home/edoput/repo/isabelle-tool-library
demo_isabelle components -u /home/edoput/repo/isabelle-pide-mcp-adoption/library_demo
demo_isabelle scala_build
demo_isabelle scala /home/edoput/repo/isabelle-tool-library/Tests/check_scala.scala
demo_isabelle build -j 1 -d /home/edoput/repo/isabelle-mcp/mcp/Tools MCP-Tools
```

For clean JSON-RPC stdout under concurrent Flatpak JVMs, the private settings
file at `/tmp/pide-mcp-adoption-home/.isabelle/PideMcpAdoption/etc/settings`
(inside the Flatpak) contains:

```sh
ISABELLE_JAVA_SYSTEM_OPTIONS="$ISABELLE_JAVA_SYSTEM_OPTIONS -XX:+PerfDisableSharedMem"
```

Start the PIDE MCP demo:

```sh
demo_isabelle pide_mcp -d /home/edoput/repo/isabelle-mcp/mcp/Tools -l MCP-Tools
```

Sample newline-delimited requests after initialization:

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"demo_ml_catalogue","arguments":{}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"demo_ml_invoke","arguments":{"name":"MCP_Tools.shout","arguments":{"input":"shared tool"}}}}
```

`shout` returns `SHARED TOOL`. The original server exposes the same declaration
under the short name `shout`; the adapter uses its library catalogue's qualified
name, without changing library name resolution.

Run the bounded live comparison (starts each host, discovers/invokes both shared
tools, checks an argument error and subsequent recovery, and closes stdin):

```sh
python3 /home/edoput/repo/isabelle-pide-mcp-adoption/library_demo/verify.py \
  --checkout /home/edoput/repo/isabelle-pide-mcp-adoption \
  --original /home/edoput/repo/isabelle-mcp \
  --output /tmp/shared-ml-demo-evidence
```

The original host starts through its existing `tools/isabelle --profile codex`
launcher with `mcp_server -s MCP-Tools -T MCP-Tools.MCP_Tools`; it retains its own
private settings. Output includes each command, JSON-RPC request/response, stderr,
exit status, and `comparison.json` with source hash/revisions and matched results.
An individual response has a 180-second bound; shutdown has a 30-second bound.
The independent library consumer check excludes project jars from ambient
dependencies. No original-server or library source changes are required.

## Verified outcome (2026-10-07)

Both hosts discovered the shared ML tools and returned:

| Tool and arguments | PIDE MCP adapter | Original server |
| --- | --- | --- |
| `shout`, input `shared tool` | `SHARED TOOL` | `SHARED TOOL` |
| `edit_summary`, path `shared.thy`, one edit | `shared.thy:1` | `shared.thy:1` |

Both rejected a missing required `shout` input as a tool error, accepted a
subsequent valid call, and exited with status 0. PIDE MCP listed its 11 original
Scala tools plus the two demo wrappers; its existing `list_sessions` succeeded.
The original server reported its MCP-Tools image reused and completed ML readiness.
The comparison hashes the shared source before/after to confirm it was unchanged.

Build evidence from this run: `/tmp/pide-library-adapter-build.log`,
`/tmp/pide-library-consumer-build.log`, `/tmp/pide-library-theory-build.log`.
Live evidence: `/tmp/shared-ml-demo-evidence/comparison.json`, `pide.json`,
`original.json`, and their sibling `.stderr` files. These are local temporary
artifacts; rerun the comparison to regenerate them. This evidence establishes
bounded reuse, not the deferred production behavior listed in source TODOs.
