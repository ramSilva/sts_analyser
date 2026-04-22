#!/usr/bin/env python3
"""
app.py
Streamlit web app — analyses STS .run files and calculates various metrics.

Run locally:
    streamlit run app.py

Deploy free:
    https://streamlit.io/cloud  (point it at this file in your GitHub repo)
"""

import json

import altair as alt

import streamlit as st


# ---------------------------------------------------------------------------
# Persistent file store — keyed by username
# ---------------------------------------------------------------------------

@st.cache_resource
def get_all_stores() -> dict[str, dict[str, bytes]]:
    """Global store: { username -> { filename -> raw bytes } }. Persists across refreshes."""
    return {}


def get_user_store(username: str) -> dict[str, bytes]:
    all_stores = get_all_stores()
    if username not in all_stores:
        all_stores[username] = {}
    return all_stores[username]


# ---------------------------------------------------------------------------
# .run file loading
# ---------------------------------------------------------------------------

def parse_run(name: str, raw: bytes) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        st.warning(f"⚠️ Skipping **{name}**: {e}")
        return None


def sync_uploads(uploaded_files, username: str) -> None:
    store = get_user_store(username)
    for f in uploaded_files:
        if f.name not in store:
            store[f.name] = f.read()


def load_runs(username: str) -> list[dict]:
    runs = []
    for name, raw in get_user_store(username).items():
        data = parse_run(name, raw)
        if data is not None:
            runs.append(data)
    return runs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_win(run: dict) -> bool:
    return run.get("win", False)


def finished_act1(run: dict) -> bool:
    return len(run.get("map_point_history", [])) >= 2


def finished_act2(run: dict) -> bool:
    return len(run.get("map_point_history", [])) >= 3


def count_elites(run: dict) -> int:
    return sum(
        1
        for act in run.get("map_point_history", [])
        for point in act
        if point.get("map_point_type") == "elite"
    )


def count_rooms(run: dict) -> int:
    return sum(len(act) for act in run.get("map_point_history", []))


def get_picked_relics(run: dict) -> list[str]:
    """Return all relic IDs the player held during this run."""
    players = run.get("players", [])
    if not players:
        return []
    return [r["id"] for r in players[0].get("relics", []) if "id" in r]


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def show_win_rate(runs: list[dict]) -> None:
    total = len(runs)
    wins = sum(1 for r in runs if is_win(r))
    losses = total - wins
    rate = (wins / total * 100) if total > 0 else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total runs", total)
    col2.metric("Wins", wins)
    col3.metric("Losses", losses)
    st.progress(rate / 100)
    st.markdown(f"### Win rate: **{rate:.1f}%**")


def show_win_rate_after_act1(runs: list[dict]) -> None:
    qualifying = [r for r in runs if finished_act1(r)]
    skipped = len(runs) - len(qualifying)
    total = len(qualifying)

    if total == 0:
        st.warning("None of the uploaded runs made it past Act 1.")
        return

    wins = sum(1 for r in qualifying if is_win(r))
    losses = total - wins
    rate = (wins / total * 100) if total > 0 else 0.0

    if skipped > 0:
        st.caption(f"ℹ️ {skipped} run(s) excluded — did not finish Act 1.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Runs past Act 1", total)
    col2.metric("Wins", wins)
    col3.metric("Losses", losses)
    st.progress(rate / 100)
    st.markdown(f"### Win rate after Act 1: **{rate:.1f}%**")


def show_win_rate_after_act2(runs: list[dict]) -> None:
    qualifying = [r for r in runs if finished_act2(r)]
    skipped = len(runs) - len(qualifying)
    total = len(qualifying)

    if total == 0:
        st.warning("None of the uploaded runs made it past Act 2.")
        return

    wins = sum(1 for r in qualifying if is_win(r))
    losses = total - wins
    rate = (wins / total * 100) if total > 0 else 0.0

    if skipped > 0:
        st.caption(f"ℹ️ {skipped} run(s) excluded — did not finish Act 2.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Runs past Act 2", total)
    col2.metric("Wins", wins)
    col3.metric("Losses", losses)
    st.progress(rate / 100)
    st.markdown(f"### Win rate after Act 2: **{rate:.1f}%**")


def show_average_time(runs: list[dict]) -> None:
    times = [r["run_time"] for r in runs if "run_time" in r]
    if not times:
        st.warning("No run_time data found in the uploaded files.")
        return

    avg = sum(times) / len(times)
    col1, col2, col3 = st.columns(3)
    col1.metric("Runs with time data", len(times))
    col2.metric("Shortest", format_duration(min(times)))
    col3.metric("Longest", format_duration(max(times)))
    st.markdown(f"### Average time per run: **{format_duration(avg)}**")


