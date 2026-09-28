"""CH.04 BOSS FIGHT: THE JUDGE, played on a Game Boy.

The data mapping is still literal: one column per problem, one block per submission, green
when the judge accepted it and violet when it did not, with brightness picking the failure
apart. What changed is that the board is no longer a photograph of a finished stack. It is
the fight, replayed:

1. The cartridge boots with a SOBADANGO logo drop, the way every Game Boy did.
2. Every submission falls into its problem's column in the order it was actually sent. Each
   accepted one lands a hit on The Judge, whose HP bar drains to exactly the account's
   accepted-to-submitted ratio. Every rated contest in between fires a LEVEL UP and moves the
   rating along its real path.
3. The bottom row is full, because every problem on the board was attempted at least once,
   so it clears. That line clear is not staged; it is the board telling the truth.
4. One authored T piece is then played by hand: rotated with A, walked across with the d-pad,
   shown as a ghost where it will land, and hard-dropped. It is the only thing on the screen
   that is not a real submission, and it is there because a Tetris nobody plays is a chart.

**Selection.** A Game Boy well is ten columns wide. The ten *most recent* problems have one or
two submissions each, which is a board four rows deep in an eighteen-row well. The ten that
took the most attempts make a real stack. They are ordered by first attempt rather than by
height, because a sorted staircase reads as a bar chart and a jumbled one reads as Tetris.
"""

from __future__ import annotations

import collections
import math

from profilegen.svg import pixelfont as pf

from .. import fx, mascot, scene, tokens
from ..typography import fmt

COLS = 10
T = tokens.TETRIS_CYCLE

BOOT = (0.15, 1.1)       # logo drop
BOOT_END = 1.5
REPLAY = (1.7, 8.3)      # every submission lands inside this window
FALL = 0.24
FLASH_AT = 8.55
CLEAR_AT = 9.1
SHIFT_AT = 9.3
SPAWN_AT = 9.8
ACTION_DT = 0.26
FADE = (15.2, 15.8)

# T piece, as offsets from its rotation centre. Rotating (x, y) -> (-y, x) is a quarter turn
# clockwise on a y-down grid, which is exactly what CSS rotate(90deg) does.
T_CELLS = ((-1, 0), (0, 0), (1, 0), (0, 1))


def _verdict_key(verdict: str) -> str:
    return verdict if verdict in tokens.VERDICT_COLORS else "OTHER"


def _problem_key(submission: dict) -> str:
    problem = submission.get("problem") or {}
    return f"{problem.get('contestId')}{problem.get('index')}"


def _selected(submissions: list[dict], limit: int) -> list[str]:
    """The ``limit`` most-attempted problems, ordered by first attempt."""
    buckets: dict[str, int] = collections.Counter()
    first_seen: dict[str, int] = {}
    for submission in sorted(submissions, key=lambda row: row.get("creationTimeSeconds") or 0):
        key = _problem_key(submission)
        buckets[key] += 1
        first_seen.setdefault(key, submission.get("creationTimeSeconds") or 0)
    tallest = sorted(buckets, key=lambda key: (-buckets[key], first_seen[key]))[:limit]
    return sorted(tallest, key=lambda key: first_seen[key])


def columns_from(submissions: list[dict], limit: int) -> list[list[str]]:
    """Verdicts per selected problem, bottom-up in the order they were sent."""
    keys = _selected(submissions, limit)
    columns: dict[str, list[str]] = {key: [] for key in keys}
    for submission in sorted(submissions, key=lambda row: row.get("creationTimeSeconds") or 0):
        key = _problem_key(submission)
        if key in columns:
            columns[key].append(_verdict_key(str(submission.get("verdict") or "OTHER")))
    return [columns[key] for key in keys]


def first_try_accepts(columns: list[list[str]]) -> int:
    return sum(1 for column in columns if column and column[0] == "OK")


def replay_from(submissions: list[dict], limit: int, rows: int) -> tuple[list[str], list[dict]]:
    """Problem ids per column, and every block as a landing event in the order it was sent."""
    keys = _selected(submissions, limit)
    index = {key: col for col, key in enumerate(keys)}
    heights = [0] * len(keys)
    events: list[dict] = []
    for submission in sorted(submissions, key=lambda row: row.get("creationTimeSeconds") or 0):
        key = _problem_key(submission)
        if key not in index:
            continue
        col = index[key]
        if heights[col] >= rows:
            continue
        events.append({
            "col": col,
            "depth": heights[col],
            "verdict": _verdict_key(str(submission.get("verdict") or "OTHER")),
            "problem": key,
            "at": int(submission.get("creationTimeSeconds") or 0),
        })
        heights[col] += 1
    return keys, events


# --------------------------------------------------------------------------- the T piece


def _cells(rotation: int, cc: int, rr: int) -> list[tuple[int, int]]:
    cells = []
    for x, y in T_CELLS:
        for _ in range(rotation % 4):
            x, y = -y, x
        cells.append((cc + x, rr + y))
    return cells


def _free(cells: list[tuple[int, int]], heights: list[int], rows: int) -> bool:
    for col, row in cells:
        if not 0 <= col < len(heights) or row < 0 or row >= rows:
            return False
        if row >= rows - heights[col]:
            return False
    return True


