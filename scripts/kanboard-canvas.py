#!/usr/bin/env python3
"""Generate a drawio canvas from a kanboard board.

Lanes -> drawio swimlanes (falls back to columns when the board has a
single lane); cards -> cells; task links -> dependency arrows. Cells
managed by this script carry kb_ id prefixes so user-drawn content is
preserved on regeneration.
"""
import json, os, re, sys, urllib.request, html, time, base64, copy
import xml.etree.ElementTree as ET

API = "https://kanboard.paynepride.com/jsonrpc.php"
TOKEN = open(os.path.expanduser("~/.local/share/devin/kanboard-token")).read().strip()

def kb(method, **params):
    req = urllib.request.Request(API, data=json.dumps(
        {"jsonrpc": "2.0", "method": method, "id": 1, "params": params}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Basic " + base64.b64encode(("jsonrpc:" + TOKEN).encode()).decode()})
    return json.load(urllib.request.urlopen(req))["result"]

COL_STYLE = {
    "backlog":           "fillColor=#eceff1;strokeColor=#78909c;fontColor=#263238;",
    "ready":             "fillColor=#dae8fc;strokeColor=#42a5f5;fontColor=#0d47a1;",
    "work in progress":  "fillColor=#ffe6cc;strokeColor=#ffa726;fontColor=#4e2c00;",
    "done":              "fillColor=#d5e8d4;strokeColor=#66bb6a;fontColor=#1b5e20;",
}
EDGE_STYLE = {
    "blocks": "strokeColor=#e53935;strokeWidth=2;",
    "is blocked by": "strokeColor=#e53935;strokeWidth=2;",
    "is a parent of": "strokeColor=#1e88e5;",
    "is a child of": "strokeColor=#1e88e5;",
    "fixes": "strokeColor=#43a047;",
    "is fixed by": "strokeColor=#43a047;",
    "targets milestone": "strokeColor=#8e24aa;",
    "is a milestone of": "strokeColor=#8e24aa;",
}
FLIP = {"is blocked by", "is a child of", "is a milestone of", "is fixed by"}
DIRECTED = {"blocks", "is blocked by", "is a parent of", "is a child of",
            "targets milestone", "is a milestone of", "fixes", "is fixed by"}

def esc(s):
    return html.escape(str(s or ""), quote=True)

def card_diagram(task_id):
    """Return (root Element, {kb_id: (x,y,w,h)}, {kb_id: parent}) from a card's ```diagram fence."""
    task = kb("getTask", task_id=task_id)
    m = re.search(r"```diagram\s*\n([A-Za-z0-9+/=\s]+?)\n```", task.get("description") or "")
    if not m:
        return None, {}, {}
    svg = base64.b64decode(re.sub(r"\s", "", m.group(1))).decode("utf-8", "replace")
    cm = re.search(r'content="([^"]*)"', svg)
    if not cm:
        return None, {}, {}
    xml = html.unescape(cm.group(1))
    try:
        mx = ET.fromstring(xml)
    except ET.ParseError:
        return None, {}, {}
    model = mx.find("diagram/mxGraphModel")
    if model is None and mx.tag == "mxGraphModel":
        model = mx
    if model is None:
        return None, {}, {}
    root = model.find("root")
    pos = {}
    parents = {}
    for cell in root.findall("mxCell"):
        cid = cell.get("id", "")
        if not cid.startswith("kb_"):
            continue
        parents[cid] = cell.get("parent", "1")
        g = cell.find("mxGeometry")
        if g is not None and g.get("x") is not None:
            pos[cid] = (g.get("x"), g.get("y"), g.get("width"), g.get("height"))
    return root, pos, parents


def build(project_id, out_path, card_id=None):
    if card_id is None:
        prev_root, prev_pos, prev_parent = ET.Element("root"), {}, {}
    else:
        prev_root, prev_pos, prev_parent = card_diagram(card_id)
        if prev_root is None:
            prev_root, prev_pos, prev_parent = ET.Element("root"), {}, {}

    columns = kb("getColumns", project_id=project_id)
    col_order = [c["id"] for c in columns]
    col_name = {c["id"]: c["title"] for c in columns}
    all_lanes = kb("getAllSwimlanes", project_id=project_id) or []
    use_lanes = any(l["name"] != "Default swimlane" for l in all_lanes)
    lane_name = {l["id"]: (l["name"] if l["name"] != "Default swimlane" else "Uncategorized")
                 for l in all_lanes}
    tasks = kb("getAllTasks", project_id=project_id, status_id=1)

    groups = {}
    for t in tasks:
        key = int(t["swimlane_id"]) if use_lanes else int(t["column_id"])
        groups.setdefault(key, []).append(t)
    if use_lanes:
        gorder = [l["id"] for l in all_lanes if l["id"] in groups] + \
                 [k for k in groups if k not in lane_name]
        gname = lane_name
    else:
        gorder = [c for c in col_order if c in groups]
        gname = {c["id"]: c["title"] for c in columns}
    for g in groups.values():
        g.sort(key=lambda t: (col_order.index(t["column_id"])
                              if t["column_id"] in col_order else 99, t["id"]))

    CARD_W, CARD_H, GAP, PAD, PER_ROW = 210, 64, 24, 70, 6

    mx = ET.Element("mxfile", host="app.diagrams.net")
    dg = ET.SubElement(mx, "diagram", id=f"kb-{project_id}", name=f"board-{project_id}")
    model = ET.SubElement(dg, "mxGraphModel", dx="800", dy="600", grid="1",
                          gridSize="10", guides="1", tooltips="1", connect="1",
                          arrows="1", fold="1", page="0", pageScale="1", math="0", shadow="0")
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")

    edges, seen = [], set()
    y = 40
    for gk in gorder:
        members = groups[gk]
        rows = max(1, -(-len(members) // PER_ROW))
        w = max(1100, min(len(members), PER_ROW) * (CARD_W + GAP) + 2 * PAD + 20)
        h = rows * (CARD_H + 14) + 2 * PAD
        lane_id = f"kb_g_{gk}"
        lx, ly, lw, lh = prev_pos.get(lane_id, ("40", str(y), str(w), str(h)))
        lane = ET.SubElement(root, "mxCell", id=lane_id, value=esc(gname.get(gk, "Tasks")),
                             style="swimlane;startSize=30;horizontal=1;fillColor=none;"
                                   "swimlaneFillColor=none;fontSize=16;fontStyle=1;",
                             vertex="1", parent="1")
        ET.SubElement(lane, "mxGeometry", x=str(lx), y=str(ly),
                      width=str(lw), height=str(lh)).set("as", "geometry")

        for i, t in enumerate(members):
            col = col_name.get(int(t["column_id"]), "?").lower()
            style = ("rounded=1;whiteSpace=wrap;html=1;fontSize=11;align=center;"
                     + COL_STYLE.get(col, COL_STYLE["backlog"]))
            tags = kb("getTaskTags", task_id=t["id"]) or {}
            if any("agent-ready" in str(v) for v in tags.values()):
                style += "strokeColor=#7e57c2;strokeWidth=3;dashed=1;"
            label = f"#{t['id']} {t['title']}"
            if int(t.get("date_due") or 0):
                label += f"  |  due {time.strftime('%m/%d', time.localtime(int(t['date_due'])))}"
            cell_id = f"kb_t_{t['id']}"
            parent = lane_id if cell_id not in prev_pos else prev_parent.get(cell_id, lane_id)
            cx, cy, cw, ch = prev_pos.get(
                cell_id,
                (str(PAD + 10 + (i % PER_ROW) * (CARD_W + GAP)),
                 str(PAD - 10 + (i // PER_ROW) * (CARD_H + 14)),
                 str(CARD_W), str(CARD_H)))
            cell = ET.SubElement(root, "mxCell", id=cell_id, value=esc(label),
                                 style=style, vertex="1", parent=parent)
            ET.SubElement(cell, "mxGeometry", x=str(cx), y=str(cy),
                          width=str(cw), height=str(ch)).set("as", "geometry")

            for link in kb("getAllTaskLinks", task_id=t["id"]) or []:
                if link["id"] in seen:
                    continue
                seen.add(link["id"])
                lab = link["label"].lower()
                other = int(link["task_id"])
                src, dst = (other, int(t["id"])) if lab in FLIP else (int(t["id"]), other)
                edges.append((src, dst, lab, link["label"]))
        y += h + 60

    for i, (src, dst, key, label) in enumerate(edges):
        st = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow=block;"
              + (EDGE_STYLE.get(key, "strokeColor=#9e9e9e;dashed=1;")
                 if key in DIRECTED else "strokeColor=#9e9e9e;dashed=1;endArrow=none;"))
        e = ET.SubElement(root, "mxCell", id=f"kb_e_{i}", value=esc(label), style=st,
                          edge="1", parent="1", source=f"kb_t_{src}", target=f"kb_t_{dst}")
        ET.SubElement(e, "mxGeometry", relative="1").set("as", "geometry")

    # carry over user-drawn (non-kb_) cells from the existing card diagram
    for cell in prev_root.findall("mxCell"):
        cid = cell.get("id", "")
        if cid in ("0", "1") or cid.startswith("kb_"):
            continue
        root.append(copy.deepcopy(cell))

    ET.ElementTree(mx).write(out_path, xml_declaration=True, encoding="utf-8")
    print(f"wrote {out_path}: {len(tasks)} cards, {len(edges)} edges, {len(gorder)} groups "
          f"({'lanes' if use_lanes else 'columns'})")

if __name__ == "__main__":
    build(int(sys.argv[1]), sys.argv[2],
          int(sys.argv[3]) if len(sys.argv) > 3 else None)
