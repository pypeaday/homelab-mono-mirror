function initCanvas() {
    var el = document.getElementById('canvas-network');
    if (!el || !el.dataset.dataUrl) return;
    var D = {
        dataUrl: el.dataset.dataUrl,
        saveUrl: el.dataset.saveUrl,
        notesUrl: el.dataset.notesUrl,
        csrf: el.dataset.csrf
    };

    el.textContent = 'Loading canvas…';
    fetch(D.dataUrl)
        .then(function (r) { return r.json(); })
        .then(function (graph) { D.data = graph; renderCanvas(el, D); })
        .catch(function (err) {
            el.textContent = 'Canvas failed to load: ' + err;
            el.style.padding = '20px';
            el.style.color = '#c62828';
        });
}

function renderCanvas(el, D) {
    el.textContent = '';

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
        });
    }

    var urls = {};
    var saved = {};
    var nodes = D.data.nodes.map(function (n) {
        urls[n.id] = n.url;
        var isAgentReady = n.tags.indexOf('agent-ready') >= 0;
        var label = '#' + n.id + '  ' + (n.title.length > 42 ? n.title.slice(0, 42) + '…' : n.title);
        if (n.due) label += '\n' + 'due ' + n.due;
        if (n.closed) label += '  (closed)';

        var tip = '<b>#' + n.id + ' ' + esc(n.title) + '</b><br>' +
            esc(n.lane ? n.lane + ' · ' : '') + esc(n.column) +
            (n.owner ? '<br>Owner: ' + esc(n.owner) : '') +
            (n.tags.length ? '<br>Tags: ' + esc(n.tags.join(', ')) : '') +
            (n.due ? '<br>Due: ' + esc(n.due) : '') +
            (n.done_on ? '<br>Done: ' + esc(n.done_on) : '');

        if (n.x !== null && n.y !== null) saved[n.id] = { x: n.x, y: n.y };

        return {
            id: n.id,
            label: label,
            title: tip,
            shape: 'box',
            margin: 10,
            widthConstraint: { maximum: 280 },
            color: { background: n.fill, border: isAgentReady ? '#7e57c2' : '#455a64' },
            borderWidth: isAgentReady ? 3 : 1,
            shapeProperties: { borderDashes: isAgentReady },
            opacity: n.closed ? 0.5 : 1,
            font: { size: 13, color: '#f5f5f5' }
        };
    });

    var edges = D.data.edges.map(function (e) {
        return {
            from: e.from,
            to: e.to,
            title: e.label,
            arrows: e.directed ? 'to' : '',
            dashes: !e.directed,
            color: { color: e.color, opacity: 0.85 },
            width: e.directed ? 2 : 1,
            smooth: { type: 'cubicBezier', forceDirection: 'horizontal', roundness: 0.4 }
        };
    });

    var hierarchical = {
        enabled: true,
        direction: 'LR',
        sortMethod: 'directed',
        levelSeparation: 220,
        nodeSpacing: 30,
        treeSpacing: 70
    };

    var noteStore = {};
    (D.data.notes || []).forEach(function (n) {
        noteStore[n.id] = { id: n.id, text: n.text, x: n.x, y: n.y };
        nodes.push({
            id: n.id,
            label: n.text,
            title: 'Note — double-click to edit',
            shape: 'box',
            margin: 10,
            widthConstraint: { maximum: 220 },
            color: { background: '#fff59d', border: '#f9a825' },
            font: { size: 13, color: '#333' },
            x: n.x,
            y: n.y
        });
    });

    var dsNodes = new vis.DataSet(nodes);
    var net = new vis.Network(el, {
        nodes: dsNodes,
        edges: new vis.DataSet(edges)
    }, {
        layout: { hierarchical: hierarchical },
        physics: { enabled: true, solver: 'hierarchicalRepulsion', hierarchicalRepulsion: { nodeDistance: 110 } },
        interaction: { dragNodes: true, dragView: true, zoomView: true, multiselect: true, hover: true }
    });

    var settled = false;
    function freeze() {
        net.setOptions({ physics: { enabled: false }, layout: { hierarchical: { enabled: false } } });
    }
    function applySaved() {
        Object.keys(saved).forEach(function (id) {
            net.moveNode(parseInt(id, 10), saved[id].x, saved[id].y);
        });
        Object.keys(noteStore).forEach(function (id) {
            net.moveNode(id, noteStore[id].x, noteStore[id].y);
        });
    }
    function settle() {
        if (settled) return;
        settled = true;
        freeze();
        applySaved();
        net.fit({ animation: { duration: 300 } });
    }
    net.once('stabilizationIterationsDone', settle);
    setTimeout(settle, 5000);

    function savePosition(id, x, y) {
        fetch(D.saveUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'csrf_token=' + encodeURIComponent(D.csrf) +
                  '&task_id=' + id + '&x=' + Math.round(x) + '&y=' + Math.round(y)
        });
    }

    function saveNotes() {
        fetch(D.notesUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'csrf_token=' + encodeURIComponent(D.csrf) +
                  '&notes=' + encodeURIComponent(JSON.stringify(Object.keys(noteStore).map(function (k) { return noteStore[k]; })))
        });
    }

    net.on('dragEnd', function (params) {
        if (!params.nodes || !params.nodes.length) return;
        var positions = net.getPositions(params.nodes);
        var notesMoved = false;
        params.nodes.forEach(function (id) {
            if (/^note_/.test(id)) {
                noteStore[id].x = positions[id].x;
                noteStore[id].y = positions[id].y;
                notesMoved = true;
                return;
            }
            if (!/^\d+$/.test(id)) return;
            saved[id] = positions[id];
            savePosition(id, positions[id].x, positions[id].y);
        });
        if (notesMoved) saveNotes();
    });

    net.on('doubleClick', function (params) {
        if (!params.nodes || !params.nodes.length) return;
        var id = params.nodes[0];
        if (/^note_/.test(id)) {
            var next = prompt('Note text (leave empty to delete):', noteStore[id].text);
            if (next === null) return;
            if (next === '') {
                dsNodes.remove(id);
                delete noteStore[id];
            } else {
                noteStore[id].text = next;
                dsNodes.update({ id: id, label: next });
            }
            saveNotes();
            return;
        }
        if (urls[id]) window.location.href = urls[id];
    });

    var addNoteBtn = document.getElementById('canvas-add-note');
    if (addNoteBtn) {
        addNoteBtn.onclick = function () {
            var text = prompt('Note text:');
            if (!text) return;
            var c = net.DOMtoCanvas({ x: el.clientWidth / 2, y: el.clientHeight / 2 });
            var id = 'note_' + Date.now();
            noteStore[id] = { id: id, text: text, x: c.x, y: c.y };
            dsNodes.add({
                id: id, label: text, title: 'Note — double-click to edit', shape: 'box',
                margin: 10, widthConstraint: { maximum: 220 },
                color: { background: '#fff59d', border: '#f9a825' },
                font: { size: 13, color: '#333' }, x: c.x, y: c.y
            });
            saveNotes();
        };
    }

    var autolayoutBtn = document.getElementById('canvas-autolayout');
    if (autolayoutBtn) {
        autolayoutBtn.onclick = function () {
            clearHeaders();
            settled = false;
            net.setOptions({ layout: { hierarchical: hierarchical }, physics: { enabled: true, solver: 'hierarchicalRepulsion', hierarchicalRepulsion: { nodeDistance: 110 } } });
            net.stabilize();
            net.once('stabilizationIterationsDone', settle);
            setTimeout(settle, 5000);
        };
    }

    var hdrIds = [];
    function clearHeaders() {
        if (hdrIds.length) dsNodes.remove(hdrIds);
        hdrIds = [];
    }

    function groupBy(field) {
        clearHeaders();
        freeze();
        var order = field === 'lane'
            ? (D.data.lanes.length ? D.data.lanes.slice() : ['No lane'])
            : D.data.columns.slice();
        var groups = {};
        order.forEach(function (k) { groups[k] = []; });
        D.data.nodes.forEach(function (n) {
            var k = field === 'lane' ? (n.lane || 'No lane') : n.column;
            if (!groups[k]) { groups[k] = []; order.push(k); }
            groups[k].push(n);
        });
        var cardW = 300, rowH = 62, bandGap = 60, perRow = 6;
        var gi = 0;
        order.forEach(function (k) {
            if (!groups[k].length) return;
            var rows = Math.ceil(groups[k].length / perRow);
            var bandH = rows * rowH + bandGap;
            var y0 = gi * bandH;
            var hid = 'hdr_' + gi;
            dsNodes.add({ id: hid, label: k + '  (' + groups[k].length + ')', shape: 'text',
                          x: 0, y: y0 - 40, fixed: true, font: { size: 17, color: '#eceff1' },
                          color: { background: 'rgba(0,0,0,0)', border: 'rgba(0,0,0,0)' } });
            hdrIds.push(hid);
            groups[k].forEach(function (n, i) {
                var x = (i % perRow) * cardW + 150;
                var y = y0 + Math.floor(i / perRow) * rowH;
                dsNodes.update({ id: n.id, x: x, y: y });
                saved[n.id] = { x: x, y: y };
                savePosition(n.id, x, y);
            });
            gi++;
        });
        net.fit({ animation: { duration: 300 } });
    }

    var gl = document.getElementById('canvas-group-lane');
    if (gl) gl.onclick = function () { groupBy('lane'); };
    var gc = document.getElementById('canvas-group-column');
    if (gc) gc.onclick = function () { groupBy('column'); };

    var resetBtn = document.getElementById('canvas-reset');
    if (resetBtn) {
        resetBtn.onclick = function () {
            if (!confirm('Clear all manually saved card positions?')) return;
            Object.keys(urls).forEach(function (id) {
                fetch(D.saveUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: 'csrf_token=' + encodeURIComponent(D.csrf) + '&task_id=' + id + '&x=&y='
                });
                delete saved[id];
            });
            if (autolayoutBtn) autolayoutBtn.click();
        };
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCanvas);
} else {
    initCanvas();
}
