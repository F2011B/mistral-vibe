# Plan for Issue #106: Feature request - Accept edits mode

- Status: open
- Labels: none
- Link: https://github.com/mistralai/mistral-vibe/issues/106

## Description
# Description 

I want an accept edits mode in addition to the current manual and automatic modes.

# Usecase

I want to be able to take my eyes off the vibe CLI to multi-task, but the automatic mode provides too much access(MCP servers against external systems etc.)
An accept-edits mode would allow for workflows where manual mode is cumbersome and automatic is risky.

# Alternatives

For the time being I have created myself a config that allows the use of grep, read_file, search_replace,  todo and write_file, but not bash or MCP provided tools. 
This works, but it is not elegant.
