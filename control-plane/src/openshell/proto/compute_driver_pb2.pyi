from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetCapabilitiesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetCapabilitiesResponse(_message.Message):
    __slots__ = ("driver_name", "driver_version", "default_image", "supports_gpu", "gpu_count")
    DRIVER_NAME_FIELD_NUMBER: _ClassVar[int]
    DRIVER_VERSION_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_IMAGE_FIELD_NUMBER: _ClassVar[int]
    SUPPORTS_GPU_FIELD_NUMBER: _ClassVar[int]
    GPU_COUNT_FIELD_NUMBER: _ClassVar[int]
    driver_name: str
    driver_version: str
    default_image: str
    supports_gpu: bool
    gpu_count: int
    def __init__(self, driver_name: _Optional[str] = ..., driver_version: _Optional[str] = ..., default_image: _Optional[str] = ..., supports_gpu: bool = ..., gpu_count: _Optional[int] = ...) -> None: ...

class DriverSandbox(_message.Message):
    __slots__ = ("id", "name", "namespace", "spec", "status")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    namespace: str
    spec: DriverSandboxSpec
    status: DriverSandboxStatus
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., namespace: _Optional[str] = ..., spec: _Optional[_Union[DriverSandboxSpec, _Mapping]] = ..., status: _Optional[_Union[DriverSandboxStatus, _Mapping]] = ...) -> None: ...

class DriverSandboxSpec(_message.Message):
    __slots__ = ("log_level", "environment", "template", "gpu", "gpu_device", "sandbox_token")
    class EnvironmentEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    LOG_LEVEL_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    GPU_FIELD_NUMBER: _ClassVar[int]
    GPU_DEVICE_FIELD_NUMBER: _ClassVar[int]
    SANDBOX_TOKEN_FIELD_NUMBER: _ClassVar[int]
    log_level: str
    environment: _containers.ScalarMap[str, str]
    template: DriverSandboxTemplate
    gpu: bool
    gpu_device: str
    sandbox_token: str
    def __init__(self, log_level: _Optional[str] = ..., environment: _Optional[_Mapping[str, str]] = ..., template: _Optional[_Union[DriverSandboxTemplate, _Mapping]] = ..., gpu: bool = ..., gpu_device: _Optional[str] = ..., sandbox_token: _Optional[str] = ...) -> None: ...