def show_total_time(runs: list[dict]) -> None:
    times = [r["run_time"] for r in runs if "run_time" in r]
    if not times:
        st.warning("No run_time data found in the uploaded files.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Runs with time data", len(times))
    col2.metric("Total time", format_duration(sum(times)))
    st.markdown(f"### Total time spent: **{format_duration(sum(times))}**")


def show_total_time_truncated(runs: list[dict]) -> None:
    st.markdown("**Truncation thresholds**")
    col1, col2 = st.columns(2)
    win_cap_mins = col1.number_input("Max time for wins (minutes)", min_value=1, value=60)
    loss_cap_mins = col2.number_input("Max time for losses (minutes)", min_value=1, value=15)

    win_cap = win_cap_mins * 60
    loss_cap = loss_cap_mins * 60

    times = []
    for r in runs:
        if "run_time" not in r:
            continue
        cap = win_cap if is_win(r) else loss_cap
        times.append(min(r["run_time"], cap))

    if not times:
        st.warning("No run_time data found in the uploaded files.")
        return

    col1, col2 = st.columns(2)
    col1.metric("Runs with time data", len(times))
    col2.metric("Total time (truncated)", format_duration(sum(times)))
    st.markdown(f"### Total time (truncated): **{format_duration(sum(times))}**")


def show_elite_analysis(runs: list[dict]) -> None:
    """Win rate by elite count bracket + elite density per outcome."""
    wins_list = [r for r in runs if is_win(r)]
    loss_list = [r for r in runs if not is_win(r)]

    # ── Elite density ────────────────────────────────────────────────
    st.subheader("Elite density (elites ÷ total rooms)")

    def avg_density(run_list: list[dict]) -> float:
        densities = [count_elites(r) / count_rooms(r) for r in run_list if count_rooms(r) > 0]
        return sum(densities) / len(densities) if densities else 0.0

    col1, col2 = st.columns(2)
    col1.metric("Avg density — wins", f"{avg_density(wins_list):.1%}")
    col2.metric("Avg density — losses", f"{avg_density(loss_list):.1%}")

    st.divider()

    # ── Win rate by bracket ──────────────────────────────────────────
    st.subheader("Win rate by number of elites fought")

    sort_order = [str(i) for i in range(11)] + ["10+"]

    data = []
    for label in sort_order:
        bracket_runs = [r for r in runs if (
            (count_elites(r) == int(label)) if label != "10+" else (count_elites(r) > 10)
        )]
        if not bracket_runs:
            continue
        wins = sum(1 for r in bracket_runs if is_win(r))
        losses = len(bracket_runs) - wins
        data.append({"elites": label, "outcome": "Loss", "runs": losses})
        data.append({"elites": label, "outcome": "Win", "runs": wins})

    chart = (
        alt.Chart(alt.Data(values=data))
        .mark_bar()
        .encode(
            x=alt.X("elites:O", sort=sort_order, title="Elites fought"),
            y=alt.Y("runs:Q", title="Total runs"),
            color=alt.Color(
                "outcome:N",
                scale=alt.Scale(domain=["Loss", "Win"], range=["#a8c5da", "#1a5276"]),
                legend=alt.Legend(title="Outcome"),
            ),
            order=alt.Order("outcome:N", sort="ascending"),
            tooltip=["elites:O", "outcome:N", "runs:Q"],
        )
        .properties(width="container")
    )
    st.altair_chart(chart, use_container_width=True)


def get_chosen_relic_ids(run: dict) -> set[str]:
    """Relic IDs the player was offered as an explicit choice during the run."""
    chosen = set()
    for act in run.get("map_point_history", []):
        for point in act:
            for ps in point.get("player_stats", []):
                for rc in ps.get("relic_choices", []):
                    if "choice" in rc:
                        chosen.add(rc["choice"])
    return chosen


def get_starting_relic_ids(run: dict) -> set[str]:
    """Relics the player had that were never offered as a choice — true starting relics."""
    chosen = get_chosen_relic_ids(run)
    all_relics = {r["id"] for r in run.get("players", [{}])[0].get("relics", []) if "id" in r}
    return all_relics - chosen


def relic_id_to_slug(relic_id: str) -> str:
    return relic_id.replace("RELIC.", "").replace("_", "-").lower()


def relic_id_to_img_name(relic_id: str) -> str:
    return relic_id.replace("RELIC.", "").lower()


