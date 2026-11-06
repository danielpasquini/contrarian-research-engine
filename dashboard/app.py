"""
Dark-Mode Quantitative Command Center (`dashboard/app.py`).
State-of-the-art UI/UX incorporating DavidHDev/react-bits patterns:
- Subtle ambient gradient background (zero grid lines)
- SpotlightCard mouse-tracking radial illumination
- ShinyText & GradientText headers
- Plus Jakarta Sans + JetBrains Mono tabular typography
- Human-readable micro-badges ("Falling Knife - No Absorption")
- Live Alpaca IEX + Gemini Flash (temp=0.0) scan & manual Bracket Order execution.
Contains zero embedded financial or position-sizing calculations (`C-CQ-05`).
"""

from html import escape

from src.config import EngineSettings

SURVIVORSHIP_BANNER_TEXT = "Static Universe - Survivorship Bias Unadjusted (Free Data Mode)"


def get_dashboard_banner() -> dict[str, str]:
    settings = EngineSettings()
    return {
        "title": "Contrarian Engine",
        "mode": settings.execution_mode.upper(),
        "bias_notice": SURVIVORSHIP_BANNER_TEXT,
    }


def get_command_center_state() -> dict[str, object]:
    """Read-only telemetry state for the Two-Stage Funnel & Immutable Risk Guardrails."""
    settings = EngineSettings()
    return {
        "title": "Contrarian Engine",
        "execution_mode": settings.execution_mode.upper(),
        "survivorship_bias_warning": SURVIVORSHIP_BANNER_TEXT,
        "funnel_stages": {
            "stage1_universe_size": settings.universe_size,
            "stage1_max_shortlist": settings.max_daily_llm_candidates,
            "stage1_min_dollar_volume": settings.min_average_dollar_volume,
            "stage1_min_share_price": settings.min_share_price,
            "stage1_intraday_absorption_window": "AM 09:30-10:30 ET vs PM 15:00-16:00 ET (15m)",
            "stage2_forensic_modules": [
                "SEC 8-K/10-Q difflib Redline Forensics",
                "SEC Form 4 Discretionary C-Suite Open-Market Purchases (Code P)",
                "Cross-Entity Sympathy Contagion vs. Rival Failure",
            ],
            "llm_veto_engine": {
                "model": settings.gemini_model,
                "temperature": settings.gemini_temperature,
                "fail_closed_on_timeout_or_schema_error": True,
            },
        },
        "immutable_guardrails": {
            "no_averaging_down": not settings.allow_averaging_down,
            "mandatory_bracket_oco": settings.require_bracket_order,
            "atr_period": settings.atr_period,
            "atr_stop_multiplier": settings.atr_stop_multiplier,
            "min_reward_risk_ratio": settings.min_reward_risk_ratio,
            "max_risk_per_trade_pct": settings.max_risk_per_trade_pct,
            "max_position_pct": settings.max_position_pct,
            "max_portfolio_exposure": settings.max_portfolio_exposure,
            "daily_kill_switch_pct": settings.max_daily_loss_pct,
            "earnings_blackout_sessions": settings.earnings_blackout_days,
            "alpaca_paper_endpoint": settings.alpaca_paper_api_url,
        },
    }


