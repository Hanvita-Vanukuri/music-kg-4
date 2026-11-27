"""Interactive knowledge graph: Artist -> Song -> Album -> Genre -> Mood (+ optional Language)."""
import json

from . import db

GRAPH_Q = """
MATCH (a:Artist)-[:PERFORMED]->(s:Song)-[:IN_ALBUM]->(al:Album)-[:ALBUM_GENRE]->(g:Genre)
WHERE s.song_id IN $ids
MATCH (s)-[:HAS_MOOD]->(m:Mood)
MATCH (s)-[:IN_LANGUAGE]->(l:Language)
RETURN s.song_id AS sid, s.title AS title, s.popularity AS pop, a.name AS artist,
       al.album_id AS album_id, al.name AS album, g.name AS genre, m.name AS mood, l.name AS language
"""
FEEL_Q = """
MATCH (g:Genre)-[r:TYPICALLY_FEELS]->(m:Mood)
WHERE g.name IN $genres AND m.name IN $moods
RETURN g.name AS genre, m.name AS mood, r.songs AS songs
"""

STYLE = {  # type -> (color, shape, size)
    "Artist": ("#1DB954", "dot", 26), "Song": ("#FFFFFF", "dot", 12), "Album": ("#8E6CEF", "square", 18),
    "Genre": ("#FF9F1C", "diamond", 24), "Mood": ("#FF4D8D", "triangle", 22), "Language": ("#2EC4F1", "star", 20),
}

PAGE = """
<div id="g" style="height:640px;background:#0b0b0b;border:1px solid #262626;border-radius:12px"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"></script>
<script>
const nodes=new vis.DataSet(__NODES__), edges=new vis.DataSet(__EDGES__);
new vis.Network(document.getElementById('g'),{nodes,edges},{
 nodes:{font:{color:'#fff',size:13},borderWidth:2},
 edges:{color:{color:'#4a4a4a',highlight:'#1DB954'},arrows:'to',font:{color:'#9a9a9a',size:9,strokeWidth:0,align:'middle'},smooth:{type:'continuous'}},
 physics:{solver:'forceAtlas2Based',forceAtlas2Based:{gravitationalConstant:-70,springLength:110},stabilization:{iterations:180}},
 interaction:{hover:true,tooltipDelay:80,navigationButtons:true}
});
</script>
"""


def build(song_ids, show_language=False):
    """Query Neo4j for the given songs; return (html, n_nodes, n_edges, cypher)."""
    rows = db.run(GRAPH_Q, ids=list(song_ids))
    nodes, edges = {}, set()

    def node(key, typ, label, title=""):
        if key not in nodes:
            color, shape, size = STYLE[typ]
            nodes[key] = {"id": key, "label": label, "title": f"{typ}: {title or label}", "shape": shape,
                          "size": size, "color": {"background": color, "border": "#000"}, "group": typ}

    for r in rows:
        sk, ak, alk = f"s:{r['sid']}", f"a:{r['artist']}", f"al:{r['album_id']}"
        gk, mk = f"g:{r['genre']}", f"m:{r['mood']}"
        node(ak, "Artist", r["artist"])
        node(sk, "Song", r["title"], f"{r['title']} (popularity {r['pop']:.0f})")
        node(alk, "Album", r["album"])
        node(gk, "Genre", r["genre"])
        node(mk, "Mood", r["mood"])
        edges |= {(ak, sk, "PERFORMED"), (sk, alk, "IN_ALBUM"), (alk, gk, "ALBUM_GENRE")}
        if show_language:
            lk = f"l:{r['language']}"
            node(lk, "Language", r["language"])
            edges.add((sk, lk, "IN_LANGUAGE"))
    genres = sorted({r["genre"] for r in rows})
    moods = sorted({r["mood"] for r in rows})
    for r in db.run(FEEL_Q, genres=genres, moods=moods):
        edges.add((f"g:{r['genre']}", f"m:{r['mood']}", f"TYPICALLY_FEELS ({r['songs']})"))
    e = [{"from": a, "to": b, "label": lbl} for a, b, lbl in sorted(edges)]
    payload = lambda o: json.dumps(o).replace("</", "<\\/")
    html = PAGE.replace("__NODES__", payload(list(nodes.values()))).replace("__EDGES__", payload(e))
    return html, len(nodes), len(e), GRAPH_Q.strip()
