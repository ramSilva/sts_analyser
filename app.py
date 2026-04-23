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
import os
import re

import altair as alt

import streamlit as st

_encounter_table = st.components.v1.declare_component(
    "encounter_table",
    path=os.path.join(os.path.dirname(__file__), "components/encounter_table"),
)


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

def get_character(run: dict) -> str:
    """Extract the character class from a run, trying known STS2 field names."""
    player = run.get("players", [{}])[0]
    return (
        player.get("char_type")
        or player.get("character")
        or run.get("character_id")
        or run.get("char_type")
        or "Unknown"
    )


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



_ENCOUNTER_SUFFIX = re.compile(r"_(ELITE|WEAK|STRONG|EASY|HARD|MEDIUM)$", re.IGNORECASE)


def encounter_id_to_name(enc_id: str) -> str:
    name = enc_id.replace("ENCOUNTER.", "")
    name = _ENCOUNTER_SUFFIX.sub("", name)
    return name.replace("_", " ").title()


def encounter_id_to_slug(enc_id: str) -> str:
    name = enc_id.replace("ENCOUNTER.", "")
    name = _ENCOUNTER_SUFFIX.sub("", name)
    return name.replace("_", "-").lower()


def encounter_id_to_img(enc_id: str) -> str:
    name = enc_id.replace("ENCOUNTER.", "")
    name = _ENCOUNTER_SUFFIX.sub("", name)
    return name.lower()


@st.cache_data(ttl=86400)
def fetch_encounter_info(enc_id: str) -> dict:
    """Fetch move names from spirewiki.com/monsters/."""
    import urllib.request as _ur
    slug = encounter_id_to_slug(enc_id)
    page_url = f"https://spirewiki.com/monsters/{slug}"
    try:
        req = _ur.Request(page_url, headers={"User-Agent": "STS2Analyser/1.0"})
        html = _ur.urlopen(req, timeout=5).read().decode()
        m = re.search(r"Moves\s*(.*?)(?:---|Data extracted)", html, re.DOTALL)
        if m:
            chunk = re.sub(r"<[^>]+>", " ", m.group(1))
            moves = re.sub(r"[:\s]+", " ", chunk).strip().strip(",").strip()
        else:
            moves = ""
    except Exception:
        moves = ""
    return {"moves": moves}


def get_elite_encounter_stats(runs: list[dict]) -> list[dict]:
    """Aggregate per-encounter stats across all runs."""
    from collections import defaultdict
    stats: dict = defaultdict(lambda: {"count": 0, "dmg": [], "turns": [], "wins": 0, "losses": 0, "acts": set()})

    for run in runs:
        won = is_win(run)
        counted_for_win: set[str] = set()
        for act_idx, act in enumerate(run.get("map_point_history", []), start=1):
            for point in act:
                if point.get("map_point_type") != "elite":
                    continue
                rooms = point.get("rooms", [])
                if not rooms:
                    continue
                enc_id = rooms[0].get("model_id", "")
                if not enc_id:
                    continue
                turns = rooms[0].get("turns_taken", 0)
                ps_list = point.get("player_stats", [])
                dmg = ps_list[0].get("damage_taken", 0) if ps_list else 0
                s = stats[enc_id]
                s["count"] += 1
                s["dmg"].append(dmg)
                s["turns"].append(turns)
                s["acts"].add(act_idx)
                if enc_id not in counted_for_win:
                    counted_for_win.add(enc_id)
                    if won:
                        s["wins"] += 1
                    else:
                        s["losses"] += 1

    result = []
    for enc_id, s in stats.items():
        total_runs = s["wins"] + s["losses"]
        result.append({
            "enc_id":    enc_id,
            "name":      encounter_id_to_name(enc_id),
            "count":     s["count"],
            "avg_dmg":   sum(s["dmg"]) / len(s["dmg"]) if s["dmg"] else 0,
            "avg_turns": sum(s["turns"]) / len(s["turns"]) if s["turns"] else 0,
            "win_rate":  s["wins"] / total_runs if total_runs else 0,
            "total_runs": total_runs,
            "acts":       ", ".join(str(a) for a in sorted(s["acts"])),
            "enc_type":   "elite",
        })

    return sorted(result, key=lambda x: x["count"], reverse=True)


