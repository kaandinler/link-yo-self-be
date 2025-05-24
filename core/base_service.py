from typing import List, Any

class BaseService:
    def __init__(self, repository):
        self._repo = repository

    async def list(self, model) -> List[Any]:
        return await self._repo.list_all(model)

    async def get(self, model, id: Any) -> Any:
        return await self._repo.get_by_id(model, id)
