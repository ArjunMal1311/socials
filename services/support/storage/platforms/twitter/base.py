from typing import Dict
from abc import abstractmethod
from services.support.storage.base_storage import BaseStorage

class BaseTwitterStorage(BaseStorage):
    @abstractmethod
    def _get_table_name(self) -> str:
        pass

    @abstractmethod
    def _get_table_schema(self) -> Dict[str, str]:
        pass
