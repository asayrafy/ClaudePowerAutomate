#!/usr/bin/env python3
"""Convert a filled Automation Intake Workbook into build inputs.

Same workbook in, same files out. Produces in --out:
    specification.md      the Flow Specification for the user to confirm
    lists.json            lists to provision (skips lists marked as existing)
    flow_<n>.json         one flow file per flow, ready for validate and package
    conversion_report.txt every assumption, warning and item needing hand-work

Usage: python intake_to_build.py Intake.xlsx --out build/
Then:  python validate_definition.py build/flow_*.json
       python make_provisioning_flow.py build/lists.json --out build/flow_0.json
       python build_package.py build/flow_*.json --out /mnt/user-data/outputs
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

from openpyxl import load_workbook

SP = "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"
OUTLOOK = "/providers/Microsoft.PowerApps/apis/shared_office365"
APPROVALS = "/providers/Microsoft.PowerApps/apis/shared_approvals"
USERS = "/providers/Microsoft.PowerApps/apis/shared_office365users"
TEAMS = "/providers/Microsoft.PowerApps/apis/shared_teams"
SCHEMA = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
TRIGGER_OPS = {
    "sharepoint item created": "GetOnNewItems",
    "sharepoint item created or modified": "GetOnUpdatedItems",
    "sharepoint file created": "GetOnNewFileItems",
}
OPS = {
    "equals": "equals", "not equals": "notequals", "greater than": "greater",
    "greater or equal": "greaterOrEquals", "less than": "less", "less or equal": "lessOrEquals",
    "contains": "contains", "starts with": "startsWith", "is empty": "isempty", "is not empty": "isnotempty",
}
TOKEN_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_.]*)\}")
# Currency code -> SharePoint locale ID (LCID). A number in the Currency cell is used as given.
CURRENCY_LCID = {
    "USD": 1033, "GBP": 2057, "EUR": 6153, "SAR": 1025, "AED": 14337, "KWD": 13313, "QAR": 16385,
    "BHD": 15361, "OMR": 8193, "EGP": 3073, "JOD": 11265, "CAD": 4105, "AUD": 3081, "NZD": 5129,
    "INR": 16393, "ZAR": 7177, "SGD": 18441, "JPY": 1041, "CNY": 2052, "CHF": 2055,
}
SETTING_FALLBACKS = {
    "Time zone": "not set; UTC is used",
    "Date format": "not set; yyyy-MM-dd is used",
    "Currency": "not set; the SharePoint site's regional currency is used",
}

report = []
uses_time_zone = []  # flows that need a time zone (schedules, {Now})


def warn(msg):
    report.append("WARNING  " + msg)


def note(msg):
    report.append("NOTE     " + msg)


def cell(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def rows(ws, ncols):
    out = []
    for r in ws.iter_rows(min_row=2, max_col=ncols, values_only=True):
        vals = [cell(v) for v in r]
        if any(vals):
            out.append(vals)
    return out


def ident(s):
    s = re.sub(r"[^A-Za-z0-9_]", "_", s.strip()).strip("_")
    return s or "Step"


def yes(v):
    return v.strip().lower() in ("yes", "y", "true", "1")


def conn(api, op, params, webhook=False):
    return {
        "type": "OpenApiConnectionWebhook" if webhook else "OpenApiConnection",
        "inputs": {
            "host": {"apiId": api, "connectionName": api.rsplit("/", 1)[-1], "operationId": op},
            "parameters": params,
            "authentication": "@parameters('$authentication')",
        },
    }


class Ctx:
    def __init__(self, process, columns, flow):
        self.process = process
        self.columns = columns          # list title -> {internal: type}
        self.flow = flow
        self.trigger_list = flow["trigger_list"]
        self.is_sp_trigger = flow["trigger"].lower().startswith("sharepoint")
        self.last_approval = None
        self.last_manager = None
        self.tz = process.get("Time zone") or "UTC"
        self.date_format = (process.get("Date format") or "yyyy-MM-dd").replace("'", "''")

    def col_type(self, lst, col):
        return self.columns.get(lst, {}).get(col)

    def token_expr(self, tok):
        parts = tok.split(".")
        head = parts[0]
        if head == "Trigger":
            if not self.is_sp_trigger:
                warn(f"Flow {self.flow['no']}: {{{tok}}} used but the trigger is not a SharePoint item or file.")
            if len(parts) == 1:
                warn(f"Flow {self.flow['no']}: {{Trigger}} needs a column, e.g. {{Trigger.Title}}.")
                return "triggerOutputs()?['body']"
            col = parts[1]
            if col == "Link":
                return "triggerOutputs()?['body/{Link}']"
            if col == "CreatedBy":
                col = "Author"
            if col == "ModifiedBy":
                col = "Editor"
            sub = parts[2] if len(parts) > 2 else None
            ctype = self.col_type(self.trigger_list, col)
            if col in ("Author", "Editor"):
                ctype = "person"
            if sub is None:
                if ctype in ("choice",):
                    sub = "Value"
                elif ctype in ("person",):
                    sub = "Email"
                elif ctype in ("lookup",):
                    sub = "Value"
            elif sub == "Name":
                sub = "DisplayName"
            if col not in ("ID", "Title", "Author", "Editor", "Created", "Modified") and ctype is None \
                    and self.trigger_list in self.columns:
                warn(f"Flow {self.flow['no']}: column '{col}' is not on the Columns sheet for "
                     f"'{self.trigger_list}'. Check the internal name.")
            return f"triggerOutputs()?['body/{col}" + (f"/{sub}']" if sub else "']")
        if head == "Approval":
            if not self.last_approval:
                warn(f"Flow {self.flow['no']}: {{{tok}}} used before any approval step.")
                return "''"
            a = self.last_approval
            field = parts[1] if len(parts) > 1 else "Outcome"
            if field == "Outcome":
                return f"body('{a}')?['outcome']"
            if field == "Comments":
                return f"first(body('{a}')?['responses'])?['comments']"
            if field == "Responder":
                return f"first(body('{a}')?['responses'])?['responder']?['email']"
        if head == "Manager":
            if not self.last_manager:
                warn(f"Flow {self.flow['no']}: {{{tok}}} used before any Get manager step.")
                return "''"
            field = parts[1] if len(parts) > 1 else "Email"
            return f"body('{self.last_manager}')?['" + ("displayName" if field == "Name" else "mail") + "']"
        if tok == "Today":
            return "utcNow('yyyy-MM-dd')"
        if tok == "Now":
            uses_time_zone.append(self.flow["no"])
            return f"convertFromUtc(utcNow(), '{self.tz}', '{self.date_format} HH:mm')"
        if tok == "Owner.Email":
            return "'" + self.process.get("Owner email", "").replace("'", "''") + "'"
        warn(f"Flow {self.flow['no']}: unknown token {{{tok}}}; left as literal text.")
        return None

    def text(self, s, html=False):
        """Text with tokens -> WDL string with @{...} interpolation."""
        if s.startswith("@"):
            s = "@" + s
        def rep(m):
            e = self.token_expr(m.group(1))
            return m.group(0) if e is None else "@{" + e + "}"
        out = TOKEN_RE.sub(rep, s)
        if html:
            out = "<p>" + out.replace("\n", "<br>") + "</p>"
        return out

    def value(self, s):
        """Single value: a lone token keeps its type; numbers become numbers."""
        m = TOKEN_RE.fullmatch(s.strip())
        if m:
            e = self.token_expr(m.group(1))
            return "@" + e if e else s
        if re.fullmatch(r"-?\d+(\.\d+)?", s.strip()):
            return float(s) if "." in s else int(s)
        return self.text(s)

    def expr(self, s):
        """Operand inside a trigger-condition expression string."""
        m = TOKEN_RE.fullmatch(s.strip())
        if m:
            return self.token_expr(m.group(1)) or "''"
        if re.fullmatch(r"-?\d+(\.\d+)?", s.strip()):
            return s.strip()
        return "'" + s.replace("'", "''") + "'"


def parse_condition(text, flow_no, step_no):
    parts = [p.strip() for p in text.split("|")]
    if len(parts) == 2 and parts[1].lower() in ("is empty", "is not empty"):
        parts.append("")
    if len(parts) != 3 or parts[1].lower() not in OPS:
        warn(f"Flow {flow_no} step {step_no}: condition '{text}' is not 'Left | operator | Right'.")
        return None
    return parts[0], OPS[parts[1].lower()], parts[2]


def condition_json(ctx, cond):
    left, op, right = cond
    L = ctx.value(left)
    R = ctx.value(right) if right != "" else ""
    if op == "isempty":
        return {"and": [{"equals": [f"@empty({ctx.expr(left)})", True]}]}
    if op == "isnotempty":
        return {"and": [{"equals": [f"@empty({ctx.expr(left)})", False]}]}
    if op == "notequals":
        return {"and": [{"not": {"equals": [L, R]}}]}
    return {"and": [{op: [L, R]}]}


def condition_expr(ctx, cond):
    left, op, right = cond
    L, R = ctx.expr(left), (ctx.expr(right) if right != "" else "''")
    if op == "isempty":
        return f"@empty({L})"
    if op == "isnotempty":
        return f"@not(empty({L}))"
    if op == "notequals":
        return f"@not(equals({L}, {R}))"
    return f"@{op}({L}, {R})"


def field_params(ctx, lst, spec, flow_no, step_no):
    params = {}
    if not spec:
        return params
    for pair in [p for p in re.split(r";(?![^{]*\})", spec) if p.strip()]:
        if "=" not in pair:
            warn(f"Flow {flow_no} step {step_no}: field value '{pair.strip()}' has no '='.")
            continue
        col, val = [x.strip() for x in pair.split("=", 1)]
        ctype = ctx.col_type(lst, col)
        if ctype is None:
            warn(f"Flow {flow_no} step {step_no}: column '{col}' not on the Columns sheet for '{lst}'; written as plain text.")
        if ctype == "choice":
            params[f"item/{col}/Value"] = ctx.text(val)
        elif ctype == "person":
            params[f"item/{col}/Claims"] = "i:0#.f|membership|" + ctx.text(val)
        elif ctype == "lookup":
            params[f"item/{col}/Id"] = ctx.value(val)
        elif ctype == "boolean":
            params[f"item/{col}"] = yes(val) if not TOKEN_RE.fullmatch(val) else ctx.value(val)
        elif ctype in ("number", "currency"):
            params[f"item/{col}"] = ctx.value(val)
        elif ctype in ("multichoice", "personmulti"):
            warn(f"Flow {flow_no} step {step_no}: multi-value column '{col}' needs hand-editing after conversion.")
            params[f"item/{col}"] = ctx.text(val)
        else:
            params[f"item/{col}"] = ctx.text(val)
    return params


def build_step(ctx, st, site, names):
    t = st["type"].lower()
    fno, sno = st["flow"], st["no"]
    name = st["action"]
    to = st["to"]
    if t.startswith("start approval"):
        if not to:
            warn(f"Flow {fno} step {sno}: approval has no 'To / Assigned to'.")
        p = {
            "approvalType": "BasicAwaitAll" if "everyone" in t else "Basic",
            "WebhookApprovalCreationInput/title": ctx.text(st["subject"] or "Approval request"),
            "WebhookApprovalCreationInput/assignedTo": ctx.text(to or "<<APPROVER_EMAIL>>"),
            "WebhookApprovalCreationInput/details": ctx.text(st["body"]),
            "WebhookApprovalCreationInput/enableNotifications": True,
            "WebhookApprovalCreationInput/enableReassignment": True,
        }
        if ctx.is_sp_trigger:
            p["WebhookApprovalCreationInput/itemLink"] = "@{triggerOutputs()?['body/{Link}']}"
            p["WebhookApprovalCreationInput/itemLinkDescription"] = "Open the item"
        act = conn(APPROVALS, "StartAndWaitForAnApproval", p, webhook=True)
        ctx.last_approval = name
        return act
    if t == "condition":
        cond = parse_condition(st["condition"], fno, sno)
        expr = condition_json(ctx, cond) if cond else {"and": [{"equals": [True, True]}]}
        return {"type": "If", "expression": expr, "actions": {}, "else": {"actions": {}}}
    if t in ("update item", "create item"):
        lst = st["list"] or ctx.trigger_list
        if not lst:
            warn(f"Flow {fno} step {sno}: no Target list.")
        p = {"dataset": site, "table": lst or "<<LIST>>"}
        if t == "update item":
            p["id"] = ctx.value(st["item"] or "{Trigger.ID}")
        p.update(field_params(ctx, lst, st["fields"], fno, sno))
        return conn(SP, "PatchItem" if t == "update item" else "PostItem", p)
    if t == "send email":
        return conn(OUTLOOK, "SendEmailV2", {
            "emailMessage/To": ctx.text(to or "<<EMAIL_TO>>"),
            "emailMessage/Subject": ctx.text(st["subject"]),
            "emailMessage/Body": ctx.text(st["body"], html=True),
            "emailMessage/Importance": "Normal",
        })
    if t == "post to teams channel":
        team, chan = (to.split("|", 1) + [""])[:2] if to else ("", "")
        if not to:
            note(f"Flow {fno} step {sno}: Teams team and channel must be selected after import.")
        return conn(TEAMS, "PostMessageToConversation", {
            "poster": "Flow bot", "location": "Channel",
            "body/recipient/groupId": team.strip() or "<<TEAM_ID>>",
            "body/recipient/channelId": chan.strip() or "<<CHANNEL_ID>>",
            "body/messageBody": ctx.text(st["body"], html=True),
        })
    if t == "get manager":
        act = conn(USERS, "Manager_V2", {"id": ctx.text(to or "{Trigger.CreatedBy.Email}")})
        ctx.last_manager = name
        return act
    if t == "delay":
        m = re.match(r"\s*(\d+)\s*(second|minute|hour|day|week|month)s?", st["subject"], re.I)
        if not m:
            warn(f"Flow {fno} step {sno}: delay duration '{st['subject']}' not understood; defaulting to 1 Day.")
            count, unit = 1, "Day"
        else:
            count, unit = int(m.group(1)), m.group(2).capitalize()
        return {"type": "Wait", "inputs": {"interval": {"count": count, "unit": unit}}}
    note(f"Flow {fno} step {sno} '{st['name']}' is Custom: Claude must write it by hand. Brief: {st['notes'] or '(none)'}")
    return {"type": "Compose", "inputs": f"CUSTOM STEP TO BUILD: {st['notes'] or st['name']}",
            "description": "Placeholder from the intake workbook. Replace before use."}


def build_flow(process, columns, flow, steps):
    site = process.get("SharePoint site URL") or "<<SITE_URL>>"
    ctx = Ctx(process, columns, flow)
    trig_type = flow["trigger"].lower()
    if trig_type in TRIGGER_OPS:
        trig = conn(SP, TRIGGER_OPS[trig_type], {"dataset": site, "table": flow["trigger_list"] or "<<LIST>>"})
        trig["recurrence"] = {"interval": 1, "frequency": "Minute"}
        trig["splitOn"] = "@triggerOutputs()?['body/value']"
        if flow["condition"]:
            cond = parse_condition(flow["condition"], flow["no"], "trigger")
            if cond:
                trig["conditions"] = [{"expression": condition_expr(ctx, cond)}]
        elif trig_type == "sharepoint item created or modified" and any(
                s["type"].lower() == "update item" and (s["list"] or flow["trigger_list"]) == flow["trigger_list"]
                for s in steps):
            warn(f"Flow {flow['no']}: 'created or modified' trigger updates its own list with no trigger condition. "
                 "This loops. Add a Trigger condition (e.g. {Trigger.Status} | equals | Submitted).")
        triggers = {ident(flow["trigger"]): trig}
    elif trig_type == "schedule":
        uses_time_zone.append(flow["no"])
        rec = {"frequency": flow["freq"] or "Day", "interval": int(flow["interval"] or 1), "timeZone": ctx.tz}
        sched = {}
        if flow["days"]:
            sched["weekDays"] = [d.strip().capitalize() for d in flow["days"].split(";") if d.strip()]
        if flow["time"]:
            hh, _, mm = flow["time"].partition(":")
            sched["hours"] = [str(int(hh))]
            sched["minutes"] = [int(mm or 0)]
        if sched:
            rec["schedule"] = sched
        triggers = {"Recurrence": {"type": "Recurrence", "recurrence": rec}}
    else:
        if trig_type != "manual button":
            warn(f"Flow {flow['no']}: unknown trigger '{flow['trigger']}'; using a manual button.")
        triggers = {"manual": {"type": "Request", "kind": "Button",
                               "inputs": {"schema": {"type": "object", "properties": {}, "required": []}}}}

    # Unique action names in step order.
    used = set(triggers)
    for st in sorted(steps, key=lambda s: s["no_num"]):
        base = ident(st["name"] or f"Step_{st['no']}")[:70]
        name, k = base, 2
        while name in used:
            name, k = f"{base}_{k}", k + 1
        used.add(name)
        st["action"] = name

    by_no = {st["no"]: st for st in steps}
    built = {}
    for st in sorted(steps, key=lambda s: s["no_num"]):  # global order, so tokens see earlier steps
        built[st["no"]] = build_step(ctx, st, site, used)

    containers = defaultdict(list)  # (parent_no, branch) -> [steps]
    for st in steps:
        parent = st["parent"]
        if parent and parent not in by_no:
            warn(f"Flow {flow['no']} step {st['no']}: 'Inside step no' {parent} does not exist; placed at top level.")
            parent = ""
        if parent and by_no[parent]["type"].lower() != "condition":
            warn(f"Flow {flow['no']} step {st['no']}: parent step {parent} is not a Condition; placed at top level.")
            parent = ""
        branch = "no" if parent and st["branch"].strip().lower() in ("no", "n", "false") else "yes"
        containers[(parent, branch if parent else "")].append(st)

    def chain(items):
        out, prev = {}, None
        for st in sorted(items, key=lambda s: s["no_num"]):
            act = built[st["no"]]
            act["runAfter"] = {prev: ["Succeeded"]} if prev else {}
            out[st["action"]] = act
            prev = st["action"]
        return out

    for st in steps:
        if st["type"].lower() == "condition":
            act = built[st["no"]]
            act["actions"] = chain(containers.get((st["no"], "yes"), []))
            act["else"] = {"actions": chain(containers.get((st["no"], "no"), []))}
    top = chain(containers.get(("", ""), []))

    alert = process.get("Failure alert email")
    if alert:
        run_link = ("concat('https://make.powerautomate.com/environments/', workflow()?['tags']?['environmentName'], "
                    "'/flows/', workflow()?['name'], '/runs/', workflow()?['run']?['name'])")
        catch_mail = conn(OUTLOOK, "SendEmailV2", {
            "emailMessage/To": alert,
            "emailMessage/Subject": f"Flow failed: {flow['display']}",
            "emailMessage/Body": f"<p>The flow <b>{flow['display']}</b> failed.</p><p><a href=\"@{{{run_link}}}\">Open the failed run</a></p>",
            "emailMessage/Importance": "High",
        })
        catch_mail["runAfter"] = {}
        actions = {
            "Try": {"type": "Scope", "actions": top, "runAfter": {}},
            "Catch": {"type": "Scope", "actions": {"Notify_owner_of_failure": catch_mail},
                      "runAfter": {"Try": ["Failed", "TimedOut"]}},
        }
    else:
        note(f"Flow {flow['no']}: no Failure alert email on the Process sheet, so no Try/Catch was added.")
        actions = top

    return {
        "displayName": flow["display"],
        "description": flow["description"],
        "definition": {
            "$schema": SCHEMA, "contentVersion": "1.0.0.0",
            "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                           "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
            "triggers": triggers, "actions": actions,
        },
    }


def currency_lcid(process):
    """Currency code or locale ID from the Process sheet -> LCID, or None for the site's own currency."""
    raw = (process.get("Currency") or process.get("Currency LCID") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return int(raw)
    code = re.split(r"[^A-Za-z]", raw)[0].upper()
    if code in CURRENCY_LCID:
        return CURRENCY_LCID[code]
    warn(f"Currency '{raw}' is not recognised. Use a code such as USD, GBP or EUR, or a SharePoint locale ID. "
         "Currency columns will use the site's regional currency.")
    return None


def spec_markdown(process, lists, cols_rows, flows, steps_by_flow):
    L = [f"# Flow Specification: {process.get('Process name', '')}", ""]
    for k, v in process.items():
        if v:
            L.append(f"- **{k}:** {v}")
    for k, v in SETTING_FALLBACKS.items():
        if not (process.get(k) or (k == "Currency" and process.get("Currency LCID"))):
            L.append(f"- **{k}:** {v}")
    L += ["", "## Lists", ""]
    for lst in lists:
        L.append(f"### {lst['title']}" + (" (already exists)" if lst["exists"] else f" (URL name: {lst['urlName']})"))
        if lst.get("titleDisplayName"):
            L.append(f"Title column shown as: {lst['titleDisplayName']}")
        L += ["", "| Internal name | Display name | Type | Required | Choices / default / lookup |", "|---|---|---|---|---|"]
        for c in [c for c in cols_rows if c[0] == lst["title"]]:
            extra = "; ".join(x for x in [c[5], ("default " + c[6]) if c[6] else "", ("→ " + c[7] + "." + (c[8] or "Title")) if c[7] else ""] if x)
            L.append(f"| {c[1]} | {c[2] or c[1]} | {c[3]} | {c[4] or 'No'} | {extra} |")
        L.append("")
    L += ["## Flows", ""]
    for f in flows:
        L.append(f"### Flow {f['no']}: {f['display']}")
        trig = f["trigger"] + (f" on '{f['trigger_list']}'" if f["trigger_list"] else "")
        if f["trigger"].lower() == "schedule":
            trig += f" every {f['interval'] or 1} {f['freq'] or 'Day'}" + (f" on {f['days']}" if f["days"] else "") + (f" at {f['time']}" if f["time"] else "")
        L.append(f"Trigger: {trig}" + (f", only when {f['condition']}" if f["condition"] else ""))
        if f["description"]:
            L.append(f"Purpose: {f['description']}")
        L.append("")
        for st in sorted(steps_by_flow.get(f["no"], []), key=lambda s: s["no_num"]):
            where = f" (inside step {st['parent']}, {st['branch'] or 'Yes'} branch)" if st["parent"] else ""
            detail = "; ".join(x for x in [
                st["condition"] and f"if {st['condition']}", st["list"] and f"list {st['list']}",
                st["fields"] and f"set {st['fields']}", st["to"] and f"to {st['to']}",
                st["subject"] and f"'{st['subject']}'"] if x)
            L.append(f"{st['no']}. **{st['name']}** [{st['type']}]{where}: {detail}")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workbook")
    ap.add_argument("--out", default="build")
    a = ap.parse_args()
    wb = load_workbook(a.workbook, data_only=True)
    for s in ("Process", "Lists", "Columns", "Flows", "Steps"):
        if s not in wb.sheetnames:
            sys.exit(f"Sheet '{s}' missing. Start from the Automation Intake template.")

    process = {}
    for r in wb["Process"].iter_rows(min_row=2, max_col=2, values_only=True):
        if r[0]:
            process[cell(r[0])] = cell(r[1])
    site = process.get("SharePoint site URL", "")
    if not site.startswith("https://"):
        warn("SharePoint site URL is missing or not https://...; flows will carry <<SITE_URL>>.")
    dept, pname = process.get("Department", ""), process.get("Process name", "Process")
    lcid = currency_lcid(process)
    prefix = " - ".join(x for x in [dept, pname] if x)

    lists = []
    for r in rows(wb["Lists"], 5):
        lists.append({"title": r[0], "urlName": r[1] or re.sub(r"[^A-Za-z0-9]", "", r[0]),
                      "description": r[2], "titleDisplayName": r[3], "exists": yes(r[4])})
    cols_rows = rows(wb["Columns"], 11)
    columns = defaultdict(dict)
    list_cols = defaultdict(list)
    for c in cols_rows:
        lst, internal, display, ctype = c[0], c[1], c[2], c[3].lower()
        if not internal:
            continue
        if " " in internal:
            warn(f"Column '{internal}' on '{lst}': internal name has spaces; using '{ident(internal)}'.")
            internal = ident(internal)
        columns[lst][internal] = ctype
        col = {"name": internal, "displayName": display or internal, "type": ctype or "text",
               "required": yes(c[4])}
        if c[5]:
            col["choices"] = [x.strip() for x in c[5].split(";") if x.strip()]
        if c[6]:
            col["default"] = c[6]
        if c[7]:
            col["lookupList"], col["lookupField"] = c[7], c[8] or "Title"
        if yes(c[9]):
            col["indexed"] = True
        if ctype == "currency" and lcid:
            col["lcid"] = lcid
        list_cols[lst].append(col)
    for lst in list_cols:
        if lst not in {l["title"] for l in lists}:
            warn(f"Columns given for '{lst}', which is not on the Lists sheet.")

    os.makedirs(a.out, exist_ok=True)
    to_make = [l for l in lists if not l["exists"]]
    if to_make:
        spec = {"siteUrl": site or "<<SITE_URL>>", "flowName": f"{prefix} - 0 Provision lists", "lists": []}
        for l in to_make:
            entry = {"title": l["title"], "urlName": l["urlName"], "description": l["description"],
                     "columns": list_cols.get(l["title"], [])}
            if l["titleDisplayName"]:
                entry["titleDisplayName"] = l["titleDisplayName"]
            spec["lists"].append(entry)
        made = {l["title"] for l in to_make}
        for l in spec["lists"]:
            for c in l["columns"]:
                if c.get("lookupList") and c["lookupList"] not in made:
                    warn(f"Lookup '{c['name']}' points to '{c['lookupList']}', which is not being created here. "
                         "Create that column by hand.")
        with open(os.path.join(a.out, "lists.json"), "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)

    flows = []
    for r in rows(wb["Flows"], 10):
        flows.append({"no": r[0], "display": f"{prefix} - {r[0]} {r[1]}".strip(), "trigger": r[2] or "Manual button",
                      "trigger_list": r[3], "condition": r[4], "freq": r[5], "interval": r[6],
                      "days": r[7], "time": r[8], "description": r[9]})
    steps_by_flow = defaultdict(list)
    for r in rows(wb["Steps"], 14):
        try:
            num = float(r[1])
        except ValueError:
            warn(f"Step '{r[2]}' has a non-numeric Step no '{r[1]}'; skipped.")
            continue
        steps_by_flow[r[0]].append({
            "flow": r[0], "no": r[1], "no_num": num, "name": r[2], "type": r[3] or "Custom", "parent": r[4],
            "branch": r[5], "list": r[6], "item": r[7], "fields": r[8], "to": r[9], "subject": r[10],
            "body": r[11], "condition": r[12], "notes": r[13]})

    for f in flows:
        st = steps_by_flow.get(f["no"], [])
        if not st:
            warn(f"Flow {f['no']} has no steps.")
            continue
        doc = build_flow(process, columns, f, st)
        with open(os.path.join(a.out, f"flow_{ident(f['no'])}.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
    if uses_time_zone and not process.get("Time zone"):
        flows_tz = ", ".join(dict.fromkeys(str(n) for n in uses_time_zone))
        warn(f"Time zone is blank on the Process sheet, so flow(s) {flows_tz} use UTC for schedules and {{Now}}. "
             "Ask the user for the organisation's time zone.")

    with open(os.path.join(a.out, "specification.md"), "w", encoding="utf-8") as f:
        f.write(spec_markdown(process, lists, cols_rows, flows, steps_by_flow))
    with open(os.path.join(a.out, "conversion_report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) or "No warnings.")
    print(f"Lists to create: {len(to_make)} | Flows: {len(flows)} | Output: {a.out}")
    print("\n".join(report) or "No warnings.")


if __name__ == "__main__":
    main()