def get_boss_encounter_stats(runs: list[dict]) -> list[dict]:
    """Aggregate per-boss stats across all runs."""
    from collections import defaultdict
    stats: dict = defaultdict(lambda: {"count": 0, "dmg": [], "turns": [], "wins": 0, "losses": 0, "acts": set()})

    for run in runs:
        won = is_win(run)
        counted_for_win: set[str] = set()
        for act_idx, act in enumerate(run.get("map_point_history", []), start=1):
            for point in act:
                if point.get("map_point_type") != "boss":
                    continue
                rooms = point.get("rooms", [])
                if not rooms:
                    continue
                enc_id = rooms[0].get("model_id", "")
                if not enc_id:
                    continue
                turns = rooms[0].get("turns_taken", 0)
                ps_list = point.get("player_stats", [])
                dmg = ps_list[0].get("damage_taken", 0) if ps_list else 0
                s = stats[enc_id]
                s["count"] += 1
                s["dmg"].append(dmg)
                s["turns"].append(turns)
                s["acts"].add(act_idx)
                if enc_id not in counted_for_win:
                    counted_for_win.add(enc_id)
                    if won:
                        s["wins"] += 1
                    else:
                        s["losses"] += 1

    result = []
    for enc_id, s in stats.items():
        total_runs = s["wins"] + s["losses"]
        result.append({
            "enc_id":     enc_id,
            "name":       encounter_id_to_name(enc_id),
            "count":      s["count"],
            "avg_dmg":    sum(s["dmg"]) / len(s["dmg"]) if s["dmg"] else 0,
            "avg_turns":  sum(s["turns"]) / len(s["turns"]) if s["turns"] else 0,
            "win_rate":   s["wins"] / total_runs if total_runs else 0,
            "total_runs": total_runs,
            "acts":       ", ".join(str(a) for a in sorted(s["acts"])),
            "enc_type":   "boss",
        })

    return sorted(result, key=lambda x: x["count"], reverse=True)

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



    # ── Per-encounter table ──────────────────────────────────────────────
    st.divider()
    st.subheader("Elite encounter breakdown")

    enc_stats = get_elite_encounter_stats(runs)
    if not enc_stats:
        st.info("No elite encounter data found.")
        return

    with st.spinner("Fetching elite info from wiki..."):
        enc_stats_data = []
        for row in enc_stats:
            info = fetch_encounter_info(row["enc_id"])
            enc_stats_data.append({
                "enc_id":    row["enc_id"],
                "enc_type":  row["enc_type"],
                "name":      row["name"],
                "count":     row["count"],
                "avg_dmg":   f"{row['avg_dmg']:.1f}",
                "avg_turns": f"{row['avg_turns']:.1f}",
                "win_rate":  f"{row['win_rate']:.1%}",
                "acts":      row["acts"],
                "moves":     info["moves"],
            })

    selected = _encounter_table(enc_stats=enc_stats_data, key="elite_table", default=None)
    if selected:
        st.query_params["enc_detail"] = selected["enc_id"]
        st.query_params["enc_type"]   = selected["enc_type"]
        st.rerun()


def get_chosen_relic_ids(run: dict) -> set[str]:
    """Relic IDs the player was offered as an explicit choice during the run."""
    chosen = set()
    for act_idx, act in enumerate(run.get("map_point_history", []), start=1):
        for point in act:
            ps_list = point.get("player_stats", [])
            ps = ps_list[0] if ps_list else {}
            for rc in ps.get("relic_choices", []):
                if "choice" in rc:
                    chosen.add(rc["choice"])
    return chosen


