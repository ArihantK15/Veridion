from abc import ABC, abstractmethod


class AgentAdapter(ABC):
    name: str = "unnamed"

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def invoke(self, instruction: str, cwd: str) -> str:
        raise NotImplementedError
