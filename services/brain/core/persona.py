from dataclasses import dataclass
from core.gateway.base import ChatMessage


@dataclass
class PersonaConfig:
    """Configurable system identity and behavioral guidelines for LEVIATHAN."""

    name: str = "LEVIATHAN"
    role: str = "Personal AI Assistant and Integrated AI Coding Companion"
    tone: str = "Concise, precise, direct, helpful, and technically adept"
    custom_instructions: str = ""

    def get_system_prompt(self, model_name: str) -> str:
        """Generate the full system prompt for a given model."""
        prompt_lines = [
            f"You are {self.name}, a {self.role}.",
            f"You must always identify yourself as {self.name}. Never refer to yourself as Qwen, Gemma, Llama, or any other base model family.",
            f"Your underlying model architecture is '{model_name}'. If the user specifically asks what model, engine, or architecture powers you, answer honestly that you are powered by {model_name}.",
            f"Demeanor and communication style: {self.tone}.",
        ]
        if self.custom_instructions:
            prompt_lines.append(f"Additional instructions: {self.custom_instructions}")

        return "\n".join(prompt_lines)


# Default global persona
default_persona = PersonaConfig()


def prepare_messages_with_persona(
    messages: list[ChatMessage],
    model: str,
    persona: PersonaConfig = default_persona,
) -> list[ChatMessage]:
    """Ensure the system prompt is present exactly once at the beginning of the message list.

    Any existing system messages (e.g. from previous turns or client requests)
    are consolidated into a single leading system prompt to prevent duplication across multi-turn chats.
    """
    system_prompt = persona.get_system_prompt(model)

    # Filter out existing system messages to avoid duplication across turns
    non_system_messages = [m for m in messages if m.role != "system"]

    # Exactly one system prompt at index 0, followed by user/assistant turns
    return [ChatMessage(role="system", content=system_prompt)] + non_system_messages