@st.cache_data(ttl=86400)
def fetch_relic_info(relic_id: str) -> dict:
    """Fetch relic effect text from spirewiki.com. Image URL is derived directly."""
    import re
    import urllib.request

    slug = relic_id_to_slug(relic_id)
    img_name = relic_id_to_img_name(relic_id)
    image_url = f"https://spirewiki.com/images/relics/{img_name}.png"
    page_url = f"https://spirewiki.com/relics/{slug}"

    try:
        req = urllib.request.Request(page_url, headers={"User-Agent": "STS2Analyser/1.0"})
        html = urllib.request.urlopen(req, timeout=5).read().decode()
        match = re.search(r'Effect\s*</[^>]+>\s*<[^>]+>\s*([^<]+)', html)
        effect = match.group(1).strip() if match else "No description available."
    except Exception:
        effect = "Could not load description."

    return {"image": image_url, "effect": effect}


def show_relic_analysis(runs: list[dict]) -> None:
    """Win rate per relic with wiki image/description on hover, persistent sort and filter."""
    import base64
    import json as _json
    from collections import defaultdict

    # ── Controls ─────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 1])
    ignore_starting = col1.toggle("Ignore starting relics", value=True)
    sort_col = col2.selectbox(
        "Sort by",
        ["Win Rate", "Runs", "Wins", "Losses", "Relic"],
        index=0,
        key="relic_sort_col",
    )
    sort_asc = col3.toggle("Ascending", value=False, key="relic_sort_asc")

    # ── Aggregate ────────────────────────────────────────────────────────
    relic_runs: dict[str, list[bool]] = defaultdict(list)
    for r in runs:
        won = is_win(r)
        starting = get_starting_relic_ids(r) if ignore_starting else set()
        for relic_id in get_picked_relics(r):
            if relic_id not in starting:
                relic_runs[relic_id].append(won)

    if not relic_runs:
        st.warning("No relic data found in the uploaded runs.")
        return

    with st.spinner("Fetching relic info from wiki..."):
        rows = []
        for relic_id, outcomes in relic_runs.items():
            total = len(outcomes)
            wins = sum(outcomes)
            info = fetch_relic_info(relic_id)
            rows.append({
                "name": relic_id.replace("RELIC.", "").replace("_", " ").title(),
                "total": total,
                "wins": wins,
                "losses": total - wins,
                "rate": wins / total,
                "rate_str": f"{wins / total:.1%}",
                "image": info["image"],
                "effect": info["effect"],
            })

    sort_key_map = {"Win Rate": "rate", "Runs": "total", "Wins": "wins", "Losses": "losses", "Relic": "name"}
    rows.sort(key=lambda x: x[sort_key_map[sort_col]], reverse=not sort_asc)

    # ── Build HTML ───────────────────────────────────────────────────────
    rows_html = ""
    for row in rows:
        tip_b64 = base64.b64encode(
            _json.dumps({"name": row["name"], "image": row["image"], "effect": row["effect"]}).encode()
        ).decode()
        rows_html += (
            f'''<tr class="rr" data-tip="{tip_b64}">'''
            f'''<td>{row["name"]}</td><td>{row["total"]}</td>'''
            f'''<td>{row["wins"]}</td><td>{row["losses"]}</td>'''
            f'''<td>{row["rate_str"]}</td></tr>'''
        )

    height = max(500, 80 + len(rows) * 42)

    html = f"""<!DOCTYPE html>
<html>
<head><style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0e1117; color: #fafafa; font-family: "Source Sans Pro", sans-serif; font-size: 14px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead tr {{ background: #262730; }}
    th {{
        padding: 10px 14px; text-align: left; font-weight: 600; color: #a0a0b0;
        font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
        border-bottom: 1px solid #3d3d4d;
    }}
    td {{ padding: 9px 14px; border-bottom: 1px solid #1e1e2e; }}
    .rr:hover {{ background: #1e2130; cursor: default; }}
    #tip {{
        display: none; position: fixed; background: #1e2130; color: #e0e0e0;
        border: 1px solid #3d3d5c; border-radius: 10px; padding: 14px;
        z-index: 9999; width: 240px; box-shadow: 0 6px 24px rgba(0,0,0,0.6); pointer-events: none;
    }}
    #tip img {{ width: 72px; height: 72px; object-fit: contain; display: block; margin: 0 auto 10px; }}
    #tip .tip-name {{ font-weight: 700; font-size: 14px; color: #fff; text-align: center; margin-bottom: 6px; }}
    #tip .tip-effect {{ font-size: 12px; line-height: 1.6; color: #9ab; }}
</style></head>
<body>
<div id="tip">
    <img id="tip-img" src="" onerror="this.style.display='none'">
    <div class="tip-name" id="tip-name"></div>
    <div class="tip-effect" id="tip-effect"></div>
</div>
<div style="margin-bottom:10px;display:flex;align-items:center;gap:8px;">
    <label style="color:#a0a0b0;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;">Show</label>
    <select id="page-size" style="background:#262730;color:#fafafa;border:1px solid #3d3d4d;border-radius:6px;padding:4px 8px;font-size:13px;cursor:pointer;">
        <option value="5">5</option>
        <option value="10">10</option>
        <option value="25">25</option>
        <option value="all">All</option>
    </select>
    <span id="row-count" style="color:#a0a0b0;font-size:12px;margin-left:4px;"></span>
</div>
<table id="tbl">
    <thead><tr>
        <th>Relic</th><th>Runs</th><th>Wins</th><th>Losses</th><th>Win Rate</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
</table>
<script>
    const tip = document.getElementById('tip');

    function applyPageSize() {{
        const val = document.getElementById('page-size').value;
        const limit = val === 'all' ? Infinity : parseInt(val);
        const rows = document.querySelectorAll('#tbl tbody tr');
        let shown = 0;
        rows.forEach(r => {{
            if (shown < limit) {{ r.style.display = ''; shown++; }}
            else {{ r.style.display = 'none'; }}
        }});
        document.getElementById('row-count').textContent =
            limit >= rows.length ? `${{rows.length}} relics` : `${{shown}} of ${{rows.length}} relics`;
    }}

    document.getElementById('page-size').addEventListener('change', applyPageSize);
    applyPageSize();

    document.querySelectorAll('.rr').forEach(row => {{
        row.addEventListener('mouseenter', () => {{
            const d = JSON.parse(atob(row.dataset.tip));
            document.getElementById('tip-img').src = d.image;
            document.getElementById('tip-img').style.display = 'block';
            document.getElementById('tip-name').textContent = d.name;
            document.getElementById('tip-effect').textContent = d.effect;
            tip.style.display = 'block';
        }});
        row.addEventListener('mousemove', e => {{
            tip.style.left = (e.clientX + 16) + 'px';
            tip.style.top  = (e.clientY + 16) + 'px';
        }});
        row.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; }});
    }});
</script>
</body></html>"""

    st.components.v1.html(html, height=height, scrolling=True)