def build_react_bits_background_html() -> str:
    """
    Returns React Bits-inspired subtle gradient background (no grid lines),
    SpotlightCard, ShinyText, StarBorder, and refined Plus Jakarta Sans + JetBrains Mono CSS.
    """
    return """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap">
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap">
<style>
  :root {
    --bg-base: #060a12;
    --bg-surface: rgba(18, 24, 38, 0.72);
    --bg-surface-elevated: rgba(24, 32, 50, 0.82);
    --border-subtle: rgba(255, 255, 255, 0.075);
    --border-hover: rgba(56, 189, 248, 0.32);
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --accent-cyan: #38bdf8;
    --accent-emerald: #10b981;
    --accent-amber: #f59e0b;
    --accent-rose: #f43f5e;
    --accent-indigo: #818cf8;
  }
  * {
    box-sizing: border-box;
  }
  ::-webkit-scrollbar {
    width: 7px;
    height: 7px;
  }
  ::-webkit-scrollbar-track {
    background: rgba(6, 10, 18, 0.6);
  }
  ::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.22);
    border-radius: 999px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: rgba(148, 163, 184, 0.38);
  }
  body, .stApp {
    margin: 0;
    padding: 0;
    background-color: var(--bg-base) !important;
    color: var(--text-primary) !important;
    font-family: 'Segoe UI Variable Display', 'Segoe UI Variable Text',
      'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    min-height: 100vh;
    user-select: none;
  }
  /* Sleek monochrome dark background — zero glow/blobs */
  .react-bits-aurora-canvas {
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background: linear-gradient(180deg, #080b11 0%, #0b1018 100%);
  }
  .win11-app-logo {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
  }
  /* Sleek matte card surface — zero glow or radial spotlight */
  .glass-metric-card {
    position: relative;
    z-index: 1;
    background: rgba(15, 20, 30, 0.88);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.065);
    border-radius: 10px;
    padding: 16px 18px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
    overflow: hidden;
    transition: border-color 0.15s ease;
  }
  .glass-metric-card:hover {
    border-color: rgba(255, 255, 255, 0.12);
  }
  .glass-card-title {
    font-size: 0.68rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-secondary);
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .glass-card-value {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 1.42rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text-primary);
    margin: 7px 0 5px 0;
  }
  .glass-card-subtitle {
    font-size: 0.74rem;
    color: var(--text-muted);
    font-weight: 500;
  }
  /* Clean solid title — zero shimmer/shine */
  .rb-shiny-title {
    color: #f8fafc;
    letter-spacing: -0.025em;
  }
  .survivorship-banner {
    position: relative;
    z-index: 1;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(245, 158, 11, 0.05);
    border: 1px solid rgba(245, 158, 11, 0.18);
    color: #d97706;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 0.71rem;
    font-weight: 500;
    letter-spacing: 0.01em;
    margin-bottom: 14px;
  }
  .action-toolbar {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    background: rgba(15, 20, 30, 0.88);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.065);
    border-radius: 10px;
    padding: 14px 18px;
    margin: 14px 0;
  }
  /* Sleek muted-emerald primary button — zero glow */
  .btn-scan {
    position: relative;
    background: rgba(16, 185, 129, 0.12);
    color: #6ee7b7;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 600;
    font-size: 0.81rem;
    letter-spacing: -0.01em;
    border: 1px solid rgba(16, 185, 129, 0.28);
    border-radius: 7px;
    padding: 9px 16px;
    cursor: pointer;
    box-shadow: none;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }
  .btn-scan:hover {
    background: rgba(16, 185, 129, 0.20);
    border-color: rgba(16, 185, 129, 0.42);
    color: #a7f3d0;
  }
  .btn-scan:disabled {
    opacity: 0.50;
    cursor: wait;
  }
  .btn-order {
    margin-top: 8px;
    background: rgba(16, 185, 129, 0.08);
    color: #34d399;
    font-family: 'Plus Jakarta Sans', sans-serif;
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 0.71rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    cursor: pointer;
    box-shadow: none;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .btn-order:hover {
    background: #10b981;
    color: #060a12;
    border-color: #10b981;
  }
  .btn-order-short {
    margin-top: 8px;
    background: rgba(244, 63, 94, 0.09);
    color: #fda4af;
    font-family: 'Plus Jakarta Sans', sans-serif;
    border: 1px solid rgba(244, 63, 94, 0.28);
    border-radius: 6px;
    padding: 5px 11px;
    font-size: 0.71rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    cursor: pointer;
    box-shadow: none;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .btn-order-short:hover {
    background: #f43f5e;
    color: #060a12;
    border-color: #f43f5e;
  }
  .btn-order:disabled, .btn-order-short:disabled, .btn-desk-action:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  /* Capital Reserve & Tail-Risk Desk */
  .capital-desk-bar {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 14px;
    background: rgba(15, 20, 30, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.065);
    border-radius: 10px;
    padding: 12px 18px;
    margin-top: 12px;
  }
  .desk-telemetry {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
  .desk-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }
  .btn-desk-action {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.035);
    color: #cbd5e1;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    padding: 6px 11px;
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }
  .btn-desk-action:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.20);
    color: #f8fafc;
  }
  .btn-desk-tbill {
    background: rgba(16, 185, 129, 0.09);
    color: #6ee7b7;
    border-color: rgba(16, 185, 129, 0.25);
  }
  .btn-desk-tbill:hover {
    background: rgba(16, 185, 129, 0.18);
    border-color: rgba(16, 185, 129, 0.40);
    color: #a7f3d0;
  }
  .btn-desk-hedge {
    background: rgba(56, 189, 248, 0.08);
    color: #7dd3fc;
    border-color: rgba(56, 189, 248, 0.24);
  }
  .btn-desk-hedge:hover {
    background: rgba(56, 189, 248, 0.16);
    border-color: rgba(56, 189, 248, 0.38);
    color: #bae6fd;
  }
  /* Segmented Filter Tabs */
  .filter-tabs {
    display: inline-flex;
    align-items: center;
    background: rgba(8, 11, 18, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 7px;
    padding: 3px;
    gap: 3px;
  }
  .filter-tab {
    background: transparent;
    color: var(--text-secondary);
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 0.71rem;
    font-weight: 600;
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    cursor: pointer;
    transition: background-color 0.14s ease, color 0.14s ease;
  }
  .filter-tab:hover {
    color: var(--text-primary);
  }
  .filter-tab.active {
    background: rgba(255, 255, 255, 0.08);
    color: #f8fafc;
  }
  .badge-dir-long {
    background: rgba(16, 185, 129, 0.11);
    border: 1px solid rgba(16, 185, 129, 0.28);
    color: #6ee7b7;
    font-size: 0.63rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 1px 6px;
    border-radius: 4px;
  }
  .badge-dir-short {
    background: rgba(244, 63, 94, 0.11);
    border: 1px solid rgba(244, 63, 94, 0.30);
    color: #fda4af;
    font-size: 0.63rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 1px 6px;
    border-radius: 4px;
  }
  .badge-put-proxy {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(129, 140, 248, 0.10);
    border: 1px solid rgba(129, 140, 248, 0.26);
    color: #a5b4fc;
    font-size: 0.66rem;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 5px;
    margin-top: 5px;
  }
  .glass-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
  }
  .glass-table th {
    background: rgba(10, 14, 24, 0.65);
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.68rem;
    letter-spacing: 0.07em;
    padding: 13px 16px;
    text-align: left;
    border-bottom: 1px solid var(--border-subtle);
  }
  .glass-table td {
    padding: 15px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.045);
    vertical-align: middle;
  }
  .glass-table tbody tr {
    transition: background-color 0.15s ease;
  }
  .glass-table tbody tr:hover td {
    background: rgba(255, 255, 255, 0.025);
  }
  /* Refined micro-badges for status & veto */
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 0.70rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    line-height: 1.3;
  }
  .badge-actionable {
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.30);
    color: #6ee7b7;
  }
  .badge-veto {
    background: rgba(244, 63, 94, 0.10);
    border: 1px solid rgba(244, 63, 94, 0.24);
    color: #fda4af;
  }
  .badge-watch {
    background: rgba(245, 158, 11, 0.10);
    border: 1px solid rgba(245, 158, 11, 0.24);
    color: #fcd34d;
  }
  .badge-setup {
    background: rgba(56, 189, 248, 0.09);
    border: 1px solid rgba(56, 189, 248, 0.22);
    color: #7dd3fc;
    font-size: 0.66rem;
    font-weight: 500;
    padding: 2px 8px;
  }
  .mono {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
  }
  /* Modern accessible floating tooltip styling */
  .tooltip-wrapper {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: help;
  }
  .tooltip-trigger {
    border-bottom: 1px dotted rgba(255, 255, 255, 0.35);
    transition: border-color 0.15s ease, color 0.15s ease;
  }
  .tooltip-wrapper:hover .tooltip-trigger {
    border-bottom-color: var(--accent-cyan);
    color: var(--text-primary);
  }
  #globalTooltip {
    position: fixed;
    display: none;
    background: #0b1120;
    color: #f1f5f9;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 0.72rem;
    font-weight: 500;
    line-height: 1.45;
    text-transform: none;
    letter-spacing: normal;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow: 0 14px 30px -4px rgba(0, 0, 0, 0.85), 0 0 1px rgba(255, 255, 255, 0.25);
    max-width: 280px;
    z-index: 999999;
    pointer-events: none;
    white-space: normal;
    word-break: normal;
    transition: opacity 0.12s ease;
  }
</style>
<div class="react-bits-aurora-canvas"></div>
<div id="globalTooltip"></div>
""".strip()


