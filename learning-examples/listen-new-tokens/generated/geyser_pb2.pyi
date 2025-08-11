import solana_storage_pb2 as _solana_storage_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import (
    ClassVar as _ClassVar,
    Iterable as _Iterable,
    Mapping as _Mapping,
    Optional as _Optional,
    Union as _Union,
)
from solana_storage_pb2 import ConfirmedBlock as ConfirmedBlock
from solana_storage_pb2 import ConfirmedTransaction as ConfirmedTransaction
from solana_storage_pb2 import Transaction as Transaction
from solana_storage_pb2 import Message as Message
from solana_storage_pb2 import MessageHeader as MessageHeader
from solana_storage_pb2 import MessageAddressTableLookup as MessageAddressTableLookup
from solana_storage_pb2 import TransactionStatusMeta as TransactionStatusMeta
from solana_storage_pb2 import TransactionError as TransactionError
from solana_storage_pb2 import InnerInstructions as InnerInstructions
from solana_storage_pb2 import InnerInstruction as InnerInstruction
from solana_storage_pb2 import CompiledInstruction as CompiledInstruction
from solana_storage_pb2 import TokenBalance as TokenBalance
from solana_storage_pb2 import UiTokenAmount as UiTokenAmount
from solana_storage_pb2 import ReturnData as ReturnData
from solana_storage_pb2 import Reward as Reward
from solana_storage_pb2 import Rewards as Rewards
from solana_storage_pb2 import UnixTimestamp as UnixTimestamp
from solana_storage_pb2 import BlockHeight as BlockHeight
from solana_storage_pb2 import NumPartitions as NumPartitions
from solana_storage_pb2 import RewardType as RewardType

DESCRIPTOR: _descriptor.FileDescriptor
Unspecified: _solana_storage_pb2.RewardType
Fee: _solana_storage_pb2.RewardType
Rent: _solana_storage_pb2.RewardType
Staking: _solana_storage_pb2.RewardType
Voting: _solana_storage_pb2.RewardType

class CommitmentLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    PROCESSED: _ClassVar[CommitmentLevel]
    CONFIRMED: _ClassVar[CommitmentLevel]
    FINALIZED: _ClassVar[CommitmentLevel]
    FIRST_SHRED_RECEIVED: _ClassVar[CommitmentLevel]
    COMPLETED: _ClassVar[CommitmentLevel]
    CREATED_BANK: _ClassVar[CommitmentLevel]
    DEAD: _ClassVar[CommitmentLevel]

PROCESSED: CommitmentLevel
CONFIRMED: CommitmentLevel
FINALIZED: CommitmentLevel
FIRST_SHRED_RECEIVED: CommitmentLevel
COMPLETED: CommitmentLevel
CREATED_BANK: CommitmentLevel
DEAD: CommitmentLevel