def _landing(rotation: int, cc: int, rr: int, heights: list[int], rows: int) -> int:
    while _free(_cells(rotation, cc, rr + 1), heights, rows):
        rr += 1
    return rr


def _plan(heights: list[int], rows: int) -> dict:
    """Pick where the T goes: deepest landing that leaves the fewest holes, reachable in a
    straight line from the spawn point."""
    spawn = (0, 4, 1)
    best = None
    for rotation in range(4):
        for cc in range(len(heights)):
            if not _free(_cells(rotation, spawn[1], spawn[2]), heights, rows):
                continue
            step = 1 if cc >= spawn[1] else -1
            if not all(_free(_cells(rotation, c, spawn[2]), heights, rows)
                       for c in range(spawn[1], cc + step, step)):
                continue
            rr = _landing(rotation, cc, spawn[2], heights, rows)
            cells = _cells(rotation, cc, rr)
            occupied = set(cells)
            holes = 0
            for col, row in cells:
                below = row + 1
                if (col, below) in occupied:
                    continue
                if below < rows - heights[col]:
                    holes += 1
            depth = max(row for _c, row in cells)
            score = (holes, -depth, abs(cc - spawn[1]) + rotation)
            if best is None or score < best[0]:
                best = (score, rotation, cc, rr)
    if best is None:
        return {"rotation": 0, "col": spawn[1], "row": spawn[2], "spawn": spawn}
    _score, rotation, cc, rr = best
    return {"rotation": rotation, "col": cc, "row": rr, "spawn": spawn}


# --------------------------------------------------------------------------- drawing


def _block(ident: str, color: str, cell: float) -> str:
    """A bevelled block: lit top-left, shadowed bottom-right, flat face between."""
    light, base, dark = tokens.bevel(color)
    c, b = cell, max(2, round(cell / 5))
    return (
        f'<g id="{ident}">'
        f'<rect width="{fmt(c)}" height="{fmt(c)}" fill="{base}"/>'
        f'<path d="M0 0H{fmt(c)}L{fmt(c - b)} {b}H{b}V{fmt(c - b)}L0 {fmt(c)}Z" fill="{light}"/>'
        f'<path d="M{fmt(c)} 0V{fmt(c)}H0L{b} {fmt(c - b)}H{fmt(c - b)}V{b}Z" fill="{dark}"/>'
        "</g>"
    )


def _cross(cx: float, cy: float, arm: float, half: float) -> str:
    return (
        f"M{fmt(cx - half)} {fmt(cy - arm)}h{fmt(half * 2)}v{fmt(arm - half)}h{fmt(arm - half)}"
        f"v{fmt(half * 2)}h{fmt(-(arm - half))}v{fmt(arm - half)}h{fmt(-half * 2)}v{fmt(-(arm - half))}"
        f"h{fmt(-(arm - half))}v{fmt(-half * 2)}h{fmt(arm - half)}Z"
    )


def _dpad(s: scene.Scene, cx: float, cy: float, presses: dict[str, list[float]]) -> str:
    """Recessed well, raised cross, and an arm that lights while it is held."""
    parts = [
        f'<path d="{_cross(cx, cy, 30, 11)}" fill="{tokens.VOID}" stroke="{tokens.HAIRLINE}"/>',
        f'<path d="{_cross(cx, cy - 1, 26, 9)}" fill="{tokens.PANEL_HI}"/>',
        f'<circle cx="{fmt(cx)}" cy="{fmt(cy - 1)}" r="4" fill="{tokens.VOID}" opacity="0.55"/>',
    ]
    arms = {
        "left": f"M{fmt(cx - 26)} {fmt(cy - 10)}h15v18h-15z",
        "right": f"M{fmt(cx + 11)} {fmt(cy - 10)}h15v18h-15z",
        "down": f"M{fmt(cx - 9)} {fmt(cy + 9)}h18v15h-18z",
        "up": f"M{fmt(cx - 9)} {fmt(cy - 27)}h18v15h-18z",
    }
    for arm, times in presses.items():
        if not times:
            continue
        cls = fx.track(s.anim, fx.windows([(t, t + 0.14) for t in times], T))
        parts.append(f'<path class="{cls}" opacity="0" d="{arms[arm]}" fill="{tokens.ACID}"/>')
    return "".join(parts)


def _button(s: scene.Scene, cx: float, cy: float, label: str, presses: list[float]) -> str:
    parts = [
        f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="23" fill="{tokens.VOID}" stroke="{tokens.HAIRLINE}"/>',
    ]
    cap = (
        f'<circle cy="-1" r="19" fill="{tokens.VIOLET_DEEP}"/>'
        f'<circle cy="-2" r="16" fill="{tokens.VIOLET}" opacity="0.55"/>'
    )
    if presses:
        points: list[tuple[float, dict]] = [(0.0, {"transform": "scale(1)"})]
        for t in presses:
            points += [(t, {"transform": "scale(0.84)"}), (t + 0.14, {"transform": "scale(1)"})]
        cls = fx.track(s.anim, fx.steps(points, T))
        glow = fx.track(s.anim, fx.windows([(t, t + 0.14) for t in presses], T))
        cap += f'<circle class="{glow}" opacity="0" cy="-2" r="16" fill="{tokens.HOT_VIOLET}"/>'
        parts.append(fx.place(cx, cy, cls, cap))
    else:
        parts.append(fx.place(cx, cy, None, cap))
    parts.append(pf.render_path(label, cx - pf.measure(label, scale=2)[0] / 2, cy + 28, scale=2, fill=tokens.DIM))
    return "".join(parts)


