#!/usr/bin/env python3
"""Generate a self-contained, read-only wine cellar browser from cellar.jsonl.

The JSONL path follows the installed skill's WINE_CELLAR_PATH compatibility
contract. Output is written beside that file as cellar-view.html and to the
repository root as index.html for GitHub Pages.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from schema import needs_review


def resolve_cellar_path() -> Path:
    env = os.environ.get("WINE_CELLAR_PATH")
    if env:
        return Path(env).expanduser()
    repo_path = Path(__file__).resolve().parents[2] / "cellar.jsonl"
    if repo_path.exists():
        return repo_path
    cfg_path = Path.home() / ".claude" / "skills" / "wine-cellar" / ".local-config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text())
            repo_path = cfg.get("repo_path")
            if repo_path:
                return Path(repo_path) / "cellar.jsonl"
        except (json.JSONDecodeError, OSError) as e:
            print(f"ERROR: could not read {cfg_path}: {e}", file=sys.stderr)
            sys.exit(2)
    print(
        "ERROR: cellar.jsonl path not configured.\n"
        "  Run `bash <repo>/skill/scripts/sync_skill.sh` to set it up,\n"
        "  or set WINE_CELLAR_PATH env var.",
        file=sys.stderr,
    )
    sys.exit(2)


def source_commit(repo_dir: Path) -> str:
    supplied = (
        os.environ.get("SOURCE_COMMIT")
        or os.environ.get("WINE_CELLAR_COMMIT")
        or os.environ.get("GITHUB_SHA")
    )
    if supplied:
        return supplied[:12]
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_dir), "rev-parse", "--short=12", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip() or "unavailable"
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def load_rows(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("expected a JSON object")
                rows.append(row)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"ERROR: line {line_number} of cellar.jsonl is invalid: {e}", file=sys.stderr)
                return None
    return rows


def main() -> int:
    cellar_path = resolve_cellar_path()
    if not cellar_path.exists():
        print(f"ERROR: cellar file not found: {cellar_path}", file=sys.stderr)
        return 2
    rows = load_rows(cellar_path)
    if rows is None:
        return 2

    # Give every source row a local stable key while preserving backend IDs
    # whenever present. The fallback is for older installations and rows.
    for index, row in enumerate(rows):
        row.setdefault("_view_id", str(row.get("bottle_id") or f"legacy-{index + 1}"))
        row["_needs_review"] = needs_review(row)

    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    # Prevent a wine name or note from ending the JSON script element.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    commit = source_commit(cellar_path.parent)
    html = PAGE.replace("__ROWS__", payload).replace("__GENERATED__", escape(generated)).replace(
        "__COMMIT__", escape(commit)
    )

    view_path = cellar_path.parent / "cellar-view.html"
    view_path.write_text(html, encoding="utf-8")
    index_path = cellar_path.parent / "index.html"
    index_path.write_text(INDEX, encoding="utf-8")
    print(f"Generated {view_path} and {index_path} from {len(rows)} bottle records.")
    return 0


INDEX = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url=cellar-view.html"><title>Wine Cellar</title>
<link rel="canonical" href="cellar-view.html"></head><body><p>Opening the <a href="cellar-view.html">Wine Cellar</a>…</p>
<script>location.replace(new URL('cellar-view.html', location.href).href);</script></body></html>
"""


