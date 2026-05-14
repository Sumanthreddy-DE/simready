"""Rich-formatted event renderer for the SimReady Copilot CLI.

Receives `on_event` callbacks from `CopilotAgent.run` and prints rich panels.
A plain-text renderer is provided as fallback (`--no-rich` or no rich install).
"""
from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


SEVERITY_STYLES = {
    "Critical": "bold red",
    "Major": "bold yellow",
    "Minor": "cyan",
    "Info": "dim",
}


class RichRenderer:
    """Rich-formatted printer for agent events. Stateful: tracks iteration counts."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._tool_call_count = 0

    def header(self, model: str, step_path: str, question: str) -> None:
        body = Text()
        body.append("Model: ", style="dim")
        body.append(f"{model}\n")
        body.append("Part:  ", style="dim")
        body.append(f"{step_path}\n")
        body.append("Q:     ", style="dim")
        body.append(question)
        self.console.print(Panel(body, title="SimReady Copilot", border_style="cyan"))

    def __call__(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "tool_call":
            self._render_tool_call(event)
        elif kind == "tool_result":
            self._render_tool_result(event)
        elif kind == "final_text":
            self._render_final(event)
        elif kind == "max_iterations":
            self.console.print(Panel(
                f"Hit max_iterations={event['iterations']} without final text.",
                title="Stopped", border_style="red",
            ))

    def _render_tool_call(self, event: dict[str, Any]) -> None:
        self._tool_call_count += 1
        name = event["name"]
        args = event["arguments"]
        try:
            args_pretty = json.dumps(json.loads(args), indent=2)
        except (json.JSONDecodeError, TypeError):
            args_pretty = str(args)
        self.console.print(
            f"\n[bold green]>>> tool_call #{self._tool_call_count}[/bold green] "
            f"[bold]{name}[/bold]"
        )
        self.console.print(Text(args_pretty, style="dim"))

    def _render_tool_result(self, event: dict[str, Any]) -> None:
        name = event["name"]
        result = event["result"] or {}
        if "error" in result:
            self.console.print(Panel(
                Text(f"{result.get('error')}: {result.get('message') or result.get('detail', '')}",
                     style="red"),
                title=f"{name} — error",
                border_style="red",
            ))
            return
        if name == "analyze_geometry":
            self._render_analyze_result(result)
        elif name == "suggest_fixes":
            self._render_fix_result(result)
        elif name == "lookup_standard":
            self._render_lookup_result(result)
        else:
            self.console.print(Panel(
                Text(json.dumps(result, indent=2, default=str)[:1500], style="dim"),
                title=f"{name} — result",
                border_style="green",
            ))

    def _render_analyze_result(self, result: dict[str, Any]) -> None:
        score = result.get("score") or {}
        geometry = result.get("geometry") or {}
        sev_counts = result.get("severity_counts") or {}
        header = Text()
        header.append("Status: ", style="dim")
        header.append(f"{result.get('status', 'Unknown')}", style="bold")
        header.append("   Complexity: ", style="dim")
        header.append(f"{result.get('complexity', '-')}\n")
        header.append("Score:  ", style="dim")
        overall = score.get("overall")
        if overall is not None:
            header.append(f"{overall:.1f}/100  ({score.get('label', '-')})\n", style="bold")
        else:
            header.append("n/a\n")
        header.append("Faces/Edges/Solids: ", style="dim")
        header.append(
            f"{geometry.get('face_count')}/{geometry.get('edge_count')}/{geometry.get('solid_count')}\n"
        )
        header.append("Bodies: ", style="dim")
        header.append(f"{result.get('body_count', 1)}\n")
        header.append("Severity: ", style="dim")
        for sev, n in sev_counts.items():
            style = SEVERITY_STYLES.get(sev, "white")
            header.append(f"{sev}={n}  ", style=style)

        findings = result.get("findings", []) or []
        self.console.print(Panel(header, title="analyze_geometry", border_style="green"))
        if findings:
            table = Table(title=f"Findings (top {len(findings)} of {result.get('findings_total', len(findings))})",
                          show_lines=False, box=None)
            table.add_column("Severity", style="bold")
            table.add_column("Check")
            table.add_column("Detail", overflow="fold")
            for f in findings:
                sev = f.get("severity", "Info")
                table.add_row(
                    Text(sev, style=SEVERITY_STYLES.get(sev, "white")),
                    f.get("check", ""),
                    (f.get("detail") or "")[:160],
                )
            self.console.print(table)

    def _render_fix_result(self, result: dict[str, Any]) -> None:
        suggestions = result.get("suggestions", []) or []
        sev_counts = result.get("severity_counts") or {}
        if not suggestions:
            self.console.print(Panel(
                Text(result.get("note") or "No suggestions.", style="dim"),
                title="suggest_fixes", border_style="green",
            ))
            return
        sev_text = Text()
        sev_text.append("Severity: ", style="dim")
        for sev, n in sev_counts.items():
            sev_text.append(f"{sev}={n}  ", style=SEVERITY_STYLES.get(sev, "white"))
        self.console.print(Panel(sev_text, title="suggest_fixes", border_style="green"))
        table = Table(box=None, show_lines=False)
        table.add_column("#", style="dim")
        table.add_column("Severity", style="bold")
        table.add_column("Check")
        table.add_column("Fix", overflow="fold")
        for i, s in enumerate(suggestions, 1):
            sev = s.get("severity", "Info")
            table.add_row(
                str(i),
                Text(sev, style=SEVERITY_STYLES.get(sev, "white")),
                s.get("check", ""),
                (s.get("fix") or "")[:200],
            )
        self.console.print(table)

    def _render_lookup_result(self, result: dict[str, Any]) -> None:
        status = result.get("status", "ok")
        if status != "ok":
            self.console.print(Panel(
                Text(result.get("message") or status, style="yellow"),
                title=f"lookup_standard ({status})",
                border_style="yellow",
            ))
            return
        hits = result.get("results", []) or []
        if not hits:
            self.console.print(Panel("No matches.", title="lookup_standard", border_style="yellow"))
            return
        for hit in hits:
            cite = f"{hit.get('source')} (p.{hit.get('page', '?')}) — score={hit.get('score', 0):.3f}"
            body = Text(hit.get("text") or "")
            self.console.print(Panel(body, title=cite, border_style="magenta"))

    def _render_final(self, event: dict[str, Any]) -> None:
        text = event.get("text") or "(no text)"
        usage = event.get("usage") or {}
        self.console.print(Panel(Text(text), title="Copilot Answer", border_style="cyan"))
        if usage:
            self.console.print(
                f"[dim]usage: {json.dumps(usage)}  iterations={event.get('iterations')}[/dim]"
            )


class PlainRenderer:
    """No-rich fallback. Same call signature as RichRenderer."""

    def __init__(self) -> None:
        self._tool_call_count = 0

    def header(self, model: str, step_path: str, question: str) -> None:
        print("=" * 60)
        print(f"MODEL: {model}")
        print(f"PART:  {step_path}")
        print(f"Q:     {question}")
        print("=" * 60)

    def __call__(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "tool_call":
            self._tool_call_count += 1
            print(f"\n[tool_call #{self._tool_call_count}] {event['name']}({event['arguments']})")
        elif kind == "tool_result":
            preview = json.dumps(event.get("result"), default=str)[:400]
            print(f"[tool_result] {event['name']} -> {preview}...")
        elif kind == "final_text":
            print("\n--- ANSWER ---")
            print(event.get("text", ""))
            usage = event.get("usage") or {}
            if usage:
                print(f"\nusage: {json.dumps(usage)}  iterations={event.get('iterations')}")
        elif kind == "max_iterations":
            print(f"\n[stopped] hit max_iterations={event['iterations']}")
