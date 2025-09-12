# DSSAT MCP Server — Claude Desktop Integration

Connect Claude Desktop to a DSSAT MCP server to download inputs, run experiments, and collect outputs—directly from a chat.

## Quick Start

### 1) Install Claude Desktop
- **Windows:** [Download](https://claude.ai/download) and install the official Windows app, then sign in.
- **Ubuntu/Debian (community build):** Use the [community repo](https://github.com/aaddrick/claude-desktop-debian.git) `aaddrick/claude-desktop-debian` to install a `.deb`/`.AppImage`, or build from source:
  
  ```bash
  git clone https://github.com/aaddrick/claude-desktop-debian.git
  cd claude-desktop-debian
  ./build.sh
  sudo dpkg -i ./claude-desktop_*.deb
  
  # If you encounter dependency issues:
  sudo apt --fix-broken install
  ```

**Config paths:**
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

- **Linux:** `~/.config/Claude/claude_desktop_config.json`

  Tip: You can also open the config from **Settings → Developer → Edit Config** in Claude Desktop.

### 2) Add MCP configuration
Paste the JSON below into your config file. **Replace only the token value**; keep everything else identical. Tokens will be provided upon request.

```json
{
  "mcpServers": {
    "dssat": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://dev.mcp.crops.qvantum.scio.services/mcp",
        "--allow-http",
        "--header",
        "Authorization: Bearer ${ACCESS_TOKEN}}"
      ],
      "env": {
        "ACCESS_TOKEN": "<REPLACE_WITH_YOUR_ACCESS_TOKEN>"
      }
    }
  }
}
```

> If your config invokes `npx`, ensure Node.js and npm are installed.

### 3) Use it from Claude Desktop
- Restart Claude Desktop (or reload the developer config).
- Open a new chat. Claude Desktop will automatically discover the MCP server and list available tools.
- Use the example prompt below to run a typical DSSAT workflow.

### Tools (high-level description)

- **download_files_from_s3** — Download DSSAT input files (e.g., SOIL.SOL, *.WTH, *.MZX) from S3 into a local working folder and verify presence.
- **run_dssat_experiment** — Run DSSAT using the specified experiment file (FileX) inside the working folder and capture logs/summary.
- **upload_and_collect_output_files** — Archive the working folder, upload to S3, return a presigned URL for outputs, and perform cleanup.

## Example Prompt (paste in Claude Desktop)
```
I want to run a DSSAT experiment. Check the list of tools to find the correct tool input format. First download and save to folder CUSTOM_EXPERIMENT the following files from S3: SOIL.SOL, UFGA8201.WTH, UFGA8201.MZX. Next execute the experiment with the experiment file UFGA8201.MZX. Then, upload the file to S3 in order to collect the output files.
```