class SubscribeRequest(_message.Message):
    __slots__ = (
        "accounts",
        "slots",
        "transactions",
        "transactions_status",
        "blocks",
        "blocks_meta",
        "entry",
        "commitment",
        "accounts_data_slice",
        "ping",
    )
    class AccountsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SubscribeRequestFilterAccounts
        def __init__(
            self,
            key: _Optional[str] = ...,
            value: _Optional[_Union[SubscribeRequestFilterAccounts, _Mapping]] = ...,
        ) -> None: ...

    class SlotsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SubscribeRequestFilterSlots
        def __init__(
            self,
            key: _Optional[str] = ...,
            value: _Optional[_Union[SubscribeRequestFilterSlots, _Mapping]] = ...,
        ) -> None: ...

    class TransactionsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SubscribeRequestFilterTransactions
        def __init__(
            self,
            key: _Optional[str] = ...,
            value: _Optional[
                _Union[SubscribeRequestFilterTransactions, _Mapping]
            ] = ...,
        ) -> None: ...

    class TransactionsStatusEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SubscribeRequestFilterTransactions
        def __init__(
            self,
            key: _Optional[str] = ...,
            value: _Optional[
                _Union[SubscribeRequestFilterTransactions, _Mapping]
            ] = ...,
        ) -> None: ...

    class BlocksEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SubscribeRequestFilterBlocks
        def __init__(
            self,
            key: _Optional[str] = ...,
            value: _Optional[_Union[SubscribeRequestFilterBlocks, _Mapping]] = ...,
        ) -> None: ...

    class BlocksMetaEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SubscribeRequestFilterBlocksMeta
        def __init__(
            self,
            key: _Optional[str] = ...,
            value: _Optional[_Union[SubscribeRequestFilterBlocksMeta, _Mapping]] = ...,
        ) -> None: ...

    class EntryEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: SubscribeRequestFilterEntry
        def __init__(
            self,
            key: _Optional[str] = ...,
            value: _Optional[_Union[SubscribeRequestFilterEntry, _Mapping]] = ...,
        ) -> None: ...

    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    SLOTS_FIELD_NUMBER: _ClassVar[int]
    TRANSACTIONS_FIELD_NUMBER: _ClassVar[int]
    TRANSACTIONS_STATUS_FIELD_NUMBER: _ClassVar[int]
    BLOCKS_FIELD_NUMBER: _ClassVar[int]
    BLOCKS_META_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FIELD_NUMBER: _ClassVar[int]
    COMMITMENT_FIELD_NUMBER: _ClassVar[int]
    ACCOUNTS_DATA_SLICE_FIELD_NUMBER: _ClassVar[int]
    PING_FIELD_NUMBER: _ClassVar[int]
    accounts: _containers.MessageMap[str, SubscribeRequestFilterAccounts]
    slots: _containers.MessageMap[str, SubscribeRequestFilterSlots]
    transactions: _containers.MessageMap[str, SubscribeRequestFilterTransactions]
    transactions_status: _containers.MessageMap[str, SubscribeRequestFilterTransactions]
    blocks: _containers.MessageMap[str, SubscribeRequestFilterBlocks]
    blocks_meta: _containers.MessageMap[str, SubscribeRequestFilterBlocksMeta]
    entry: _containers.MessageMap[str, SubscribeRequestFilterEntry]
    commitment: CommitmentLevel
    accounts_data_slice: _containers.RepeatedCompositeFieldContainer[
        SubscribeRequestAccountsDataSlice
    ]
    ping: SubscribeRequestPing
    def __init__(
        self,
        accounts: _Optional[_Mapping[str, SubscribeRequestFilterAccounts]] = ...,
        slots: _Optional[_Mapping[str, SubscribeRequestFilterSlots]] = ...,
        transactions: _Optional[
            _Mapping[str, SubscribeRequestFilterTransactions]
        ] = ...,
        transactions_status: _Optional[
            _Mapping[str, SubscribeRequestFilterTransactions]
        ] = ...,
        blocks: _Optional[_Mapping[str, SubscribeRequestFilterBlocks]] = ...,
        blocks_meta: _Optional[_Mapping[str, SubscribeRequestFilterBlocksMeta]] = ...,
        entry: _Optional[_Mapping[str, SubscribeRequestFilterEntry]] = ...,
        commitment: _Optional[_Union[CommitmentLevel, str]] = ...,
        accounts_data_slice: _Optional[
            _Iterable[_Union[SubscribeRequestAccountsDataSlice, _Mapping]]
        ] = ...,
        ping: _Optional[_Union[SubscribeRequestPing, _Mapping]] = ...,
    ) -> None: ...

class SubscribeRequestFilterAccounts(_message.Message):
    __slots__ = ("account", "owner", "filters", "nonempty_txn_signature")
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    NONEMPTY_TXN_SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    account: _containers.RepeatedScalarFieldContainer[str]
    owner: _containers.RepeatedScalarFieldContainer[str]
    filters: _containers.RepeatedCompositeFieldContainer[
        SubscribeRequestFilterAccountsFilter
    ]
    nonempty_txn_signature: bool
    def __init__(
        self,
        account: _Optional[_Iterable[str]] = ...,
        owner: _Optional[_Iterable[str]] = ...,
        filters: _Optional[
            _Iterable[_Union[SubscribeRequestFilterAccountsFilter, _Mapping]]
        ] = ...,
        nonempty_txn_signature: bool = ...,
    ) -> None: ...

