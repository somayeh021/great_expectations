from __future__ import annotations

import copy
import pathlib
from typing import Callable, List, Optional, cast
from unittest import mock

import pytest

import great_expectations.exceptions as gx_exceptions
from great_expectations.core.batch_config import BatchConfig
from great_expectations.core.data_context_key import DataContextVariableKey
from great_expectations.core.serializer import (
    AbstractConfigSerializer,
    DictConfigSerializer,
    JsonConfigSerializer,
)
from great_expectations.core.yaml_handler import YAMLHandler
from great_expectations.data_context.cloud_constants import GXCloudRESTResource
from great_expectations.data_context.data_context.file_data_context import (
    FileDataContext,
)
from great_expectations.data_context.data_context_variables import (
    DataContextVariableSchema,
)
from great_expectations.data_context.store.datasource_store import DatasourceStore
from great_expectations.data_context.store.gx_cloud_store_backend import (
    GXCloudStoreBackend,
)
from great_expectations.data_context.types.base import (
    DatasourceConfig,
    datasourceConfigSchema,
)
from great_expectations.datasource.datasource_serializer import (
    JsonDatasourceConfigSerializer,
    NamedDatasourceSerializer,
    YAMLReadyDictDatasourceConfigSerializer,
)
from great_expectations.datasource.fluent.interfaces import Datasource
from great_expectations.datasource.fluent.pandas_datasource import PandasDatasource
from tests.data_context.conftest import MockResponse

yaml = YAMLHandler()


@pytest.fixture
def fake_datasource_name() -> str:
    return "my_first_datasource"


@pytest.fixture
def empty_asset_name() -> str:
    return "empty asset"


@pytest.fixture
def asset_with_batch_config_name() -> str:
    return "i have a batch config"


@pytest.fixture
def batch_config_name() -> str:
    return "my cool batch config"


@pytest.fixture
def datasource_store_with_fds_datasource(
    empty_datasource_store: DatasourceStore,
    fake_datasource_name: str,
    empty_asset_name: str,
    asset_with_batch_config_name: str,
    batch_config_name: str,
) -> DatasourceStore:
    """Datasource store on datasource that has 2 assets. one of the assets has a batch config."""
    datasource = PandasDatasource(name=fake_datasource_name)
    datasource.add_csv_asset(empty_asset_name, "taxi.csv")
    asset = datasource.add_csv_asset(asset_with_batch_config_name, "taxi.csv")
    asset.add_batch_config(batch_config_name)

    key = DataContextVariableKey(
        resource_name=fake_datasource_name,
    )
    empty_datasource_store.set(key=key, value=datasource)
    return empty_datasource_store


@pytest.fixture
def empty_datasource_store(datasource_store_name: str) -> DatasourceStore:
    return DatasourceStore(
        store_name=datasource_store_name,
        serializer=DictConfigSerializer(schema=datasourceConfigSchema),
    )


@pytest.fixture
def datasource_store_with_single_datasource(
    fake_datasource_name,
    block_config_datasource_config: DatasourceConfig,
    empty_datasource_store: DatasourceStore,
) -> DatasourceStore:
    key = DataContextVariableKey(
        resource_name=fake_datasource_name,
    )
    empty_datasource_store.set(key=key, value=block_config_datasource_config)
    return empty_datasource_store


@pytest.mark.unit
def test_datasource_store_with_bad_key_raises_error(
    empty_datasource_store: DatasourceStore,
    block_config_datasource_config: DatasourceConfig,
) -> None:
    store: DatasourceStore = empty_datasource_store

    error_msg: str = "key must be an instance of DataContextVariableKey"

    with pytest.raises(TypeError, match=error_msg) as e:
        store.set(key="my_bad_key", value=block_config_datasource_config)  # type: ignore[arg-type]
    assert error_msg in str(e.value)

    with pytest.raises(TypeError) as e:
        store.get(key="my_bad_key")  # type: ignore[arg-type]


