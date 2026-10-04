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

    if request.provider == "spotify":
        return SpotifyDownloader(request).plan()
    errors: list[str] = []
    stages = (
        [("gallery", GalleryDownloader), ("video", VideoDownloader)]
        if request.provider == "instagram"
        else [("video", VideoDownloader), ("gallery", GalleryDownloader)]
    )
    for provider, downloader in stages:
        if (
            provider not in request.policy.providers
            and request.provider not in request.policy.providers
        ):
            continue
        try:
            return downloader(request).plan()
        except Exception as exc:
            errors.append(type(exc).__name__)
    if "direct" in request.policy.providers and urlsplit(
        request.url
    ).path.lower().endswith(
        (".mp4", ".mp3", ".m4a", ".jpg", ".png", ".webm", ".ogg", ".pdf")
    ):
        return DownloadPlan(
            items=[
                DownloadItem(
                    url=request.url,
                    source_url=request.url,
                    engine="direct",
                    title=urlsplit(request.url).path.rsplit("/", 1)[-1][:200],
                )
            ]
        )
    if (
        request.policy.browser_enabled
        and "browser" in request.policy.providers
    ):
        from src.modules.media.infra.downloaders.browser import (
            BrowserDownloader,
        )

        return BrowserDownloader(request).plan()
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
