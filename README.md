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

Install the project in editable mode with the same Python interpreter you plan
to use for running the server.  The commands below show both the standard
`python -m pip` invocation and the equivalent `uv` workflow.  Using
[`uv`](https://docs.astral.sh/uv/latest/) can be more robust on platforms where
`pip` occasionally fails to resolve the `modelcontextprotocol` dependency.

```bash
# Standard Python packaging tools
python -m pip install -e '.[dev]'

# Or, with uv
uv pip install -e '.[dev]'
```

The runtime dependency on `modelcontextprotocol` is now installed automatically
with the package.  If you previously installed the project before this
dependency was added, rerun the command above (with `pip` or `uv`) to refresh
the editable install.  Verify that the module is importable with the same
interpreter you use to start the server:

```bash
python -c "import modelcontextprotocol; print(modelcontextprotocol.__file__)"
# or
uv run -- python -c "import modelcontextprotocol; print(modelcontextprotocol.__file__)"
```

If the import still fails, install the upstream package directly from GitHub to
work around the packaging issue tracked in the
[`modelcontextprotocol` issue tracker](https://github.com/modelcontextprotocol/python-sdk/issues):

```bash
python -m pip install --upgrade \
  'modelcontextprotocol @ git+https://github.com/modelcontextprotocol/python-sdk.git'
# or
uv pip install --upgrade \
  'modelcontextprotocol @ git+https://github.com/modelcontextprotocol/python-sdk.git'
```

Run the reference stdio server:

```bash
python -m teadata_mcp
# or
uv run -- python -m teadata_mcp
```

If the server still fails to import `modelcontextprotocol`, run the built-in
diagnostics to check the active environment:

```bash
python -m teadata_mcp --diagnose
# or
uv run -- python -m teadata_mcp --diagnose
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

## Troubleshooting the MCP dependency

The `modelcontextprotocol` package is under active development.  If `python -m
pip install -e '.[dev]'` reports that the distribution is unavailable or the
server still raises `ModuleNotFoundError: No module named 'modelcontextprotocol'`
after installation:

1. Confirm that you are running the install command with the interpreter you
   plan to use for `python -m teadata_mcp`.
2. Clear out any stale editable installs that predate the dependency update by
   rerunning the install command.
3. Install the upstream SDK directly from GitHub using the command listed above.
   The GitHub install has been the most reliable workaround reported in the
   [`modelcontextprotocol` issue tracker](https://github.com/modelcontextprotocol/python-sdk/issues).
4. If the import still fails, run `python -m pip show modelcontextprotocol` to
   inspect where the package was installed and confirm that location appears on
   `sys.path` when launching the server.

## Deploying the server to Render

The reference implementation runs over stdin/stdout transport only.  Remote
hosting platforms such as Render do not expose an interactive standard I/O
stream to inbound clients, so the binary built from `python -m teadata_mcp`
cannot be deployed directly as a Render service.  The existing entry point
initialises :class:`modelcontextprotocol.adapters.stdio.StdioServerTransport`
and blocks waiting for traffic on the local file descriptors instead of opening
a network listener.  To serve MCP traffic over the public internet you must
supply an alternate transport layer (for example a small ASGI or WebSocket
bridge) that translates between Render's HTTP load balancer and the MCP
protocol primitives before calling ``teadata_mcp.server.build_app``.

If you add such a network-aware adapter, Render's "Web Service" product is the
closest fit.  The "Starter" tier is the lowest priced always-on option at the
time of writing, and you can either

* deploy from this repository directly with Render's native build system (set
  **Start Command** to the module that launches your network adapter), or
* push a Dockerfile that installs the project and launches the same command.

Render's free tier spins services down after periods of inactivity and is not
suited for MCP clients that expect a persistent connection.  If you only need
the tools for personal experimentation, running the stdio server locally and
connecting via the ChatGPT for Developers desktop app remains the most cost
effective workflow.
