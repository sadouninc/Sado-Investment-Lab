from __future__ import annotations

from html import escape
from pathlib import Path


def _img(relative_url: str, alt: str) -> str:
    return (
        '<figure class="codex-card">'
        f'<img src="{{{{ \'{relative_url}\' | relative_url }}}}" alt="{escape(alt)}" '
        'loading="lazy" style="width:100%;height:auto">'
        f'<figcaption>{escape(alt)}</figcaption>'
        '</figure>'
    )


def render_runtime_architecture_page(diagram_base: str = "/assets/architecture/349") -> str:
    """Render #349 as a summary-first derived read model.

    Canonical architecture Markdown/SVGs remain the source; this function only composes
    the public Pages view using the existing #320 semantic primitives.
    """
    sections = [
        (
            "System Overview — User / AI / GitHub",
            "誰が、どの入口から、GitHub上のInvestment OSを使うか。ChatGPT/CodexとPages/Cockpit、OpenAI API、Broker/Marketの境界を俯瞰します。",
            f"{diagram_base}_system_overview.svg",
            "Sado Investment OS全体図。ユーザー、端末、対話UI、Pages/Cockpit、GitHub上のOS、OpenAI API、外部世界の責務境界。",
        ),
        (
            "Runtime Architecture",
            "AI Semantic LayerとDeterministic Logicを分離し、GitHub上の提案・検証・Canonical StateからDerived Read Modelへ流れるCURRENT runtimeを確認します。",
            f"{diagram_base}_runtime_architecture.svg",
            "Runtime Architecture図。AIの意味解釈とdeterministic処理を別レイヤーとして示す。",
        ),
        (
            "Git as State Machine",
            "Issue / branch / commit / PR / review / CI / mergeを、監査可能なstate transitionとして確認します。mergeはBUY/SELL Authorityではありません。",
            f"{diagram_base}_git_state_machine.svg",
            "Git State Machine図。提案、レビュー、CI、mergeと状態遷移の関係。",
        ),
        (
            "Versioned Input / Self-evolving Observation",
            "データだけでなく、何を観測するか・どうvalidateするかもversion管理し、将来のreplay可能性につなげる構造です。",
            f"{diagram_base}_versioned_input.svg",
            "Versioned Input図。観測contract自体をGit管理して進化させる流れ。",
        ),
    ]

    out = [
        '<section class="codex-page-shell">',
        '<header class="codex-page-header">',
        '<p class="codex-eyebrow">Architecture / Runtime</p>',
        '<h1>Sado Investment OS — 仕組みを30秒で理解する</h1>',
        '<p>Investment OSの本体はGitHub上の永続状態・Issue/PR・Actions・履歴です。AIは意味理解と提案を担い、検証可能な処理はdeterministic logicへ分離し、最終の投資判断Authorityは👑サドに残ります。</p>',
        '</header>',
        '<div class="codex-summary-grid">',
        '<article class="codex-summary-card"><strong>OS本体</strong><p>GitHub Operating Substrate + Canonical State</p></article>',
        '<article class="codex-summary-card"><strong>AIの責務</strong><p>意味理解・整理・提案。verified factへのsilent promotionはしない。</p></article>',
        '<article class="codex-summary-card"><strong>安全境界</strong><p>CI green / merge ≠ BUY・SELL承認。Owner Authorityは別。</p></article>',
        '</div>',
        '<div class="codex-alert" data-state="normal"><strong>CURRENT / EVOLUTION</strong><p>実線は現在確認できるflow。将来のPages input、external integration、replay等はEVOLUTIONとして分離します。</p></div>',
    ]

    for index, (title, summary, url, alt) in enumerate(sections):
        open_attr = " open" if index == 0 else ""
        out.extend([
            f'<details class="codex-progressive-disclosure"{open_attr}>',
            f'<summary><strong>{escape(title)}</strong><span>{escape(summary)}</span></summary>',
            '<div class="codex-progressive-disclosure__content">',
            _img(url, alt),
            '</div>',
            '</details>',
        ])

    out.extend([
        '<div class="codex-alert" data-state="warning"><strong>重要</strong><p>Brokerで約定しただけではInvestment OSは未観測です。会話・CSV・将来integrationなどで入力され、Validation / Preview / Owner Approvalを経て初めてCanonical Stateへ反映されます。</p></div>',
        '<p><a class="codex-action" href="{{ \'/architecture/git-native-agentic-runtime-diagrams/\' | relative_url }}">Accessible text explanationを見る</a></p>',
        '</section>',
    ])
    return "\n".join(out) + "\n"


def publish_diagram_assets(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "349_system_overview.svg",
        "349_runtime_architecture.svg",
        "349_git_state_machine.svg",
        "349_versioned_input.svg",
    ):
        source = source_dir / name
        if not source.is_file():
            raise FileNotFoundError(f"missing #349 diagram asset: {source}")
        (destination_dir / name).write_bytes(source.read_bytes())
