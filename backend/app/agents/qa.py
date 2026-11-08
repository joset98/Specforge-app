from app.agents.base import Agent
from app.schemas import QAOutput


class QAAgent(Agent[QAOutput]):
    name = "qa"
    output_model = QAOutput
    prompt_file = "qa.md"
