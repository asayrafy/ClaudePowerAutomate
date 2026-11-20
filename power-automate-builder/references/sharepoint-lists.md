# SharePoint lists: design and creation

## Contents
1. Designing the lists
2. Column types and how each is written
3. Creating the lists: provisioning flow 0
4. Permissions and good practice

## 1. Designing the lists

* One list per business object (requests, approvers, departments). Reference data that drives routing (approvers per department, thresholds) goes in its own small list so the business can change it without editing the flow.
* Every list already has `Title` (required, single line). Rename its display name rather than adding a duplicate "Name" column.
* Keep a `Status` Choice column on any list a flow moves through stages. It drives trigger conditions, views and reporting.
* Index any column used in a flow filter or a view filter once the list may pass 5,000 items.
* Prefer Person columns over typed email addresses. Prefer Lookup columns over typed department names.

## 2. Column types

Spec `type` value, SharePoint type, and how a flow writes it:

| Spec type | SharePoint | Flow write format |
|---|---|---|
| `text` | Single line of text | plain string |
| `note` / `richtext` | Multiple lines of text | string / HTML |
| `number` | Number | number |
| `currency` | Currency (`lcid` sets the currency; leave it out to use the site's regional setting) | number |
| `date` / `datetime` | Date and time | `yyyy-MM-dd` / ISO 8601 |
| `boolean` | Yes/No | `true` / `false` |
| `choice` / `multichoice` | Choice | `item/Col/Value` |
| `person` / `personmulti` | Person or Group | `item/Col/Claims` = `i:0#.f|membership|<email>` |
| `url` | Hyperlink | `item/Col` = URL (description optional) |
| `lookup` | Lookup to another list | `item/Col/Id` = target item ID |

Currency locale IDs for `lcid`: 1033 US dollar, 2057 pound sterling, 6153 euro, 1025 Saudi riyal, 14337 UAE dirham, 4105 Canadian dollar, 3081 Australian dollar, 16393 Indian rupee, 1041 Japanese yen, 2055 Swiss franc. Use the currency from the organisation settings, and ask if it is not set.

Avoid these for flow-driven lists unless needed: Managed Metadata (needs term IDs), Calculated (read only, cannot filter well), Image and Location (awkward to write).

## 3. Creating the lists: provisioning flow 0

`scripts/make_provisioning_flow.py` turns a lists spec into a manual flow that uses the standard "Send an HTTP request to SharePoint" action with the user's own connection. No premium licence, no admin consent, no app registration.

```
python scripts/make_provisioning_flow.py lists.json --out flow0.json
python scripts/validate_definition.py flow0.json
python scripts/build_package.py flow0.json --out /mnt/user-data/outputs --set SITE_URL=https://tenant.sharepoint.com/sites/X
```

The spec format is documented at the top of the script, and `assets/examples/purchase-request/lists.json` is a complete example. Put lookup target lists first.

Always build this package with the real site URL (`--set SITE_URL=...`). A placeholder here would mean editing every HTTP action by hand after import, so ask for the URL instead.

What the user does: import the package, select their SharePoint connection, open the flow, save, Run, then check the lists. The flow:
* creates each list with a clean URL (`/Lists/PurchaseRequests`) and then renames it to the display title,
* skips lists that already exist,
* adds columns with internal names without spaces and friendly display names, adds them to the default view,
* carries on past columns that already exist (those steps show as failed; this is expected on a re-run).

Requirements: the person running it needs Edit (or higher) on the site to create lists; Members of a team site normally have this. After the lists exist the provisioning flow can be deleted or kept for rebuilding test sites.

The claude.ai Microsoft 365 connector works with files, mail, calendar and Teams; it cannot create lists or columns. Do not claim otherwise.

## 4. Permissions and good practice

* Break inheritance only when the data is confidential; otherwise lists inherit site permissions.
* Flows act with the connection owner's permissions. If the owner cannot see a list, neither can the flow.
* Turn on versioning (default on new lists) so changes made by flows are auditable.
* Add a view per stage (e.g. "Awaiting approval": Status = Submitted) for the people who work the list.