class SubscribeRequestFilterAccountsFilter(_message.Message):
    __slots__ = ("memcmp", "datasize", "token_account_state", "lamports")
    MEMCMP_FIELD_NUMBER: _ClassVar[int]
    DATASIZE_FIELD_NUMBER: _ClassVar[int]
    TOKEN_ACCOUNT_STATE_FIELD_NUMBER: _ClassVar[int]
    LAMPORTS_FIELD_NUMBER: _ClassVar[int]
    memcmp: SubscribeRequestFilterAccountsFilterMemcmp
    datasize: int
    token_account_state: bool
    lamports: SubscribeRequestFilterAccountsFilterLamports
    def __init__(
        self,
        memcmp: _Optional[
            _Union[SubscribeRequestFilterAccountsFilterMemcmp, _Mapping]
        ] = ...,
        datasize: _Optional[int] = ...,
        token_account_state: bool = ...,
        lamports: _Optional[
            _Union[SubscribeRequestFilterAccountsFilterLamports, _Mapping]
        ] = ...,
    ) -> None: ...

class SubscribeRequestFilterAccountsFilterMemcmp(_message.Message):
    __slots__ = ("offset", "bytes", "base58", "base64")
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    BYTES_FIELD_NUMBER: _ClassVar[int]
    BASE58_FIELD_NUMBER: _ClassVar[int]
    BASE64_FIELD_NUMBER: _ClassVar[int]
    offset: int
    bytes: bytes
    base58: str
    base64: str
    def __init__(
        self,
        offset: _Optional[int] = ...,
        bytes: _Optional[bytes] = ...,
        base58: _Optional[str] = ...,
        base64: _Optional[str] = ...,
    ) -> None: ...

class SubscribeRequestFilterAccountsFilterLamports(_message.Message):
    __slots__ = ("eq", "ne", "lt", "gt")
    EQ_FIELD_NUMBER: _ClassVar[int]
    NE_FIELD_NUMBER: _ClassVar[int]
    LT_FIELD_NUMBER: _ClassVar[int]
    GT_FIELD_NUMBER: _ClassVar[int]
    eq: int
    ne: int
    lt: int
    gt: int
    def __init__(
        self,
        eq: _Optional[int] = ...,
        ne: _Optional[int] = ...,
        lt: _Optional[int] = ...,
        gt: _Optional[int] = ...,
    ) -> None: ...

class SubscribeRequestFilterSlots(_message.Message):
    __slots__ = ("filter_by_commitment",)
    FILTER_BY_COMMITMENT_FIELD_NUMBER: _ClassVar[int]
    filter_by_commitment: bool
    def __init__(self, filter_by_commitment: bool = ...) -> None: ...

class SubscribeRequestFilterTransactions(_message.Message):
    __slots__ = (
        "vote",
        "failed",
        "signature",
        "account_include",
        "account_exclude",
        "account_required",
    )
    VOTE_FIELD_NUMBER: _ClassVar[int]
    FAILED_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_INCLUDE_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_EXCLUDE_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_REQUIRED_FIELD_NUMBER: _ClassVar[int]
    vote: bool
    failed: bool
    signature: str
    account_include: _containers.RepeatedScalarFieldContainer[str]
    account_exclude: _containers.RepeatedScalarFieldContainer[str]
    account_required: _containers.RepeatedScalarFieldContainer[str]
    def __init__(
        self,
        vote: bool = ...,
        failed: bool = ...,
        signature: _Optional[str] = ...,
        account_include: _Optional[_Iterable[str]] = ...,
        account_exclude: _Optional[_Iterable[str]] = ...,
        account_required: _Optional[_Iterable[str]] = ...,
    ) -> None: ...

class SubscribeRequestFilterBlocks(_message.Message):
    __slots__ = (
        "account_include",
        "include_transactions",
        "include_accounts",
        "include_entries",
    )
    ACCOUNT_INCLUDE_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_TRANSACTIONS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_ENTRIES_FIELD_NUMBER: _ClassVar[int]
    account_include: _containers.RepeatedScalarFieldContainer[str]
    include_transactions: bool
    include_accounts: bool
    include_entries: bool
    def __init__(
        self,
        account_include: _Optional[_Iterable[str]] = ...,
        include_transactions: bool = ...,
        include_accounts: bool = ...,
        include_entries: bool = ...,
    ) -> None: ...

