# TEA Data MCP Server Scaffolding

This repository contains the initial scaffolding for a Model Context Protocol
(MCP) server that exposes a narrow slice of the [`teadata`](knowledge/teadata)
library.  The goal is to make the server easy to extend incrementally while
remaining transparent for large language models (LLMs) that will be asked to
maintain it over time.

## Project layout

```
.
├── src/teadata_mcp/        # Python package containing the server code
│   ├── config.py           # Declarative runtime configuration
│   ├── data_engine_provider.py  # Lazy ``DataEngine`` bootstrapper
│   ├── query_models.py     # Shared response models
│   ├── router.py           # Tool routing and guard rails
│   └── server.py           # MCP integration and I/O plumbing
├── knowledge/              # Vendored copy of the upstream teadata project
└── tests/                  # Unit tests exercising the scaffolding
```

The `knowledge` directory mirrors the upstream project so that LLMs can inspect
API details offline.  The MCP package is deliberately separated under `src/` to
avoid collisions with the original source tree and to make packaging easier.

## Quick start

Install the project in editable mode:

```bash
pip install -e .[dev]
```

The runtime dependency on `modelcontextprotocol` is now installed automatically
with the package.

Run the reference stdio server:

```bash
python -m teadata_mcp
```

By default the server will search for a pre-built TEA Data snapshot using the
same logic as `DataEngine.from_snapshot(search=True)`.  Provide an explicit path
by setting the `TEADATA_SNAPSHOT` environment variable or by wiring a custom
`ServerConfig` instance before calling :func:`teadata_mcp.server.run`.

## Extending the server

The `QueryRouter` class is the main integration point for new capabilities.  It
receives structured tool calls and is responsible for returning
:class:`~teadata_mcp.query_models.QueryResult` objects.  Each new tool should:

1. Add a method to `QueryRouter` that invokes the relevant `teadata` API.
2. Update `teadata_mcp.server.build_app` to advertise the tool in
   ``list_tools`` and to handle it in ``call_tool``.
3. Add focused unit tests under `tests/` that exercise both successful and
   failure modes.

The scaffolding already demonstrates the "refuse to answer" behaviour.  When the
underlying data is not available the server returns a status of
``QueryResultStatus.UNKNOWN`` instead of attempting to guess.  Tests assert this
behaviour to guard against future regressions.

## Using the server with ChatGPT for Developers

ChatGPT for Developers can connect to local MCP servers by reading a JSON
configuration file from its application support directory.  After installing the
package (see the quick-start instructions above) create or update the
configuration file to point at the local stdio entry point:

1. Quit the ChatGPT desktop application if it is running.
2. Create the configuration directory if it does not exist yet:

   ```bash
   mkdir -p "${HOME}/Library/Application Support/com.openai.chat"
   ```

3. Open `"${HOME}/Library/Application Support/com.openai.chat/config.json"` and
   add a new entry under the top-level `"mcpServers"` key:

   ```json
   {
     "mcpServers": {
       "teadata": {
         "command": "python",
         "args": ["-m", "teadata_mcp"],
         "env": {
           "TEADATA_SNAPSHOT": "/absolute/path/to/your/snapshot"
         }
       }
     }
   }
   ```

   The `env` block is optional, but it is often convenient to point the server
   at a specific TEA Data snapshot.  Remove the key entirely if you would rather
   let the provider use its default search behaviour.

4. Restart the ChatGPT application.  The MCP server should now appear in the
   *Developers → Manage MCP Servers* panel, and ChatGPT can invoke it directly.

If you use the ChatGPT for Developers command-line client, supply the same
`command` and `args` values when registering the MCP server with the CLI.