def _assert_serialized_datasource_configs_are_equal(
    datasource_configs: List[DatasourceConfig],
    serializers: Optional[List[AbstractConfigSerializer]] = None,
) -> None:
    """Assert that the datasource configs are equal using the DictConfigSerializer

    Args:
        datasource_configs: List of datasource configs to check

    Returns:
        None

    Raises:
        AssertionError
    """
    if len(datasource_configs) <= 1:
        raise AssertionError("Must provide at least 2 datasource configs")

    if serializers is None:
        serializers = [DictConfigSerializer(schema=datasourceConfigSchema)] * (
            len(datasource_configs) + 1
        )
    else:
        if len(serializers) <= 1:
            raise AssertionError("Must provide at least 2 datasource serializers")
        if not len(datasource_configs) == len(serializers):
            raise AssertionError(
                "Must provide the same number of serializers as datasource configs"
            )

    for idx, config in enumerate(datasource_configs[:-1]):
        assert serializers[idx].serialize(config) == serializers[idx + 1].serialize(
            datasource_configs[idx + 1]
        )


@pytest.mark.unit
def test__assert_serialized_datasource_configs_are_equal(
    block_config_datasource_config: DatasourceConfig,
    datasource_config_with_names: DatasourceConfig,
) -> None:
    """Verify test helper method."""

    # Input errors:
    with pytest.raises(AssertionError):
        _assert_serialized_datasource_configs_are_equal([])

    with pytest.raises(AssertionError):
        _assert_serialized_datasource_configs_are_equal(
            [block_config_datasource_config]
        )

    # Happy path
    _assert_serialized_datasource_configs_are_equal(
        [block_config_datasource_config, block_config_datasource_config]
    )
    _assert_serialized_datasource_configs_are_equal(
        [
            block_config_datasource_config,
            block_config_datasource_config,
            block_config_datasource_config,
        ]
    )

    # Unequal configs
    with pytest.raises(AssertionError):
        _assert_serialized_datasource_configs_are_equal(
            [block_config_datasource_config, datasource_config_with_names]
        )

    with pytest.raises(AssertionError):
        _assert_serialized_datasource_configs_are_equal(
            [
                block_config_datasource_config,
                block_config_datasource_config,
                datasource_config_with_names,
            ]
        )

    with pytest.raises(AssertionError):
        _assert_serialized_datasource_configs_are_equal(
            [
                block_config_datasource_config,
                block_config_datasource_config,
                datasource_config_with_names,
                block_config_datasource_config,
            ]
        )


@pytest.mark.unit
def test_datasource_store_retrieval(
    empty_datasource_store: DatasourceStore,
    block_config_datasource_config: DatasourceConfig,
) -> None:
    store: DatasourceStore = empty_datasource_store

    key = DataContextVariableKey(
        resource_name="my_datasource",
    )
    store.set(key=key, value=block_config_datasource_config)
    res: DatasourceConfig = store.get(key=key)

    assert isinstance(res, DatasourceConfig)
    set_config_serializer = DictConfigSerializer(schema=datasourceConfigSchema)
    retrieved_config_serializer = YAMLReadyDictDatasourceConfigSerializer(
        schema=datasourceConfigSchema
    )
    _assert_serialized_datasource_configs_are_equal(
        [block_config_datasource_config, res],
        [set_config_serializer, retrieved_config_serializer],
    )


@pytest.mark.unit
def test_datasource_store__add_batch_config__success(
    datasource_store_with_fds_datasource: DatasourceStore,
    empty_asset_name: str,
    fake_datasource_name: str,
) -> None:
    # Arrange
    store = datasource_store_with_fds_datasource
    asset = store.get_fluent_datasource_by_name(fake_datasource_name).get_asset(
        empty_asset_name
    )

    # Act
    batch_config = BatchConfig(name="my cool batch config")
    batch_config._data_asset = asset
    updated_batch_config = store.add_batch_config(batch_config)

    # Assert
    updated_datasource = store.get_fluent_datasource_by_name(fake_datasource_name)
    assert updated_batch_config.name == batch_config.name
    assert isinstance(updated_datasource, Datasource)
    updated_batch_configs = updated_datasource.get_asset(asset.name).batch_configs
    assert any(bc.name == batch_config.name for bc in updated_batch_configs)


