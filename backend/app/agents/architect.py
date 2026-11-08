from app.agents.base import Agent
from app.schemas import ArchitectOutput


class ArchitectAgent(Agent[ArchitectOutput]):
    name = "architect"
    output_model = ArchitectOutput
    prompt_file = "architect.md"
