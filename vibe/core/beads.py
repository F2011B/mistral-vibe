import asyncio
import logging
import shutil
import uuid
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

@runtime_checkable
class BeadsAdapter(Protocol):
    async def create_task(self, description: str) -> Optional[str]:
        ...

    async def close_task(self, task_id: str) -> bool:
        ...

class CLIAdapter:
    def __init__(self, bd_path: str):
        self.bd_path = bd_path

    async def create_task(self, description: str) -> Optional[str]:
        try:
            cmd = [self.bd_path, "q", description]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Failed to create beads task via CLI: {stderr.decode()}")
                return None

            task_id = stdout.decode().strip()
            return task_id
        except Exception as e:
            logger.error(f"Error creating beads task via CLI: {e}")
            return None

    async def close_task(self, task_id: str) -> bool:
        try:
            cmd = [self.bd_path, "close", task_id]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Failed to close beads task {task_id} via CLI: {stderr.decode()}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error closing beads task {task_id} via CLI: {e}")
            return False

class MCPAdapter:
    def __init__(self, module):
        self.module = module

    async def create_task(self, description: str) -> Optional[str]:
        try:
            # Assuming standard MCP sync API wrapped in asyncio for now, or direct async if available
            # If the library is sync, we might need run_in_executor
            # For now, let's assume a hypothetical async API or wrapped sync
            if asyncio.iscoroutinefunction(self.module.create_task):
                 return await self.module.create_task(description)
            else:
                 return self.module.create_task(description)
        except Exception as e:
            logger.error(f"Error creating beads task via MCP: {e}")
            return None

    async def close_task(self, task_id: str) -> bool:
        try:
            if asyncio.iscoroutinefunction(self.module.close_task):
                 await self.module.close_task(task_id)
            else:
                 self.module.close_task(task_id)
            return True
        except Exception as e:
            logger.error(f"Error closing beads task via MCP: {e}")
            return False

class InternalAdapter:
    def __init__(self):
        self.tasks = {}
        logger.info("Using Internal Beads Adapter (Memory-only)")

    async def create_task(self, description: str) -> Optional[str]:
        task_id = f"mem-{str(uuid.uuid4())[:8]}"
        self.tasks[task_id] = {"description": description, "status": "open"}
        logger.info(f"Created internal task {task_id}: {description}")
        return task_id

    async def close_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "closed"
            logger.info(f"Closed internal task {task_id}")
            return True
        return False

class BeadsClient:
    def __init__(self):
        self.adapter: BeadsAdapter = self._select_adapter()

    def _select_adapter(self) -> BeadsAdapter:
        # Priority 1: CLI
        bd_path = shutil.which("bd")
        if bd_path:
            logger.info(f"Beads CLI found at {bd_path}")
            return CLIAdapter(bd_path)

        # Priority 2: MCP Package
        try:
            import beads_mcp
            logger.info("beads_mcp package found")
            return MCPAdapter(beads_mcp)
        except ImportError:
            pass

        # Priority 3: Internal Fallback
        return InternalAdapter()

    async def create_task(self, description: str) -> Optional[str]:
        return await self.adapter.create_task(description)

    async def close_task(self, task_id: str) -> bool:
        return await self.adapter.close_task(task_id)