PAGE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f8f5ef">
<title>Wine Cellar</title>
<style>
:root{color-scheme:light;--bg:#f8f5ef;--paper:#fffefa;--ink:#211c19;--muted:#5c514b;--line:#d8cec3;--wine:#762f35;--wine-dark:#542127;--gold:#80520b;--gold-bg:#fbf0d6;--blue:#1e5065;--green:#28613f;--shadow:0 4px 18px #3826190d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
main{max-width:1160px;margin:auto;padding:clamp(16px,4vw,38px)}header{margin-bottom:20px}h1{font-family:Georgia,serif;font-size:clamp(2rem,7vw,3.1rem);line-height:1.08;letter-spacing:-.035em;color:var(--wine-dark);margin:0 0 7px}.subhead{color:var(--muted);margin:0}
.summary{display:flex;flex-wrap:wrap;gap:8px 20px;margin:18px 0 22px;padding:12px 15px;background:var(--paper);border:1px solid var(--line);border-radius:12px;color:var(--muted);box-shadow:var(--shadow)}.summary strong{color:var(--ink);font-variant-numeric:tabular-nums}
.controls{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:end;margin-bottom:13px}.search label,.sort-wrap label{display:block;font-size:.82rem;font-weight:700;color:var(--muted);margin:0 0 5px}.search input,.sort-wrap select{min-height:46px;border:1px solid #94877c;border-radius:9px;background:white;color:var(--ink);font:inherit;padding:9px 12px}.search input{width:100%}.sort-wrap select{max-width:100%}input:focus-visible,select:focus-visible,button:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid #176b8e;outline-offset:2px}
.tabs{display:flex;overflow:auto;gap:7px;padding:2px 2px 10px;scrollbar-width:thin}.tab{flex:0 0 auto;border:1px solid #8e8177;border-radius:999px;background:var(--paper);color:var(--ink);min-height:42px;padding:8px 13px;font:inherit;font-weight:600;font-size:.9rem;cursor:pointer}.tab[aria-pressed="true"]{background:var(--wine);border-color:var(--wine);color:white}.tab:hover{border-color:var(--wine);color:var(--wine-dark)}.tab[aria-pressed="true"]:hover{color:white}
.result-line{color:var(--muted);font-size:.9rem;margin:2px 0 12px}.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,330px),1fr));gap:12px}.card{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);overflow:hidden;min-width:0}.card.needs-review{border-left:5px solid #a56b11}.card-top{padding:15px 16px 13px}.wine-name{font:600 1.27rem/1.25 Georgia,serif;color:var(--wine-dark);margin:0;overflow-wrap:anywhere}.producer{color:var(--muted);font-size:.92rem;margin:3px 0 10px}.topline{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.vintage{white-space:nowrap;font-weight:700;color:var(--wine);font-size:1.05rem;font-variant-numeric:tabular-nums}.badge{display:inline-flex;align-items:center;min-height:27px;border-radius:999px;padding:3px 9px;font-size:.78rem;font-weight:700;background:#e9e2d9;color:#3c342e}.badge.available{background:#e0eddf;color:#214a2d}.badge.opened{background:#e2edf1;color:#204c5e}.badge.finished{background:#eee4e0;color:#68373b}.badge.review{background:#fbebc9;color:#624107}.facts{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px 16px;border-top:1px solid #e8e1d9}.fact{min-width:0}.fact-label{text-transform:uppercase;letter-spacing:.06em;font-size:.69rem;font-weight:750;color:var(--muted);display:block}.fact-value{display:block;font-weight:650;overflow-wrap:anywhere}.fact.region{grid-column:1/-1}.grapes{color:var(--muted);font-size:.9rem;margin:0;padding:0 16px 13px;overflow-wrap:anywhere}.grapes strong{color:var(--ink)}
.records{border-top:1px solid var(--line);background:#fcfaf6}.records>summary{list-style:none;padding:12px 16px;min-height:46px;cursor:pointer;font-weight:700;color:var(--wine-dark);display:flex;justify-content:space-between;gap:12px}.records>summary::-webkit-details-marker{display:none}.records>summary:after{content:"＋";font-size:1.1rem}.records[open]>summary:after{content:"−"}.record{margin:0 12px 12px;padding:13px;background:white;border:1px solid var(--line);border-radius:10px}.record h3{font-size:.98rem;margin:0 0 8px;overflow-wrap:anywhere}.record-meta{color:var(--muted);font-size:.83rem;margin:-4px 0 11px}.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px 13px;margin:0}.detail{min-width:0}.detail dt{font-size:.7rem;text-transform:uppercase;letter-spacing:.045em;color:var(--muted);font-weight:750}.detail dd{margin:1px 0 0;overflow-wrap:anywhere}.detail.wide{grid-column:1/-1}.history{margin:12px 0 0;padding:0;list-style:none}.history li{border-left:2px solid #c6a6a7;padding:0 0 11px 10px;margin-left:3px}.history time{display:block;color:var(--muted);font-size:.78rem;font-weight:700}.history p{margin:2px 0 0}.empty{border:1px dashed #9b8b7e;border-radius:12px;padding:24px;text-align:center;color:var(--muted);background:#fffefa}.desktop{display:none}footer{margin:24px 0 5px;padding-top:13px;border-top:1px solid var(--line);font-size:.8rem;color:var(--muted);display:flex;flex-wrap:wrap;gap:5px 16px;justify-content:space-between}.love-note{color:#765053}.love-note summary{cursor:pointer;display:inline;font-size:.8rem}.love-note p{display:inline;margin:0 0 0 5px}
@media(min-width:720px){.controls{grid-template-columns:minmax(260px,1fr) minmax(180px,auto)}.cards{grid-template-columns:repeat(auto-fill,minmax(360px,1fr))}.desktop{display:block;margin-top:24px}.desktop details{background:var(--paper);border:1px solid var(--line);border-radius:12px;overflow:hidden}.desktop summary{padding:12px 15px;font-weight:700;cursor:pointer}.table-wrap{overflow:auto;max-height:70vh}table{border-collapse:collapse;width:100%;font-size:.83rem}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}th{position:sticky;top:0;background:#eee8df;z-index:1}td{max-width:30ch;white-space:pre-wrap;overflow-wrap:anywhere}}
@media(max-width:430px){.controls{grid-template-columns:1fr}.sort-wrap select{width:100%}.summary{gap:5px 15px}.detail-grid{grid-template-columns:1fr 1fr}.card-top{padding:14px 13px 11px}.facts{padding:11px 13px}.grapes{padding:0 13px 12px}}
@media(prefers-reduced-motion:no-preference){.card{transition:box-shadow .15s ease,transform .15s ease}.card:hover{box-shadow:0 6px 22px #38261916;transform:translateY(-1px)}}
</style>
</head>
<body><main>
<header><h1>Wine Cellar</h1><p class="subhead">Recorded wines, opening targets, drinking windows, and tasting history.</p></header>
<section class="summary" id="summary" aria-label="Cellar summary" aria-live="polite"></section>
<section aria-label="Find cellar wines">
  <div class="controls"><div class="search"><label for="search">Search wines, regions, grapes, or notes</label><input id="search" type="search" autocomplete="off" placeholder="Try “Napa” or “Pinot Noir”"></div>
    <div class="sort-wrap"><label for="sort">Sort by</label><select id="sort"><option value="wine">Wine name</option><option value="vintage">Vintage, newest first</option><option value="region">Region</option><option value="opening">Target opening year</option></select></div></div>
  <div class="tabs" role="group" aria-label="Filter cellar records" id="tabs">
    <button type="button" class="tab" data-filter="available" aria-pressed="true">Recorded available <span class="tab-count">0</span></button>
    <button type="button" class="tab" data-filter="opened" aria-pressed="false">Opened <span class="tab-count">0</span></button>
    <button type="button" class="tab" data-filter="finished" aria-pressed="false">Finished <span class="tab-count">0</span></button>
    <button type="button" class="tab" data-filter="review" aria-pressed="false">Needs review <span class="tab-count">0</span></button>
    <button type="button" class="tab" data-filter="all" aria-pressed="false">All <span class="tab-count">0</span></button>
  </div>
  <p class="result-line" id="result-line" aria-live="polite"></p>
  <div class="cards" id="cards"></div><div class="desktop" id="desktop"></div>
</section>
<footer><span>Read-only view · generated __GENERATED__ · source <span id="commit">__COMMIT__</span></span>
  <details class="love-note"><summary aria-label="A small note">♥</summary><p>Andrew loves Sarah.</p></details></footer>
</main>
<script id="cellar-data" type="application/json">__ROWS__</script>
<script>
const rows=JSON.parse(document.getElementById('cellar-data').textContent);
let active='available';
const $=id=>document.getElementById(id);
const desktopQuery=matchMedia('(min-width: 720px)');
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function category(r){const s=String(r.status||'cellared').toLowerCase();if(r._needs_review)return'review';if(['love','like','meh','pass','finished'].includes(s))return'finished';if(s==='opened'||r.opened_on)return'opened';if(['pending','cellared'].includes(s)&&!r.opened_on)return'available';return'review'}
function isAvailable(r){return['pending','cellared'].includes(String(r.status||'cellared').toLowerCase())&&!r.opened_on}
function isFinished(r){return['love','like','meh','pass','finished'].includes(String(r.status||'').toLowerCase())}
function isOpened(r){return!isFinished(r)&&(String(r.status||'').toLowerCase()==='opened'||Boolean(r.opened_on))}
function inFilter(r,filter){if(filter==='all')return true;if(filter==='available')return isAvailable(r);if(filter==='review')return Boolean(r._needs_review)||category(r)==='review';if(filter==='opened')return isOpened(r);return isFinished(r)}
function displayStatus(r){const c=category(r);return c==='available'?(r.status==='pending'?'Needs opening year':'Available'):c==='opened'?'Opened':c==='finished'?(r.status==='finished'?'Finished':r.status==='love'?'Loved':r.status==='like'?'Liked':r.status==='meh'?'Finished · mixed':'Finished · passed'):'Needs review'}
function windowText(r){const a=r.drink_from,b=r.drink_by;return a&&b?`${a}–${b}`:'Unknown'}
function openingText(r){return r.cellared_under||'Not set'}
function groupKey(r){return`${r.wine||'Unknown wine'}\u0000${r.vintage??'Unknown'}`}
function groupRows(list){const groups=new Map();for(const r of list){const k=groupKey(r);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r)}return [...groups.values()]}
function yearSummary(group,key){const years=[...new Set(group.map(r=>r[key]).filter(v=>v!==null&&v!==undefined&&v!==''))].map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!years.length)return'Not set';const value=years.length===1?String(years[0]):`${years[0]}–${years[years.length-1]}`;return group.some(r=>r[key]===null||r[key]===undefined||r[key]==='')?`${value} · some not set`:value}
function windowSummary(group){const windows=[...new Set(group.filter(r=>r.drink_from&&r.drink_by).map(r=>`${r.drink_from}:${r.drink_by}`))].map(v=>v.split(':').map(Number));if(!windows.length)return'Unknown';const start=Math.min(...windows.map(w=>w[0])),end=Math.max(...windows.map(w=>w[1]));const value=`${start}–${end}`;return group.some(r=>!r.drink_from||!r.drink_by)?`${value} · some unknown`:value}
function groupStats(group){const key=groupKey(group[0]),all=rows.filter(r=>groupKey(r)===key),available=all.filter(isAvailable).length;return{available,shown:group.length,total:all.length,all}}
function matches(r,q){return !q||JSON.stringify(r).toLocaleLowerCase().includes(q)}
function sortGroups(groups,mode){const first=g=>g[0],opening=g=>{const all=rows.filter(r=>groupKey(r)===groupKey(first(g)));return Math.min(...all.map(r=>r.cellared_under).filter(v=>v!==null&&v!==undefined&&v!=='').map(Number),Infinity)};return groups.sort((a,b)=>{let av,bv;if(mode==='vintage'){av=Number(first(a).vintage)||0;bv=Number(first(b).vintage)||0;return bv-av||String(first(a).wine).localeCompare(String(first(b).wine))}if(mode==='region'){av=first(a).region||'';bv=first(b).region||'';return av.localeCompare(bv)||String(first(a).wine).localeCompare(String(first(b).wine))}if(mode==='opening'){av=opening(a);bv=opening(b);return av-bv||String(first(a).wine).localeCompare(String(first(b).wine))}return String(first(a).wine||'').localeCompare(String(first(b).wine||''))||((Number(first(b).vintage)||0)-(Number(first(a).vintage)||0))})}
function field(label,val,wide=false){if(val===null||val===undefined||val==='')return'';if(Array.isArray(val))val=val.map(x=>typeof x==='object'?`${x.date||''} — ${x.note||''}`:x).join('; ');return`<div class="detail${wide?' wide':''}"><dt>${esc(label)}</dt><dd>${esc(val)}</dd></div>`}
const DETAIL_FIELDS=[['Bottle ID','bottle_id'],['Status','status'],['Target opening year','cellared_under'],['Drink window','__window'],['Opened on','opened_on'],['Country','country'],['Subregion','subregion'],['Estate','estate'],['Soil','soil'],['Elevation','elevation'],['Vine age','vine_age'],['Importer','importer'],['Harvest date','harvest_date'],['Fermentation vessel','fermentation_vessel'],['Whole bunch','whole_bunch_pct'],['Malolactic','malolactic'],['Barrel time','barrel_time'],['Oak origin','oak_origin'],['New oak','new_oak_pct'],['ABV','abv'],['pH','ph'],['TA','ta'],['Residual sugar','residual_sugar'],['Cases produced','cases_produced'],['Release date','release_date'],['Tasting notes','tasting_notes'],['Additional notes','fallback_tasting_notes'],['Verdict','verdict']];
function recordMarkup(r,index,count){const fields=DETAIL_FIELDS.map(([label,key])=>field(label,key==='__window'?windowText(r):r[key],['tasting_notes','fallback_tasting_notes','verdict'].includes(key))).join('');const history=(Array.isArray(r.impressions)?r.impressions:[]).map(i=>`<li><time>${esc(i.date||'Tasting note')}</time><p>${esc(i.note||'')}</p></li>`).join('');const ident=r.bottle_id?`Bottle ${r.bottle_id}`:count>1?`Bottle record ${index+1}`:'Bottle record';return`<article class="record"><h3>${esc(ident)} <span class="badge ${category(r)}">${esc(displayStatus(r))}</span></h3><p class="record-meta">${r.opened_on?`Opened ${esc(r.opened_on)}`:'Opening date not recorded'} · target ${esc(openingText(r))} · window ${esc(windowText(r))}</p><dl class="detail-grid">${fields}</dl>${history?`<h4>History</h4><ol class="history">${history}</ol>`:''}</article>`}
function cardMarkup(group){
  const r=group[0],stats=groupStats(group),cats=[...new Set(group.map(category))],cat=cats.length===1?cats[0]:'review';
  const records=group.map((x,i)=>recordMarkup(x,i,stats.total)).join('');
  const region=[...new Set(stats.all.map(x=>[x.subregion,x.region,x.country].filter(Boolean).join(' · ')).filter(Boolean))].join(' / ')||'Unknown';
  const grapes=[...new Set(stats.all.map(x=>x.grapes).filter(Boolean))].join(' / ');
  const facts=`<div class="facts"><div class="fact"><span class="fact-label">Target opening</span><span class="fact-value">${esc(yearSummary(stats.all,'cellared_under'))}</span></div><div class="fact"><span class="fact-label">Drinking window</span><span class="fact-value">${esc(windowSummary(stats.all))}</span></div><div class="fact region"><span class="fact-label">Region</span><span class="fact-value">${esc(region)}</span></div></div>`;
  const grapeLine=grapes?`<p class="grapes"><strong>Grapes:</strong> ${esc(grapes)}</p>`:'';
  const shownLabel=stats.shown===1?'record':'records',totalLabel=stats.total===1?'record':'records';
  return`<article class="card ${cat==='review'?'needs-review':''}"><div class="card-top"><div class="topline"><h2 class="wine-name">${esc(r.wine||'Unknown wine')}</h2><span class="vintage">${esc(r.vintage??'Unknown')}</span></div><p class="producer">${stats.available} available · ${stats.shown} shown of ${stats.total} recorded ${totalLabel}</p><span class="badge ${cat}">${cats.length>1?'Mixed records':esc(displayStatus(r))}</span></div>${facts}${grapeLine}<details class="records"><summary>Details &amp; history <span>(${stats.shown} ${shownLabel})</span></summary>${records}</details></article>`
}
function render(){const q=$('search').value.trim().toLocaleLowerCase();const matching=rows.filter(r=>inFilter(r,active)&&matches(r,q));const groups=sortGroups(groupRows(matching),$('sort').value);const available=rows.filter(isAvailable);const availableGroups=groupRows(available).length;const opened=rows.filter(isOpened).length;const finished=rows.filter(isFinished).length;const review=rows.filter(r=>inFilter(r,'review')).length;
$('summary').innerHTML=`<span><strong>${available.length}</strong> recorded available bottles</span><span><strong>${availableGroups}</strong> distinct wine/vintage groups</span><span><strong>${opened}</strong> opened</span><span><strong>${finished}</strong> finished</span><span><strong>${review}</strong> need review</span>`;
for(const button of $('tabs').querySelectorAll('[data-filter]')){const id=button.dataset.filter;button.setAttribute('aria-pressed',String(active===id));button.querySelector('.tab-count').textContent=rows.filter(r=>inFilter(r,id)).length}
$('result-line').textContent=`Showing ${matching.length} bottle records in ${groups.length} wine/vintage ${groups.length===1?'group':'groups'}.`;
$('cards').innerHTML=groups.map(cardMarkup).join('')||'<div class="empty">No matching bottles. Try another search or filter.</div>';
if(desktopQuery.matches)$('desktop').innerHTML=`<details><summary>Detailed table view</summary><div class="table-wrap"><table><thead><tr><th>Wine</th><th>Winery</th><th>Vintage</th><th>Grapes</th><th>Region</th><th>Status</th><th>Target opening</th><th>Drink window</th><th>Opened</th><th>Verdict</th></tr></thead><tbody>${matching.map(r=>`<tr><td>${esc(r.wine)}</td><td>${esc(r.winery)}</td><td>${esc(r.vintage??'Unknown')}</td><td>${esc(r.grapes)}</td><td>${esc([r.subregion,r.region,r.country].filter(Boolean).join(' · '))}</td><td>${esc(displayStatus(r))}</td><td>${esc(openingText(r))}</td><td>${esc(windowText(r))}</td><td>${esc(r.opened_on||'')}</td><td>${esc(r.verdict)}</td></tr>`).join('')}</tbody></table></div></details>`;else $('desktop').innerHTML='';
}
$('tabs').addEventListener('click',e=>{const button=e.target.closest('[data-filter]');if(button){active=button.dataset.filter;render()}});$('search').addEventListener('input',render);$('sort').addEventListener('change',render);desktopQuery.addEventListener('change',render);render();
</script>
</body></html>
'''


if __name__ == "__main__":
    raise SystemExit(main())
