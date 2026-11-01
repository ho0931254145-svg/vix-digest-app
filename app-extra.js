// VIX 日報 App 附加區塊：近期評分與倉位（data/history.json）＋ Watchdog 核對狀態（data/status.json）
// 只在 App（GitHub Pages）載入；日報網頁本身不含這支腳本。兩個 JSON 每天由排程更新，App 開啟時直接讀最新版。
(function () {
  'use strict';
  var head = document.getElementById('home');
  if (!head) return;
  var live = head.querySelector('.live');
  var pageDate = live ? (live.textContent.match(/\d{4}-\d{2}-\d{2}/) || [])[0] : null;

  var css = document.createElement('style');
  css.textContent = [
    '.hx{margin-top:12px;border:1px solid var(--ink-rule);border-radius:var(--r,10px);background:var(--ink-2);color:var(--ink-fg);overflow:hidden}',
    '.hx-top{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 14px;border-bottom:1px solid var(--ink-rule)}',
    '.hx-title{margin:0;font-size:.86rem;font-weight:700;letter-spacing:.04em;color:var(--ink-fg)}',
    '.hx-badge{font:inherit;font-size:.74rem;border-radius:999px;padding:2px 10px;border:1px solid var(--ink-rule);background:transparent;color:var(--ink-muted);cursor:pointer;white-space:nowrap}',
    '.hx-badge.ok{color:var(--down-ink);border-color:currentColor}.hx-badge.bad{color:var(--warn,#f0b54a);border-color:currentColor}',
    '.hx-badge:focus-visible{outline:2px solid var(--ink-fg);outline-offset:2px}',
    '.hx-checks{margin:0;padding:8px 14px 10px;list-style:none;font-size:.78rem;line-height:1.5;color:var(--ink-muted);border-bottom:1px solid var(--ink-rule)}',
    '.hx-checks li{display:grid;grid-template-columns:3.2em 1fr;gap:6px;padding:2px 0}',
    '.hx-checks b{font-weight:600}.hx-checks .ok b{color:var(--down-ink)}.hx-checks .fail b{color:var(--warn,#f0b54a)}.hx-checks .skip b{color:var(--ink-muted)}',
    '.hx-msg{padding:10px 14px;font-size:.8rem;color:var(--ink-muted)}',
    '.hx-bars{display:flex;align-items:flex-end;gap:3px;height:64px;padding:10px 14px 0}',
    '.hx-bars span{flex:1 1 0;min-width:4px;max-width:22px;border-radius:3px 3px 0 0;background:var(--ink-rule)}',
    '.hx-bars span.last{background:var(--ink-fg)}',
    '.hx-axis{display:flex;justify-content:space-between;padding:4px 14px 8px;font-family:var(--f-data);font-size:.68rem;color:var(--ink-muted)}',
    '.hx-wrap{overflow-x:auto}',
    '.hx table{width:100%;min-width:0;border-collapse:collapse;font-size:.78rem;line-height:1.4;font-variant-numeric:tabular-nums;margin:0}',
    '.hx th{font-weight:500;font-size:.72rem;color:var(--ink-muted);background:transparent;text-align:right;padding:6px 5px;border:0;border-top:1px solid var(--ink-rule);white-space:nowrap}',
    '.hx td{text-align:right;padding:6px 5px;border:0;border-top:1px solid var(--ink-rule);font-family:var(--f-num);white-space:nowrap;color:var(--ink-fg)}',
    '.hx th:first-child,.hx td:first-child{text-align:left;font-family:var(--f-data)}',
    '.hx td span{font-size:.68rem}.hx .up{color:var(--up-ink)}.hx .down{color:var(--down-ink)}.hx .mut{color:var(--ink-muted)}',
    '.hx-note{margin:0;padding:6px 14px 10px;font-size:.7rem;color:var(--ink-muted);border-top:1px solid var(--ink-rule)}',
    '.ab-t .hx-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-left:6px;vertical-align:middle;background:var(--ink-rule)}',
    '.ab-t .hx-dot.ok{background:var(--down-ink)}.ab-t .hx-dot.bad{background:var(--warn,#f0b54a)}'
  ].join('\n');
  document.head.appendChild(css);

  var box = document.createElement('section');
  box.className = 'hx';
  box.setAttribute('aria-label', '近期評分與倉位');
  box.innerHTML = '<div class="hx-top"><div class="hx-title">近期評分與倉位</div><button class="hx-badge" type="button" aria-expanded="false" hidden></button></div>' +
    '<ul class="hx-checks" hidden></ul><div class="hx-body"><p class="hx-msg">讀取歷史紀錄…</p></div>';
  var anchor = head.querySelector('.verdict');
  (anchor || head.lastElementChild).insertAdjacentElement('afterend', box);

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); }
  function md(d) { var p = String(d).split('-'); return (+p[1]) + '/' + (+p[2]); }
  function num(v, k) { return v == null ? '—' : Number(v).toLocaleString('en-US', {minimumFractionDigits: k, maximumFractionDigits: k}); }
  function cls(x) { return x > 0 ? 'up' : x < 0 ? 'down' : 'mut'; }
  function delta(cur, prev, unit) {
    if (cur == null || prev == null || cur === prev) return '';
    var x = cur - prev;
    return ' <span class="' + cls(x) + '">' + (x > 0 ? '▲' : '▼') + Math.abs(x) + (unit || '') + '</span>';
  }
  function get(path) {
    return fetch(path + '?t=' + Date.now(), {cache: 'no-store'}).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }

  get('data/history.json').then(function (h) {
    var rows = (h.rows || []).slice();
    var body = box.querySelector('.hx-body');
    if (!rows.length) { body.innerHTML = '<p class="hx-msg">還沒有歷史紀錄。</p>'; return; }
    var last = rows[rows.length - 1];
    var bars = rows.slice(-20);
    var html = '<div class="hx-bars" role="img" aria-label="最近 ' + bars.length + ' 個交易日的建議倉位">' +
      bars.map(function (r, i) {
        return '<span class="' + (i === bars.length - 1 ? 'last' : '') + '" style="height:' + Math.max(4, +r.pos || 0) + '%" title="' +
          esc(md(r.d) + '：評分 ' + r.score + '/10，倉位 ' + r.pos + '%') + '"></span>';
      }).join('') + '</div>' +
      '<div class="hx-axis"><span>' + esc(md(bars[0].d)) + '</span><span>建議倉位（%）</span><span>' + esc(md(last.d)) + '</span></div>';
    var recent = rows.slice(-7).reverse();
    html += '<div class="hx-wrap"><table><thead><tr><th>日期</th><th>評分</th><th>倉位</th><th>VIX</th><th>期限差</th><th>S&amp;P</th></tr></thead><tbody>' +
      recent.map(function (r) {
        var p = rows[rows.indexOf(r) - 1];
        var spx = p && p.spx ? (r.spx / p.spx - 1) * 100 : null;
        return '<tr><td>' + esc(md(r.d)) + '</td>' +
          '<td>' + esc(r.score) + delta(r.score, p && p.score) + '</td>' +
          '<td>' + esc(r.pos) + '%' + delta(r.pos, p && p.pos, '%') + '</td>' +
          '<td>' + num(r.vix, 2) + '</td>' +
          '<td class="' + (r.spread < 0 ? 'up' : '') + '">' + (r.spread == null ? '—' : (r.spread > 0 ? '+' : '') + num(r.spread, 2)) + '</td>' +
          '<td class="' + cls(spx) + '">' + (spx == null ? '—' : (spx > 0 ? '+' : '') + spx.toFixed(2) + '%') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
    var note = '每個美股交易日一列，由日報自動記錄。期限差＝VIX3M − VIX，轉負即逆價差。';
    if (pageDate && last.d < pageDate) note = '歷史紀錄只到 ' + md(last.d) + '，日報已是 ' + md(pageDate) + '，下次更新會補上。';
    if (rows.some(function (r) { return r.src === '前日回推'; })) note += '標「前日回推」的列取自隔日日報的前日數字。';
    body.innerHTML = html + '<p class="hx-note">' + esc(note) + '</p>';
  }).catch(function () {
    box.querySelector('.hx-body').innerHTML = '<p class="hx-msg">目前讀不到歷史紀錄（離線或尚未建立）。</p>';
  });

  get('data/status.json').then(function (s) {
    var btn = box.querySelector('.hx-badge'), list = box.querySelector('.hx-checks');
    var fresh = pageDate && s.date === pageDate;
    var fails = (s.checks || []).filter(function (c) { return c.state === 'fail'; }).length;
    var t = s.checked_at ? s.checked_at.slice(5, 16).replace('-', '/').replace('T', ' ') : '';
    var state = !fresh ? '' : fails ? 'bad' : 'ok';
    btn.className = 'hx-badge ' + state;
    btn.textContent = !fresh ? '今日尚未核對' : fails ? '⚠ ' + fails + ' 項異常' : '✓ 已核對 ' + t;
    btn.hidden = false;
    list.innerHTML = '<li class="mut"><b>時間</b><span>' + esc(t || '—') + '（資料日 ' + esc(s.date ? md(s.date) : '—') + '）</span></li>' +
      (s.checks || []).map(function (c) {
        return '<li class="' + esc(c.state) + '"><b>' + (c.state === 'ok' ? '通過' : c.state === 'fail' ? '異常' : '略過') + '</b><span>' +
          esc(c.name) + '：' + esc(c.detail) + '</span></li>';
      }).join('');
    if (state === 'bad') { list.hidden = false; btn.setAttribute('aria-expanded', 'true'); }
    btn.addEventListener('click', function () {
      list.hidden = !list.hidden;
      btn.setAttribute('aria-expanded', String(!list.hidden));
    });
    var tag = document.querySelector('.appbar .ab-t span');
    if (tag && state) {
      var dot = document.createElement('i');
      dot.className = 'hx-dot ' + state;
      dot.setAttribute('aria-hidden', 'true');
      dot.title = fails ? fails + ' 項異常' : '已核對';
      tag.appendChild(dot);
    }
  }).catch(function () {});
})();
