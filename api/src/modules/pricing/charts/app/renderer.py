from datetime import datetime
from io import BytesIO
from threading import Lock
from zoneinfo import ZoneInfo

from src.modules.pricing.charts.domain.models import AssetChartCard

_render_lock = Lock()


class AssetChartRenderer:
    def render(self, card: AssetChartCard) -> bytes:
        """Render a frozen chart off the caller's event loop."""
        with _render_lock:
            result = self.draw(card)
        return result

    def draw(self, card: AssetChartCard) -> bytes:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.dates import AutoDateLocator, DateFormatter, date2num
        from matplotlib.figure import Figure
        from matplotlib.ticker import FuncFormatter

        style = card.style
        figure = Figure(
            figsize=(style.width / 100, style.height / 100),
            dpi=100,
            facecolor=style.background,
            layout="constrained",
        )
        zone = ZoneInfo(card.timezone)
        title = style.asset_labels.get(
            card.asset.code.value, card.asset.code.value.upper()
        )
        figure.suptitle(
            title, color=style.foreground, fontsize=19, fontweight="bold"
        )
        line, bars = figure.subplots(2, 1, sharex=True)
        for axis, label in [
            (line, style.line_label),
            (bars, style.ohlc_label),
        ]:
            axis.set_facecolor(style.background)
            axis.set_title(
                label, color=style.foreground, fontsize=12, loc="left"
            )
            axis.set_ylabel(style.unit_label, color=style.foreground)
            axis.tick_params(colors=style.foreground, labelsize=9)
            axis.grid(alpha=0.15, color=style.foreground)
            axis.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _: f"{value:,.0f}")
            )
            for spine in axis.spines.values():
                spine.set_color(style.foreground)
                spine.set_alpha(0.15)
        rows = sorted(card.chart.candles, key=lambda row: row.st_ts)
        times = [
            date2num(datetime.fromtimestamp(row.en_ts, zone)) for row in rows
        ]
        closing = [row.close / 10 for row in rows]
        if rows:
            xs, ys = [], []
            previous = None
            for row, stamp, close in zip(rows, times, closing, strict=True):
                if previous is not None and row.st_ts > previous:
                    xs.append(stamp)
                    ys.append(float("nan"))
                xs.append(stamp)
                ys.append(close)
                previous = row.en_ts
            line.plot(
                xs,
                ys,
                color=style.rising,
                linewidth=2,
                marker="." if len(rows) < 4 else None,
            )
            width = card.chart.timeframe.seconds / 86400 * 0.25
            for row, stamp in zip(rows, times, strict=True):
                color = (
                    style.rising if row.close >= row.open else style.falling
                )
                bars.vlines(
                    stamp,
                    row.low / 10,
                    row.high / 10,
                    color=color,
                    linewidth=1.4,
                )
                bars.hlines(
                    row.open / 10,
                    stamp - width,
                    stamp,
                    color=color,
                    linewidth=1.7,
                )
                bars.hlines(
                    row.close / 10,
                    stamp,
                    stamp + width,
                    color=color,
                    linewidth=1.7,
                )
            if len(rows) == 1:
                line.set_xlim(times[0] - width * 4, times[0] + width * 4)
        else:
            for axis in (line, bars):
                axis.text(
                    0.5,
                    0.5,
                    style.empty_label,
                    transform=axis.transAxes,
                    ha="center",
                    va="center",
                    color=style.foreground,
                )
        bars.xaxis.set_major_locator(
            AutoDateLocator(tz=zone, minticks=3, maxticks=7)
        )
        bars.xaxis.set_major_formatter(DateFormatter("%m-%d %H:%M", tz=zone))
        bars.set_xlabel(
            f"{style.footer}\n{card.timezone}",
            color=style.foreground,
            fontsize=9,
        )
        output = BytesIO()
        FigureCanvasAgg(figure).print_png(output)
        figure.clear()
        payload = output.getvalue()
        if len(payload) > 256 * 1024:
            raise ValueError("Chart image exceeds the transport limit")
        return payload