class DriverSandboxTemplate(_message.Message):
    __slots__ = ("image", "agent_socket_path", "labels", "environment", "resources", "platform_config")
    class LabelsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    class EnvironmentEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    AGENT_SOCKET_PATH_FIELD_NUMBER: _ClassVar[int]
    LABELS_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_CONFIG_FIELD_NUMBER: _ClassVar[int]
    image: str
    agent_socket_path: str
    labels: _containers.ScalarMap[str, str]
    environment: _containers.ScalarMap[str, str]
    resources: DriverResourceRequirements
    platform_config: _struct_pb2.Struct
    def __init__(self, image: _Optional[str] = ..., agent_socket_path: _Optional[str] = ..., labels: _Optional[_Mapping[str, str]] = ..., environment: _Optional[_Mapping[str, str]] = ..., resources: _Optional[_Union[DriverResourceRequirements, _Mapping]] = ..., platform_config: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class DriverResourceRequirements(_message.Message):
    __slots__ = ("cpu_request", "cpu_limit", "memory_request", "memory_limit")
    CPU_REQUEST_FIELD_NUMBER: _ClassVar[int]
    CPU_LIMIT_FIELD_NUMBER: _ClassVar[int]
    MEMORY_REQUEST_FIELD_NUMBER: _ClassVar[int]
    MEMORY_LIMIT_FIELD_NUMBER: _ClassVar[int]
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str
    def __init__(self, cpu_request: _Optional[str] = ..., cpu_limit: _Optional[str] = ..., memory_request: _Optional[str] = ..., memory_limit: _Optional[str] = ...) -> None: ...

class DriverSandboxStatus(_message.Message):
    __slots__ = ("sandbox_name", "instance_id", "agent_fd", "sandbox_fd", "conditions", "deleting")
    SANDBOX_NAME_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    AGENT_FD_FIELD_NUMBER: _ClassVar[int]
    SANDBOX_FD_FIELD_NUMBER: _ClassVar[int]
    CONDITIONS_FIELD_NUMBER: _ClassVar[int]
    DELETING_FIELD_NUMBER: _ClassVar[int]
    sandbox_name: str
    instance_id: str
    agent_fd: str
    sandbox_fd: str
    conditions: _containers.RepeatedCompositeFieldContainer[DriverCondition]
    deleting: bool
    def __init__(self, sandbox_name: _Optional[str] = ..., instance_id: _Optional[str] = ..., agent_fd: _Optional[str] = ..., sandbox_fd: _Optional[str] = ..., conditions: _Optional[_Iterable[_Union[DriverCondition, _Mapping]]] = ..., deleting: bool = ...) -> None: ...

class DriverCondition(_message.Message):
    __slots__ = ("type", "status", "reason", "message", "last_transition_time")
    TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    LAST_TRANSITION_TIME_FIELD_NUMBER: _ClassVar[int]
    type: str
    status: str
    reason: str
    message: str
    last_transition_time: str
    def __init__(self, type: _Optional[str] = ..., status: _Optional[str] = ..., reason: _Optional[str] = ..., message: _Optional[str] = ..., last_transition_time: _Optional[str] = ...) -> None: ...

class DriverPlatformEvent(_message.Message):
    __slots__ = ("timestamp_ms", "source", "type", "reason", "message", "metadata")
    class MetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    TIMESTAMP_MS_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    timestamp_ms: int
    source: str
    type: str
    reason: str
    message: str
    metadata: _containers.ScalarMap[str, str]
    def __init__(self, timestamp_ms: _Optional[int] = ..., source: _Optional[str] = ..., type: _Optional[str] = ..., reason: _Optional[str] = ..., message: _Optional[str] = ..., metadata: _Optional[_Mapping[str, str]] = ...) -> None: ...

class ValidateSandboxCreateRequest(_message.Message):
    __slots__ = ("sandbox",)
    SANDBOX_FIELD_NUMBER: _ClassVar[int]
    sandbox: DriverSandbox
    def __init__(self, sandbox: _Optional[_Union[DriverSandbox, _Mapping]] = ...) -> None: ...

class ValidateSandboxCreateResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetSandboxRequest(_message.Message):
    __slots__ = ("sandbox_id", "sandbox_name")
    SANDBOX_ID_FIELD_NUMBER: _ClassVar[int]
    SANDBOX_NAME_FIELD_NUMBER: _ClassVar[int]
    sandbox_id: str
    sandbox_name: str
    def __init__(self, sandbox_id: _Optional[str] = ..., sandbox_name: _Optional[str] = ...) -> None: ...

class GetSandboxResponse(_message.Message):
    __slots__ = ("sandbox",)
    SANDBOX_FIELD_NUMBER: _ClassVar[int]
    sandbox: DriverSandbox
    def __init__(self, sandbox: _Optional[_Union[DriverSandbox, _Mapping]] = ...) -> None: ...

class ListSandboxesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListSandboxesResponse(_message.Message):
    __slots__ = ("sandboxes",)
    SANDBOXES_FIELD_NUMBER: _ClassVar[int]
    sandboxes: _containers.RepeatedCompositeFieldContainer[DriverSandbox]
    def __init__(self, sandboxes: _Optional[_Iterable[_Union[DriverSandbox, _Mapping]]] = ...) -> None: ...

class CreateSandboxRequest(_message.Message):
    __slots__ = ("sandbox",)
    SANDBOX_FIELD_NUMBER: _ClassVar[int]
    sandbox: DriverSandbox
    def __init__(self, sandbox: _Optional[_Union[DriverSandbox, _Mapping]] = ...) -> None: ...

class CreateSandboxResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class StopSandboxRequest(_message.Message):
    __slots__ = ("sandbox_id", "sandbox_name")
    SANDBOX_ID_FIELD_NUMBER: _ClassVar[int]
    SANDBOX_NAME_FIELD_NUMBER: _ClassVar[int]
    sandbox_id: str
    sandbox_name: str
    def __init__(self, sandbox_id: _Optional[str] = ..., sandbox_name: _Optional[str] = ...) -> None: ...

class StopSandboxResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DeleteSandboxRequest(_message.Message):
    __slots__ = ("sandbox_id", "sandbox_name")
    SANDBOX_ID_FIELD_NUMBER: _ClassVar[int]
    SANDBOX_NAME_FIELD_NUMBER: _ClassVar[int]
    sandbox_id: str
    sandbox_name: str
    def __init__(self, sandbox_id: _Optional[str] = ..., sandbox_name: _Optional[str] = ...) -> None: ...

class DeleteSandboxResponse(_message.Message):
    __slots__ = ("deleted",)
    DELETED_FIELD_NUMBER: _ClassVar[int]
    deleted: bool
    def __init__(self, deleted: bool = ...) -> None: ...

class WatchSandboxesRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WatchSandboxesSandboxEvent(_message.Message):
    __slots__ = ("sandbox",)
    SANDBOX_FIELD_NUMBER: _ClassVar[int]
    sandbox: DriverSandbox
    def __init__(self, sandbox: _Optional[_Union[DriverSandbox, _Mapping]] = ...) -> None: ...

class WatchSandboxesDeletedEvent(_message.Message):
    __slots__ = ("sandbox_id",)
    SANDBOX_ID_FIELD_NUMBER: _ClassVar[int]
    sandbox_id: str
    def __init__(self, sandbox_id: _Optional[str] = ...) -> None: ...

class WatchSandboxesPlatformEvent(_message.Message):
    __slots__ = ("sandbox_id", "event")
    SANDBOX_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    sandbox_id: str
    event: DriverPlatformEvent
    def __init__(self, sandbox_id: _Optional[str] = ..., event: _Optional[_Union[DriverPlatformEvent, _Mapping]] = ...) -> None: ...

class WatchSandboxesEvent(_message.Message):
    __slots__ = ("sandbox", "deleted", "platform_event")
    SANDBOX_FIELD_NUMBER: _ClassVar[int]
    DELETED_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_EVENT_FIELD_NUMBER: _ClassVar[int]
    sandbox: WatchSandboxesSandboxEvent
    deleted: WatchSandboxesDeletedEvent
    platform_event: WatchSandboxesPlatformEvent
    def __init__(self, sandbox: _Optional[_Union[WatchSandboxesSandboxEvent, _Mapping]] = ..., deleted: _Optional[_Union[WatchSandboxesDeletedEvent, _Mapping]] = ..., platform_event: _Optional[_Union[WatchSandboxesPlatformEvent, _Mapping]] = ...) -> None: ...
