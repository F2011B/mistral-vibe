from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from vibe.core.orchestrator import Orchestrator
from vibe.core.tools.base import BaseTool, BaseToolConfig, BaseToolState, ToolPermission


class SpawnSubAgentArgs(BaseModel):
    task: str = Field(..., description="The task description for the sub-agent.")
    use_worktree: bool = Field(
        default=True,
        description="Whether to use a separate git worktree for isolation.",
    )


class SpawnSubAgentResult(BaseModel):
    agent_id: str
    status: str


class SpawnSubAgentConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK


class SpawnSubAgent(
    BaseTool[
        SpawnSubAgentArgs, SpawnSubAgentResult, SpawnSubAgentConfig, BaseToolState
    ]
):
    description: ClassVar[str] = "Spawn a new sub-agent to perform a task in the background."

    def __init__(
        self,
        config: SpawnSubAgentConfig,
        state: BaseToolState,
        orchestrator: Orchestrator,
    ) -> None:
        super().__init__(config=config, state=state)
        self.orchestrator = orchestrator

    async def run(self, args: SpawnSubAgentArgs) -> SpawnSubAgentResult:
        agent_id = await self.orchestrator.spawn_subagent(
            task=args.task, use_worktree=args.use_worktree
        )
        return SpawnSubAgentResult(agent_id=agent_id, status="STARTING")


class ListSubAgentsArgs(BaseModel):
    pass


class ListSubAgentsResult(BaseModel):
    agents: list[dict]


class ListSubAgentsConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class ListSubAgents(
    BaseTool[
        ListSubAgentsArgs, ListSubAgentsResult, ListSubAgentsConfig, BaseToolState
    ]
):
    description: ClassVar[str] = "List all running or completed sub-agents."

    def __init__(
        self,
        config: ListSubAgentsConfig,
        state: BaseToolState,
        orchestrator: Orchestrator,
    ) -> None:
        super().__init__(config=config, state=state)
        self.orchestrator = orchestrator

    async def run(self, args: ListSubAgentsArgs) -> ListSubAgentsResult:
        agents = []
        for agent in self.orchestrator.list_subagents():
            agents.append(
                {
                    "id": agent.id,
                    "task": agent.task,
                    "status": agent.status,
                    "worktree": str(agent.worktree_path) if agent.worktree_path else None,
                    "exit_code": agent.exit_code,
                }
            )
        return ListSubAgentsResult(agents=agents)


class GetSubAgentLogsArgs(BaseModel):
    agent_id: str


class GetSubAgentLogsResult(BaseModel):
    logs: list[str]


class GetSubAgentLogsConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ALWAYS


class GetSubAgentLogs(
    BaseTool[
        GetSubAgentLogsArgs,
        GetSubAgentLogsResult,
        GetSubAgentLogsConfig,
        BaseToolState,
    ]
):
    description: ClassVar[str] = "Get the logs of a specific sub-agent."

    def __init__(
        self,
        config: GetSubAgentLogsConfig,
        state: BaseToolState,
        orchestrator: Orchestrator,
    ) -> None:
        super().__init__(config=config, state=state)
        self.orchestrator = orchestrator

    async def run(self, args: GetSubAgentLogsArgs) -> GetSubAgentLogsResult:
        agent = self.orchestrator.get_subagent(args.agent_id)
        if not agent:
            return GetSubAgentLogsResult(logs=["Agent not found"])
        return GetSubAgentLogsResult(logs=agent.logs)


class MergeWorktreeArgs(BaseModel):
    agent_id: str


class MergeWorktreeResult(BaseModel):
    branch_name: str


class MergeWorktreeConfig(BaseToolConfig):
    permission: ToolPermission = ToolPermission.ASK


class MergeWorktree(
    BaseTool[
        MergeWorktreeArgs, MergeWorktreeResult, MergeWorktreeConfig, BaseToolState
    ]
):
    description: ClassVar[
        str
    ] = "Prepare a sub-agent's worktree for merging by converting it to a branch."

    def __init__(
        self,
        config: MergeWorktreeConfig,
        state: BaseToolState,
        orchestrator: Orchestrator,
    ) -> None:
        super().__init__(config=config, state=state)
        self.orchestrator = orchestrator

    async def run(self, args: MergeWorktreeArgs) -> MergeWorktreeResult:
        branch = await self.orchestrator.convert_worktree_to_branch(args.agent_id)
        return MergeWorktreeResult(branch_name=branch)
