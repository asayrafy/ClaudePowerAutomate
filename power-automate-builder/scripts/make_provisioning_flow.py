#!/usr/bin/env python3
"""Generate a "provisioning" cloud flow that creates SharePoint lists and columns.

Why a flow: the SharePoint connector has no "Create list" action, but its
standard (non-premium) "Send an HTTP request to SharePoint" action can call
the SharePoint REST API with the user's own connection. Importing and running
this flow once builds every list in the spec, so nobody has to click through
List settings column by column.

Behaviour of the generated flow (manual trigger):
  * For each list: looks it up by title; creates it only if missing, using the
    URL name first (clean URL) and then renaming it to the display title.
  * Adds each column with CreateFieldAsXml. If a column already exists that
    call fails and the flow carries on, so the flow is safe to re-run.
  * Lists are processed in spec order, so put lookup targets first.

Input lists spec (JSON):
{
  "siteUrl": "https://contoso.sharepoint.com/sites/Operations",   # or "<<SITE_URL>>"
  "flowName": "Purchase Requests - Provision lists",               # optional
  "lists": [
    {
      "title": "Purchase Requests",          # display title
      "urlName": "PurchaseRequests",         # optional, defaults to title without spaces
      "description": "Raised by staff",
      "titleDisplayName": "Request Ref",     # optional rename of the built-in Title column
      "columns": [
        {"name": "Amount", "displayName": "Amount", "type": "currency", "required": true, "lcid": 1033},
        {"name": "Status", "type": "choice", "choices": ["Draft", "Submitted", "Approved", "Rejected"], "default": "Draft"},
        {"name": "Approver", "type": "person"},
        {"name": "Department", "type": "lookup", "lookupList": "Departments", "lookupField": "Title"}
      ]
    }
  ]
}

Column types: text, note, richtext, number, currency, date, datetime, boolean,
choice, multichoice, person, personmulti, url, lookup.
Optional column keys: displayName, required, indexed, unique, default,
choices, decimals, min, max, maxLength, lcid (currency locale ID, e.g. 1033 = US dollar;
omit it to use the site's regional currency),
lookupList, lookupField, description.

Usage:
  python make_provisioning_flow.py lists.json --out provisioning_flow.json
Then package it with build_package.py.
"""
import argparse
import json
import re
import sys
from xml.sax.saxutils import escape, quoteattr

SP_API = "/providers/Microsoft.PowerApps/apis/shared_sharepointonline"
VERBOSE = {"Accept": "application/json;odata=verbose", "Content-Type": "application/json;odata=verbose"}
VALID_TYPES = {"text", "note", "richtext", "number", "currency", "date", "datetime", "boolean",
               "choice", "multichoice", "person", "personmulti", "url", "lookup"}


