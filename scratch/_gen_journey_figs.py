"""Defense visuals (replace chap4/ versions):
  1. passenger_journey_snapshots.png      -- one passenger's transfer journey, leg by leg (2-route toy)
  2. simulation_temporal_snapshots.png    -- the same passenger in a running mini-sim (jeeps + boarding counts)
  3. journey_travelgraph_3d.png           -- the journey through the 3-layer TravelGraph (static)
  4. journey_travelgraph_3d_temporal.png  -- the journey building up through the layers, w/ boarding count

Built by stitching the prepared draw functions + the 3D visualizer (frankenstein per request).
"""
import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import utils.travel_graph_3d_vis as vis
from utils.toy_city import toy_setup_from_yaml
from utils_simplified import generate_route_system
from utils.travel_graph import TravelGraph
from utils.jeep import Jeep
from utils.jeep_system import JeepSystem
from utils.passenger import Passenger

IMG = "results_and_discussion/images"
os.makedirs(IMG, exist_ok=True)
SPT = 1
RA, RB = "#E63946", "#1D3557"
C_WALK, C_PAX, C_ORIG, C_DEST, C_TR = "#2e7d32", "#111111", "#2ecc71", "#e74c3c", "#F29900"
SIZE = 760


def _font(sz, bold=True):
    names = (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf"))
    for n in names + ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(n, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def collapsed_sig(j):
    if not j:
        return []
    s = [j[0].id[:2]]
    for e in j[1:]:
        if e.id[:2] != s[-1]:
            s.append(e.id[:2])
    return s


def find_transfer_scenario():
    city, sampler, config = toy_setup_from_yaml("configs/toy_city_configs.yaml", verbose=False)
    tw = config.get("travel_graph", {})
    for seed in range(300):
        random.seed(seed); np.random.seed(seed)
        routes = generate_route_system(2, city, sampler)
        if len(routes) < 2:
            continue
        tg = TravelGraph(city, config=tw, routes=routes)
        l1, l3 = list(tg.l1_nodes.values()), list(tg.l3_nodes.values())
        rng = random.Random(seed)
        for _ in range(400):
            o, d = rng.choice(l1), rng.choice(l3)
            j = tg.findShortestJourney(o, d)
            if j and "TR" in collapsed_sig(j) and collapsed_sig(j).count("RI") >= 2:
                print("seed %d -> %s (%d edges)" % (seed, collapsed_sig(j), len(j)))
                return city, sampler, config, routes, tg, o, d, j
    raise RuntimeError("no transfer journey found")


# -------------------------------------------------------------- 2D helpers
def to_px(img, ctx, lon, lat):
    (tl_lon, tl_lat), (br_lon, br_lat) = ctx
    return (img.width * (lon - tl_lon) / (br_lon - tl_lon),
            img.height * (tl_lat - lat) / (tl_lat - br_lat))


def ridx_of(e):
    if e.id[:2] == "RI" and "_" in e.id:
        try:
            return int(e.id.split("_")[1][1:])
        except Exception:
            return None
    return None


def journey_phases(journey):
    phases, pts = [], {"board": None, "transfer": None}
    ck, cr, cur = None, None, []
    for e in journey:
        pre = e.id[:2]
        if pre == "WA" and pts["board"] is None:
            pts["board"] = (e.start.lon, e.start.lat)
        if pre == "TR":
            pts["transfer"] = (e.start.lon, e.start.lat)
        if pre in ("WA", "AL", "TR", "DI"):
            continue
        kind = "ride" if pre == "RI" else "walk"
        ridx = ridx_of(e)
        if kind == ck and ridx == cr:
            cur.append((e.end.lon, e.end.lat))
        else:
            if cur:
                phases.append((ck, cr, cur))
            ck, cr, cur = kind, ridx, [(e.start.lon, e.start.lat), (e.end.lon, e.end.lat)]
    if cur:
        phases.append((ck, cr, cur))
    return phases, pts


def base_map(city, routes, route_width=4, faint=True):
    img = city.draw(size=SIZE, only_drivable=False).convert("RGBA")
    img = Image.alpha_composite(img, Image.new("RGBA", img.size, (255, 255, 255, 165)))
    a = 110 if faint else 255
    img = routes[0].draw(city.get_bounds(), img, color=RA, width=route_width)
    img = routes[1].draw(city.get_bounds(), img, color=RB, width=route_width)
    if faint:  # fade the full route loops so the *ridden* path stands out
        img = Image.alpha_composite(img, Image.new("RGBA", img.size, (255, 255, 255, 90)))
    return img


def line(dr, img, ctx, pts, color, width):
    px = [to_px(img, ctx, lo, la) for lo, la in pts]
    if len(px) >= 2:
        dr.line(px, fill=color, width=width, joint="curve")


def marker(dr, xy, r, fill, outline="#ffffff", ow=3):
    x, y = xy
    dr.ellipse([x - r, y - r, x + r, y + r], fill=fill, outline=outline, width=ow)


def title_band(img, text):
    dr = ImageDraw.Draw(img, "RGBA")
    dr.rectangle([0, 0, img.width, 36], fill=(17, 17, 17, 225))
    dr.text((10, 8), text, fill="#ffffff", font=_font(19))


def draw_full_journey(dr, img, ctx, phases, rides):
    for kind, ridx, pts in phases:
        if kind == "walk":
            line(dr, img, ctx, pts, C_WALK, 7)
        else:
            line(dr, img, ctx, pts, RA if ridx == rides[0][1] else RB, 13)


def tile(panels, cols, pad=8, bg=(255, 255, 255, 255)):
    w, h = panels[0].size
    rows = (len(panels) + cols - 1) // cols
    out = Image.new("RGBA", (cols * w + (cols + 1) * pad, rows * h + (rows + 1) * pad), bg)
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        out.paste(p, (pad + c * (w + pad), pad + r * (h + pad)))
    return out


def legend_strip(width, items, h=46):
    img = Image.new("RGBA", (width, h), (255, 255, 255, 255))
    dr = ImageDraw.Draw(img)
    x = 14
    f = _font(17)
    for kind, color, label in items:
        if kind == "line":
            dr.line([(x, h // 2), (x + 34, h // 2)], fill=color, width=7)
            x += 42
        else:
            marker(dr, (x + 9, h // 2), 9, color, outline="#ffffff", ow=2)
            x += 24
        dr.text((x, h // 2 - 10), label, fill="#111111", font=f)
        x += dr.textlength(label, font=f) + 26
    return img


def stack_legend(grid, items):
    leg = legend_strip(grid.width, items)
    out = Image.new("RGBA", (grid.width, grid.height + leg.height), (255, 255, 255, 255))
    out.paste(grid, (0, 0)); out.paste(leg, (0, grid.height))
    return out


JLEG = [("line", RA, "Route A"), ("line", RB, "Route B"), ("line", C_WALK, "walk"),
        ("dot", C_ORIG, "origin"), ("dot", C_TR, "transfer"), ("dot", C_DEST, "dest"),
        ("dot", "#FFD400", "passenger")]


def fig_journey_snapshots(city, routes, journey):
    ctx = city.get_bounds()
    phases, key = journey_phases(journey)
    rides = [p for p in phases if p[0] == "ride"]
    walks = [p for p in phases if p[0] == "walk"]
    mid = lambda seg: seg[len(seg) // 2]
    origin, dest = phases[0][2][0], phases[-1][2][-1]
    stages = [
        ("1. Walk from origin to a stop", mid(walks[0][2]) if walks else origin),
        ("2. Wait & board Route A", key["board"] or origin),
        ("3. Ride Route A", mid(rides[0][2])),
        ("4. Transfer to Route B", key["transfer"] or origin),
        ("5. Ride Route B", mid(rides[1][2]) if len(rides) > 1 else origin),
        ("6. Alight & walk to destination", dest),
    ]
    panels = []
    for title, pax in stages:
        img = base_map(city, routes, route_width=4, faint=True)
        dr = ImageDraw.Draw(img, "RGBA")
        draw_full_journey(dr, img, ctx, phases, rides)
        marker(dr, to_px(img, ctx, *origin), 9, C_ORIG)
        if key["transfer"]:
            marker(dr, to_px(img, ctx, *key["transfer"]), 11, C_TR)
        marker(dr, to_px(img, ctx, *dest), 9, C_DEST)
        marker(dr, to_px(img, ctx, *pax), 14, C_PAX, outline="#FFD400", ow=4)
        title_band(img, title)
        panels.append(img)
    out = stack_legend(tile(panels, cols=3), JLEG)
    out.convert("RGB").save(os.path.join(IMG, "passenger_journey_snapshots.png"))
    print("saved passenger_journey_snapshots.png  (%dx%d)" % out.size)


# -------------------------------------------------------------- temporal sim
def fig_temporal_snapshots(city, config, routes, journey, origin):
    ctx = city.get_bounds()
    tg = TravelGraph(city, config=config.get("travel_graph", {}), routes=routes)
    jeeps = [Jeep(r, curr_pos=(r.path[0].start.lon, r.path[0].start.lat), speed=30.0,
                  max_capacity=16, seconds_per_tick=SPT) for r in routes for _ in range(3)]
    js = JeepSystem(jeeps=jeeps, routes=routes, weight_tolerance=14.4, equidistant_spawn=True)
    pax = Passenger(start_pos=(origin.lon, origin.lat), journey=journey, speed=5.0,
                    spawn_time=0, seconds_per_tick=SPT)
    js.add_passenger(pax)
    frames, seen, tick = [], set(), 0
    while tick < 5000 and pax.state != Passenger.DONE and len(frames) < 5:
        pax._stepped_this_tick = False
        js.update(); tick += 1
        tag = (pax.state, pax.current_jeep.route.id if pax.current_jeep else None)
        if pax.state in (Passenger.WALKING, Passenger.WAITING, Passenger.RIDING) and tag not in seen:
            seen.add(tag)
            frames.append(render_sim_frame(city, ctx, routes, js, pax, tick))
    frames.append(render_sim_frame(city, ctx, routes, js, pax, tick, done=(pax.state == Passenger.DONE)))
    out = stack_legend(tile(frames[:6], cols=3),
                       [("dot", "#FFD400", "tracked passenger"), ("line", RA, "Route A"),
                        ("line", RB, "Route B"), ("dot", "#888", "jeep (shows # onboard)")])
    out.convert("RGB").save(os.path.join(IMG, "simulation_temporal_snapshots.png"))
    print("saved simulation_temporal_snapshots.png  (pax final state=%d)" % pax.state)


def render_sim_frame(city, ctx, routes, js, pax, tick, done=False):
    img = base_map(city, routes, route_width=6, faint=False)
    img = js.draw(ctx, img, radius=19)
    dr = ImageDraw.Draw(img, "RGBA")
    try:
        marker(dr, to_px(img, ctx, pax.curr_lon, pax.curr_lat), 13, C_PAX, outline="#FFD400", ow=4)
    except Exception:
        pass
    st = {0: "WALKING", 1: "WAITING", 2: "RIDING", 3: "DONE"}.get(pax.state, "?")
    lbl = "t=%ds   passenger: %s" % (tick, "DONE" if done else st)
    if pax.state == Passenger.RIDING and pax.current_jeep:
        lbl += "   (its jeep: %d pax)" % pax.current_jeep.curr_passenger_count
    title_band(img, lbl)
    return img


# -------------------------------------------------------------- 3D (static + temporal)
def _3d_image(tg, hl):
    viz = vis.TravelGraph3DVisualizer(base_edges=list(tg.travel_graph), highlight_edges=hl,
                                      mode="light", journey_thickness=5.0, edge_thickness=1.3,
                                      layer_opacity=0.55)
    return viz.draw(nodes_on=False, legend_on=bool(hl)).convert("RGBA")


def fig_3d_static(tg, journey):
    _3d_image(tg, journey).save(os.path.join(IMG, "journey_travelgraph_3d.png"))
    print("saved journey_travelgraph_3d.png")


def phase_boundaries(journey):
    """(edge_idx_upto, label, onboard) at each journey milestone."""
    sig = collapsed_sig(journey)
    idx_board = next(i for i, e in enumerate(journey) if e.id[:2] == "WA")
    idx_tr = next(i for i, e in enumerate(journey) if e.id[:2] == "TR")
    # end of ride A = the AL right after the first RI run (the AL before TR)
    idx_alA = next(i for i in range(idx_board, idx_tr) if journey[i].id[:2] == "AL")
    idx_alB = next(i for i in range(idx_tr, len(journey)) if journey[i].id[:2] == "AL")
    return [
        (idx_board, "1. Walk to stop (Layer 1)", 0),
        (idx_alA + 1, "2. Board + Ride Route A (Layer 2)", 1),
        (idx_tr + 1, "3. Alight + Transfer (Layer 3->2)", 0),
        (idx_alB + 1, "4. Ride Route B (Layer 2)", 1),
        (len(journey), "5. Alight + walk to destination", 0),
    ]


def fig_3d_temporal(tg, journey):
    frames = []
    for k, label, onboard in phase_boundaries(journey):
        img = _3d_image(tg, journey[:k])
        dr = ImageDraw.Draw(img, "RGBA")
        dr.rectangle([0, 0, img.width, 60], fill=(17, 17, 17, 220))
        dr.text((8, 6), label, fill="#ffffff", font=_font(15))
        dr.text((8, 32), "onboard jeep: %d pax" % onboard, fill="#FFD400" if onboard else "#bbbbbb",
                font=_font(15))
        frames.append(img)
    # normalize heights then tile horizontally
    h = max(f.height for f in frames)
    norm = []
    for f in frames:
        c = Image.new("RGBA", (f.width, h), (255, 255, 255, 255))
        c.paste(f, (0, (h - f.height) // 2)); norm.append(c)
    out = tile(norm, cols=len(norm), pad=6)
    out.convert("RGB").save(os.path.join(IMG, "journey_travelgraph_3d_temporal.png"))
    print("saved journey_travelgraph_3d_temporal.png  (%dx%d)" % out.size)


if __name__ == "__main__":
    city, sampler, config, routes, tg, origin, dest, journey = find_transfer_scenario()
    fig_journey_snapshots(city, routes, journey)
    fig_temporal_snapshots(city, config, routes, journey, origin)
    fig_3d_static(tg, journey)
    fig_3d_temporal(tg, journey)
    print("DONE")
