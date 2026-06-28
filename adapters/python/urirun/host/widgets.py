from __future__ import annotations


def query_value(query: dict[str, list[str]], name: str, default: str | None = None) -> str | None:
    values = query.get(name)
    return values[0] if values else default


class _WidgetRenderCallable:
    def __init__(self, name: str) -> None:
        self.name = name
        self.__name__ = name

    def __call__(self, *args, **kwargs):
        from urirun_widgets import render
        return getattr(render, self.name)(*args, **kwargs)


scanner_stream_summary = _WidgetRenderCallable("scanner_stream_summary")
select_service_view = _WidgetRenderCallable("select_service_view")
service_widget_summary = _WidgetRenderCallable("service_widget_summary")