@pytest.mark.unit
def test_datasource_store__add_batch_config__duplicate_name(
    datasource_store_with_fds_datasource: DatasourceStore,
    asset_with_batch_config_name: str,
    fake_datasource_name: str,
    batch_config_name: str,
) -> None:
    # Arrange
    store = datasource_store_with_fds_datasource
    asset = store.get_fluent_datasource_by_name(fake_datasource_name).get_asset(
        asset_with_batch_config_name
    )

    # Act + Assert
    new_batch_config = BatchConfig(name=batch_config_name)
    new_batch_config._data_asset = asset

    with pytest.raises(ValueError, match="already exists"):
        store.add_batch_config(new_batch_config)


@pytest.mark.unit
def test_datasource_store__delete_batch_config__success(
    datasource_store_with_fds_datasource: DatasourceStore,
    asset_with_batch_config_name: str,
    fake_datasource_name: str,
) -> None:
    # Arrange
    store = datasource_store_with_fds_datasource
    asset = store.get_fluent_datasource_by_name(fake_datasource_name).get_asset(
        asset_with_batch_config_name
    )
    assert len(asset.batch_configs) == 1

    # Act
    store.delete_batch_config(asset.batch_configs[0])

    # Assert
    updated_asset = store.get_fluent_datasource_by_name(fake_datasource_name).get_asset(
        asset_with_batch_config_name
    )
    assert len(updated_asset.batch_configs) == 0


@pytest.mark.unit
def test_datasource_store__delete_batch_config__does_not_exist(
    datasource_store_with_fds_datasource: DatasourceStore,
    empty_asset_name: str,
    fake_datasource_name: str,
    batch_config_name: str,
) -> None:
    # Arrange
    store = datasource_store_with_fds_datasource
    asset = store.get_fluent_datasource_by_name(fake_datasource_name).get_asset(
        empty_asset_name
    )

    # Act + Assert
    new_batch_config = BatchConfig(name=batch_config_name)
    new_batch_config._data_asset = asset

    with pytest.raises(ValueError, match="does not exist"):
        store.delete_batch_config(new_batch_config)


@pytest.mark.cloud
def test_datasource_store_set_cloud_mode(
    block_config_datasource_config: DatasourceConfig,
    datasource_config_with_names_and_ids: DatasourceConfig,
    mocked_datasource_post_response: Callable[[], MockResponse],
    mocked_datasource_get_response: Callable[[], MockResponse],
    ge_cloud_base_url: str,
    ge_cloud_access_token: str,
    ge_cloud_organization_id: str,
) -> None:
    ge_cloud_store_backend_config: dict = {
        "class_name": GXCloudStoreBackend.__name__,
        "ge_cloud_base_url": ge_cloud_base_url,
        "ge_cloud_resource_type": GXCloudRESTResource.DATASOURCE,
        "ge_cloud_credentials": {
            "access_token": ge_cloud_access_token,
            "organization_id": ge_cloud_organization_id,
        },
        "suppress_store_backend_id": True,
    }

    store = DatasourceStore(
        store_name="my_cloud_datasource_store",
        store_backend=ge_cloud_store_backend_config,
        serializer=JsonConfigSerializer(schema=datasourceConfigSchema),
    )

    with mock.patch(
        "requests.Session.post",
        autospec=True,
        side_effect=mocked_datasource_post_response,
    ) as mock_post, mock.patch(
        "requests.Session.get",
        autospec=True,
        side_effect=mocked_datasource_get_response,
    ):
        retrieved_datasource_config = store.set(
            key=None, value=block_config_datasource_config
        )

        serializer = NamedDatasourceSerializer(schema=datasourceConfigSchema)
        expected_datasource_config = serializer.serialize(
            block_config_datasource_config
        )

        mock_post.assert_called_with(
            mock.ANY,  # requests.Session object
            f"{ge_cloud_base_url}/organizations/{ge_cloud_organization_id}/datasources",
            json={
                "data": {
                    "type": "datasource",
                    "attributes": {
                        "datasource_config": expected_datasource_config,
                        "organization_id": ge_cloud_organization_id,
                    },
                }
            },
        )

        json_serializer = JsonDatasourceConfigSerializer(schema=datasourceConfigSchema)

        assert json_serializer.serialize(
            retrieved_datasource_config
        ) == json_serializer.serialize(datasource_config_with_names_and_ids)