def ident(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


def odata_literal(s):
    return s.replace("'", "''")


def uri_text(s):
    return odata_literal(s).replace(" ", "%20").replace("&", "%26").replace("#", "%23")


def sp_http(site, method, uri, body=None, extra_headers=None, run_after=None):
    headers = dict(VERBOSE)
    if extra_headers:
        headers.update(extra_headers)
    params = {"dataset": site, "parameters/method": method, "parameters/uri": uri, "parameters/headers": headers}
    if body is not None:
        params["parameters/body"] = json.dumps(body, ensure_ascii=False)
    return {
        "type": "OpenApiConnection",
        "inputs": {
            "host": {"apiId": SP_API, "connectionName": "shared_sharepointonline", "operationId": "HttpRequest"},
            "parameters": params,
            "authentication": "@parameters('$authentication')",
        },
        "runAfter": run_after or {},
    }


def field_xml(col, list_vars):
    t = col["type"].lower()
    if t not in VALID_TYPES:
        sys.exit(f"Unknown column type '{col['type']}' for column {col['name']}")
    name = ident(col["name"])
    attrs = {
        "DisplayName": col.get("displayName", col["name"]),
        "Name": name,
        "StaticName": name,
        "Required": "TRUE" if col.get("required") else "FALSE",
    }
    if col.get("description"):
        attrs["Description"] = col["description"]
    if col.get("indexed") or col.get("unique"):
        attrs["Indexed"] = "TRUE"
    if col.get("unique"):
        attrs["EnforceUniqueValues"] = "TRUE"
    inner = ""
    if t == "text":
        attrs.update(Type="Text", MaxLength=str(col.get("maxLength", 255)))
    elif t in ("note", "richtext"):
        attrs.update(Type="Note", NumLines="6", RichText="TRUE" if t == "richtext" else "FALSE")
        if t == "richtext":
            attrs["RichTextMode"] = "FullHtml"
    elif t in ("number", "currency"):
        attrs["Type"] = "Number" if t == "number" else "Currency"
        attrs["Decimals"] = str(col.get("decimals", 0 if t == "number" else 2))
        for k, a in (("min", "Min"), ("max", "Max")):
            if k in col:
                attrs[a] = str(col[k])
        if t == "currency" and col.get("lcid"):
            attrs["LCID"] = str(col["lcid"])
    elif t in ("date", "datetime"):
        attrs.update(Type="DateTime", Format="DateOnly" if t == "date" else "DateTime")
    elif t == "boolean":
        attrs["Type"] = "Boolean"
        inner = f"<Default>{'1' if col.get('default') else '0'}</Default>"
    elif t in ("choice", "multichoice"):
        attrs.update(Type="Choice" if t == "choice" else "MultiChoice", FillInChoice="FALSE")
        if t == "choice":
            attrs["Format"] = "Dropdown"
        choices = col.get("choices") or sys.exit(f"Column {col['name']} needs 'choices'")
        inner = "<CHOICES>" + "".join(f"<CHOICE>{escape(c)}</CHOICE>" for c in choices) + "</CHOICES>"
        if col.get("default"):
            inner += f"<Default>{escape(col['default'])}</Default>"
    elif t in ("person", "personmulti"):
        attrs.update(Type="User" if t == "person" else "UserMulti", List="UserInfo",
                     ShowField="ImnName", UserSelectionMode="PeopleOnly", UserSelectionScope="0")
        if t == "personmulti":
            attrs["Mult"] = "TRUE"
    elif t == "url":
        attrs.update(Type="URL", Format="Hyperlink")
    elif t == "lookup":
        target = col.get("lookupList") or sys.exit(f"Column {col['name']} needs 'lookupList'")
        if target not in list_vars:
            sys.exit(f"Lookup target '{target}' must be an earlier list in the same spec")
        attrs.update(Type="Lookup", List="{@{variables('" + list_vars[target] + "')}}",
                     ShowField=col.get("lookupField", "Title"))
    if t not in ("boolean", "choice", "multichoice") and col.get("default") is not None:
        inner = f"<Default>{escape(str(col['default']))}</Default>"
    attr_text = " ".join(f"{k}={quoteattr(v)}" for k, v in attrs.items())
    return f"<Field {attr_text}>{inner}</Field>" if inner else f"<Field {attr_text} />"


def build(spec):
    site = spec["siteUrl"]
    lists = spec["lists"]
    actions, prev = {}, None
    list_vars = {}

    for i, lst in enumerate(lists, 1):
        var = f"ListId_{i}"
        list_vars[lst["title"]] = var
        name = f"Initialise_{var}"
        actions[name] = {
            "type": "InitializeVariable",
            "inputs": {"variables": [{"name": var, "type": "string", "value": ""}]},
            "runAfter": {prev: ["Succeeded"]} if prev else {},
        }
        prev = name

    for i, lst in enumerate(lists, 1):
        var = list_vars[lst["title"]]
        title = lst["title"]
        url_name = lst.get("urlName") or re.sub(r"[^A-Za-z0-9]", "", title)
        tag = ident(url_name)[:40]
        scope_name = f"Provision_{tag}"
        inner = {}
        find = f"Find_{tag}"
        inner[find] = sp_http(site, "GET",
                              f"_api/web/lists?$filter=Title eq '{uri_text(title)}'&$select=Id,Title")
        set_existing, create, set_new, rename = (f"Use_existing_{tag}", f"Create_{tag}",
                                                 f"Use_new_{tag}", f"Rename_{tag}")
        yes = {set_existing: {
            "type": "SetVariable",
            "inputs": {"name": var, "value": f"@{{first(body('{find}')?['d']?['results'])?['Id']}}"},
            "runAfter": {},
        }}
        no = {
            create: sp_http(site, "POST", "_api/web/lists", body={
                "__metadata": {"type": "SP.List"}, "AllowContentTypes": True, "BaseTemplate": 100,
                "ContentTypesEnabled": False, "Description": lst.get("description", ""), "Title": url_name}),
            set_new: {
                "type": "SetVariable",
                "inputs": {"name": var, "value": f"@{{body('{create}')?['d']?['Id']}}"},
                "runAfter": {create: ["Succeeded"]},
            },
        }
        if url_name != title:
            no[rename] = sp_http(site, "POST", f"_api/web/lists(guid'@{{variables('{var}')}}')",
                                 body={"__metadata": {"type": "SP.List"}, "Title": title},
                                 extra_headers={"X-HTTP-Method": "MERGE", "IF-MATCH": "*"},
                                 run_after={set_new: ["Succeeded"]})
        cond = f"List_exists_{tag}"
        inner[cond] = {
            "type": "If",
            "expression": {"and": [{"greater": [f"@length(coalesce(body('{find}')?['d']?['results'], json('[]')))", 0]}]},
            "actions": yes,
            "else": {"actions": no},
            "runAfter": {find: ["Succeeded"]},
        }
        step_prev = cond
        if lst.get("titleDisplayName"):
            nm = f"Rename_Title_column_{tag}"
            inner[nm] = sp_http(site, "POST",
                                f"_api/web/lists(guid'@{{variables('{var}')}}')/fields/getbyinternalnameortitle('Title')",
                                body={"__metadata": {"type": "SP.Field"}, "Title": lst["titleDisplayName"]},
                                extra_headers={"X-HTTP-Method": "MERGE", "IF-MATCH": "*"},
                                run_after={step_prev: ["Succeeded"]})
            step_prev = nm
        for col in lst.get("columns", []):
            nm = f"Add_{tag}_{ident(col['name'])}"[:80]
            body = {"parameters": {"__metadata": {"type": "SP.XmlSchemaFieldCreationInformation"},
                                   "SchemaXml": field_xml(col, list_vars), "Options": 24}}
            ra = [] if step_prev == cond else ["Failed"]
            inner[nm] = sp_http(site, "POST",
                                f"_api/web/lists(guid'@{{variables('{var}')}}')/fields/CreateFieldAsXml",
                                body=body, run_after={step_prev: ["Succeeded"] + ra})
            step_prev = nm
        actions[scope_name] = {
            "type": "Scope", "actions": inner,
            "runAfter": {prev: ["Succeeded", "Failed"] if prev.startswith("Provision_") else ["Succeeded"]},
        }
        prev = scope_name

    actions["Summary"] = {
        "type": "Compose",
        "inputs": {lst["title"]: f"@variables('{list_vars[lst['title']]}')" for lst in lists},
        "runAfter": {prev: ["Succeeded", "Failed", "Skipped"]},
    }

    definition = {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$connections": {"defaultValue": {}, "type": "Object"},
                       "$authentication": {"defaultValue": {}, "type": "SecureObject"}},
        "triggers": {"manual": {"type": "Request", "kind": "Button",
                                "inputs": {"schema": {"type": "object", "properties": {}, "required": []}}}},
        "actions": actions,
    }
    return {
        "displayName": spec.get("flowName", "Provision SharePoint lists"),
        "description": "One-off flow. Run once to create the lists and columns. Safe to re-run; "
                       "columns that already exist show as failed steps and are skipped.",
        "definition": definition,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--out", default="provisioning_flow.json")
    a = ap.parse_args()
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    flow = build(spec)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(flow, f, indent=2, ensure_ascii=False)
    n_cols = sum(len(l.get("columns", [])) for l in spec["lists"])
    print(f"Wrote {a.out}: {len(spec['lists'])} list(s), {n_cols} column(s).")


if __name__ == "__main__":
    main()
