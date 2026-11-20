#!/usr/bin/env python3
"""Generate the Install Checklist page that accompanies the import packages.

Output is one self-contained .html file with tick boxes, tailored to this
build: the real package file names in import order, the connections each
package asks for, the lists flow 0 creates, the values still to set after
import, and the test cases. Ticks are remembered in the user's browser.

Deliver it as an artifact when the session can publish one (so the user gets a
link they can keep open beside Power Automate); otherwise present the file.

Usage:
  python make_install_checklist.py flow_0.json flow_1.json ... \
      --title "Purchase Requests" --site https://tenant.sharepoint.com/sites/X \
      [--lists lists.json] [--extras extras.json] [--set KEY=VALUE ...] \
      --out /mnt/user-data/outputs/Install_Checklist.html

Pass the same flow files, in the same order, and the same --set values as
build_package.py, so file names and leftover placeholders match the zips.

extras.json (optional, all keys optional):
{
  "coOwner": "name@company.com",
  "values": [{"flow": "…", "action": "…", "field": "…", "value": "…"}],
  "tests":  [{"do": "Create an item with …", "expect": "Approval email within 2 minutes"}],
  "notes":  ["Emails are sent from the owner's mailbox."]
}
"""
import argparse
import html
import json
import re
import sys

KNOWN = {
    "shared_sharepointonline": "SharePoint", "shared_office365": "Office 365 Outlook",
    "shared_office365users": "Office 365 Users", "shared_teams": "Microsoft Teams",
    "shared_approvals": "Approvals", "shared_onedriveforbusiness": "OneDrive for Business",
    "shared_excelonlinebusiness": "Excel Online (Business)", "shared_planner": "Planner",
    "shared_microsoftforms": "Microsoft Forms",
}


def safe_filename(name):  # must match build_package.py
    name = re.sub(r"[^\w\- ]+", "", name).strip().replace(" ", "_")
    return (name[:80] or "flow") + ".zip"


def connectors(node, found):
    if isinstance(node, dict):
        host = node.get("host")
        if isinstance(host, dict) and host.get("apiId"):
            short = host["apiId"].rsplit("/", 1)[-1]
            found.add(KNOWN.get(short, short.replace("shared_", "")))
        for v in node.values():
            connectors(v, found)
    elif isinstance(node, list):
        for v in node:
            connectors(v, found)
    return found


def placeholders(defn, sets):
    text = json.dumps(defn, ensure_ascii=False)
    for k, v in sets.items():
        text = text.replace(f"<<{k}>>", v)
    return sorted(set(re.findall(r"<<([^<>]+)>>", text)))


def trigger_kind(defn):
    trig = next(iter(defn.get("triggers", {}).values()), {})
    if trig.get("type") == "Recurrence":
        return "schedule"
    if trig.get("kind") == "Button":
        return "manual"
    return "automatic"


def e(s):
    return html.escape(str(s).replace("'", "’"), quote=True)