@pytest.mark.filesystem
def test_datasource_store_with_inline_store_backend(
    block_config_datasource_config: DatasourceConfig, empty_data_context
) -> None:
    inline_store_backend_config: dict = {
        "class_name": "InlineStoreBackend",
        "resource_type": DataContextVariableSchema.DATASOURCES,
        "data_context": empty_data_context,
        "suppress_store_backend_id": True,
    }

    store = DatasourceStore(
        store_name="my_datasource_store",
        store_backend=inline_store_backend_config,
        serializer=YAMLReadyDictDatasourceConfigSerializer(
            schema=datasourceConfigSchema
        ),
    )

    key = DataContextVariableKey(
        resource_name="my_datasource",
    )

    store.set(key=key, value=block_config_datasource_config)
    res: DatasourceConfig = store.get(key=key)

    assert isinstance(res, DatasourceConfig)
    set_config_serializer = DictConfigSerializer(schema=datasourceConfigSchema)
    retrieved_config_serializer = YAMLReadyDictDatasourceConfigSerializer(
        schema=datasourceConfigSchema
    )
    _assert_serialized_datasource_configs_are_equal(
        [block_config_datasource_config, res],
        [set_config_serializer, retrieved_config_serializer],
    )


@pytest.mark.unit
def test_datasource_store_add_by_name(
    empty_datasource_store: DatasourceStore,
    block_config_datasource_config: DatasourceConfig,
    fake_datasource_name,
) -> None:
    assert len(empty_datasource_store.list_keys()) == 0

    empty_datasource_store.add_by_name(
        datasource_name=fake_datasource_name,
        datasource_config=block_config_datasource_config,
    )

    assert len(empty_datasource_store.list_keys()) == 1


@pytest.mark.unit
def test_datasource_store_set(
    empty_datasource_store: DatasourceStore,
    block_config_datasource_config: DatasourceConfig,
    fake_datasource_name,
) -> None:
    assert len(empty_datasource_store.list_keys()) == 0

    block_config_datasource_config.name = fake_datasource_name
    retrieved_datasource_config: DatasourceConfig = empty_datasource_store.set(
        key=None, value=block_config_datasource_config
    )

    assert len(empty_datasource_store.list_keys()) == 1

    # Use a consistent serializer to check equality
    serializer = JsonDatasourceConfigSerializer(schema=datasourceConfigSchema)
    assert serializer.serialize(retrieved_datasource_config) == serializer.serialize(
        block_config_datasource_config
    )


@pytest.mark.unit
def test_datasource_store_retrieve_by_name(
    fake_datasource_name,
    block_config_datasource_config: DatasourceConfig,
    datasource_store_with_single_datasource: DatasourceStore,
) -> None:
    actual_config: DatasourceConfig = (
        datasource_store_with_single_datasource.retrieve_by_name(
            datasource_name=fake_datasource_name
        )
    )
    set_config_serializer = DictConfigSerializer(schema=datasourceConfigSchema)
    retrieved_config_serializer = YAMLReadyDictDatasourceConfigSerializer(
        schema=datasourceConfigSchema
    )
    _assert_serialized_datasource_configs_are_equal(
        [block_config_datasource_config, actual_config],
        [set_config_serializer, retrieved_config_serializer],
    )


