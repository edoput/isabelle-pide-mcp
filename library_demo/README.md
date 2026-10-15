# Paper tools through PIDE MCP

This demo adapts Kevin Kappelmann's PIDE MCP server to the extracted
verifier-native tool library. `Reuse_Demo.thy` imports
`MCP-Tool-Library-Paper-Examples.Paper_Tools` from the sibling
`isabelle-tool-library` checkout. The Scala adapter publishes each imported ML declaration directly in MCP
`tools/list`, with its qualified name, description, input schema, and annotations.
Call it through `tools/call` using that name and its declared arguments.
Session startup and shutdown are managed by an internal service.
The adapter does not copy the Isabelle/ML implementation.

The server advertises `tools.listChanged` and sends
`notifications/tools/list_changed` when the prepared session publishes or removes
its ML tools. Refresh `tools/list` after that notification if the initial list
arrives before session startup finishes. Names that collide with existing tools
fail session startup; the demo supports one prepared session. Tools are removed
when that session stops. This is a pinned root catalogue: editing a theory does
not refresh it automatically; restart the session to load changed declarations.

The current paper catalogue contains `Proof_Tasks.proof_tasks`,
`Change_Detection.theory_add`, and `Change_Detection.theory_diff`. It also imports a
proof fixture with `quick_and_dirty` enabled locally for its `sorry`, and a
small logical-signature fixture. The checkpoint remains in one prover process;
call `theory_diff` in the same server session.

## Build and start

Register the PIDE MCP checkout, the extracted library, this library's
`Examples` directory, and this `library_demo` directory as Isabelle components.
Build Scala and the example session with Isabelle2025-2:

```sh
isabelle components -u /path/to/isabelle-pide-mcp-adoption
isabelle components -u /path/to/isabelle-tool-library
isabelle components -u /path/to/isabelle-tool-library/Examples
isabelle components -u /path/to/isabelle-pide-mcp-adoption/library_demo
isabelle scala_build
isabelle build -j 1 -d /path/to/isabelle-tool-library/Examples MCP-Tool-Library-Paper-Examples
```

Start the adapted server over stdio:

```sh
isabelle pide_mcp -d /path/to/isabelle-tool-library/Examples -l MCP-Tool-Library-Paper-Examples
```

For a bounded, LLM-free smoke test of startup, discovery, invocation, and
shutdown, run `smoke_paper.py` with the exact server command after `--`:

```sh
python3 smoke_paper.py --output /tmp/pide-paper-smoke -- \
  isabelle pide_mcp -d /path/to/isabelle-tool-library/Examples \
  -l MCP-Tool-Library-Paper-Examples
```

The test prints a short PASS summary and writes request, response, and stderr
logs under the output directory. On failure, keep those logs to diagnose the
setup. The test checks the proof fixture, an in-process checkpoint, and an
unchanged signature comparison; it does not yet test a changed signature.

## MCP Inspector

The official Inspector can launch the same stdio command:

```sh
npx @modelcontextprotocol/inspector isabelle pide_mcp \
  -d /path/to/isabelle-tool-library/Examples \
  -l MCP-Tool-Library-Paper-Examples
```

In the Inspector, refresh the tool list after startup and select
`Proof_Tasks.proof_tasks`. Its arguments are:

```json
{"theories":["MCP-Tool-Library-Paper-Examples.Paper_Proof_Fixture"]}
```

The current proof-task implementation uses `Thy_Info.get_theory`, so pass the
qualified fixture theory name shown above.

For change detection, invoke `Change_Detection.theory_add` and then
`Change_Detection.theory_diff` with `{"theories":["Paper_Signature_Fixture"]}` in the
same connection. The unchanged report is expected. The Inspector is a client,
so it must start a fresh server process; it does not attach to a server already
running on a separate terminal's stdio.

The earlier `shout`/`edit_summary` two-server comparison is preserved in
`README.previous-demo.md` and `verify.py`; that script targets the older root
and is not the smoke test for this paper catalogue.

For a focused Scala-only check of catalogue collision rejection, publication,
withdrawal, and notification callbacks:

```sh
isabelle scala /path/to/isabelle-pide-mcp-adoption/library_demo/check_registry.scala
```
