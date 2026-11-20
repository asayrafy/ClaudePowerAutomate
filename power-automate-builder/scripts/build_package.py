#!/usr/bin/env python3
"""Wrap a cloud flow definition in a Power Automate import package (.zip).

The output is the "Package (.zip)" format that Power Automate imports through
My flows > Import > Import Package (Legacy). Layout:

    manifest.json
    Microsoft.Flow/flows/manifest.json
    Microsoft.Flow/flows/<flow-guid>/definition.json
    Microsoft.Flow/flows/<flow-guid>/apisMap.json
    Microsoft.Flow/flows/<flow-guid>/connectionsMap.json

Connectors are detected automatically from every action's
inputs.host.apiId, so the importer is asked to pick (or create) one
connection per connector used.

Input flow file (JSON):
    {
      "displayName": "Purchase Requests - Approval on new request",
      "description": "optional",
      "definition": { "$schema": ..., "triggers": {...}, "actions": {...} }
    }

Usage:
    python build_package.py flow.json [more.json ...] --out /mnt/user-data/outputs
        [--set SITE_URL=https://contoso.sharepoint.com/sites/Ops ...]

--set replaces every <<KEY>> placeholder in the definition before packaging.
"""
import argparse
import copy
import json
import os
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone

SCHEMA = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"

KNOWN_CONNECTORS = {
    "shared_sharepointonline": "SharePoint",
    "shared_office365": "Office 365 Outlook",
    "shared_office365users": "Office 365 Users",
    "shared_teams": "Microsoft Teams",
    "shared_approvals": "Approvals",
    "shared_onedriveforbusiness": "OneDrive for Business",
    "shared_excelonlinebusiness": "Excel Online (Business)",
    "shared_planner": "Planner",
    "shared_microsoftforms": "Microsoft Forms",
    "shared_flowpush": "Notifications",
    "shared_office365groups": "Office 365 Groups",
    "shared_wordonlinebusiness": "Word Online (Business)",
    "shared_commondataserviceforapps": "Microsoft Dataverse",
    "shared_webcontents": "HTTP with Microsoft Entra ID",
}
PREMIUM_HINTS = {"shared_commondataserviceforapps", "shared_webcontents", "shared_sql", "shared_wordonlinebusiness"}


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "0Z"


def find_connectors(node, found):
    if isinstance(node, dict):
        host = node.get("host")
        if isinstance(host, dict) and host.get("apiId") and host.get("connectionName"):
            found[host["connectionName"]] = host["apiId"]
        for v in node.values():
            find_connectors(v, found)
    elif isinstance(node, list):
        for v in node:
            find_connectors(v, found)
    return found


def apply_sets(text, sets):
    for key, value in sets.items():
        text = text.replace(f"<<{key}>>", value)
    return text


def safe_filename(name):
    name = re.sub(r"[^\w\- ]+", "", name).strip().replace(" ", "_")
    return name[:80] or "flow"


