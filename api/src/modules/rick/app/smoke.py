import time
from datetime import timedelta

from papilio.infra.db.transaction import transaction

from portal_contracts.configuration import PortalConfiguration
from src.config.settings import PortalAppSettings
from src.modules.missions.domain.dtos import MissionChange
from src.modules.missions.domain.models import MissionModel
from src.modules.missions.infra.mysql import MissionRepository
from src.modules.rick.interfaces import IRickAgent
from src.shared.dates import utc_now
from src.shared.errors import conflict, forbidden


class ModelSmokeCommands:
    def __init__(
        self,
        missions: MissionRepository,
        agent: IRickAgent,
        runtime: PortalAppSettings,
        settings: PortalConfiguration,
    ):
        self.missions = missions
        self.agent = agent
        self.runtime = runtime
        self.settings = settings

    async def run(self, owner_id: int, bot_id: int) -> str:
        if owner_id not in self.runtime.security.admin_ids:
            raise forbidden()
        if self.settings.ai.mode != "openrouter":
            raise conflict("A live OpenRouter model must be configured")
        now = utc_now()
        deadline = now + timedelta(
            seconds=self.settings.portal.mission_timeout
        )
        async with transaction():
            mission = await self.missions.create(
                MissionModel(
                    owner_id=owner_id,
                    origin_chat_id=owner_id,
                    origin_bot="rick",
                    origin_message_id=1,
                    bot_id=bot_id,
                    update_id=time.time_ns(),
                    actor="rick",
                    intent="chat",
                    text=(
                        "Confirm that the portal is working in one short "
                        "sentence. Do not call tools."
                    ),
                    deadline=deadline,
                    lease_expires_at=deadline,
                    status="running",
                    stage="smoke",
                )
            )
            snapshot = mission.model_copy()
        try:
            outcome = await self.agent.step(snapshot, tools_enabled=False)
            if outcome.waiting or not outcome.text:
                raise ValueError("Model smoke test did not produce a reply")
        except Exception:
            async with transaction():
                await self.missions.change(
                    mission.id,
                    MissionChange(
                        status="failed",
                        stage="smoke",
                        failure_reason="model_smoke_failed",
                    ),
                )
            raise
        async with transaction():
            await self.missions.change(
                mission.id,
                MissionChange(
                    status="completed",
                    stage="smoke",
                    result=outcome.text,
                ),
            )
        return outcome.text