@pytest.mark.unit
def test_datasource_store_delete(
    block_config_datasource_config: DatasourceConfig,
    datasource_store_with_single_datasource: DatasourceStore,
) -> None:
    initial_keys = datasource_store_with_single_datasource.list_keys()
    assert len(initial_keys) == 1

    datasource_name = initial_keys[0].resource_name
    block_config_datasource_config.name = datasource_name

    datasource_store_with_single_datasource.delete(
        datasource_config=block_config_datasource_config,
    )

    assert len(datasource_store_with_single_datasource.list_keys()) == 0


@pytest.mark.unit
def test_datasource_store_update_by_name(
    fake_datasource_name,
    block_config_datasource_config: DatasourceConfig,
    datasource_store_with_single_datasource: DatasourceStore,
) -> None:
    updated_base_directory: str = "foo/bar/baz"

    updated_datasource_config = copy.deepcopy(block_config_datasource_config)
    updated_datasource_config.data_connectors["tripdata_monthly_configured"][
        "base_directory"
    ] = updated_base_directory

    datasource_store_with_single_datasource.update_by_name(
        datasource_name=fake_datasource_name,
        datasource_config=updated_datasource_config,
    )

    key = DataContextVariableKey(
        resource_name=fake_datasource_name,
    )
    actual_config = cast(
        DatasourceConfig, datasource_store_with_single_datasource.get(key=key)
    )

    set_config_serializer = DictConfigSerializer(schema=datasourceConfigSchema)
    retrieved_config_serializer = YAMLReadyDictDatasourceConfigSerializer(
        schema=datasourceConfigSchema
    )
    _assert_serialized_datasource_configs_are_equal(
        [updated_datasource_config, actual_config],
        [set_config_serializer, retrieved_config_serializer],
    )


@pytest.mark.unit
def test_datasource_store_update_raises_error_if_datasource_doesnt_exist(
    fake_datasource_name,
    empty_datasource_store: DatasourceStore,
) -> None:
    updated_datasource_config = DatasourceConfig()
    with pytest.raises(
        gx_exceptions.DatasourceNotFoundError,
        match=f"Could not find an existing Datasource named {fake_datasource_name}.",
    ):
        empty_datasource_store.update_by_name(
            datasource_name=fake_datasource_name,
            datasource_config=updated_datasource_config,
        )


@pytest.mark.unit
def test_datasource_store_with_inline_store_backend_config_with_names_does_not_store_datasource_name(
    datasource_config_with_names: DatasourceConfig,
    block_config_datasource_config: DatasourceConfig,
    empty_data_context,
) -> None:
    inline_store_backend_config: dict = {
        "class_name": "InlineStoreBackend",
        "resource_type": DataContextVariableSchema.DATASOURCES,
        "data_context": empty_data_context,
        "suppress_store_backend_id": True,
    }

    store = DatasourceStore(
        store_name="my_datasource_store",
        store_backend=inline_store_backend_config,
        serializer=YAMLReadyDictDatasourceConfigSerializer(
            schema=datasourceConfigSchema
        ),
    )

    key = DataContextVariableKey(
        resource_name="my_datasource",
    )

    store.set(key=key, value=datasource_config_with_names)
    res: DatasourceConfig = store.get(key=key)

    assert isinstance(res, DatasourceConfig)
    set_config_serializer = DictConfigSerializer(schema=datasourceConfigSchema)
    retrieved_config_serializer = YAMLReadyDictDatasourceConfigSerializer(
        schema=datasourceConfigSchema
    )
    _assert_serialized_datasource_configs_are_equal(
        [block_config_datasource_config, res],
        [set_config_serializer, retrieved_config_serializer],
    )

    with open(
        pathlib.Path(empty_data_context.root_directory) / FileDataContext.GX_YML
    ) as f:
        context_config_from_disk: dict = yaml.load(f)

    assert "name" not in context_config_from_disk["datasources"]["my_datasource"]


