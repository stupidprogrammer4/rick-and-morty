from dishka import Provider, Scope, provide

from src.media_tasks.schedulers import (
    CleanMedia,
    CompleteMedia,
    DispatchMedia,
    ExecuteMedia,
    RecordMediaDownload,
    RecoverMedia,
    SendMedia,
    TransferMedia,
    TransferMediaBatch,
)


class MediaTaskProvider(Provider):
    scope = Scope.REQUEST
    execute = provide(ExecuteMedia)
    recover = provide(RecoverMedia)
    clean = provide(CleanMedia)
    transfer = provide(TransferMedia)
    transfers = provide(TransferMediaBatch)
    results = provide(RecordMediaDownload)
    dispatch = provide(DispatchMedia)
    complete = provide(CompleteMedia)
    send = provide(SendMedia)