PAGE = """<!DOCTYPE html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>__TITLE__: install checklist</title>
<style>
:root{--bg:#F3F5F6;--surface:#FFFFFF;--ink:#1E262C;--muted:#56636C;--slate:#5F7482;--tint:#E3E7EA;--accent:#BC1818;--line:#D2D1D7;--ok:#2E6B45;--focus:#1C4E80;
 box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#151A1E;--surface:#1E252A;--ink:#E8ECEE;--muted:#A3B0B8;--slate:#93A6B3;--tint:#2A343B;--accent:#EC6A60;--line:#37424A;--ok:#7BC495;--focus:#8DBBEA}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#151A1E;--surface:#1E252A;--ink:#E8ECEE;--muted:#A3B0B8;--slate:#93A6B3;--tint:#2A343B;--accent:#EC6A60;--line:#37424A;--ok:#7BC495;--focus:#8DBBEA}
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{margin:0;background:var(--bg);color:var(--ink);font-family:Arial,"Helvetica Neue",Helvetica,sans-serif;font-size:16px;line-height:1.5}
.wrap{max-width:780px;margin:0 auto;padding:28px 20px 72px}
h1{font-size:1.6rem;line-height:1.2;margin:0 0 6px}
.lede{margin:0 0 4px;color:var(--muted)}
.site{margin:0;font-size:.9rem;color:var(--muted);word-break:break-all}
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--bg);padding:14px 0 10px;margin-top:14px;border-bottom:2px solid var(--line);display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.track{flex:1;min-width:140px;height:10px;background:var(--tint);border-radius:5px;overflow:hidden}
.fill{height:100%;width:0;background:var(--ok)}
.count{font-weight:700;white-space:nowrap}
button{font:inherit;font-weight:700;border-radius:4px;padding:6px 12px;cursor:pointer;border:1px solid var(--slate);background:var(--surface);color:var(--ink)}
button:focus-visible,input:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
h2{font-size:1.1rem;margin:30px 0 4px;display:flex;gap:10px;align-items:baseline}
h2 .n{flex:none;display:inline-block;width:1.7em;height:1.7em;line-height:1.7em;text-align:center;border-radius:50%;background:var(--slate);color:var(--surface);font-size:.85rem}
h2.done .n{background:var(--ok)}
p.why{margin:0 0 10px;color:var(--muted);font-size:.93rem}
.file{display:inline-block;font-family:"Courier New",Courier,monospace;font-size:.88rem;background:var(--tint);padding:2px 7px;border-radius:3px;word-break:break-all}
ol.steps{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--line);border-radius:4px}
ol.steps li{border-bottom:1px solid var(--line)}
ol.steps li:last-child{border-bottom:0}
ol.steps label{display:flex;gap:12px;padding:11px 14px;cursor:pointer}
ol.steps input{margin-top:5px;flex:none;width:17px;height:17px;accent-color:var(--ok)}
ol.steps input:checked + span{color:var(--muted);text-decoration:line-through}
ol.steps small{display:block;color:var(--muted);text-decoration:none}
.note{background:var(--surface);border:1px solid var(--line);border-left:5px solid var(--accent);padding:12px 14px;border-radius:2px;margin-top:26px;font-size:.93rem}
.note ul{margin:6px 0 0;padding-left:18px}
.finish{display:none;margin-top:26px;padding:14px 16px;border:2px solid var(--ok);border-radius:4px;font-weight:700;color:var(--ok)}
.finish.on{display:block}
footer{margin-top:36px;color:var(--muted);font-size:.85rem}
@media print{.bar button{display:none}.bar{position:static}}
</style></head><body><div class="wrap">
<h1>__TITLE__: install checklist</h1>
<p class="lede">Work top to bottom. Tick each step as you finish it. Your ticks stay in this browser.</p>
__SITE__
<div class="bar"><div class="track" aria-hidden="true"><div class="fill" id="fill"></div></div><span class="count" id="count" role="status"></span><button type="button" id="reset">Clear ticks</button></div>
__BODY__
<div class="finish" id="finish">All steps done. File the Build Sheet with your test results as the change record.</div>
__NOTES__
<footer>Generated by the Power Automate Builder skill on __DATE__. Packages are validated by script; your import and tests are what prove they work. Claude never needs your password.</footer>
</div>
<script>
(function(){
  var KEY = 'pab-install-__KEY__';
  var boxes = Array.prototype.slice.call(document.querySelectorAll('ol.steps input'));
  var state = {};
  try { state = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { state = {}; }
  function save(){ try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
  function paint(){
    var done = boxes.filter(function(b){ return b.checked; }).length;
    document.getElementById('count').textContent = done + ' of ' + boxes.length + ' done';
    document.getElementById('fill').style.width = (boxes.length ? Math.round(done / boxes.length * 100) : 0) + '%';
    document.getElementById('finish').classList.toggle('on', boxes.length > 0 && done === boxes.length);
    Array.prototype.forEach.call(document.querySelectorAll('section'), function(s){
      var all = s.querySelectorAll('input'), ok = s.querySelectorAll('input:checked');
      s.querySelector('h2').classList.toggle('done', all.length > 0 && all.length === ok.length);
    });
  }
  boxes.forEach(function(b){
    b.checked = !!state[b.id];
    b.addEventListener('change', function(){ state[b.id] = b.checked; save(); paint(); });
  });
  document.getElementById('reset').addEventListener('click', function(){
    state = {}; save(); boxes.forEach(function(b){ b.checked = false; }); paint();
  });
  paint();
})();
</script></body></html>
"""