# ---------------------------------------------------------------------------
# Metric registry
# ---------------------------------------------------------------------------

METRICS: dict[str, callable] = {
    "Win rate":                              show_win_rate,
    "Win rate after finishing Act 1":        show_win_rate_after_act1,
    "Win rate after finishing Act 2":        show_win_rate_after_act2,
    "Average time per run":                  show_average_time,
    "Total time spent on runs":              show_total_time,
    "Total time (truncated per outcome)":    show_total_time_truncated,
    "Elite analysis":                        show_elite_analysis,
    "Relic analysis":                        show_relic_analysis,
}


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="STS Run Analyser", page_icon="🗡️", layout="centered")
    st.title("🗡️ STS Run Analyser")

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Who are you?")
        username = st.text_input("Enter your name", placeholder="e.g. Ricardo").strip()

        if not username:
            st.info("Enter your name to get started.")
            st.stop()

        if username.strip().lower() == "zeperimo":
            st.markdown("""
            <style>
                [data-testid="stSidebar"] { display: none !important; }
                header, footer, [data-testid="stToolbar"],
                [data-testid="stDecoration"] { display: none !important; }
                .main .block-container { padding: 0 !important; max-width: 100% !important; }
            </style>
            """, unsafe_allow_html=True)
            _IMG = "data:image/jpeg;base64,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"
            st.components.v1.html(
            f'<html><body style="margin:0;padding:0;overflow:hidden;background:#000">'
            f'<img src="{_IMG}" style="position:fixed;top:0;left:0;width:100vw;height:100vh;object-fit:fill;">'
            f'</body></html>',
                height=10000,
            )
            st.stop()

        st.divider()
        st.header("Upload your .run files")
        uploaded = st.file_uploader(
            "Select one or more .run files",
            type="run",
            accept_multiple_files=True,
        )

        if uploaded:
            sync_uploads(uploaded, username)

        store = get_user_store(username)
        if store:
            st.success(f"{len(store)} file(s) loaded")
            with st.expander("Loaded files"):
                for name in store:
                    st.text(f"• {name}")
            if st.button("🗑️ Clear my files", use_container_width=True):
                store.clear()
                st.rerun()

    runs = load_runs(username)

    if not runs:
        st.info("👈 Upload your .run files using the sidebar to get started.")
        return

    st.divider()
    st.header("2. Choose a metric")
    metric_label = st.selectbox("What would you like to calculate?", list(METRICS.keys()))

    st.divider()
    st.header("3. Results")
    METRICS[metric_label](runs)


if __name__ == "__main__":
    main()