def _gavel(x: float, y: float, color: str) -> str:
    """The Judge, as the one object that has only ever said no to me."""
    return (
        f'<g transform="translate({fmt(x)} {fmt(y)}) rotate(-30)">'
        f'<rect x="-9" y="-6" width="18" height="10" fill="{color}"/>'
        f'<rect x="-11" y="-7" width="3" height="12" fill="{color}"/>'
        f'<rect x="8" y="-7" width="3" height="12" fill="{color}"/>'
        f'<rect x="-2" y="4" width="4" height="15" fill="{color}"/></g>'
    )


def _states(s: scene.Scene, spans_by_text: list[tuple[str, list[tuple[float, float]]]], render,
            resting: int) -> str:
    """Several readouts in one slot, each shown during its spans. ``resting`` is the one the
    static frame keeps."""
    parts = []
    for index, (text, spans) in enumerate(spans_by_text):
        spans = [(a, b) for a, b in spans if b - a > 0.02]
        if not spans:
            continue
        cls = fx.track(s.anim, fx.windows(spans, T))
        if cls is None and index != resting:
            continue
        parts.append(fx.wrap(cls, render(text), hidden=index != resting))
    return "".join(parts)


def build(data: dict, *, width: int = tokens.WIDE) -> str:
    s = scene.Scene(width, T, prefix="t")
    narrow = s.narrow
    submissions = data.get("codeforces_submissions") or []
    stats = data.get("codeforces") or {}
    profile = data.get("codeforces_profile") or {}

    cell = 18 if narrow else 15
    rows = 14 if narrow else 18
    keys, events = replay_from(submissions, COLS, rows)
    cols = max(1, len(keys))
    well_w, well_h = COLS * cell, rows * cell
    screen_pad = 12 if narrow else 16
    hud_w = 0 if narrow else 196
    gap = 0 if narrow else 18
    screen_w = well_w + gap + hud_w + screen_pad * 2
    screen_h = well_h + screen_pad * 2
    top = 84 if narrow else 92
    screen_x = (width - screen_w) / 2
    screen_y = top
    well_x, well_y = screen_x + screen_pad, screen_y + screen_pad
    body = s.body

    total = int(stats.get("total") or 0)
    accepted = int(stats.get("accepted") or 0)
    hp_final = 1 - accepted / total if total else 1.0
    contests = list(profile.get("contests") or [])
    rating = int(profile.get("rating") or 0)
    rank = str(profile.get("rank") or "").upper()

    # --- when things happen ------------------------------------------------------------
    n = len(events)
    dt = (REPLAY[1] - REPLAY[0]) / max(1, n)
    for k, event in enumerate(events):
        event["t"] = REPLAY[0] + (k + 1) * dt
    ok_times = [event["t"] for event in events if event["verdict"] == "OK"]
    level_times: list[float] = []
    for contest in contests:
        later = [event["t"] for event in events if event["at"] >= contest.get("at", 0)]
        level_times.append(later[0] - dt / 2 if later else REPLAY[1])
    # Contests that happened after the last block on the board fire in sequence once the
    # replay ends, far enough apart to read each one.
    spaced: list[float] = []
    for at in level_times:
        at = max(REPLAY[0] + 0.1, at)
        if spaced:
            at = max(at, spaced[-1] + 0.8)
        spaced.append(min(at, FADE[0] - 1.0))
    level_times = spaced

    heights = [0] * COLS
    for event in events:
        heights[event["col"]] = max(heights[event["col"]], event["depth"] + 1)
    bottom_full = all(h > 0 for h in heights[:COLS]) and len(keys) >= COLS
    after = [max(0, h - 1) for h in heights] if bottom_full else list(heights)
    plan = _plan(after, rows)
    rot_target = plan["rotation"]
    col_target = plan["col"]
    _r0, spawn_col, spawn_row = plan["spawn"]
    actions: list[tuple[float, str]] = []
    t = SPAWN_AT + 0.35
    rotation_steps = rot_target if rot_target <= 2 else 1
    rotate_dir = 1 if rot_target <= 2 else -1
    for _ in range(rotation_steps):
        actions.append((t, "rotate"))
        t += ACTION_DT
    step = 1 if col_target > spawn_col else -1
    for _ in range(abs(col_target - spawn_col)):
        actions.append((t, "right" if step > 0 else "left"))
        t += ACTION_DT
    drop_at = t + 0.35
    lock_at = drop_at + 0.06

    # --- the shell -----------------------------------------------------------------------
    if not narrow:
        shell_x, shell_w = s.pad + 4, width - 2 * (s.pad + 4)
        shell_y = top - 20
        shell_h = screen_h + 100
        body.append(
            f'<rect x="{fmt(shell_x)}" y="{fmt(shell_y)}" width="{fmt(shell_w)}" height="{fmt(shell_h)}" rx="22"'
            f' fill="{tokens.PANEL}" stroke="{tokens.HAIRLINE}"/>'
            f'<rect x="{fmt(shell_x + 8)}" y="{fmt(shell_y + 8)}" width="{fmt(shell_w - 16)}" height="3" rx="1.5"'
            f' fill="{tokens.VIOLET}" opacity="0.25"/>'
        )
        presses = {"left": [], "right": [], "down": [drop_at - 0.1], "up": []}
        a_presses = []
        for at, kind in actions:
            if kind == "rotate":
                a_presses.append(at)
            else:
                presses[kind].append(at)
        body.append(
            f'<circle cx="{fmt(shell_x + 30)}" cy="{fmt(screen_y + 14)}" r="4.5" fill="{tokens.ACID}"/>'
            f'<circle cx="{fmt(shell_x + 30)}" cy="{fmt(screen_y + 14)}" r="9" fill="{tokens.ACID}" opacity="0.18"/>'
            + pf.render_path("POWER", shell_x + 44, screen_y + 10, scale=2, fill=tokens.DIM)
        )
        body.append(_dpad(s, shell_x + 96, screen_y + 130, presses))
        body.append(_button(s, width - shell_x - 140, screen_y + 160, "B", []))
        body.append(_button(s, width - shell_x - 76, screen_y + 124, "A", a_presses))
        for index in range(6):
            ox = width - shell_x - 150 + index * 12
            body.append(f'<rect x="{fmt(ox)}" y="{fmt(screen_y + 236)}" width="6" height="44" rx="3" fill="{tokens.VOID}"'
                        f' stroke="{tokens.HAIRLINE}" transform="rotate(-22 {fmt(ox)} {fmt(screen_y + 236)})"/>')
        for label, ox in (("SELECT", shell_x + 58), ("START", shell_x + 150)):
            oy = screen_y + 232
            body.append(
                f'<rect x="{fmt(ox - 22)}" y="{fmt(oy - 5)}" width="44" height="10" rx="5" fill="{tokens.PANEL_HI}"'
                f' stroke="{tokens.HAIRLINE}" transform="rotate(-18 {fmt(ox)} {fmt(oy)})"/>'
                + pf.render_path(label, ox - pf.measure(label, scale=2)[0] / 2, oy + 16, scale=2, fill=tokens.DIM)
            )
        tag = "DOT MATRIX WITH EMOTIONAL DAMAGE"
        body.append(pf.render_path(tag, (width - pf.measure(tag, scale=2)[0]) / 2, screen_y + screen_h + 22,
                                   scale=2, fill=tokens.DIM))
        # Bit rides the top corner of the shell and reacts to the fight.
        px = 3
        bx = width - shell_x - 122
        by = screen_y + 6
        body.append(mascot.bit(s.anim, T, bx, by, px, jumps=[CLEAR_AT + 0.05, lock_at + 0.1],
                               cheer=[(lock_at + 0.1, lock_at + 1.4)], point=[(4.0, 5.4)],
                               blinks=[2.5, 6.9, 12.6], bob=0.5))
        bubble = fx.track(s.anim, fx.pop_frames([CLEAR_AT + 0.1, lock_at + 0.15], T, rise=10, life=1.1),
                          base={"opacity": "0"})
        body.append(fx.place(bx + 50, by + 6, bubble,
                             pf.render_path("NICE!", 0, 0, scale=2, fill=tokens.ACID)))
    else:
        body.append(
            f'<rect x="{fmt(screen_x - 10)}" y="{fmt(screen_y - 10)}" width="{fmt(screen_w + 20)}"'
            f' height="{fmt(screen_h + 20)}" rx="12" fill="{tokens.PANEL}" stroke="{tokens.HAIRLINE}"/>'
        )

    body.append(
        f'<rect x="{fmt(screen_x - 6)}" y="{fmt(screen_y - 6)}" width="{fmt(screen_w + 12)}"'
        f' height="{fmt(screen_h + 12)}" rx="8" fill="{tokens.PANEL_HI}"/>'
        f'<rect x="{fmt(screen_x)}" y="{fmt(screen_y)}" width="{fmt(screen_w)}" height="{fmt(screen_h)}"'
        f' rx="4" fill="{tokens.GB[0]}"/>'
    )

    # --- the well ------------------------------------------------------------------------
    grid = "".join(
        f"M{fmt(well_x + c * cell)} {fmt(well_y + r * cell)}h{fmt(cell - 1)}v{fmt(cell - 1)}h{fmt(1 - cell)}z"
        for c in range(COLS) for r in range(rows)
    )
    board: list[str] = [f'<path d="{grid}" fill="{tokens.GB[1]}" opacity="0.22"/>']

    used = {event["verdict"] for event in events} | {"OK"}
    for verdict in sorted(used):
        s.defs.append(_block(f"tb{verdict}", tokens.VERDICT_COLORS[verdict], cell))

    bottom_row: list[str] = []
    upper: list[str] = []
    for event in events:
        x = well_x + event["col"] * cell
        y = well_y + well_h - (event["depth"] + 1) * cell
        dist = (rows - event["depth"]) * cell
        land = event["t"]
        cls = fx.track(
            s.anim,
            fx.steps(
                [
                    (0.0, {"transform": f"translate(0px,{fmt(-dist)}px)", "opacity": "0"}),
                    (land - FALL - fx.HOLD, {"transform": f"translate(0px,{fmt(-dist)}px)", "opacity": "0"}),
                    (land - FALL, {"transform": f"translate(0px,{fmt(-dist)}px)", "opacity": "1"}),
                    (land, {"transform": "translate(0px,0px)", "opacity": "1"}),
                    (T - fx.HOLD, {"transform": "translate(0px,0px)", "opacity": "1"}),
                ],
                T,
            ),
            easing="cubic-bezier(0.55,0,1,0.45)",
        )
        block = fx.wrap(cls, f'<use href="#tb{event["verdict"]}" x="{fmt(x)}" y="{fmt(y)}"/>')
        (bottom_row if event["depth"] == 0 and bottom_full else upper).append(block)

    if bottom_full:
        flash = fx.track(
            s.anim,
            fx.steps([(0.0, {"opacity": "1"}), (FLASH_AT, {"opacity": "0.15"}), (FLASH_AT + 0.14, {"opacity": "1"}),
                      (FLASH_AT + 0.28, {"opacity": "0.15"}), (FLASH_AT + 0.42, {"opacity": "1"}),
                      (CLEAR_AT, {"opacity": "0"})], T),
        )
        shift = fx.track(
            s.anim,
            fx.steps([(0.0, {"transform": "translate(0px,0px)"}), (SHIFT_AT, {"transform": "translate(0px,0px)"}),
                      (SHIFT_AT + 0.12, {"transform": f"translate(0px,{fmt(cell)}px)"}),
                      (T - fx.HOLD, {"transform": f"translate(0px,{fmt(cell)}px)"})], T),
            easing="linear",
        )
        white = fx.track(s.anim, fx.windows([(FLASH_AT + 0.42, CLEAR_AT)], T))
        board.append(fx.wrap(flash, "".join(bottom_row)))
        board.append(f'<rect class="{white}" opacity="0" x="{fmt(well_x)}" y="{fmt(well_y + well_h - cell)}"'
                     f' width="{fmt(well_w)}" height="{fmt(cell)}" fill="#FFFFFF"/>')
        board.append(fx.wrap(shift, "".join(upper)))
        for k in range(4):
            board.append(fx.burst(s.anim, well_x + well_w * (k + 0.5) / 4, well_y + well_h - cell / 2, [CLEAR_AT], T,
                                  count=7, radius=40, size=4, seed=40 + k, life=0.6))
    else:
        board.append("".join(upper))

    # Accepted pops over the column that just took the hit.
    for event in events:
        if event["verdict"] != "OK":
            continue
        cls = fx.track(s.anim, fx.pop_frames([event["t"]], T, rise=18, life=0.7), base={"opacity": "0"})
        x = well_x + event["col"] * cell + cell / 2
        y = well_y + well_h - (event["depth"] + 1) * cell - 10
        label = "AC"
        lw = pf.measure(label, scale=2)[0]
        board.append(fx.place(x - lw / 2, y, cls,
                              f'<rect x="-2" y="-2" width="{fmt(lw + 4)}" height="18" fill="{tokens.GB[0]}"/>'
                              + pf.render_path(label, 0, 0, scale=2, fill=tokens.ACID_BRIGHT)))

    # --- the hand-played T ----------------------------------------------------------------
    def center(col: int, row: int) -> tuple[float, float]:
        return well_x + col * cell + cell / 2, well_y + row * cell + cell / 2

    state_rot, state_col, state_row = 0, spawn_col, spawn_row
    piece_points: list[tuple[float, dict]] = []
    ghost_points: list[tuple[float, dict]] = []
    sx0, sy0 = center(spawn_col, spawn_row)

    def record(at: float, rot: int, col: int, row: int, *, visible: bool = True) -> None:
        cx, cy = center(col, row)
        gy = center(col, _landing(rot % 4, col, row, after, rows))[1]
        transform = f"translate({fmt(cx - sx0)}px,{fmt(cy - sy0)}px) rotate({rot * 90}deg)"
        ghost = f"translate({fmt(cx - sx0)}px,{fmt(gy - sy0)}px) rotate({rot * 90}deg)"
        piece_points.append((at, {"transform": transform, "opacity": "1" if visible else "0"}))
        ghost_points.append((at, {"transform": ghost, "opacity": "0.9" if visible else "0"}))

    record(0.0, 0, spawn_col, spawn_row, visible=False)
    record(SPAWN_AT - fx.HOLD, 0, spawn_col, spawn_row, visible=False)
    record(SPAWN_AT, 0, spawn_col, spawn_row)
    for at, kind in actions:
        if kind == "rotate":
            state_rot += rotate_dir
        else:
            state_col += 1 if kind == "right" else -1
        record(at, state_rot, state_col, state_row)
    final_row = _landing(state_rot % 4, state_col, state_row, after, rows)
    fx_, fy_ = center(state_col, final_row)
    locked = f"translate({fmt(fx_ - sx0)}px,{fmt(fy_ - sy0)}px) rotate({state_rot * 90}deg)"
    piece_points.append((drop_at, {"transform": locked, "opacity": "1"}))
    piece_points.append((FADE[1], {"transform": locked, "opacity": "1"}))
    piece_points.append((FADE[1] + fx.HOLD, {"transform": locked, "opacity": "0"}))
    ghost_points.append((drop_at, {"transform": locked, "opacity": "0"}))
    piece_cls = fx.track(s.anim, fx.steps(piece_points, T))
    ghost_cls = fx.track(s.anim, fx.steps(ghost_points, T))
    cells_markup = "".join(
        f'<use href="#tbOK" x="{fmt(x * cell - cell / 2)}" y="{fmt(y * cell - cell / 2)}"/>' for x, y in T_CELLS
    )
    ghost_markup = "".join(
        f'<rect x="{fmt(x * cell - cell / 2 + 1.5)}" y="{fmt(y * cell - cell / 2 + 1.5)}" width="{fmt(cell - 3)}"'
        f' height="{fmt(cell - 3)}" fill="none" stroke="{tokens.ACID}" stroke-width="1.5" stroke-dasharray="3 2"/>'
        for x, y in T_CELLS
    )
    board.append(fx.place(sx0, sy0, ghost_cls, ghost_markup, hidden=True))
    # Hard-drop trail: a streak from where the piece was to where it lands.
    trail_top = center(state_col, state_row)[1] - cell
    trail_h = fy_ - trail_top + cell / 2
    trail_cls = fx.track(
        s.anim,
        fx.steps([(0.0, {"opacity": "0"}), (drop_at - fx.HOLD, {"opacity": "0"}), (drop_at, {"opacity": "0.8"}),
                  (drop_at + 0.35, {"opacity": "0"})], T),
        easing="ease-out",
        base={"opacity": "0"},
    )
    trail_grad = s.ids.next()
    s.defs.append(
        f'<linearGradient id="{trail_grad}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{tokens.ACID}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{tokens.ACID_BRIGHT}" stop-opacity="0.9"/></linearGradient>'
    )
    occupied_cols = sorted({c for c, _r in _cells(state_rot % 4, state_col, final_row)})
    trail_x = well_x + occupied_cols[0] * cell
    trail_w = (occupied_cols[-1] - occupied_cols[0] + 1) * cell
    board.append(f'<rect class="{trail_cls}" opacity="0" x="{fmt(trail_x)}" y="{fmt(trail_top)}" width="{fmt(trail_w)}"'
                 f' height="{fmt(max(1, trail_h))}" fill="url(#{trail_grad})"/>')
    board.append(fx.place(sx0, sy0, piece_cls, cells_markup, hidden=True))
    board.append(fx.burst(s.anim, fx_, fy_ + cell, [lock_at], T, count=10, radius=34, size=3, seed=77, life=0.5))

    # Big banner messages in the middle of the well.
    def banner(text: str, at: float, until: float, color: str) -> str:
        cls = fx.track(s.anim, fx.stamp_frames(at, until, T), base={"opacity": "0"})
        tw, th = pf.measure(text, scale=2)
        cx, cy = well_x + well_w / 2, well_y + well_h * 0.38
        return fx.place(cx, cy, cls,
                        f'<rect x="{fmt(-tw / 2 - 6)}" y="{fmt(-th / 2 - 6)}" width="{fmt(tw + 12)}" height="{fmt(th + 12)}"'
                        f' fill="{tokens.GB[0]}" stroke="{color}" stroke-width="2"/>'
                        + pf.render_path(text, -tw / 2, -th / 2, scale=2, fill=color))

    if bottom_full:
        board.append(banner("LINE CLEAR!", CLEAR_AT, CLEAR_AT + 0.9, tokens.ACID))
    board.append(banner("ACCEPTED!", lock_at + 0.05, lock_at + 1.3, tokens.ACID))
    hp_pct = round(hp_final * 100)
    board.append(banner(f"JUDGE {hp_pct}%", lock_at + 1.7, FADE[0] - 0.2, tokens.VIOLET_BRIGHT))

    clip = s.ids.next()
    s.defs.append(f'<clipPath id="{clip}"><rect x="{fmt(well_x)}" y="{fmt(well_y)}" width="{fmt(well_w)}"'
                  f' height="{fmt(well_h)}"/></clipPath>')
    screen_parts = [f'<g clip-path="url(#{clip})">{"".join(board)}</g>']

    # --- HUD -----------------------------------------------------------------------------
    hp_points: list[tuple[float, dict]] = [(0.0, {"transform": "scale(1,1)"})]
    drain = (1 - hp_final) / max(1, len(ok_times))
    for k, at in enumerate(ok_times):
        hp_points.append((at, {"transform": f"scale({fmt(max(0.001, 1 - drain * (k + 1)))},1)"}))
    hp_points.append((FADE[1], {"transform": "scale(1,1)"}))
    hp_cls = fx.track(s.anim, fx.steps(hp_points, T), base={"transform": f"scale({fmt(max(0.001, hp_final))},1)"})
    judge_hit = fx.jitter(s.anim, ok_times, T, amp=3, seed=51) if ok_times else None

    rating_path = [0] + [int(c.get("new") or 0) for c in contests]
    spans: list[tuple[str, list[tuple[float, float]]]] = []
    starts = [0.0] + level_times
    for j, value in enumerate(rating_path):
        start = starts[j]
        end = starts[j + 1] if j + 1 < len(starts) else FADE[1]
        spans.append((f"{value:04d}", [(start, end)]))
    if rating and not contests:
        spans = [(f"{rating:04d}", [(0.0, T)])]
    level_up = fx.track(s.anim, fx.windows([(t, t + 0.7) for t in level_times], T)) if level_times else None
    level_blink = fx.track(s.anim, fx.blink_frames(0, T, 0.18, T, low="0.2")) if level_times else None

    # NEXT: the problem whose block is falling next, straight from the replay order.
    next_spans: dict[str, list[tuple[float, float]]] = collections.defaultdict(list)
    for k, event in enumerate(events):
        start = event["t"] - FALL - dt if k else BOOT_END
        end = event["t"] - FALL
        next_spans[event["problem"]].append((start, end))
    first_problem = events[0]["problem"] if events else ""

    def hud_block(hx: float, hy: float) -> str:
        parts = [pf.render_path("THE JUDGE", hx, hy, scale=2, fill=tokens.GB[3])]
        parts.append(fx.place(hx + 170, hy + 8, judge_hit, _gavel(0, 0, tokens.VIOLET_BRIGHT)))
        bar_y = hy + 20
        parts.append(pf.render_path("HP", hx, bar_y, scale=2, fill=tokens.GB[2]))
        bar_x, bar_w = hx + 28, 124
        parts.append(f'<rect x="{fmt(bar_x)}" y="{fmt(bar_y)}" width="{bar_w}" height="14" fill="none" stroke="{tokens.GB[2]}"/>')
        parts.append(fx.place(bar_x + 2, bar_y + 2, hp_cls,
                              f'<rect width="{bar_w - 4}" height="10" fill="{tokens.VIOLET}"/>'
                              f'<rect width="{bar_w - 4}" height="3" fill="{tokens.VIOLET_BRIGHT}"/>'))
        return "".join(parts)

    def rating_block(hx: float, hy: float, scale: int) -> str:
        parts = [pf.render_path("RATING", hx, hy, scale=2, fill=tokens.GB[2])]
        resting = len(spans) - 1
        parts.append(_states(s, spans, lambda text: pf.render_path(text, hx, hy + 16, scale=scale, fill=tokens.ACID),
                             resting))
        level_spans = [(f"LV {j:02d} {rank}".strip(), sp) for j, (_t, sp) in enumerate(spans)]
        if rating and not contests:
            level_spans = [(rank or "RATED", [(0.0, T)])]
        parts.append(_states(s, level_spans,
                             lambda text: pf.render_path(text, hx, hy + 22 + 7 * scale, scale=2, fill=tokens.GB[3]),
                             len(level_spans) - 1))
        if level_up:
            parts.append(
                fx.wrap(level_up,
                        fx.wrap(level_blink, pf.render_path("LEVEL UP!", hx + (80 if scale > 3 else 64), hy, scale=2,
                                                            fill=tokens.HOT_VIOLET)),
                        hidden=True)
            )
        return "".join(parts)

    def next_block(hx: float, hy: float, w: float) -> str:
        parts = [pf.render_path("NEXT", hx, hy, scale=2, fill=tokens.GB[2])]
        box_y = hy + 18
        parts.append(f'<rect x="{fmt(hx)}" y="{fmt(box_y)}" width="{fmt(w)}" height="34" fill="none" stroke="{tokens.GB[2]}"/>')
        for problem in keys:
            spans_p = next_spans.get(problem)
            if not spans_p:
                continue
            cls = fx.track(s.anim, fx.windows(spans_p, T))
            tw = pf.measure(problem, scale=2)[0]
            parts.append(fx.wrap(cls, pf.render_path(problem, hx + (w - tw) / 2, box_y + 10, scale=2,
                                                     fill=tokens.ACID_BRIGHT), hidden=problem != first_problem))
        mini = cell * 0.5
        piece = "".join(
            f'<rect x="{fmt(hx + w / 2 + x * mini - mini / 2)}" y="{fmt(box_y + 12 + y * mini)}" width="{fmt(mini - 1)}"'
            f' height="{fmt(mini - 1)}" fill="{tokens.ACID}"/>'
            for x, y in T_CELLS
        )
        cls = fx.track(s.anim, fx.windows([(REPLAY[1], SPAWN_AT)], T))
        parts.append(fx.wrap(cls, piece, hidden=True))
        return "".join(parts)

    if not narrow:
        hx = well_x + well_w + gap
        hy = well_y + 6
        screen_parts.append(hud_block(hx, hy))
        screen_parts.append(f'<rect x="{fmt(hx)}" y="{fmt(hy + 44)}" width="{hud_w - 12}" height="1" fill="{tokens.GB[1]}"/>')
        screen_parts.append(rating_block(hx, hy + 56, 5))
        screen_parts.append(f'<rect x="{fmt(hx)}" y="{fmt(hy + 136)}" width="{hud_w - 12}" height="1" fill="{tokens.GB[1]}"/>')
        screen_parts.append(next_block(hx, hy + 148, 84))
        sy = hy + 214
        for label, value in (("SUBMITTED", f"{total:04d}"), ("ACCEPTED", f"{accepted:04d}")):
            screen_parts.append(pf.render_path(label, hx, sy, scale=2, fill=tokens.GB[2]))
            screen_parts.append(pf.render_path(value, hx + hud_w - 12 - pf.measure(value, scale=2)[0], sy,
                                               scale=2, fill=tokens.GB[3]))
            sy += 22
    body_bottom = screen_y + screen_h + (100 - 20 if not narrow else 20)

    # --- boot logo and power fade ----------------------------------------------------------
    logo = "SOBADANGO"
    lscale = 3
    lw, lh = pf.measure(logo, scale=lscale)
    lx = screen_x + (screen_w - lw) / 2
    ly = screen_y + screen_h / 2 - lh
    drop_points = []
    frames = 12
    for k in range(frames + 1):
        f = k / frames
        drop_points.append((BOOT[0] + (BOOT[1] - BOOT[0]) * f,
                            {"transform": f"translate(0px,{fmt(-(ly - screen_y + lh) * (1 - f))}px)", "opacity": "1"}))
    drop_points.insert(0, (0.0, {"transform": f"translate(0px,{fmt(-(ly - screen_y + lh))}px)", "opacity": "1"}))
    drop_points.append((BOOT_END, {"transform": "translate(0px,0px)", "opacity": "0"}))
    logo_cls = fx.track(s.anim, fx.steps(drop_points, T))
    sub = "CODEFORCES"
    sw = pf.measure(sub, scale=2)[0]
    sub_cls = fx.track(s.anim, fx.windows([(BOOT[1], BOOT_END)], T))
    cover_cls = fx.track(
        s.anim,
        fx.steps([(0.0, {"opacity": "1"}), (BOOT_END - 0.1, {"opacity": "1"}), (BOOT_END, {"opacity": "0"}),
                  (FADE[0], {"opacity": "0"}), (FADE[1], {"opacity": "1"})], T),
        easing="linear",
    )
    ding = fx.track(s.anim, fx.steps([(0.0, {"opacity": "0"}), (BOOT[1] - fx.HOLD, {"opacity": "0"}),
                                      (BOOT[1], {"opacity": "0.35"}),
                                      (BOOT[1] + 0.25, {"opacity": "0"})], T), easing="ease-out", base={"opacity": "0"})
    screen_clip = s.ids.next()
    s.defs.append(f'<clipPath id="{screen_clip}"><rect x="{fmt(screen_x)}" y="{fmt(screen_y)}" width="{fmt(screen_w)}"'
                  f' height="{fmt(screen_h)}" rx="4"/></clipPath>')
    boot_layer = (
        f'<rect class="{cover_cls}" opacity="0" x="{fmt(screen_x)}" y="{fmt(screen_y)}" width="{fmt(screen_w)}"'
        f' height="{fmt(screen_h)}" fill="{tokens.GB[0]}"/>'
        + fx.wrap(logo_cls, pf.render_path(logo, lx, ly, scale=lscale, fill=tokens.ACID), hidden=True)
        + fx.wrap(sub_cls, pf.render_path(sub, screen_x + (screen_w - sw) / 2, ly + lh + 12, scale=2,
                                          fill=tokens.GB[2]), hidden=True)
        + f'<rect class="{ding}" opacity="0" x="{fmt(screen_x)}" y="{fmt(screen_y)}" width="{fmt(screen_w)}"'
        f' height="{fmt(screen_h)}" fill="{tokens.ACID_BRIGHT}"/>'
    )
    scan = s.ids.next()
    s.defs.append(f'<pattern id="{scan}" width="3" height="3" patternUnits="userSpaceOnUse">'
                  f'<rect width="3" height="1" fill="{tokens.VOID}" opacity="0.34"/></pattern>')
    body.append(
        f'<g clip-path="url(#{screen_clip})">{"".join(screen_parts)}{boot_layer}'
        f'<rect x="{fmt(screen_x)}" y="{fmt(screen_y)}" width="{fmt(screen_w)}" height="{fmt(screen_h)}"'
        f' fill="url(#{scan})"/></g>'
    )

    if narrow:
        # The side HUD does not fit, so the fight's numbers sit in a strip under the screen,
        # and Bit and the NEXT box stand either side of it.
        px = 3
        body.append(mascot.bit(s.anim, T, s.pad + 4, screen_y + screen_h - mascot.height(px) + 4, px,
                               jumps=[CLEAR_AT + 0.05, lock_at + 0.1], cheer=[(lock_at + 0.1, lock_at + 1.4)],
                               blinks=[2.5, 6.9, 12.6], bob=0.5))
        side_x = screen_x + screen_w + 16
        body.append(next_block(side_x, screen_y + 6, width - s.pad - side_x - 4))
        strip_y = screen_y + screen_h + 26
        body.append(hud_block(s.pad + 8, strip_y))
        body.append(rating_block(s.pad + 8, strip_y + 44, 4))
        for k, line in enumerate((f"SENT {total:04d}", f"AC {accepted:04d}")):
            body.append(pf.render_path(line, width - s.pad - 8 - pf.measure(line, scale=2)[0],
                                       strip_y + 60 + k * 20, scale=2, fill=tokens.GB[3]))
        body_bottom = strip_y + 44 + 22 + 28 + 26

    height = body_bottom + 22
    note = f"{stats.get('solved', 0)} SOLVED · {total} SUBMITTED"
    return s.render(
        height,
        chapter=3,
        title="Boss fight: The Judge. Codeforces submissions replayed as Game Boy Tetris",
        description=(
            f"Chapter four, boss fight. The ten Codeforces problems that took the most attempts, one "
            f"column each and one block per submission, fall in the order they were sent. Each accepted "
            f"submission hits The Judge, whose HP drains to {hp_pct} percent. The rating climbs "
            f"{', '.join(str(v) for v in rating_path[1:]) or rating} and the full bottom row clears."
        ),
        note=note,
    )
