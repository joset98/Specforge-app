from app.agents.base import Agent
from app.schemas import ProductOwnerOutput


class ProductOwnerAgent(Agent[ProductOwnerOutput]):
    name = "product_owner"
    output_model = ProductOwnerOutput
    prompt_file = "product_owner.md"