class SubscribeRequestFilterBlocksMeta(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SubscribeRequestFilterEntry(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SubscribeRequestAccountsDataSlice(_message.Message):
    __slots__ = ("offset", "length")
    OFFSET_FIELD_NUMBER: _ClassVar[int]
    LENGTH_FIELD_NUMBER: _ClassVar[int]
    offset: int
    length: int
    def __init__(
        self, offset: _Optional[int] = ..., length: _Optional[int] = ...
    ) -> None: ...

class SubscribeRequestPing(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    def __init__(self, id: _Optional[int] = ...) -> None: ...

class SubscribeUpdate(_message.Message):
    __slots__ = (
        "filters",
        "account",
        "slot",
        "transaction",
        "transaction_status",
        "block",
        "ping",
        "pong",
        "block_meta",
        "entry",
    )
    FILTERS_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    TRANSACTION_FIELD_NUMBER: _ClassVar[int]
    TRANSACTION_STATUS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_FIELD_NUMBER: _ClassVar[int]
    PING_FIELD_NUMBER: _ClassVar[int]
    PONG_FIELD_NUMBER: _ClassVar[int]
    BLOCK_META_FIELD_NUMBER: _ClassVar[int]
    ENTRY_FIELD_NUMBER: _ClassVar[int]
    filters: _containers.RepeatedScalarFieldContainer[str]
    account: SubscribeUpdateAccount
    slot: SubscribeUpdateSlot
    transaction: SubscribeUpdateTransaction
    transaction_status: SubscribeUpdateTransactionStatus
    block: SubscribeUpdateBlock
    ping: SubscribeUpdatePing
    pong: SubscribeUpdatePong
    block_meta: SubscribeUpdateBlockMeta
    entry: SubscribeUpdateEntry
    def __init__(
        self,
        filters: _Optional[_Iterable[str]] = ...,
        account: _Optional[_Union[SubscribeUpdateAccount, _Mapping]] = ...,
        slot: _Optional[_Union[SubscribeUpdateSlot, _Mapping]] = ...,
        transaction: _Optional[_Union[SubscribeUpdateTransaction, _Mapping]] = ...,
        transaction_status: _Optional[
            _Union[SubscribeUpdateTransactionStatus, _Mapping]
        ] = ...,
        block: _Optional[_Union[SubscribeUpdateBlock, _Mapping]] = ...,
        ping: _Optional[_Union[SubscribeUpdatePing, _Mapping]] = ...,
        pong: _Optional[_Union[SubscribeUpdatePong, _Mapping]] = ...,
        block_meta: _Optional[_Union[SubscribeUpdateBlockMeta, _Mapping]] = ...,
        entry: _Optional[_Union[SubscribeUpdateEntry, _Mapping]] = ...,
    ) -> None: ...

class SubscribeUpdateAccount(_message.Message):
    __slots__ = ("account", "slot", "is_startup")
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    IS_STARTUP_FIELD_NUMBER: _ClassVar[int]
    account: SubscribeUpdateAccountInfo
    slot: int
    is_startup: bool
    def __init__(
        self,
        account: _Optional[_Union[SubscribeUpdateAccountInfo, _Mapping]] = ...,
        slot: _Optional[int] = ...,
        is_startup: bool = ...,
    ) -> None: ...

class SubscribeUpdateAccountInfo(_message.Message):
    __slots__ = (
        "pubkey",
        "lamports",
        "owner",
        "executable",
        "rent_epoch",
        "data",
        "write_version",
        "txn_signature",
    )
    PUBKEY_FIELD_NUMBER: _ClassVar[int]
    LAMPORTS_FIELD_NUMBER: _ClassVar[int]
    OWNER_FIELD_NUMBER: _ClassVar[int]
    EXECUTABLE_FIELD_NUMBER: _ClassVar[int]
    RENT_EPOCH_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    WRITE_VERSION_FIELD_NUMBER: _ClassVar[int]
    TXN_SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    pubkey: bytes
    lamports: int
    owner: bytes
    executable: bool
    rent_epoch: int
    data: bytes
    write_version: int
    txn_signature: bytes
    def __init__(
        self,
        pubkey: _Optional[bytes] = ...,
        lamports: _Optional[int] = ...,
        owner: _Optional[bytes] = ...,
        executable: bool = ...,
        rent_epoch: _Optional[int] = ...,
        data: _Optional[bytes] = ...,
        write_version: _Optional[int] = ...,
        txn_signature: _Optional[bytes] = ...,
    ) -> None: ...

class SubscribeUpdateSlot(_message.Message):
    __slots__ = ("slot", "parent", "status", "dead_error")
    SLOT_FIELD_NUMBER: _ClassVar[int]
    PARENT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    DEAD_ERROR_FIELD_NUMBER: _ClassVar[int]
    slot: int
    parent: int
    status: CommitmentLevel
    dead_error: str
    def __init__(
        self,
        slot: _Optional[int] = ...,
        parent: _Optional[int] = ...,
        status: _Optional[_Union[CommitmentLevel, str]] = ...,
        dead_error: _Optional[str] = ...,
    ) -> None: ...

class SubscribeUpdateTransaction(_message.Message):
    __slots__ = ("transaction", "slot")
    TRANSACTION_FIELD_NUMBER: _ClassVar[int]
    SLOT_FIELD_NUMBER: _ClassVar[int]
    transaction: SubscribeUpdateTransactionInfo
    slot: int
    def __init__(
        self,
        transaction: _Optional[_Union[SubscribeUpdateTransactionInfo, _Mapping]] = ...,
        slot: _Optional[int] = ...,
    ) -> None: ...

class SubscribeUpdateTransactionInfo(_message.Message):
    __slots__ = ("signature", "is_vote", "transaction", "meta", "index")
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    IS_VOTE_FIELD_NUMBER: _ClassVar[int]
    TRANSACTION_FIELD_NUMBER: _ClassVar[int]
    META_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    signature: bytes
    is_vote: bool
    transaction: _solana_storage_pb2.Transaction
    meta: _solana_storage_pb2.TransactionStatusMeta
    index: int
    def __init__(
        self,
        signature: _Optional[bytes] = ...,
        is_vote: bool = ...,
        transaction: _Optional[_Union[_solana_storage_pb2.Transaction, _Mapping]] = ...,
        meta: _Optional[
            _Union[_solana_storage_pb2.TransactionStatusMeta, _Mapping]
        ] = ...,
        index: _Optional[int] = ...,
    ) -> None: ...

class SubscribeUpdateTransactionStatus(_message.Message):
    __slots__ = ("slot", "signature", "is_vote", "index", "err")
    SLOT_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    IS_VOTE_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    ERR_FIELD_NUMBER: _ClassVar[int]
    slot: int
    signature: bytes
    is_vote: bool
    index: int
    err: _solana_storage_pb2.TransactionError
    def __init__(
        self,
        slot: _Optional[int] = ...,
        signature: _Optional[bytes] = ...,
        is_vote: bool = ...,
        index: _Optional[int] = ...,
        err: _Optional[_Union[_solana_storage_pb2.TransactionError, _Mapping]] = ...,
    ) -> None: ...

class SubscribeUpdateBlock(_message.Message):
    __slots__ = (
        "slot",
        "blockhash",
        "rewards",
        "block_time",
        "block_height",
        "parent_slot",
        "parent_blockhash",
        "executed_transaction_count",
        "transactions",
        "updated_account_count",
        "accounts",
        "entries_count",
        "entries",
    )
    SLOT_FIELD_NUMBER: _ClassVar[int]
    BLOCKHASH_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TIME_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    PARENT_SLOT_FIELD_NUMBER: _ClassVar[int]
    PARENT_BLOCKHASH_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_TRANSACTION_COUNT_FIELD_NUMBER: _ClassVar[int]
    TRANSACTIONS_FIELD_NUMBER: _ClassVar[int]
    UPDATED_ACCOUNT_COUNT_FIELD_NUMBER: _ClassVar[int]
    ACCOUNTS_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_COUNT_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    slot: int
    blockhash: str
    rewards: _solana_storage_pb2.Rewards
    block_time: _solana_storage_pb2.UnixTimestamp
    block_height: _solana_storage_pb2.BlockHeight
    parent_slot: int
    parent_blockhash: str
    executed_transaction_count: int
    transactions: _containers.RepeatedCompositeFieldContainer[
        SubscribeUpdateTransactionInfo
    ]
    updated_account_count: int
    accounts: _containers.RepeatedCompositeFieldContainer[SubscribeUpdateAccountInfo]
    entries_count: int
    entries: _containers.RepeatedCompositeFieldContainer[SubscribeUpdateEntry]
    def __init__(
        self,
        slot: _Optional[int] = ...,
        blockhash: _Optional[str] = ...,
        rewards: _Optional[_Union[_solana_storage_pb2.Rewards, _Mapping]] = ...,
        block_time: _Optional[
            _Union[_solana_storage_pb2.UnixTimestamp, _Mapping]
        ] = ...,
        block_height: _Optional[
            _Union[_solana_storage_pb2.BlockHeight, _Mapping]
        ] = ...,
        parent_slot: _Optional[int] = ...,
        parent_blockhash: _Optional[str] = ...,
        executed_transaction_count: _Optional[int] = ...,
        transactions: _Optional[
            _Iterable[_Union[SubscribeUpdateTransactionInfo, _Mapping]]
        ] = ...,
        updated_account_count: _Optional[int] = ...,
        accounts: _Optional[
            _Iterable[_Union[SubscribeUpdateAccountInfo, _Mapping]]
        ] = ...,
        entries_count: _Optional[int] = ...,
        entries: _Optional[_Iterable[_Union[SubscribeUpdateEntry, _Mapping]]] = ...,
    ) -> None: ...

class SubscribeUpdateBlockMeta(_message.Message):
    __slots__ = (
        "slot",
        "blockhash",
        "rewards",
        "block_time",
        "block_height",
        "parent_slot",
        "parent_blockhash",
        "executed_transaction_count",
        "entries_count",
    )
    SLOT_FIELD_NUMBER: _ClassVar[int]
    BLOCKHASH_FIELD_NUMBER: _ClassVar[int]
    REWARDS_FIELD_NUMBER: _ClassVar[int]
    BLOCK_TIME_FIELD_NUMBER: _ClassVar[int]
    BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    PARENT_SLOT_FIELD_NUMBER: _ClassVar[int]
    PARENT_BLOCKHASH_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_TRANSACTION_COUNT_FIELD_NUMBER: _ClassVar[int]
    ENTRIES_COUNT_FIELD_NUMBER: _ClassVar[int]
    slot: int
    blockhash: str
    rewards: _solana_storage_pb2.Rewards
    block_time: _solana_storage_pb2.UnixTimestamp
    block_height: _solana_storage_pb2.BlockHeight
    parent_slot: int
    parent_blockhash: str
    executed_transaction_count: int
    entries_count: int
    def __init__(
        self,
        slot: _Optional[int] = ...,
        blockhash: _Optional[str] = ...,
        rewards: _Optional[_Union[_solana_storage_pb2.Rewards, _Mapping]] = ...,
        block_time: _Optional[
            _Union[_solana_storage_pb2.UnixTimestamp, _Mapping]
        ] = ...,
        block_height: _Optional[
            _Union[_solana_storage_pb2.BlockHeight, _Mapping]
        ] = ...,
        parent_slot: _Optional[int] = ...,
        parent_blockhash: _Optional[str] = ...,
        executed_transaction_count: _Optional[int] = ...,
        entries_count: _Optional[int] = ...,
    ) -> None: ...

class SubscribeUpdateEntry(_message.Message):
    __slots__ = (
        "slot",
        "index",
        "num_hashes",
        "hash",
        "executed_transaction_count",
        "starting_transaction_index",
    )
    SLOT_FIELD_NUMBER: _ClassVar[int]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    NUM_HASHES_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    EXECUTED_TRANSACTION_COUNT_FIELD_NUMBER: _ClassVar[int]
    STARTING_TRANSACTION_INDEX_FIELD_NUMBER: _ClassVar[int]
    slot: int
    index: int
    num_hashes: int
    hash: bytes
    executed_transaction_count: int
    starting_transaction_index: int
    def __init__(
        self,
        slot: _Optional[int] = ...,
        index: _Optional[int] = ...,
        num_hashes: _Optional[int] = ...,
        hash: _Optional[bytes] = ...,
        executed_transaction_count: _Optional[int] = ...,
        starting_transaction_index: _Optional[int] = ...,
    ) -> None: ...

class SubscribeUpdatePing(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SubscribeUpdatePong(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: int
    def __init__(self, id: _Optional[int] = ...) -> None: ...

class PingRequest(_message.Message):
    __slots__ = ("count",)
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: int
    def __init__(self, count: _Optional[int] = ...) -> None: ...

class PongResponse(_message.Message):
    __slots__ = ("count",)
    COUNT_FIELD_NUMBER: _ClassVar[int]
    count: int
    def __init__(self, count: _Optional[int] = ...) -> None: ...

class GetLatestBlockhashRequest(_message.Message):
    __slots__ = ("commitment",)
    COMMITMENT_FIELD_NUMBER: _ClassVar[int]
    commitment: CommitmentLevel
    def __init__(
        self, commitment: _Optional[_Union[CommitmentLevel, str]] = ...
    ) -> None: ...

class GetLatestBlockhashResponse(_message.Message):
    __slots__ = ("slot", "blockhash", "last_valid_block_height")
    SLOT_FIELD_NUMBER: _ClassVar[int]
    BLOCKHASH_FIELD_NUMBER: _ClassVar[int]
    LAST_VALID_BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    slot: int
    blockhash: str
    last_valid_block_height: int
    def __init__(
        self,
        slot: _Optional[int] = ...,
        blockhash: _Optional[str] = ...,
        last_valid_block_height: _Optional[int] = ...,
    ) -> None: ...

class GetBlockHeightRequest(_message.Message):
    __slots__ = ("commitment",)
    COMMITMENT_FIELD_NUMBER: _ClassVar[int]
    commitment: CommitmentLevel
    def __init__(
        self, commitment: _Optional[_Union[CommitmentLevel, str]] = ...
    ) -> None: ...

class GetBlockHeightResponse(_message.Message):
    __slots__ = ("block_height",)
    BLOCK_HEIGHT_FIELD_NUMBER: _ClassVar[int]
    block_height: int
    def __init__(self, block_height: _Optional[int] = ...) -> None: ...

class GetSlotRequest(_message.Message):
    __slots__ = ("commitment",)
    COMMITMENT_FIELD_NUMBER: _ClassVar[int]
    commitment: CommitmentLevel
    def __init__(
        self, commitment: _Optional[_Union[CommitmentLevel, str]] = ...
    ) -> None: ...

class GetSlotResponse(_message.Message):
    __slots__ = ("slot",)
    SLOT_FIELD_NUMBER: _ClassVar[int]
    slot: int
    def __init__(self, slot: _Optional[int] = ...) -> None: ...

class GetVersionRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetVersionResponse(_message.Message):
    __slots__ = ("version",)
    VERSION_FIELD_NUMBER: _ClassVar[int]
    version: str
    def __init__(self, version: _Optional[str] = ...) -> None: ...

class IsBlockhashValidRequest(_message.Message):
    __slots__ = ("blockhash", "commitment")
    BLOCKHASH_FIELD_NUMBER: _ClassVar[int]
    COMMITMENT_FIELD_NUMBER: _ClassVar[int]
    blockhash: str
    commitment: CommitmentLevel
    def __init__(
        self,
        blockhash: _Optional[str] = ...,
        commitment: _Optional[_Union[CommitmentLevel, str]] = ...,
    ) -> None: ...

class IsBlockhashValidResponse(_message.Message):
    __slots__ = ("slot", "valid")
    SLOT_FIELD_NUMBER: _ClassVar[int]
    VALID_FIELD_NUMBER: _ClassVar[int]
    slot: int
    valid: bool
    def __init__(self, slot: _Optional[int] = ..., valid: bool = ...) -> None: ...