def build_glass_metric_card_html(
    title: str,
    value: str,
    subtitle: str,
    tooltip: str = "",
    badge_tone: str = "cyan",
) -> str:
    """Renders an individual SpotlightCard glassmorphism metric card with tooltip support."""
    tone_colors = {
        "cyan": "#38bdf8",
        "emerald": "#10b981",
        "amber": "#f59e0b",
        "rose": "#f43f5e",
    }
    accent = tone_colors.get(badge_tone, "#38bdf8")
    safe_title = escape(title)
    safe_value = escape(value)
    safe_subtitle = escape(subtitle)
    safe_tooltip = escape(tooltip)
    dot = f'<span style="width:6px;height:6px;border-radius:50%;background:{accent};"></span>'
    title_html = (
        f'<div class="tooltip-wrapper" data-tip="{safe_tooltip}">'
        f'<span class="tooltip-trigger glass-card-title">{dot}{safe_title}</span>'
        f"</div>"
        if tooltip
        else f'<div class="glass-card-title">{dot}{safe_title}</div>'
    )
    return (
        f'<div class="glass-metric-card">'
        f"{title_html}"
        f'<div class="glass-card-value">{safe_value}</div>'
        f'<div class="glass-card-subtitle">{safe_subtitle}</div>'
        f"</div>"
    )


