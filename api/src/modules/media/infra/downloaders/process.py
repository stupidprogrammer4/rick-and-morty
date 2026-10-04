import contextlib
import json
import resource
import sys
from pathlib import Path
from urllib.parse import urlsplit

from src.modules.media.domain.dtos import (
    DownloadItem,
    DownloadPlan,
    DownloadProcessRequest,
)
from src.modules.media.infra.downloaders.direct import DirectDownloader
from src.modules.media.infra.downloaders.network import (
    protect_network,
    validate_url,
)


def plan(request: DownloadProcessRequest) -> DownloadPlan:
    from src.modules.media.infra.downloaders.gallery import GalleryDownloader
    from src.modules.media.infra.downloaders.spotify import SpotifyDownloader
    from src.modules.media.infra.downloaders.video import VideoDownloader

    errors: list[str] = []
    from src.modules.media.infra.downloaders.browser import BrowserDownloader

    engines = {
        "video": VideoDownloader,
        "gallery": GalleryDownloader,
        "browser": BrowserDownloader,
        "spotify": SpotifyDownloader,
    }
    for stage in request.stages:
        if stage == "direct":
            return DownloadPlan(
                items=[
                    DownloadItem(
                        url=request.url,
                        source_url=request.url,
                        engine="direct",
                        title=urlsplit(request.url).path.rsplit("/", 1)[-1][
                            :200
                        ],
                    )
                ]
            )
        try:
            return engines[stage](request).plan()
        except Exception as exc:
            errors.append(stage + ": " + str(exc)[:220])
    raise ValueError("No extractor succeeded: " + ", ".join(errors))


def main() -> None:
    request = DownloadProcessRequest.model_validate_json(
        sys.stdin.read(200000)
    )
    directory = Path(request.directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (request.policy.max_file_bytes * 2, request.policy.max_file_bytes * 2),
    )
    protect_network()
    validate_url(request.url)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            if request.operation == "plan":
                result = plan(request)
            else:
                if request.item is None:
                    raise ValueError("Download item required")
                validate_url(request.item.url)
                if request.item.engine == "spotify":
                    from src.modules.media.infra.downloaders.spotify import (
                        SpotifyDownloader,
                    )

                    result = SpotifyDownloader(request).download(request.item)
                elif request.item.engine == "direct":
                    result = DirectDownloader(request).download(request.item)
                else:
                    from src.modules.media.infra.downloaders.video import (
                        VideoDownloader,
                    )

                    result = VideoDownloader(request).download(request.item)
        print(result.model_dump_json())
    except Exception as exc:
        message = str(exc)
        if len(message) > 320:
            message = message[:100] + " ... " + message[-200:]
        print(json.dumps({"error": type(exc).__name__, "message": message}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