def get_relic_offer_stats(runs: list[dict]) -> dict[str, dict]:
    """For each relic, count how many times it was offered and how many times picked."""
    from collections import defaultdict
    offered: dict[str, int] = defaultdict(int)
    picked: dict[str, int] = defaultdict(int)
    for run in runs:
        for act in run.get("map_point_history", []):
            for point in act:
                ps_list = point.get("player_stats", [])
                ps = ps_list[0] if ps_list else {}
                for rc in ps.get("relic_choices", []):
                    relic_id = rc.get("choice")
                    if not relic_id:
                        continue
                    offered[relic_id] += 1
                    if rc.get("was_picked"):
                        picked[relic_id] += 1
    return {
        relic: {"offered": offered[relic], "picked": picked.get(relic, 0)}
        for relic in offered
    }


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
    """Win rate and pick rate per relic with wiki hover tooltip."""
    import base64
    import json as _json
    from collections import defaultdict

    ignore_starting = st.toggle("Ignore starting relics", value=True)

    offer_stats = get_relic_offer_stats(runs)

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
            stats = offer_stats.get(relic_id, {})
            n_offered = stats.get("offered", 0)
            n_picked  = stats.get("picked", 0)
            pick_rate = n_picked / n_offered if n_offered else None
            info = fetch_relic_info(relic_id)
            rows.append({
                "name":          relic_id.replace("RELIC.", "").replace("_", " ").title(),
                "total":         total,
                "wins":          wins,
                "losses":        total - wins,
                "rate":          wins / total,
                "rate_str":      f"{wins / total:.1%}",
                "offered":       n_offered,
                "pick_rate":     pick_rate if pick_rate is not None else -1,
                "pick_rate_str": f"{pick_rate:.1%}" if pick_rate is not None else "—",
                "n_offered":     n_offered,
                "n_picked":      n_picked,
                "image":         info["image"],
                "effect":        info["effect"],
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
            f''' data-wins="{row["wins"]}" data-losses="{row["losses"]}"'''
            f''' data-rate="{row["rate"]}" data-offered="{row["n_offered"]}"'''
            f''' data-picked="{row["n_picked"]}" data-pick_rate="{row["pick_rate"]}">'''
            f'''<td>{row["name"]}</td><td>{row["total"]}</td>'''
            f'''<td>{row["wins"]}</td><td>{row["losses"]}</td>'''
            f'''<td>{row["rate_str"]}</td>'''
            f'''<td>{row["n_offered"] or "—"}</td>'''
            f'''<td>{row["n_picked"] if row["n_offered"] else "—"}</td>'''
            f'''<td>{row["pick_rate_str"]}</td></tr>'''
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
        <th data-key="offered">Offered <span class="arrow">↕</span></th>
        <th data-key="picked">Picked <span class="arrow">↕</span></th>
        <th data-key="pick_rate">Pick Rate <span class="arrow">↕</span></th>
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
        document.getElementById('pg-info').textContent = `Page ${{currentPage}} of ${{totalPages}}`;
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
        currentPage = 1; applyPage();
    }});
    document.getElementById('btn-prev').addEventListener('click', () => {{
        currentPage--; applyPage();
    }});
    document.getElementById('btn-next').addEventListener('click', () => {{
        currentPage++; applyPage();
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

def show_boss_analysis(runs: list[dict]) -> None:
    """Boss encounter breakdown."""

    # ── Per-encounter table ──────────────────────────────────────────────
    st.divider()
    st.subheader("Elite encounter breakdown")

    enc_stats = get_boss_encounter_stats(runs)
    if not enc_stats:
        st.info("No boss encounter data found.")
        return

    with st.spinner("Fetching boss info from wiki..."):
        import base64 as _b64, json as _json
        rows_html = ""
        for row in enc_stats:
            info = fetch_encounter_info(row["enc_id"])
            tip_data = {"name": row["name"], "moves": info["moves"]}
            tip_b64 = _b64.b64encode(_json.dumps(tip_data).encode()).decode()
            rows_html += (
                f'''<tr class="rr" data-tip="{tip_b64}"'''
                f''' data-name="{row["name"]}" data-count="{row["count"]}"'''
                f''' data-avg_dmg="{row["avg_dmg"]:.1f}" data-avg_turns="{row["avg_turns"]:.1f}"'''
                f''' data-win_rate="{row["win_rate"]}" data-acts="{row["acts"]}" data-enc-id="{row["enc_id"]}" data-enc-type="{row["enc_type"]}">'''
                f'''<td>{row["name"]}</td>'''
                f'''<td>{row["count"]}</td>'''
                f'''<td>{row["avg_dmg"]:.1f}</td>'''
                f'''<td>{row["avg_turns"]:.1f}</td>'''
                f'''<td>{row["win_rate"]:.1%}</td>'''
                f'''<td>{row["acts"]}</td></tr>'''
            )

    height = max(400, 80 + len(enc_stats) * 42)
    html = f"""<!DOCTYPE html><html><head><style>
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:#0e1117; color:#fafafa; font-family:"Source Sans Pro",sans-serif; font-size:14px; }}
    table {{ width:100%; border-collapse:collapse; }}
    thead tr {{ background:#262730; }}
    th {{ padding:10px 14px; text-align:left; font-weight:600; color:#a0a0b0; font-size:12px;
          text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid #3d3d4d;
          cursor:pointer; user-select:none; white-space:nowrap; }}
    th:hover {{ color:#fff; }}
    th.sorted {{ color:#7eb8f7; }}
    th .arrow {{ margin-left:5px; opacity:0.5; }}
    th.sorted .arrow {{ opacity:1; }}
    td {{ padding:9px 14px; border-bottom:1px solid #1e1e2e; }}
    .rr:hover {{ background:#1e2130; cursor:pointer; }}
    #tip {{ display:none; position:fixed; background:#1e2130; color:#e0e0e0;
            border:1px solid #3d3d5c; border-radius:10px; padding:14px; z-index:9999;
            width:200px; box-shadow:0 6px 24px rgba(0,0,0,0.6); pointer-events:none; }}
    #tip .tip-name {{ font-weight:700; font-size:14px; color:#fff; text-align:center; margin-bottom:4px; }}
    #tip .tip-moves {{ font-size:12px; color:#9ab; line-height:1.5; }}
    </style></head><body>
    <div id="tip">
        <div class="tip-name" id="tip-name"></div>
        <div class="tip-moves" id="tip-moves"></div>
    </div>
    <table id="tbl">
        <thead><tr>
            <th data-key="name">Encounter <span class="arrow">↕</span></th>
            <th data-key="count">Times Encountered <span class="arrow">↕</span></th>
            <th data-key="avg_dmg">Avg Dmg Taken <span class="arrow">↕</span></th>
            <th data-key="avg_turns">Avg Turns <span class="arrow">↕</span></th>
            <th data-key="win_rate">Win Rate <span class="arrow">↕</span></th>
            <th data-key="acts">Act <span class="arrow">↕</span></th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    <script>
        const tip = document.getElementById('tip');
        let sortKey = 'count', sortAsc = false;

        function updateHeaderUI() {{
            document.querySelectorAll('th[data-key]').forEach(h => {{
                h.classList.remove('sorted');
                h.querySelector('.arrow').textContent = '↕';
            }});
            const a = document.querySelector(`th[data-key="${{sortKey}}"]`);
            if (a) {{ a.classList.add('sorted'); a.querySelector('.arrow').textContent = sortAsc ? '↑' : '↓'; }}
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
        }}

        sortTable();

        document.querySelectorAll('th[data-key]').forEach(th => {{
            th.addEventListener('click', () => {{
                sortAsc = th.dataset.key === sortKey ? !sortAsc : false;
                sortKey = th.dataset.key;
                sortTable();
            }});
        }});

        document.querySelectorAll('.rr').forEach(row => {{
            row.addEventListener('mouseenter', () => {{
                const d = JSON.parse(atob(row.dataset.tip));
                document.getElementById('tip-name').textContent = d.name;
                document.getElementById('tip-moves').textContent = d.moves ? 'Moves: ' + d.moves : '';
                tip.style.display = 'block';
            }});
            row.addEventListener('mousemove', e => {{
                tip.style.left = (e.clientX + 16) + 'px';
                tip.style.top  = (e.clientY + 16) + 'px';
            }});
            row.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; }});
            row.addEventListener('click', () => {{
                const url = new URL(window.parent.location.href);
                url.searchParams.set('enc_detail', row.dataset.encId);
                url.searchParams.set('enc_type', row.dataset.encType);
                window.parent.history.pushState({{}}, '', url.toString());
                window.parent.dispatchEvent(new PopStateEvent('popstate'));
            }});
        }});
    </script>
    </body></html>"""
    st.components.v1.html(html, height=height, scrolling=True)




def card_id_to_name(card_id: str) -> str:
    """Convert a card ID like 'CARD.STRIKE_RED' or 'STRIKE_RED_UPGRADED' to a readable name."""
    name = card_id.replace("CARD.", "")
    upgraded = name.endswith("_UPGRADED")
    name = name.replace("_UPGRADED", "")
    name = name.replace("_", " ").title()
    return f"{name} +" if upgraded else name


def get_deck_at_encounter(run: dict, target_enc_id: str) -> tuple[list[str], bool]:
    """
    Reconstruct the deck at the moment a specific encounter is reached.

    Walks map_point_history in chronological order. The player_stats for each
    room describe what happened AFTER that room (rewards, gains, removals), so
    we accumulate those changes only for rooms that come BEFORE the target
    encounter.  When we reach the target we stop — the Counter at that point
    is the deck the player had going into the fight.

    Card gains:    player_stats[0].cards_gained  — list of {"id": "CARD.X", ...}
    Card removals: player_stats[0].cards_removed — list of {"id": "CARD.X", ...}
    Starting deck: players[0].starting_deck      — list of {"id": "CARD.X", ...}
                   (seeded at the beginning if the field is present)
    """
    from collections import Counter

    player = run.get("players", [{}])[0]
    deck: Counter = Counter()

    # Seed with starting deck if the run records one
    for card in player.get("starting_deck", []):
        cid = (card.get("id") if isinstance(card, dict) else card) or ""
        if cid:
            deck[cid] += 1

    found = False
    for act in run.get("map_point_history", []):
        for point in act:
            rooms   = point.get("rooms", [])
            enc_id  = (rooms[0].get("model_id", "") if rooms else "")
            ps_list = point.get("player_stats", [])
            ps      = ps_list[0] if ps_list else {}

            if enc_id == target_enc_id:
                found = True
                break

            # Cards added to deck as reward/result of this room
            for card in ps.get("cards_gained", []):
                cid = (card.get("id") if isinstance(card, dict) else card) or ""
                if cid:
                    deck[cid] += 1

            # Cards removed/purged/transformed after this room
            for card in ps.get("cards_removed", []):
                cid = (card.get("id") if isinstance(card, dict) else card) or ""
                if cid and deck[cid] > 0:
                    deck[cid] -= 1

        if found:
            break

    return list(deck.elements()), found

def show_encounter_detail(enc_id: str, enc_type: str, runs: list[dict]) -> None:
    """Card win-rate breakdown for a single encounter."""
    from collections import defaultdict
    import pandas as _pd

    name = encounter_id_to_name(enc_id)
    if st.button("\u2190 Back"):
        del st.query_params["enc_detail"]
        del st.query_params["enc_type"]
        st.rerun()

    kind = enc_type.capitalize()
    st.header(f"{kind}: {name}")
    st.divider()
    st.subheader("Card win rate at this encounter")
    st.caption(
        "Win rate of each card that was in the deck when this encounter was reached. "
        "Cards picked up or removed before the fight are accounted for."
    )

    card_stats: dict[str, dict] = defaultdict(lambda: {"wins": 0, "total": 0})
    runs_found = 0

    for run in runs:
        deck, found = get_deck_at_encounter(run, enc_id)
        if not found:
            continue
        runs_found += 1
        won = is_win(run)
        for card_id in set(deck):          # count each card once per run
            card_stats[card_id]["total"] += 1
            if won:
                card_stats[card_id]["wins"] += 1

    if not card_stats:
        st.warning(
            f"No card data found across {runs_found} run(s) with this encounter. "
            "The run files may not contain card gain/removal tracking."
        )
        return

    st.caption(f"Across **{runs_found}** run(s) that included this encounter.")

    rows = []
    for card_id, s in card_stats.items():
        total = s["total"]
        wins  = s["wins"]
        rows.append({
            "Card":      card_id_to_name(card_id),
            "In Deck":   total,
            "Wins":      wins,
            "Losses":    total - wins,
            "Win Rate":  f"{wins / total:.1%}",
            "_rate":     wins / total,
        })

    rows.sort(key=lambda x: x["_rate"], reverse=True)

    st.dataframe(
        _pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]),
        use_container_width=True,
        hide_index=True,
    )


def show_general(runs: list[dict]) -> None:
    """Combined overview: all win rate and time metrics on one page."""
    show_win_rate(runs)
    st.divider()
    show_win_rate_after_act1(runs)
    st.divider()
    show_win_rate_after_act2(runs)
    st.divider()
    show_average_time(runs)
    st.divider()
    show_total_time(runs)
    st.divider()
    show_total_time_truncated(runs)


METRICS: dict[str, callable] = {
    "General":                                show_general,
    "Elite analysis":                        show_elite_analysis,
    "Boss analysis":                         show_boss_analysis,
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
        _saved = st.query_params.get("username", "")
        username = st.text_input("Enter your name", value=_saved, placeholder="e.g. Ricardo").strip()
        if username:
            st.query_params["username"] = username

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

    # ── Encounter detail page ────────────────────────────────────────
    enc_detail = st.query_params.get("enc_detail")
    enc_type   = st.query_params.get("enc_type", "elite")
    if enc_detail:
        show_encounter_detail(enc_detail, enc_type, runs)
        return

    characters = sorted({get_character(r) for r in runs})
    char_options = ["All"] + characters
    selected_char = st.selectbox("🧙 Character", char_options, index=0)
    if selected_char != "All":
        runs = [r for r in runs if get_character(r) == selected_char]

    st.divider()
    st.header("2. Choose a metric")
    metric_label = st.selectbox("What would you like to calculate?", list(METRICS.keys()))

    st.divider()
    st.header("3. Results")
    METRICS[metric_label](runs)


if __name__ == "__main__":
    main()