def build_command_center_html() -> str:
    """Builds a self-contained state-of-the-art dark-mode HTML Command Center page."""
    banner = get_dashboard_banner()
    state = get_command_center_state()
    guard = state["immutable_guardrails"]
    if not isinstance(guard, dict):
        raise TypeError("Expected immutable_guardrails to be a dictionary.")
    funnel = state["funnel_stages"]
    if not isinstance(funnel, dict):
        raise TypeError("Expected funnel_stages to be a dictionary.")

    cards = [
        build_glass_metric_card_html(
            title="Execution Mode",
            value="Paper (Manual)",
            subtitle="Human-in-the-Loop Bracket Approval",
            tooltip=(
                "Orders require manual user confirmation before routing to Alpaca Paper API. "
                "LIVE trading is hard-blocked by policy."
            ),
            badge_tone="emerald",
        ),
        build_glass_metric_card_html(
            title="Stage 1 Shortlist Cap",
            value=f"<= {funnel['stage1_max_shortlist']} Equities",
            subtitle="Alpaca IEX Bars + Wilder ATR(14)",
            tooltip=(
                "Python deterministic scanner filters 500+ liquid US equities down to a maximum "
                "of 15 candidates before invoking Gemini AI."
            ),
            badge_tone="cyan",
        ),
        build_glass_metric_card_html(
            title="Volatility Risk Cap",
            value=f"{float(guard['max_risk_per_trade_pct']) * 100:.2f}% Equity",
            subtitle=f"Max Position {float(guard['max_position_pct']) * 100:.0f}% · OCO >= 2.0R",
            tooltip=(
                "Mathematical position sizing strictly limits loss per trade to <= 0.50% equity "
                "and max notional allocation to 8%."
            ),
            badge_tone="cyan",
        ),
        build_glass_metric_card_html(
            title="Daily Kill Switch",
            value=f"-{float(guard['daily_kill_switch_pct']) * 100:.2f}%",
            subtitle="No Averaging Down · 3d Earnings Lock",
            tooltip=(
                "Emergency halt: blocks all new entries if daily portfolio loss reaches -1.50%. "
                "Forbids averaging down on losing positions."
            ),
            badge_tone="amber",
        ),
    ]
    cards_grid = "\n".join(cards)
    bg_html = build_react_bits_background_html()
    grid_style = (
        "display:grid; grid-template-columns:repeat(auto-fit, minmax(235px, 1fr)); gap:16px;"
    )

    client_script = """
<script>
let scanTimer = null;
let latestScanResult = null;
let activeCandidateFilter = 'ALL';

function handleSpotlight(e, el) {
  const rect = el.getBoundingClientRect();
  el.style.setProperty('--mouse-x', `${e.clientX - rect.left}px`);
  el.style.setProperty('--mouse-y', `${e.clientY - rect.top}px`);
}

function initFloatingTooltips() {
  const tipEl = document.getElementById('globalTooltip');
  if (!tipEl) return;

  document.addEventListener('mouseover', e => {
    const target = e.target.closest('.tooltip-wrapper[data-tip]');
    if (!target) return;
    const text = target.getAttribute('data-tip');
    if (!text) return;

    tipEl.innerText = text;
    tipEl.style.display = 'block';
    tipEl.style.opacity = '1';

    const rect = target.getBoundingClientRect();
    const tipWidth = tipEl.offsetWidth;
    const tipHeight = tipEl.offsetHeight;

    // Calculate optimal horizontal position
    let left = rect.left + (rect.width / 2) - (tipWidth / 2);
    const margin = 14;
    if (left < margin) left = margin;
    if (left + tipWidth > window.innerWidth - margin) {
      left = window.innerWidth - margin - tipWidth;
    }

    // Prefer displaying above the element; flip below if colliding with top edge
    let top = rect.top - tipHeight - 8;
    if (top < margin) {
      top = rect.bottom + 8;
    }

    tipEl.style.left = `${Math.round(left)}px`;
    tipEl.style.top = `${Math.round(top)}px`;
  });

  document.addEventListener('mouseout', e => {
    const target = e.target.closest('.tooltip-wrapper[data-tip]');
    if (!target) return;
    tipEl.style.display = 'none';
    tipEl.style.opacity = '0';
  });
}

function humanizeCode(raw) {
  if (!raw) return 'On Watchlist';
  const map = {
    'VETO_FALLING_KNIFE_NO_ABSORPTION': 'Falling Knife - No Absorption',
    'VETO_EARNINGS_BLACKOUT_2D': 'Earnings Blackout (< 3d)',
    'VETO_EARNINGS_BLACKOUT': 'Earnings Blackout (< 3d)',
    'OVERSOLD_EXHAUSTION': 'Oversold Exhaustion',
    'STRUCTURAL_PULLBACK': 'Structural Pullback',
    'UPTREND_WATCH': 'Uptrend Watch',
    'MEAN_REVERSION_WATCH': 'Mean Reversion',
    'PARABOLIC_SHORT': 'Parabolic Exhaustion',
    'ABAIXO_SMA200_SEM_CAPITULACAO': 'Below SMA-200 Trend Filter'
  };
  if (map[raw]) return map[raw];
  if (raw.startsWith('VETO_FALLING_KNIFE')) return 'Falling Knife - No Absorption';
  if (raw.startsWith('AGUARDANDO_EXAUSTAO')) return 'Awaiting Deeper Exhaustion';
  if (raw.startsWith('MONITORAMENTO')) return 'Stabilizing - On Watchlist';
  if (raw.includes('_')) {
    return raw
      .replace(/^VETO_/, '')
      .toLowerCase()
      .split('_')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  }
  return raw;
}

function renderAccount(acct, desk) {
  if (!acct) return;
  const eqEl = document.getElementById('alpacaEquityBadge');
  const posEl = document.getElementById('positionsSummary');
  const eqVal = Number(acct.total_equity || 100000).toLocaleString('en-US', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  });
  const srvDot = '<span style="color:#10b981;">●</span> Server Online';
  const alpDot = acct.connected
    ? '<span style="color:#38bdf8;">●</span> Alpaca Paper'
    : '<span style="color:#38bdf8;">●</span> Paper Simulation';
  const ordToday = acct.orders_submitted_today || 0;
  eqEl.innerHTML =
    `${srvDot} &nbsp;·&nbsp; ${alpDot} &nbsp;·&nbsp; ` +
    `Equity: <strong>$${eqVal}</strong> &nbsp;·&nbsp; Orders Today: ${ordToday}/2`;

  const positions = acct.open_positions || [];
  const openOrders = acct.open_entry_order_tickers || [];
  if (positions.length === 0 && openOrders.length === 0) {
    posEl.innerText = 'No open positions or pending bracket orders in your Alpaca Paper account.';
  } else {
    let parts = [];
    if (positions.length > 0) {
      const pStr = positions.map(
        p => `${p.ticker} (${p.qty} sh @ $${p.avg_entry_price.toFixed(2)}, ` +
          `Now $${p.current_price.toFixed(2)})`
      ).join(' · ');
      parts.push('Open Positions: ' + pStr);
    }
    if (openOrders.length > 0) {
      parts.push('Pending Bracket Orders: ' + openOrders.join(', '));
    }
    posEl.innerText = parts.join('   |   ');
  }

  if (desk) {
    renderCapitalDesk(desk);
  }
}

function renderCapitalDesk(desk) {
  const idleEl = document.getElementById('deskIdleCash');
  const yieldEl = document.getElementById('deskTbillYield');
  if (!idleEl || !yieldEl || !desk) return;

  const idleFmt = Number(desk.idle_cash || 100000).toLocaleString('en-US', {
    minimumFractionDigits: 0, maximumFractionDigits: 0
  });
  const annFmt = Number(desk.estimated_annual_yield_usd || 5150).toLocaleString('en-US', {
    minimumFractionDigits: 0, maximumFractionDigits: 0
  });
  const moFmt = Number(desk.estimated_monthly_yield_usd || 429).toLocaleString('en-US', {
    minimumFractionDigits: 0, maximumFractionDigits: 0
  });
  idleEl.innerText = `$${idleFmt}`;
  yieldEl.innerText = `+$${annFmt}/yr (+$${moFmt}/mo @ ${desk.tbill_apy_pct || 5.15}% APY)`;
}

function setCandidateFilter(filterMode, btnEl) {
  activeCandidateFilter = filterMode;
  document.querySelectorAll('.filter-tab').forEach(b => b.classList.remove('active'));
  if (btnEl) btnEl.classList.add('active');
  if (latestScanResult) {
    renderCandidates(latestScanResult);
  }
}

async function runScan() {
  const btn = document.getElementById('scanBtn');
  const statusTxt = document.getElementById('scanStatus');
  btn.disabled = true;
  let elapsed = 0;
  statusTxt.innerText = 'Stage 1/2: Fetching live daily bars from Alpaca IEX (0.0s)...';
  scanTimer = setInterval(() => {
    elapsed += 0.2;
    btn.innerText = `Scanning Alpaca + Gemini AI (${elapsed.toFixed(1)}s)...`;
    if (elapsed < 4.5) {
      statusTxt.innerText =
        `Stage 1: Downloading 70 liquid US equities from Alpaca IEX & ` +
        `computing ATR(14)/RSI(2) (${elapsed.toFixed(1)}s)...`;
    } else {
      statusTxt.innerText =
        `Stage 2: Running Gemini Flash (temp=0.0) red-flag & ` +
        `headline analysis (${elapsed.toFixed(1)}s)...`;
    }
  }, 200);

  try {
    let res = null;
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        res = await fetch('/api/v1/scan/run', { method: 'POST' });
        if (res.ok) break;
      } catch (fetchErr) {
        if (attempt === 2) throw fetchErr;
        await new Promise(r => setTimeout(r, 800));
      }
    }
    const data = await res.json();
    clearInterval(scanTimer);
    if (data.status === 'ok' && data.result) {
      const r = data.result;
      latestScanResult = r;
      renderCandidates(r);
      if (r.account_summary) renderAccount(r.account_summary, r.capital_desk);
      const aiModel = r.ai_model_used || 'gemini-3-flash-preview';
      statusTxt.innerText =
        `Completed in ${r.scan_duration_seconds}s · Source: ${r.data_source} · ` +
        `AI Gate: ${aiModel} · ${r.universe_count} equities analyzed (${r.scan_date})`;
    } else {
      statusTxt.innerText = 'Scan encountered an error.';
    }
  } catch (err) {
    clearInterval(scanTimer);
    statusTxt.innerText = 'Network error: ' + err.message;
  } finally {
    btn.disabled = false;
    btn.innerText = 'Run Live Scan (Alpaca + Gemini AI)';
  }
}

async function submitPaperOrder(
  ticker, entryPrice, atr14, shares, stopLoss, takeProfit, riskUsd, direction, strategyName, btnEl
) {
  const isShort = direction === 'SHORT';
  const actionTitle = isShort
    ? 'SELL SHORT (Forensic Short OCO Bracket)'
    : 'BUY TO OPEN (Long OCO Bracket)';
  const stopDesc = isShort
    ? `Server-Side Buy-to-Cover Stop (1.5x ATR above): $${stopLoss.toFixed(2)}`
    : `Server-Side Stop Loss (2.0x ATR below): $${stopLoss.toFixed(2)}`;
  const tpDesc = isShort
    ? `Server-Side Buy-to-Cover Target (2.0R below): $${takeProfit.toFixed(2)}`
    : `Server-Side Take Profit (2.0R above): $${takeProfit.toFixed(2)}`;
  const riskCapLabel = isShort ? '<= 0.25% Equity (Halved Short Risk)' : '<= 0.50% Equity';

  const msg =
    `Confirm Atomic Bracket Order (OCO) to Alpaca Paper?\\n\\n` +
    `Action: ${actionTitle}\\n` +
    `Ticker: ${ticker}\\n` +
    `Quantity: ${shares} shares @ $${entryPrice.toFixed(2)}\\n` +
    `${stopDesc}\\n` +
    `${tpDesc}\\n` +
    `Max Financial Risk: $${riskUsd.toFixed(2)} (${riskCapLabel})\\n\\n` +
    `Click OK to transmit order to paper-api.alpaca.markets.`;
  if (!window.confirm(msg)) return;

  const origLabel = btnEl.innerText;
  btnEl.disabled = true;
  btnEl.innerText = 'Submitting to Alpaca...';
  try {
    const res = await fetch('/api/v1/orders/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker: ticker,
        entry_price: entryPrice,
        atr_14: atr14,
        strategy_name: strategyName || (isShort ? 'forensic_short' : 'neg_overreaction'),
        direction: direction || 'LONG'
      })
    });
    const data = await res.json();
    if (data.status === 'ok' && data.order) {
      btnEl.innerText = `Order Sent (${data.order.status})`;
      btnEl.style.background = isShort ? '#f43f5e' : '#10b981';
      btnEl.style.color = '#04070e';
      const o = data.order;
      alert(
        `Bracket Order Submitted to Alpaca Paper!\\n\\n` +
        `Ticker: ${o.ticker} (${o.direction || direction})\\n` +
        `Quantity: ${o.qty} sh @ $${o.entry_price.toFixed(2)}\\n` +
        `Stop Loss: $${o.stop_loss_price.toFixed(2)} | ` +
        `Target: $${o.take_profit_price.toFixed(2)}\\n` +
        `Status: ${o.status}\\n` +
        `Broker Order ID: ${o.broker_order_id}`
      );
      const acctRes = await fetch('/api/v1/account');
      const acctData = await acctRes.json();
      if (acctData.account) renderAccount(acctData.account, acctData.capital_desk);
    } else {
      btnEl.disabled = false;
      btnEl.innerText = origLabel;
      alert('Order Guard Rejection:\\n' + (data.message || 'Unknown validation error'));
    }
  } catch (err) {
    btnEl.disabled = false;
    btnEl.innerText = origLabel;
    alert('Network error: ' + err.message);
  }
}

function submitDeskPreset(
  ticker, entryPrice, atr14, shares, stopLoss, takeProfit, riskUsd, strat, btnEl
) {
  submitPaperOrder(
    ticker, entryPrice, atr14, shares, stopLoss, takeProfit, riskUsd, 'LONG', strat, btnEl
  );
}

function renderCandidates(result) {
  const tableBody = document.getElementById('candidatesTableBody');
  const emptyState = document.getElementById('emptyState');
  tableBody.innerHTML = '';

  if (!result || !result.candidates || result.candidates.length === 0) {
    emptyState.style.display = 'block';
    return;
  }

  const filtered = result.candidates.filter(c => {
    const dir = c.direction || 'LONG';
    if (activeCandidateFilter === 'LONG') return dir === 'LONG';
    if (activeCandidateFilter === 'SHORT') return dir === 'SHORT';
    if (activeCandidateFilter === 'ACTIONABLE') return Boolean(c.is_actionable);
    return true;
  });

  if (filtered.length === 0) {
    emptyState.style.display = 'block';
    return;
  }
  emptyState.style.display = 'none';

  filtered.forEach(c => {
    const row = document.createElement('tr');
    const isAct = c.is_actionable;
    const dir = c.direction || 'LONG';
    const isShort = dir === 'SHORT';
    const cleanReason = humanizeCode(c.veto_reason);
    const cleanSetup = humanizeCode(c.setup_type);
    const isHardVeto = cleanReason.toLowerCase().includes('knife') ||
      cleanReason.toLowerCase().includes('blackout') ||
      cleanReason.toLowerCase().includes('veto');
    const badgeClass = isAct ? 'badge-actionable' : (isHardVeto ? 'badge-veto' : 'badge-watch');
    const statusLabel = isAct ? 'Actionable Setup' : cleanReason;
    const aiText = c.ai_summary || 'Evaluated by Gemini Flash';
    const aiCapStyle =
      'color:#64748b; font-size:0.70rem; margin-top:5px; max-width:250px; line-height:1.35;';

    const shortActMsg =
      'Actionable Forensic Short: Parabolic extension + weak close fade; sized at 0.25% max risk.';
    const longActMsg =
      'Actionable Long Pullback: Met drop, volume absorption, and passed Gemini AI veto.';
    const tipStatus = isAct
      ? (isShort ? shortActMsg : longActMsg)
      : 'Vetoed/Filtered: ' + statusLabel;

    let putProxyHtml = '';
    if (isShort && c.put_option_proxy) {
      const pp = c.put_option_proxy;
      const stk = pp.strike_price.toFixed(0);
      const prem = pp.est_premium_per_share.toFixed(2);
      const mLoss = pp.max_loss_usd.toFixed(0);
      const bEven = pp.breakeven_price.toFixed(2);
      const tipPut =
        `Defined-Risk Option Alternative: Buy ${pp.contracts}x ${pp.tenor_days}d $${stk} Put ` +
        `(@ ~$${prem}/sh). Max possible loss is strictly capped at $${mLoss} ` +
        `(premium paid) with zero short-squeeze margin risk. Breakeven: $${bEven}.`;
      const putLabel =
        `Put Proxy: ${pp.contracts}x ${pp.tenor_days}d $${stk}P (Max Loss $${mLoss})`;
      putProxyHtml = `
        <div class="tooltip-wrapper" data-tip="${tipPut}">
          <span class="badge-put-proxy tooltip-trigger mono">${putLabel}</span>
        </div>`;
    }

    const statusBlock = `
      <div>
        <div class="tooltip-wrapper" data-tip="${tipStatus}">
          <span class="badge ${badgeClass} tooltip-trigger">${statusLabel}</span>
        </div>
        <div style="${aiCapStyle}">
          <span style="color:#94a3b8; font-weight:600;">AI:</span> ${aiText}
        </div>
        ${putProxyHtml}
      </div>`;

    let bracketHtml = '<span style="color:#475569; font-size:0.75rem;">—</span>';
    if (c.bracket_order) {
      const bo = c.bracket_order;
      const stratName = isShort ? 'forensic_short' : 'neg_overreaction';
      const callArgs =
        `'${c.ticker}', ${bo.entry_price}, ${c.atr_14}, ${bo.shares}, ` +
        `${bo.stop_loss_price}, ${bo.take_profit_price}, ${bo.risk_usd}, ` +
        `'${dir}', '${stratName}', this`;
      const btnCls = isShort ? 'btn-order-short' : 'btn-order';
      const btnText = isShort ? 'Execute Short Bracket' : 'Execute Long Bracket';
      const btnOrder =
        `<button class="${btnCls}" onclick="submitPaperOrder(${callArgs})">` +
        `${btnText}</button>`;
      const shVerb = isShort ? 'Short' : 'Buy';
      const slTip = isShort
        ? 'Server-side Buy-to-Cover Stop = Entry + (1.5 &times; Wilder ATR-14) above entry.'
        : 'Server-side Stop Loss = Entry - (2.0 &times; Wilder ATR-14) below entry.';
      const tpTip = isShort
        ? 'Server-side Buy-to-Cover Target = Entry - (2.0 &times; Risk) (&ge; 2.0R below entry).'
        : 'Server-side Take Profit = Entry + (2.0 &times; Risk) (&ge; 2.0R above entry).';
      const riskTip = isShort
        ? 'Halved Forensic Short Risk Cap (&le; 0.25% total equity).'
        : 'Loss if Stop Loss is hit (&le; 0.50% total equity).';
      const sizeTip = isShort
        ? 'Halved Short Position Notional Cap (&le; 4.0% of equity).'
        : 'Total position allocation (&le; 8.0% of equity).';
      const shTip =
        `${shVerb} ${bo.shares} shares at Limit Price $${bo.entry_price.toFixed(2)} per share.`;

      bracketHtml = `
        <div style="font-size:0.76rem; line-height:1.45;">
          <div class="mono" style="color:#e2e8f0; font-weight:600;">
            <span class="tooltip-wrapper" data-tip="${shTip}">
              <span class="tooltip-trigger">
                ${bo.shares} sh <span style="color:#64748b;">@</span> $${bo.entry_price.toFixed(2)}
              </span>
            </span>
          </div>
          <div class="mono" style="font-size:0.71rem; color:#94a3b8; margin-top:2px;">
            <div class="tooltip-wrapper" data-tip="${slTip}">
              <span class="tooltip-trigger" style="color:#fb7185;">
                SL $${bo.stop_loss_price.toFixed(2)}
              </span>
            </div>
            &nbsp;·&nbsp;
            <div class="tooltip-wrapper" data-tip="${tpTip}">
              <span class="tooltip-trigger" style="color:#34d399;">
                TP $${bo.take_profit_price.toFixed(2)}
              </span>
            </div>
          </div>
          <div class="mono" style="font-size:0.69rem; color:#64748b; margin-top:1px;">
            <div class="tooltip-wrapper" data-tip="${riskTip}">
              <span class="tooltip-trigger">Risk $${bo.risk_usd.toFixed(0)}</span>
            </div>
            &nbsp;·&nbsp;
            <div class="tooltip-wrapper" data-tip="${sizeTip}">
              <span class="tooltip-trigger">Size $${bo.position_usd.toFixed(0)}</span>
            </div>
          </div>
          ${btnOrder}
        </div>`;
    }

    const tkrStyle = 'font-weight:700; font-size:0.95rem; color:#f8fafc;';
    const absPct = (c.intraday_recovery * 100).toFixed(0);
    const dirBadgeCls = isShort ? 'badge-dir-short' : 'badge-dir-long';
    const shortDirTip =
      'FORENSIC SHORT: Profits when overextended price mean-reverts lower. ' +
      'Halved risk (0.25% equity) & inverted OCO bracket.';
    const longDirTip =
      'CONTRARIAN LONG: Profits when oversold price rebounds higher. ' +
      'Capped at 0.50% equity risk with 2x ATR stop below entry.';
    const dirTip = isShort ? shortDirTip : longDirTip;
    const zColor = c.z_score > 0 ? '#fda4af' : '#38bdf8';
    const zSign = c.z_score > 0 ? '+' : '';
    const zValStr = `${zSign}${c.z_score.toFixed(2)}&sigma;`;

    row.innerHTML = `
      <td>
        <div style="display:flex; align-items:center; gap:7px; flex-wrap:wrap;">
          <span class="mono" style="${tkrStyle}">${c.ticker}</span>
          <div class="tooltip-wrapper" data-tip="${dirTip}">
            <span class="${dirBadgeCls} tooltip-trigger mono">${dir}</span>
          </div>
          <div class="tooltip-wrapper"
            data-tip="Contrarian pattern based on statistical exhaustion and price action.">
            <span class="badge badge-setup tooltip-trigger">${cleanSetup}</span>
          </div>
        </div>
        <div style="color:#64748b; font-size:0.73rem; margin-top:3px;">${c.company_name}</div>
      </td>
      <td class="mono" style="font-weight:600; color:#f1f5f9;">$${c.close_price.toFixed(2)}</td>
      <td class="mono" style="color:${zColor}; font-weight:600;">${zValStr}</td>
      <td class="mono" style="color:#cbd5e1;">${c.rsi_2.toFixed(1)}</td>
      <td class="mono" style="color:#94a3b8;">$${c.atr_14.toFixed(2)}</td>
      <td class="mono" style="color:#38bdf8; font-weight:500;">${absPct}%</td>
      <td class="mono" style="font-weight:700; color:#34d399;">${c.composite_score.toFixed(1)}</td>
      <td>${statusBlock}</td>
      <td>${bracketHtml}</td>
    `;
    tableBody.appendChild(row);
  });
}

async function syncEngineState(attempt = 1) {
  try {
    const res = await fetch('/api/v1/scan/latest');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (data.account) renderAccount(data.account, data.capital_desk);
    if (data.status === 'ok' && data.result) {
      latestScanResult = data.result;
      renderCandidates(data.result);
      const r = data.result;
      const s = document.getElementById('scanStatus');
      s.innerText =
        `Last scan: ${r.data_source} · AI: ${r.ai_model_used || 'gemini-3-flash-preview'} ` +
        `(${r.scan_date}) in ${r.scan_duration_seconds}s`;
    }
  } catch (e) {
    if (attempt <= 8) {
      setTimeout(() => syncEngineState(attempt + 1), 1000);
    } else {
      console.warn('Init load failed:', e);
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  initFloatingTooltips();
  syncEngineState();
});
</script>
"""

    header_flex = (
        "display:flex; justify-content:space-between; align-items:center; "
        "flex-wrap:wrap; gap:14px; margin-bottom:20px;"
    )
    brand_row = "display:flex; align-items:center; gap:14px;"
    badge_style = (
        "font-size:0.74rem; color:#cbd5e1; background:rgba(15,20,32,0.78); "
        "padding:8px 14px; border-radius:999px; border:1px solid rgba(255,255,255,0.09);"
    )
    tbl_header_style = (
        "padding:16px 20px; border-bottom:1px solid var(--border-subtle); "
        "display:flex; justify-content:space-between; align-items:center;"
    )
    empty_style = "text-align:center; padding:42px 24px; color:#64748b; font-size:0.84rem;"
    pos_bar_style = (
        "position:relative; z-index:1; background:rgba(18,24,38,0.66); "
        "border:1px solid var(--border-subtle); border-radius:12px; "
        "padding:11px 18px; margin-top:14px; font-size:0.76rem; color:#94a3b8;"
    )

    idle_tip = (
        "Uninvested cash currently sitting idle while waiting for rare contrarian setups."
    )
    tbill_tip = (
        "Estimated risk-free sovereign yield if idle cash is parked in "
        "0-3 Month US Treasury Bills (SGOV / BIL)."
    )
    sgov_tip = (
        "1-Click Treasury Sweep: Allocates an 8% capital slice (79 sh @ $100.45) into SGOV "
        "(iShares 0-3 Month US Treasury Bond ETF) via atomic Bracket Order (~5.15% APY)."
    )
    sh_tip = (
        "Macro Tail-Risk Hedge: Buys 191 sh of SH (ProShares Short S&P 500 -1x Inverse ETF "
        "@ $41.80) with atomic OCO stop ($40.50) & target ($44.40). Zero borrow fee."
    )
    psq_tip = (
        "Tech/AI Drawdown Hedge: Buys 207 sh of PSQ (ProShares Short QQQ -1x Nasdaq-100 ETF "
        "@ $38.60) with atomic OCO stop ($37.10) & target ($41.60). Capped risk."
    )
    sgov_call = (
        "submitDeskPreset('SGOV', 100.45, 0.15, 79, 100.15, 100.75, 23.70, 'tbill_sweep', this)"
    )
    sh_call = (
        "submitDeskPreset('SH', 41.80, 0.65, 191, 40.50, 44.40, 248.30, 'tail_hedge', this)"
    )
    psq_call = (
        "submitDeskPreset('PSQ', 38.60, 0.75, 207, 37.10, 41.60, 310.50, 'tail_hedge', this)"
    )
    idle_val_style = "color:#f8fafc; font-weight:600; margin-left:5px;"
    yield_val_style = "color:#6ee7b7; font-weight:600; margin-left:5px;"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(banner["title"])}</title>
  <link rel="icon" type="image/png" href="/favicon.png" />
  <link rel="shortcut icon" href="/favicon.ico" />
