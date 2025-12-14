from __future__ import annotations

from collections.abc import Iterator
import hashlib
import importlib.util
import inspect
from logging import getLogger
from pathlib import Path
import re
import sys
from typing import TYPE_CHECKING, Any

from vibe import VIBE_ROOT
from vibe.core.config_path import CONFIG_DIR, GLOBAL_TOOLS_DIR, resolve_local_tools_dir
from vibe.core.tools.base import BaseTool, BaseToolConfig
from vibe.core.tools.mcp import (
    RemoteTool,
    create_mcp_http_proxy_tool_class,
    create_mcp_stdio_proxy_tool_class,
    list_tools_http,
    list_tools_stdio,
)
from vibe.core.tools.manifest import ToolManifest, ToolManifestEntry, _hash_file
from vibe.core.utils import run_sync

logger = getLogger("vibe")

if TYPE_CHECKING:
    from vibe.core.config import MCPHttp, MCPStdio, MCPStreamableHttp, VibeConfig


class NoSuchToolError(Exception):
    """Exception raised when a tool is not found."""


DEFAULT_TOOL_DIR = VIBE_ROOT / "core" / "tools" / "builtins"


class ToolManager:
    """Manages tool discovery and instantiation for an Agent.

    Discovers available tools from the provided search paths. Each Agent
    should have its own ToolManager instance.
    """

    def __init__(self, config: VibeConfig) -> None:
        self._config = config
        self._instances: dict[str, BaseTool] = {}
        self._search_paths: list[Path] = self._compute_search_paths(config)
        self._manifest = ToolManifest(
            CONFIG_DIR.path / "cache" / "tools_manifest.json"
        )
        self._manifest.load()
        self._tool_specs: dict[str, ToolManifestEntry] = {}

        self._refresh_manifest()
        self._available: dict[str, type[BaseTool]] = {}
        self._integrate_mcp()

    @staticmethod
    def _compute_search_paths(config: VibeConfig) -> list[Path]:
        paths: list[Path] = [DEFAULT_TOOL_DIR]

        for p in config.tool_paths:
            path = Path(p).expanduser().resolve()
            if path.is_dir():
                paths.append(path)

        if (tools_dir := resolve_local_tools_dir(config.effective_workdir)) is not None:
            paths.append(tools_dir)

        if GLOBAL_TOOLS_DIR.path.is_dir():
            paths.append(GLOBAL_TOOLS_DIR.path)

        unique: list[Path] = []
        seen: set[Path] = set()
        for p in paths:
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                unique.append(rp)
        return unique

    @staticmethod
    def _iter_tool_classes(search_paths: list[Path]) -> Iterator[type[BaseTool]]:
        """Discovery fallback used when manifest is missing or stale."""
        for base in search_paths:
            if not base.is_dir():
                continue

            for path in base.rglob("*.py"):
                if not path.is_file() or path.name.startswith("_"):
                    continue

                stem = re.sub(r"[^0-9A-Za-z_]", "_", path.stem) or "mod"
                module_hash = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
                module_name = f"vibe_tools_discovered_{stem}_{module_hash}"

                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                try:
                    spec.loader.exec_module(module)
                except Exception as exc:  # pragma: no cover - best-effort guard
                    logger.debug("Tool discovery failed for %s: %s", path, exc)
                    sys.modules.pop(module_name, None)
                    continue

                for obj in vars(module).values():
                    if not inspect.isclass(obj):
                        continue
                    if not issubclass(obj, BaseTool) or obj is BaseTool:
                        continue
                    if inspect.isabstract(obj):
                        continue
                    yield obj
                sys.modules.pop(module_name, None)

    def _refresh_manifest(self) -> None:
        valid_entries: list[ToolManifestEntry] = []
        for entry in self._manifest.entries.values():
            if entry.last_error is not None:
                continue
            if entry.is_valid():
                valid_entries.append(entry)

        if len(valid_entries) != len(self._manifest.entries) or not valid_entries:
            valid_entries = self._discover_tools()
            self._manifest.entries = {e.tool_name: e for e in valid_entries}
            self._manifest.save()

        self._tool_specs = {entry.tool_name: entry for entry in valid_entries}

    def _discover_tools(self) -> list[ToolManifestEntry]:
        entries: list[ToolManifestEntry] = []
        for cls in self._iter_tool_classes(self._search_paths):
            try:
                class_path = Path(inspect.getfile(cls)).resolve()
                module_hash = hashlib.sha256(str(class_path).encode("utf-8")).hexdigest()[
                    :16
                ]
                module_name = f"vibe_tools_cached_{module_hash}"

                entry = ToolManifestEntry(
                    tool_name=cls.get_name(),
                    file_path=class_path,
                    file_hash=_hash_file(class_path),
                    module_name=module_name,
                    qualname=cls.__qualname__,
                    description=getattr(cls, "description", None),
                )
                entries.append(entry)
            except Exception as exc:  # pragma: no cover - safety net
                logger.debug("Skipping tool during discovery due to error: %s", exc)
                continue
        return entries

    def _load_class_for_entry(self, entry: ToolManifestEntry) -> type[BaseTool]:
        if entry.loaded_class is not None:
            return entry.loaded_class

        spec = importlib.util.spec_from_file_location(entry.module_name, entry.file_path)
        if spec is None or spec.loader is None:
            raise NoSuchToolError(f"Cannot load tool module at {entry.file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[entry.module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise NoSuchToolError(
                f"Error loading tool module {entry.file_path}: {exc}"
            ) from exc

        obj: Any = module
        for part in entry.qualname.split("."):
            obj = getattr(obj, part)

        if not inspect.isclass(obj) or not issubclass(obj, BaseTool):
            raise NoSuchToolError(
                f"Loaded object {entry.qualname} from {entry.file_path} is not a tool"
            )

        entry.loaded_class = obj
        return obj

    def _get_tool_class(self, tool_name: str) -> type[BaseTool]:
        if tool_name in self._available:
            return self._available[tool_name]

        spec = self._tool_specs.get(tool_name)
        if spec is None:
            raise NoSuchToolError(
                f"Unknown tool: {tool_name}. Available: {list(self._tool_specs.keys())}"
            )

        tool_class = self._load_class_for_entry(spec)
        self._available[tool_name] = tool_class
        return tool_class

    @staticmethod
    def discover_tool_defaults(
        search_paths: list[Path] | None = None,
    ) -> dict[str, dict[str, Any]]:
        if search_paths is None:
            search_paths = [DEFAULT_TOOL_DIR]

        defaults: dict[str, dict[str, Any]] = {}
        for cls in ToolManager._iter_tool_classes(search_paths):
            try:
                tool_name = cls.get_name()
                config_class = cls._get_tool_config_class()
                defaults[tool_name] = config_class().model_dump(exclude_none=True)
            except Exception as e:
                logger.warning(
                    "Failed to get defaults for tool %s: %s", cls.__name__, e
                )
                continue
        return defaults

    def available_tools(self) -> dict[str, type[BaseTool]]:
        tools: dict[str, type[BaseTool]] = {}
        for name in self._tool_specs:
            tools[name] = self._get_tool_class(name)
        for name, cls in self._available.items():
            tools.setdefault(name, cls)
        return tools

    def _integrate_mcp(self) -> None:
        if not self._config.mcp_servers:
            return
        run_sync(self._integrate_mcp_async())

    async def _integrate_mcp_async(self) -> None:
        try:
            http_count = 0
            stdio_count = 0

            for srv in self._config.mcp_servers:
                match srv.transport:
                    case "http" | "streamable-http":
                        http_count += await self._register_http_server(srv)
                    case "stdio":
                        stdio_count += await self._register_stdio_server(srv)
                    case _:
                        logger.warning("Unsupported MCP transport: %r", srv.transport)

            logger.info(
                "MCP integration registered %d tools (http=%d, stdio=%d)",
                http_count + stdio_count,
                http_count,
                stdio_count,
            )
        except Exception as exc:
            logger.warning("Failed to integrate MCP tools: %s", exc)

    async def _register_http_server(self, srv: MCPHttp | MCPStreamableHttp) -> int:
        url = (srv.url or "").strip()
        if not url:
            logger.warning("MCP server '%s' missing url for http transport", srv.name)
            return 0

        headers = srv.http_headers()
        try:
            tools: list[RemoteTool] = await list_tools_http(url, headers=headers)
        except Exception as exc:
            logger.warning("MCP HTTP discovery failed for %s: %s", url, exc)
            return 0

        added = 0
        for remote in tools:
            try:
                proxy_cls = create_mcp_http_proxy_tool_class(
                    url=url,
                    remote=remote,
                    alias=srv.name,
                    server_hint=srv.prompt,
                    headers=headers,
                )
                self._available[proxy_cls.get_name()] = proxy_cls
                added += 1
            except Exception as exc:
                logger.warning(
                    "Failed to register MCP HTTP tool '%s' from %s: %r",
                    getattr(remote, "name", "<unknown>"),
                    url,
                    exc,
                )
        return added

    async def _register_stdio_server(self, srv: MCPStdio) -> int:
        cmd = srv.argv()
        if not cmd:
            logger.warning("MCP stdio server '%s' has invalid/empty command", srv.name)
            return 0

        try:
            tools: list[RemoteTool] = await list_tools_stdio(cmd)
        except Exception as exc:
            logger.warning("MCP stdio discovery failed for %r: %s", cmd, exc)
            return 0

        added = 0
        for remote in tools:
            try:
                proxy_cls = create_mcp_stdio_proxy_tool_class(
                    command=cmd, remote=remote, alias=srv.name, server_hint=srv.prompt
                )
                self._available[proxy_cls.get_name()] = proxy_cls
                added += 1
            except Exception as exc:
                logger.warning(
                    "Failed to register MCP stdio tool '%s' from %r: %r",
                    getattr(remote, "name", "<unknown>"),
                    cmd,
                    exc,
                )
        return added

    def get_tool_config(self, tool_name: str) -> BaseToolConfig:
        tool_class = (
            self._available.get(tool_name)
            or (self._get_tool_class(tool_name) if tool_name in self._tool_specs else None)
        )

        if tool_class:
            config_class = tool_class._get_tool_config_class()
            default_config = config_class()
        else:
            config_class = BaseToolConfig
            default_config = BaseToolConfig()

        user_overrides = self._config.tools.get(tool_name)
        if isinstance(user_overrides, BaseToolConfig):
            user_dict = user_overrides.model_dump()
        elif isinstance(user_overrides, dict):
            user_dict = user_overrides
        else:
            user_dict = None

        merged_dict = default_config.model_dump()
        if isinstance(user_dict, dict):
            merged_dict.update(user_dict)

        if self._config.workdir is not None:
            merged_dict["workdir"] = self._config.workdir

        return config_class.model_validate(merged_dict)

    def get(self, tool_name: str) -> BaseTool:
        """Get a tool instance, creating it lazily on first call.

        Raises:
            NoSuchToolError: If the requested tool is not available.
        """
        if tool_name in self._instances:
            return self._instances[tool_name]

        if tool_name not in self._tool_specs and tool_name not in self._available:
            raise NoSuchToolError(
                f"Unknown tool: {tool_name}. Available: "
                f"{list({**self._tool_specs, **self._available}.keys())}"
            )

        tool_class = self._get_tool_class(tool_name)
        tool_config = self.get_tool_config(tool_name)
        self._instances[tool_name] = tool_class.from_config(tool_config)
        return self._instances[tool_name]

    def reset_all(self) -> None:
        self._instances.clear()