@pytest.mark.filesystem
def test_datasource_store_with_inline_store_backend_config_with_names_does_not_store_dataconnector_name(
    datasource_config_with_names: DatasourceConfig,
    block_config_datasource_config: DatasourceConfig,
    empty_data_context,
) -> None:
    inline_store_backend_config: dict = {
        "class_name": "InlineStoreBackend",
        "resource_type": DataContextVariableSchema.DATASOURCES,
        "data_context": empty_data_context,
        "suppress_store_backend_id": True,
    }

    store = DatasourceStore(
        store_name="my_datasource_store",
        store_backend=inline_store_backend_config,
        serializer=YAMLReadyDictDatasourceConfigSerializer(
            schema=datasourceConfigSchema
        ),
    )

    key = DataContextVariableKey(
        resource_name="my_datasource",
    )

    store.set(key=key, value=datasource_config_with_names)
    res: DatasourceConfig = store.get(key=key)

    assert isinstance(res, DatasourceConfig)
    set_config_serializer = DictConfigSerializer(schema=datasourceConfigSchema)
    retrieved_config_serializer = YAMLReadyDictDatasourceConfigSerializer(
        schema=datasourceConfigSchema
    )
    _assert_serialized_datasource_configs_are_equal(
        [block_config_datasource_config, res],
        [set_config_serializer, retrieved_config_serializer],
    )

    with open(
        pathlib.Path(empty_data_context.root_directory) / FileDataContext.GX_YML
    ) as f:
        context_config_from_disk: dict = yaml.load(f)

    assert (
        "name"
        not in context_config_from_disk["datasources"]["my_datasource"][
            "data_connectors"
        ]["tripdata_monthly_configured"]
    )


@pytest.mark.cloud
@pytest.mark.parametrize(
    "response_json, expected, error_type",
    [
        pytest.param(
            {
                "data": {
                    "id": "03d61d4e-003f-48e7-a3b2-f9f842384da3",
                    "attributes": {
                        "datasource_config": {
                            "name": "my_pandas",
                            "type": "pandas",
                            "assets": [],
                        },
                    },
                }
            },
            {
                "id": "03d61d4e-003f-48e7-a3b2-f9f842384da3",
                "name": "my_pandas",
                "type": "pandas",
                "assets": [],
            },
            None,
            id="single_config",
        ),
        pytest.param(
            {
                "data": [
                    {
                        "id": "03d61d4e-003f-48e7-a3b2-f9f842384da3",
                        "attributes": {
                            "datasource_config": {
                                "name": "my_pandas",
                                "type": "pandas",
                                "assets": [],
                            },
                        },
                    }
                ]
            },
            {
                "id": "03d61d4e-003f-48e7-a3b2-f9f842384da3",
                "name": "my_pandas",
                "type": "pandas",
                "assets": [],
            },
            None,
            id="single_config_in_list",
        ),
        pytest.param(
            {
                "data": [
                    {
                        "data": [
                            {
                                "id": "03d61d4e-003f-48e7-a3b2-f9f842384da3",
                                "attributes": {
                                    "datasource_config": {
                                        "name": "my_pandas",
                                        "type": "pandas",
                                        "assets": [],
                                    },
                                },
                            }
                        ]
                    },
                    {
                        "data": [
                            {
                                "id": "ffg61d4e-003f-48e7-a3b2-f9f842384da3",
                                "attributes": {
                                    "data_asset_config": {
                                        "name": "my_other_pandas",
                                        "type": "pandas",
                                    },
                                },
                            }
                        ]
                    },
                ]
            },
            None,
            TypeError,
            id="multiple_config_in_list",
        ),
    ],
)
def test_gx_cloud_response_json_to_object_dict(
    response_json: dict, expected: dict | None, error_type: Exception | None
) -> None:
    if error_type:
        with pytest.raises(error_type):
            _ = DatasourceStore.gx_cloud_response_json_to_object_dict(response_json)
    else:
        actual = DatasourceStore.gx_cloud_response_json_to_object_dict(response_json)
        assert actual == expected


