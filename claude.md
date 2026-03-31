# Claude Working Notes

## Terminal / Scripting Rules

- **NEVER use heredocs** — they fail frequently with quoting issues and leave the terminal in a confused state.
- Always write Python scripts into the `tools/` directory and then run the script from the terminal.