</head>
<body style="margin:0; padding:26px 28px;">
  {bg_html}
  <div style="position:relative; z-index:1; max-width:1360px; margin:0 auto;">
    <div class="survivorship-banner">
      <span>●</span> {escape(banner["bias_notice"])}
    </div>
    <div style="{header_flex}">
      <div style="{brand_row}">
        <img src="/favicon.png" alt="Contrarian Engine" class="win11-app-logo" />
        <div>
          <h1 class="rb-shiny-title" style="margin:0; font-size:1.52rem; font-weight:700;">
            {escape(banner["title"])}
          </h1>
          <div style="font-size:0.77rem; color:var(--text-muted); margin-top:3px;">
            Two-Stage Quantitative Funnel · Alpaca IEX Microstructure · Gemini Flash Contextual Veto
          </div>
        </div>
      </div>
      <span id="alpacaEquityBadge" class="mono" style="{badge_style}">
        <span style="color:#10b981;">●</span> Connecting to Engine Server...
      </span>
    </div>

    <div style="{grid_style}">
      {cards_grid}
    </div>

    <!-- Live Alpaca Paper Portfolio Bar -->
    <div style="{pos_bar_style}">
      <strong style="color:#e2e8f0; font-weight:600;">Alpaca Paper Portfolio:</strong>
      <span id="positionsSummary" class="mono" style="margin-left:8px;">
        Checking open positions & active bracket orders...
      </span>
    </div>

    <!-- Capital Reserve (T-Bill Sweep) & Macro Tail-Risk Hedge Desk -->
    <div class="capital-desk-bar">
      <div class="desk-telemetry">
        <div class="tooltip-wrapper" data-tip="{idle_tip}">
          <span class="tooltip-trigger" style="font-weight:600; color:#e2e8f0;">
            Idle Cash Reserve:
          </span>
          <span id="deskIdleCash" class="mono" style="{idle_val_style}">
            $100,000
          </span>
        </div>
        <span style="color:#334155;">|</span>
        <div class="tooltip-wrapper" data-tip="{tbill_tip}">
          <span class="tooltip-trigger">T-Bill Yield Potential (SGOV):</span>
          <span id="deskTbillYield" class="mono" style="{yield_val_style}">
            +$5,150/yr (+$429/mo @ 5.15% APY)
          </span>
        </div>
      </div>
      <div class="desk-actions">
        <div class="tooltip-wrapper" data-tip="{sgov_tip}">
          <button class="btn-desk-action btn-desk-tbill" onclick="{sgov_call}">
            Sweep Slice to SGOV (5.15% APY)
          </button>
        </div>
        <div class="tooltip-wrapper" data-tip="{sh_tip}">
          <button class="btn-desk-action btn-desk-hedge" onclick="{sh_call}">
            Hedge S&P 500 (-1x SH)
          </button>
        </div>
        <div class="tooltip-wrapper" data-tip="{psq_tip}">
          <button class="btn-desk-action btn-desk-hedge" onclick="{psq_call}">
            Hedge Nasdaq-100 (-1x PSQ)
          </button>
        </div>
      </div>
    </div>

    <!-- Action Bar -->
    <div class="action-toolbar">
      <div>
        <div style="font-size:0.88rem; font-weight:600; color:#f1f5f9;">
          Live Market Scanner & Gemini Flash Audit
        </div>
        <div id="scanStatus" style="font-size:0.75rem; color:#64748b; margin-top:3px;">
          Click to fetch live Alpaca IEX bars and run Gemini Flash news analysis (~9s)
        </div>
      </div>
      <button id="scanBtn" class="btn-scan" onclick="runScan()">
        Run Live Scan (Alpaca + Gemini AI)
      </button>
    </div>

    <!-- Results Table -->
    <div class="glass-metric-card" style="padding:0;" onmousemove="handleSpotlight(event, this)">
      <div style="{tbl_header_style} flex-wrap:wrap; gap:12px;">
        <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
          <span style="font-weight:600; font-size:0.84rem; color:#f1f5f9; letter-spacing:-0.01em;">
            Stage 1 & Stage 2 Ranked Candidates
          </span>
          <div class="filter-tabs">
            <button class="filter-tab active" onclick="setCandidateFilter('ALL', this)">
              All Setups
            </button>
            <button class="filter-tab" onclick="setCandidateFilter('LONG', this)">
              Long Pullbacks
            </button>
            <button class="filter-tab" onclick="setCandidateFilter('SHORT', this)">
              Forensic Shorts & Puts
            </button>
            <button class="filter-tab" onclick="setCandidateFilter('ACTIONABLE', this)">
              Actionable Only
            </button>
          </div>
        </div>
        <span style="font-size:0.73rem; color:#64748b;">
          Manual execution only · Long (0.50% risk) &amp; Forensic Short / Put Proxy (0.25% risk)
        </span>
      </div>
      <div style="overflow-x:auto;">
        <table class="glass-table">
          <thead>
            <tr>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Ticker symbol, company name, and detected contrarian setup pattern.">
                  <span class="tooltip-trigger">Instrument</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Latest official closing price per share from Alpaca IEX daily bar.">
                  <span class="tooltip-trigger">Close</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Price drop standard deviations vs 20d volatility (&lt; -2.0&sigma;).">
                  <span class="tooltip-trigger">Z-Score (3d)</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Connors 2-period RSI (&lt; 10 indicates extreme oversold exhaustion).">
                  <span class="tooltip-trigger">RSI(2)</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Wilder ATR on raw prices; sets stop loss and share quantity.">
                  <span class="tooltip-trigger">ATR(14)</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Late-session institutional volume and price recovery (15:00-16:00 ET).">
                  <span class="tooltip-trigger">Absorption</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Composite score (0-100) combining drop, absorption, and trend.">
                  <span class="tooltip-trigger">Score</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Stage 1 filters plus Gemini Flash contextual headline veto.">
                  <span class="tooltip-trigger">Filter & Gemini AI Audit</span>
                </div>
              </th>
              <th>
                <div class="tooltip-wrapper"
                  data-tip="Atomic Bracket: Limit Entry, 2x ATR Stop Loss, and &ge; 2.0R TP.">
                  <span class="tooltip-trigger">Bracket Order (OCO)</span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody id="candidatesTableBody">
          </tbody>
        </table>
      </div>
      <div id="emptyState" style="{empty_style}">
        <img src="/favicon.png" alt=""
          style="width:34px; height:34px; border-radius:9px; opacity:0.8; margin-bottom:10px;" />
        <div>
          Click <strong>"Run Live Scan (Alpaca + Gemini AI)"</strong> above to fetch live market
          bars and run Gemini Flash analysis.
        </div>
      </div>
    </div>
  </div>
  {client_script}
</body>
</html>"""