@pytest.mark.cloud
def test_gx_cloud_response_json_to_object_collection():
    response_json = {
        "data": [
            {
                "attributes": {
                    "datasource_config": {
                        "class_name": "Datasource",
                        "data_connectors": {
                            "pandas_data_connector": {
                                "assets": {
                                    "hurricanes_and_typhoons": {
                                        "batch_identifiers": ["ocean"],
                                        "class_name": "Asset",
                                        "module_name": "great_expectations.datasource.data_connector.asset",
                                        "name": "hurricanes_and_typhoons",
                                    }
                                },
                                "class_name": "RuntimeDataConnector",
                                "id": "7df29075-2e4d-46b1-aa6f-3e93c19bd7b2",
                                "module_name": "great_expectations.datasource.data_connector",
                                "name": "pandas_data_connector",
                            }
                        },
                        "execution_engine": {
                            "class_name": "PandasExecutionEngine",
                            "module_name": "great_expectations.execution_engine",
                        },
                        "id": "2e3248b9-465f-4933-b313-cae6e3cbe685",
                        "module_name": "great_expectations.datasource",
                        "name": "weather_ds",
                    }
                },
                "id": "2e3248b9-465f-4933-b313-cae6e3cbe685",
                "type": "datasource",
            },
            {
                "attributes": {
                    "datasource_config": {
                        "class_name": "Datasource",
                        "data_connectors": {
                            "default_runtime_data_connector": {
                                "batch_identifiers": ["my_identifier"],
                                "class_name": "RuntimeDataConnector",
                                "id": "c84911b0-a42e-4196-afb9-754532e465aa",
                                "module_name": "great_expectations.datasource.data_connector",
                                "name": "default_runtime_data_connector",
                            }
                        },
                        "execution_engine": {
                            "class_name": "PandasExecutionEngine",
                            "module_name": "great_expectations.execution_engine",
                        },
                        "id": "9bd4deb0-1729-4eda-a829-eeb41bf4bbf1",
                        "module_name": "great_expectations.datasource",
                        "name": "runtime_datasource",
                    }
                },
                "id": "9bd4deb0-1729-4eda-a829-eeb41bf4bbf1",
                "type": "datasource",
            },
        ]
    }
    expected = [
        {
            "class_name": "Datasource",
            "data_connectors": {
                "pandas_data_connector": {
                    "assets": {
                        "hurricanes_and_typhoons": {
                            "batch_identifiers": ["ocean"],
                            "class_name": "Asset",
                            "module_name": "great_expectations.datasource.data_connector.asset",
                            "name": "hurricanes_and_typhoons",
                        },
                    },
                    "class_name": "RuntimeDataConnector",
                    "id": "7df29075-2e4d-46b1-aa6f-3e93c19bd7b2",
                    "module_name": "great_expectations.datasource.data_connector",
                    "name": "pandas_data_connector",
                },
            },
            "execution_engine": {
                "class_name": "PandasExecutionEngine",
                "module_name": "great_expectations.execution_engine",
            },
            "id": "2e3248b9-465f-4933-b313-cae6e3cbe685",
            "module_name": "great_expectations.datasource",
            "name": "weather_ds",
        },
        {
            "class_name": "Datasource",
            "data_connectors": {
                "default_runtime_data_connector": {
                    "batch_identifiers": ["my_identifier"],
                    "class_name": "RuntimeDataConnector",
                    "id": "c84911b0-a42e-4196-afb9-754532e465aa",
                    "module_name": "great_expectations.datasource.data_connector",
                    "name": "default_runtime_data_connector",
                },
            },
            "execution_engine": {
                "class_name": "PandasExecutionEngine",
                "module_name": "great_expectations.execution_engine",
            },
            "id": "9bd4deb0-1729-4eda-a829-eeb41bf4bbf1",
            "module_name": "great_expectations.datasource",
            "name": "runtime_datasource",
        },
    ]

    actual = DatasourceStore.gx_cloud_response_json_to_object_collection(response_json)
    assert actual == expected
