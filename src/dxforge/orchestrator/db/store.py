from typing import Dict, Any, Optional, Type, TypeVar
from datetime import datetime
from pydantic import BaseModel, create_model, ValidationError
from pymongo import ReturnDocument

from orchestrator.db import DBHelper

T = TypeVar("T", bound=BaseModel)


class Store:
    """
    Scalable metadata manager for dxforge with Pydantic validation,
    now using MongoDBHelper for safe DB access.
    """
    def __init__(self, db_helper: DBHelper, document_collection: str, schema_collection: str = "schemas"):
        self.db_helper = db_helper
        if not self.db_helper.is_connected():
            self.db_helper.connect()

        self.schema_collection = self.db_helper.get_collection(schema_collection)
        self.document_collection = self.db_helper.get_collection(document_collection)

        # runtime cached Pydantic models
        self._models: Dict[str, Type[BaseModel]] = {}

    #########################
    # MODEL/SCHEMA MANAGEMENT
    #########################
    def register_model(self, model_name: str, model: Type[BaseModel]) -> None:
        # we need to store the model as a schema (dict of the model), not a Pydantic model
        schema = model.model_json_schema()

        doc = {
            "model_name": model_name,
            "schema": schema,
            "updated_at": datetime.now()
        }
        self.schema_collection.update_one(
            {"model_name": model_name},
            {"$set": doc},
            upsert=True
        )
        # self._models[metadata_type] = create_model(metadata_type, **schema)
        self._models[model_name] = model

    def load_schemas(self) -> None:
        """
        Load all schemas from MongoDB into runtime Pydantic models.
        """
        for doc in self.schema_collection.find():
            model_name = doc["model_name"]
            schema = doc["schema"]
            self._models[model_name] = create_model(model_name, **schema)

    def get_schema(self, model_name: str) -> Optional[Dict[str, Any]]:
        doc = self.schema_collection.find_one({"model_name": model_name})
        return doc.get("schema") if doc else None

    ###########################
    # DOCUMENT STORE MANAGEMENT
    ###########################
    def create(self, model_name: str, document_id: str, document: BaseModel) -> None:
        # ensure has been registered
        registered = self._models.get(model_name)
        # validate with pydantic
        if registered:
            validated = document.model_dump()
        else:
            raise ValueError(f"'{model_name}' not registered in store.")

        doc = {
            "model_name": model_name,
            "document_id": document_id,
            "data": validated,
            "created_at": datetime.now()
        }
        self.document_collection.insert_one(doc)

    @classmethod
    def filter(cls,
               model_name: str,
               document_filters: Optional[Dict[str, Any]] = None,
               data_filters: Optional[Dict[str, Any]] = None,
               ) -> Any:
        if data_filters is None and document_filters is None:
            raise ValueError("Must provide at least one filter.")

        filters = {"model_name": model_name}
        if document_filters:
            filters.update(document_filters)

        if data_filters:
            data_filters = {f"data.{k}": v for k, v in data_filters.items()}
            filters.update(data_filters)
        return filters

    def update(self,
               model_name: str,
               update: BaseModel,
               document_filters: Optional[Dict[str, Any]] = None,
               data_filters: Optional[Dict[str, Any]] = None,
               ) -> Any:
        filters = self.filter(model_name, document_filters, data_filters)

        data = update.model_dump()
        update = {"$set": {"data": data}}

        return self.document_collection.find_one_and_update(filters, update, return_document=ReturnDocument.AFTER)

    def partial_update(self,
                       model_name: str,
                       updates: Dict[str, Any],
                       document_filters: Optional[Dict[str, Any]] = None,
                       data_filters: Optional[Dict[str, Any]] = None,
                       validate=True
                       ) -> Any:
        """
        Update only the provided fields of an existing instance,
        preserving existing data and validating with Pydantic.
        """
        filters = self.filter(model_name, document_filters, data_filters)

        if validate:
            try:
                model = self._models[model_name]
                current = self.get(model_name, filters).model_dump() or {}
                current.update(updates)

                model.model_validate(current)
            except ValidationError as e:
                raise ValueError(f"Validation failed for updates: {e}")
            except KeyError:
                raise ValueError(f"Schema for metadata type '{model_name}' not registered.")

        update = {"$set": {f"data.{k}": v for k, v in updates.items()}}
        return self.document_collection.find_one_and_update(filters, update, upsert=True, return_document=ReturnDocument.AFTER)


    def get(self,
            model_name: str,
            document_filters: Optional[Dict[str, Any]] = None,
            data_filters: Optional[Dict[str, Any]] = None,
            ) -> Optional[T]:
        try:
            model: type[T] = self._models[model_name]
        except KeyError:
            raise KeyError("Model for document type not registered.")

        filters = self.filter(model_name, document_filters, data_filters)
        document = self.document_collection.find_one(filters)

        if document is None:
            return None

        data = document.get("data")

        try:
            return model.model_validate(data)
        except ValidationError:
            raise ValueError("Invalid schema for existing metadata.")

    def delete(self,
               model_name: str,
               documet_filters: Optional[Dict[str, Any]] = None,
               data_filters: Optional[Dict[str, Any]] = None
               ):
        filters = self.filter(model_name, documet_filters, data_filters)
        return self.document_collection.delete_one(filters)

    def list_documents(self, model_name: str) -> Dict[str, Dict[str, Any]]:
        return {
            doc["document_id"]: doc["data"]
            for doc in self.document_collection.find({"model_name": model_name})
        }