def build(args):
    sets = {}
    for item in args.set or []:
        k, _, v = item.partition("=")
        sets[k.strip()] = v
    flows = []
    for path in args.flows:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        name = doc.get("displayName", path)
        flows.append({
            "name": name, "zip": safe_filename(name),
            "conns": sorted(connectors(doc["definition"], set())),
            "left": placeholders(doc["definition"], sets),
            "kind": trigger_kind(doc["definition"]),
            "provision": bool(re.search(r"provision", name, re.I)),
        })
    extras = {}
    if args.extras:
        with open(args.extras, encoding="utf-8") as f:
            extras = json.load(f)
    lists = []
    if args.lists:
        with open(args.lists, encoding="utf-8") as f:
            lists = [(l["title"], len(l.get("columns", []))) for l in json.load(f).get("lists", [])]

    all_conns = sorted({c for fl in flows for c in fl["conns"]})
    sections, counter = [], [0]

    def step(text, small=""):
        counter[0] += 1
        sid = f"s{counter[0]}"
        extra = f"<small>{small}</small>" if small else ""
        return f'<li><label><input type="checkbox" id="{sid}"><span>{text}{extra}</span></label></li>'

    def section(title, why, steps):
        n = len(sections) + 1
        sections.append(f'<section><h2><span class="n">{n}</span><span>{title}</span></h2>'
                        f'<p class="why">{why}</p><ol class="steps">{"".join(steps)}</ol></section>')

    section("Before you start", "Five minutes here saves a failed import.", [
        step("Sign in to make.powerautomate.com with your work account."),
        step("Check the environment name at the top right is the one your team uses."),
        step("Open Connections and confirm you have a working connection for each of these: <b>"
             + e(", ".join(all_conns) or "none needed") + "</b>.",
             "If one is missing, select New connection, pick it and sign in."),
        step(f"Save the {len(flows)} package file{'s' if len(flows) != 1 else ''} to your computer. Do not unzip them."),
    ] + ([step("Confirm you can edit the SharePoint site.", e(args.site))] if args.site else []))

    for fl in flows:
        conn_text = ", ".join(fl["conns"]) or "no connections"
        steps = [
            step("Select My flows, then Import, then Import Package (Legacy)."),
            step(f'Select Upload and choose <span class="file">{e(fl["zip"])}</span>.', "Wait for the package details to appear."),
            step("Leave the flow row on “Create as new”.", "Choose Update only when replacing a flow you imported before."),
            step(f"For each connection row ({e(conn_text)}), choose Select during import, pick your connection, then Save.",
                 "A red mark on a row means it is not set yet."),
            step("Select Import. When it finishes, select Open flow."),
        ]
        if fl["provision"]:
            steps += [
                step("Select Run, then Run flow.", "This creates the lists. It makes no other change."),
                step("Open the run and confirm the list steps are green.",
                     "On a second run, red steps named Add_… only mean the column already existed."),
            ]
            if lists:
                steps.append(step("On the SharePoint site, check these lists now exist: <b>"
                                  + e(", ".join(f"{t} ({n} columns)" for t, n in lists)) + "</b>."))
            else:
                steps.append(step("On the SharePoint site, check the new lists and their columns."))
            steps.append(step("Switch this flow off or delete it. It is no longer needed."))
        else:
            if "SharePoint" in fl["conns"]:
                steps.append(step("Open each SharePoint action and confirm Site Address and List Name show values, not errors.",
                                  "If one shows an error, reselect it from the drop-down."))
            for ph in fl["left"]:
                steps.append(step(f"Set the value marked <b>{e(ph)}</b> in the flow.", "It was left open on purpose. See the Build Sheet."))
            for v in [v for v in extras.get("values", []) if v.get("flow") in (fl["name"], None, "")]:
                steps.append(step(f"In “{e(v.get('action', ''))}”, set {e(v.get('field', ''))} to <b>{e(v.get('value', ''))}</b>."))
            steps += [
                step("Select Save and clear any Flow checker errors."),
                step("On the flow’s details page, select Turn on.", "Imported flows can arrive switched off."),
                step("Select Share and add your co-owner"
                     + (f" (<b>{e(extras['coOwner'])}</b>)" if extras.get("coOwner") else "") + " with edit rights."),
            ]
        section(e(fl["name"]), ("This one creates the lists. Import it first." if fl["provision"]
                                else "Import, check, switch on, share."), steps)

    tests = extras.get("tests") or []
    tsteps = [step(e(t.get("do", "")), "Expect: " + e(t.get("expect", ""))) for t in tests]
    if not tsteps:
        for fl in [f for f in flows if not f["provision"]]:
            how = {"automatic": "Create a real test item or file that should start it, with yourself as approver and recipient.",
                   "schedule": "On the flow’s page select Run to trigger it once without waiting for the schedule.",
                   "manual": "On the flow’s page select Run."}[fl["kind"]]
            tsteps.append(step(f"Test “{e(fl['name'])}”. {how}", "Then open the run history. Allow a minute or two for SharePoint triggers."))
        tsteps.append(step("Test every branch, including a rejection."))
    tsteps += [
        step("Cause one failure on purpose and confirm the failure alert email arrives.", "For example, leave the approver empty."),
        step("Replace test people with the real ones only after every test passes."),
        step("Record the results in the Build Sheet and file it as the change record."),
    ]
    section("Test and sign off", "A flow is finished when its tests pass, not when it imports.", tsteps)

    notes = extras.get("notes") or []
    notes_html = ('<div class="note"><b>Good to know</b><ul>' + "".join(f"<li>{e(n)}</li>" for n in notes) + "</ul></div>") if notes else ""
    from datetime import date
    key = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-") or "build"
    out = (PAGE.replace("__TITLE__", e(args.title)).replace("__BODY__", "\n".join(sections))
           .replace("__SITE__", f'<p class="site">Site: {e(args.site)}</p>' if args.site else "")
           .replace("__NOTES__", notes_html).replace("__DATE__", date.today().strftime("%d/%m/%Y"))
           .replace("__KEY__", key))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote {args.out}: {len(sections)} sections, {counter[0]} tick boxes.")
    if not tests:
        print("NOTE: no extras.json tests given, so generic test steps were used. Supply the Build Sheet test cases for a better page.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("flows", nargs="+")
    ap.add_argument("--title", required=True)
    ap.add_argument("--site", default="")
    ap.add_argument("--lists")
    ap.add_argument("--extras")
    ap.add_argument("--set", action="append")
    ap.add_argument("--out", default="Install_Checklist.html")
    build(ap.parse_args())
