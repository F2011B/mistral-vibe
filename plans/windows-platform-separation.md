# Windows Platform Separation

This diagram shows how platform-specific modules are split and dispatched at runtime.

```mermaid
flowchart TB
  subgraph PlatformDispatch["Platform Dispatch (vibe.core.platform)"]
    selector["platform selector\n(sys.platform)"]
    win["vibe.core.platform.windows"]
    posix["vibe.core.platform.posix"]
    selector -->|win32| win
    selector -->|else| posix
  end

  system_prompt["vibe.core.system_prompt"] --> selector
  interaction_logger["vibe.core.interaction_logger"] --> selector

  subgraph BashDispatch["Bash Tool Platform Split"]
    bash_core["vibe.core.tools.builtins.bash"]
    bash_selector["bash_platform selector\n(sys.platform)"]
    bash_win["bash_platform_windows"]
    bash_posix["bash_platform_posix"]
    bash_core --> bash_selector
    bash_selector -->|win32| bash_win
    bash_selector -->|else| bash_posix
  end

  subgraph TerminalDispatch["Terminal Setup Split"]
    setup_entry["vibe.cli.terminal_setup"]
    setup_shared["terminal_setup_shared"]
    setup_win["terminal_setup_windows"]
    setup_posix["terminal_setup_posix"]
    setup_entry -->|win32| setup_win
    setup_entry -->|else| setup_posix
    setup_win --> setup_shared
    setup_posix --> setup_shared
  end
```

Notes:
- Windows and Unix-like implementations live in separate modules.
- Dispatch chooses the module based on sys.platform at runtime.
- Shared modules contain only OS-agnostic code.
