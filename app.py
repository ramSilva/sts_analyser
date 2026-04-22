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
    """Win rate per relic with wiki image/description on hover and click-to-sort headers."""
    import base64
    import json as _json
    from collections import defaultdict

    ignore_starting = st.toggle("Ignore starting relics", value=True)

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

    rows.sort(key=lambda x: x["rate"], reverse=True)

    rows_html = ""
    for row in rows:
        tip_b64 = base64.b64encode(
            _json.dumps({"name": row["name"], "image": row["image"], "effect": row["effect"]}).encode()
        ).decode()
        rows_html += (
            f'''<tr class="rr" data-tip="{tip_b64}"'''
            f''' data-name="{row["name"]}" data-total="{row["total"]}"'''
            f''' data-wins="{row["wins"]}" data-losses="{row["losses"]}" data-rate="{row["rate"]}">'''
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
        padding: 10px 14px; text-align: left; font-weight: 600; color: #a0a0b0; font-size: 12px;
        text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #3d3d4d;
        cursor: pointer; user-select: none; white-space: nowrap;
    }}
    th:hover {{ color: #ffffff; }}
    th.sorted {{ color: #7eb8f7; }}
    th .arrow {{ margin-left: 5px; opacity: 0.5; }}
    th.sorted .arrow {{ opacity: 1; }}
    td {{ padding: 9px 14px; border-bottom: 1px solid #1e1e2e; }}
    .rr:hover {{ background: #1e2130; cursor: default; }}
    .controls {{ display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }}
    .controls label {{ color: #a0a0b0; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
    select {{
        background: #262730; color: #fafafa; border: 1px solid #3d3d4d;
        border-radius: 6px; padding: 4px 8px; font-size: 13px; cursor: pointer;
    }}
    .pagination {{ display: none; align-items: center; gap: 8px; margin-top: 10px; }}
    .pagination.visible {{ display: flex; }}
    .pg-btn {{
        background: #262730; color: #fafafa; border: 1px solid #3d3d4d;
        border-radius: 6px; padding: 4px 12px; font-size: 13px; cursor: pointer;
    }}
    .pg-btn:hover:not(:disabled) {{ background: #3d3d5c; }}
    .pg-btn:disabled {{ opacity: 0.35; cursor: default; }}
    .pg-info {{ color: #a0a0b0; font-size: 12px; }}
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
<div class="controls">
    <label>Show</label>
    <select id="page-size">
        <option value="5">5</option>
        <option value="10">10</option>
        <option value="25">25</option>
        <option value="all">All</option>
    </select>
    <span id="row-count" style="color:#a0a0b0;font-size:12px;"></span>
</div>
<table id="tbl">
    <thead><tr>
        <th data-key="name">Relic <span class="arrow">↕</span></th>
        <th data-key="total">Runs <span class="arrow">↕</span></th>
        <th data-key="wins">Wins <span class="arrow">↕</span></th>
        <th data-key="losses">Losses <span class="arrow">↕</span></th>
        <th data-key="rate">Win Rate <span class="arrow">↕</span></th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
</table>
<div class="pagination" id="pagination">
    <button class="pg-btn" id="btn-prev">← Prev</button>
    <span class="pg-info" id="pg-info"></span>
    <button class="pg-btn" id="btn-next">Next →</button>
</div>
<script>
    const tip = document.getElementById('tip');
    const SS_KEY = 'relic_sort_key';
    const SS_ASC = 'relic_sort_asc';
    let sortKey = sessionStorage.getItem(SS_KEY) || 'rate';
    let sortAsc  = sessionStorage.getItem(SS_ASC) === 'true';
    let currentPage = 1;

    function allRows() {{ return Array.from(document.querySelectorAll('#tbl tbody tr')); }}

    function applyPage() {{
        const val = document.getElementById('page-size').value;
        const rows = allRows();
        const total = rows.length;
        const pagination = document.getElementById('pagination');

        if (val === 'all') {{
            rows.forEach(r => r.style.display = '');
            document.getElementById('row-count').textContent = `${{total}} relics`;
            pagination.classList.remove('visible');
            return;
        }}

        const limit = parseInt(val);
        const totalPages = Math.ceil(total / limit);
        currentPage = Math.min(currentPage, totalPages);
        const from = (currentPage - 1) * limit;
        const to   = currentPage * limit;

        rows.forEach((r, i) => r.style.display = (i >= from && i < to) ? '' : 'none');
        document.getElementById('row-count').textContent =
            `${{Math.min(to, total) - from}} of ${{total}} relics`;
        document.getElementById('pg-info').textContent =
            `Page ${{currentPage}} of ${{totalPages}}`;
        document.getElementById('btn-prev').disabled = currentPage <= 1;
        document.getElementById('btn-next').disabled = currentPage >= totalPages;
        pagination.classList.add('visible');
    }}

    function updateHeaderUI() {{
        document.querySelectorAll('th[data-key]').forEach(h => {{
            h.classList.remove('sorted');
            h.querySelector('.arrow').textContent = '↕';
        }});
        const active = document.querySelector(`th[data-key="${{sortKey}}"]`);
        if (active) {{
            active.classList.add('sorted');
            active.querySelector('.arrow').textContent = sortAsc ? '↑' : '↓';
        }}
    }}

    function sortTable() {{
        const tbody = document.querySelector('#tbl tbody');
        Array.from(tbody.querySelectorAll('tr')).sort((a, b) => {{
            const av = a.dataset[sortKey], bv = b.dataset[sortKey];
            const an = parseFloat(av), bn = parseFloat(bv);
            const cmp = isNaN(an) ? av.localeCompare(bv) : an - bn;
            return sortAsc ? cmp : -cmp;
        }}).forEach(r => tbody.appendChild(r));
        updateHeaderUI();
        applyPage();
    }}

    sortTable();

    document.querySelectorAll('th[data-key]').forEach(th => {{
        th.addEventListener('click', () => {{
            sortAsc = th.dataset.key === sortKey ? !sortAsc : false;
            sortKey = th.dataset.key;
            currentPage = 1;
            sessionStorage.setItem(SS_KEY, sortKey);
            sessionStorage.setItem(SS_ASC, sortAsc);
            sortTable();
        }});
    }});

    document.getElementById('page-size').addEventListener('change', () => {{
        currentPage = 1;
        applyPage();
    }});

    document.getElementById('btn-prev').addEventListener('click', () => {{
        currentPage--;
        applyPage();
    }});

    document.getElementById('btn-next').addEventListener('click', () => {{
        currentPage++;
        applyPage();
    }});

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