def build(flow_doc, out_dir, sets):
    display = flow_doc.get("displayName") or "Generated flow"
    description = flow_doc.get("description", "")
    definition = copy.deepcopy(flow_doc["definition"])

    if sets:
        definition = json.loads(apply_sets(json.dumps(definition, ensure_ascii=False), sets))

    definition.setdefault("$schema", SCHEMA)
    definition.setdefault("contentVersion", "1.0.0.0")
    params = definition.setdefault("parameters", {})
    params.setdefault("$connections", {"defaultValue": {}, "type": "Object"})
    params.setdefault("$authentication", {"defaultValue": {}, "type": "SecureObject"})

    connectors = find_connectors(definition, {})

    flow_res = str(uuid.uuid4())
    flow_name = str(uuid.uuid4())
    resources, apis_map, conns_map, depends, conn_refs = {}, {}, {}, [], {}
    for conn_name, api_id in sorted(connectors.items()):
        api_res, conn_res = str(uuid.uuid4()), str(uuid.uuid4())
        api_short = api_id.rsplit("/", 1)[-1]
        label = KNOWN_CONNECTORS.get(api_short, api_short.replace("shared_", ""))
        resources[api_res] = {
            "id": api_id, "name": api_short, "type": "Microsoft.PowerApps/apis",
            "suggestedCreationType": "Existing", "details": {"displayName": label},
            "configurableBy": "System", "hierarchy": "Child", "dependsOn": [],
        }
        resources[conn_res] = {
            "type": "Microsoft.PowerApps/apis/connections", "suggestedCreationType": "Existing",
            "creationType": "Existing", "details": {"displayName": label},
            "configurableBy": "User", "hierarchy": "Child", "dependsOn": [api_res],
        }
        apis_map[conn_name] = api_res
        conns_map[conn_name] = conn_res
        # The flow service rejects the save with "host.connectionReferenceName is missing"
        # unless every connection used by an action is declared here. The importer swaps
        # the placeholder connectionName for the connection the user selects.
        conn_refs[conn_name] = {
            "connectionName": f"{api_short.replace('_', '-')}-{uuid.uuid4().hex[:8]}",
            "source": "Embedded", "id": api_id, "tier": "NotSpecified",
        }
        depends += [api_res, conn_res]

    resources = {flow_res: {
        "type": "Microsoft.Flow/flows", "suggestedCreationType": "New",
        "creationType": "Existing, New, Update", "details": {"displayName": display},
        "configurableBy": "User", "hierarchy": "Root", "dependsOn": depends,
    }, **resources}

    root_manifest = {
        "schema": "1.0",
        "details": {
            "displayName": display, "description": description, "createdTime": now_stamp(),
            "packageTelemetryId": str(uuid.uuid4()), "creator": "power-automate-builder skill",
            "sourceEnvironment": "",
        },
        "resources": resources,
    }
    flows_manifest = {"packageSchemaVersion": "1.0", "flowAssets": {"assetPaths": [flow_res]}}
    definition_doc = {
        "name": flow_name,
        "id": f"/providers/Microsoft.Flow/flows/{flow_name}",
        "type": "Microsoft.Flow/flows",
        "properties": {
            "apiId": "/providers/Microsoft.PowerApps/apis/shared_logicflows",
            "displayName": display,
            "definition": definition,
            "connectionReferences": conn_refs,
            "flowFailureAlertSubscribed": False,
            "isManaged": False,
        },
    }

    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, safe_filename(display) + ".zip")
    base = f"Microsoft.Flow/flows/{flow_res}"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Forward slashes only: backslash entry names break the import.
        z.writestr("manifest.json", json.dumps(root_manifest, indent=2, ensure_ascii=False))
        z.writestr("Microsoft.Flow/flows/manifest.json", json.dumps(flows_manifest, indent=2))
        z.writestr(f"{base}/definition.json", json.dumps(definition_doc, indent=2, ensure_ascii=False))
        z.writestr(f"{base}/apisMap.json", json.dumps(apis_map, indent=2))
        z.writestr(f"{base}/connectionsMap.json", json.dumps(conns_map, indent=2))

    labels = [KNOWN_CONNECTORS.get(a.rsplit("/", 1)[-1], a) for a in connectors.values()]
    premium = [a for a in connectors.values() if a.rsplit("/", 1)[-1] in PREMIUM_HINTS]
    print(f"Built: {zip_path}")
    print(f"  Flow: {display}")
    print(f"  Connections the importer must select: {', '.join(labels) or 'none'}")
    if premium:
        print(f"  NOTE: likely premium connector(s): {', '.join(premium)}. Check licences and DLP policy.")
    left = sorted(set(re.findall(r"<<[^<>]+>>", json.dumps(definition))))
    if left:
        print(f"  Placeholders still present (user must set after import): {', '.join(left)}")
    return zip_path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("flows", nargs="+", help="flow JSON files")
    ap.add_argument("--out", default=".", help="output directory")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="replace <<KEY>> placeholders")
    args = ap.parse_args()
    sets = {}
    for item in args.set:
        if "=" not in item:
            sys.exit(f"--set expects KEY=VALUE, got {item}")
        k, v = item.split("=", 1)
        sets[k.strip()] = v
    for path in args.flows:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        if "definition" not in doc:
            sys.exit(f"{path}: expected a flow file with a 'definition' key")
        build(doc, args.out, sets)


if __name__ == "__main__":
    main()
