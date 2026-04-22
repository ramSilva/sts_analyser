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
import re

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

    import pandas as _pd
    _df = _pd.DataFrame([{
        "Encounter": row["name"],
        "Times":     row["count"],
        "Avg Dmg":   round(row["avg_dmg"], 1),
        "Avg Turns": round(row["avg_turns"], 1),
        "Win Rate":  f"{row['win_rate']:.1%}",
        "Act":       row["acts"],
    } for row in enc_stats])

    _event = st.dataframe(
        _df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if _event.selection.rows:
        _row = enc_stats[_event.selection.rows[0]]
        st.query_params["enc_detail"] = _row["enc_id"]
        st.query_params["enc_type"]   = _row["enc_type"]
        st.rerun()

def show_boss_analysis(runs: list[dict]) -> None:
    """Boss encounter breakdown."""

    # ── Per-encounter table ──────────────────────────────────────────────
    st.divider()
    st.subheader("Boss encounter breakdown")

    enc_stats = get_boss_encounter_stats(runs)
    if not enc_stats:
        st.info("No boss encounter data found.")
        return

    import pandas as _pd
    _df = _pd.DataFrame([{
        "Encounter": row["name"],
        "Times":     row["count"],
        "Avg Dmg":   round(row["avg_dmg"], 1),
        "Avg Turns": round(row["avg_turns"], 1),
        "Win Rate":  f"{row['win_rate']:.1%}",
        "Act":       row["acts"],
    } for row in enc_stats])

    _event = st.dataframe(
        _df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if _event.selection.rows:
        _row = enc_stats[_event.selection.rows[0]]
        st.query_params["enc_detail"] = _row["enc_id"]
        st.query_params["enc_type"]   = _row["enc_type"]
        st.rerun()

def show_encounter_detail(enc_id: str, enc_type: str, runs: list[dict]) -> None:
    """Detailed breakdown for a single elite/boss encounter. Placeholder for now."""
    name = encounter_id_to_name(enc_id)
    if st.button("← Back"):
        del st.query_params["enc_detail"]
        del st.query_params["enc_type"]
        st.rerun()

    kind = enc_type.capitalize()
    st.header(f"{kind}: {name}")
    st.info("Detailed breakdown coming soon.")


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

    # ── Encounter detail page ────────────────────────────────────────
    enc_detail = st.query_params.get("enc_detail")
    enc_type   = st.query_params.get("enc_type", "elite")
    if enc_detail:
        show_encounter_detail(enc_detail, enc_type, runs)
        return

    st.divider()
    st.header("2. Choose a metric")
    metric_label = st.selectbox("What would you like to calculate?", list(METRICS.keys()))

    st.divider()
    st.header("3. Results")
    METRICS[metric_label](runs)


if __name__ == "__main__":
    main()
