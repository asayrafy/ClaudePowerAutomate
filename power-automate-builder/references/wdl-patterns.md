# Flow definition patterns (Workflow Definition Language)

Power Automate cloud flows are stored as Azure Logic Apps Workflow Definition Language (WDL) JSON. Write the `definition` object with these patterns, then validate and package it. A full worked example sits in `assets/examples/purchase-request/flow_approval.json`.

## Contents
1. Flow file skeleton
2. Connector action anatomy
3. Triggers
4. SharePoint actions
5. Outlook, Teams, Approvals, Users
6. Control: conditions, loops, scopes, error handling
7. Expressions cheat sheet
8. Pitfalls that break imports or first runs
9. When a parameter name is uncertain

## 1. Flow file skeleton

```json
{
  "displayName": "Dept - Process - What it does",
  "description": "One sentence.",
  "definition": {
    "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
      "$connections": {"defaultValue": {}, "type": "Object"},
      "$authentication": {"defaultValue": {}, "type": "SecureObject"}
    },
    "triggers": { "<One_trigger>": { } },
    "actions": { "<Action_name>": { }, "...": { } }
  }
}
```

Rules: exactly one trigger; action names unique across the whole flow (including nested ones), letters, digits and underscores only; every action has `runAfter` (`{}` means "first in its scope").

## 2. Connector action anatomy

```json
"Action_name": {
  "type": "OpenApiConnection",
  "inputs": {
    "host": {
      "apiId": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline",
      "connectionName": "shared_sharepointonline",
      "operationId": "PostItem"
    },
    "parameters": { "dataset": "...", "table": "...", "item/Title": "..." },
    "authentication": "@parameters('$authentication')"
  },
  "runAfter": { "Previous_action": ["Succeeded"] }
}
```

Use `OpenApiConnectionWebhook` for actions that wait for a callback (approvals, "wait for" actions). `connectionName` is the connector's short name; the packager turns each distinct one into a connection the importer selects.

Connector short names: `shared_sharepointonline`, `shared_office365` (Outlook), `shared_office365users`, `shared_teams`, `shared_approvals`, `shared_onedriveforbusiness`, `shared_excelonlinebusiness`, `shared_microsoftforms`, `shared_planner`.

## 3. Triggers

Manual (button), with optional inputs:
```json
"manual": {"type": "Request", "kind": "Button",
  "inputs": {"schema": {"type": "object", "properties": {
    "text": {"title": "Request title", "type": "string", "x-ms-dynamically-added": true, "description": "Enter a title", "x-ms-content-hint": "TEXT"}
  }, "required": ["text"]}}}
```
Read with `@triggerBody()?['text']`.

Schedule (time zone matters; use the organisation's Windows time zone name, such as `GMT Standard Time`, `Eastern Standard Time` or `Arab Standard Time`):
```json
"Recurrence": {"type": "Recurrence", "recurrence": {"frequency": "Week", "interval": 1,
  "schedule": {"weekDays": ["Monday"], "hours": ["8"], "minutes": [0]}, "timeZone": "UTC"}}
```

SharePoint polling triggers (all share this shape; `splitOn` gives one run per item):
```json
"When_an_item_is_created": {
  "recurrence": {"interval": 1, "frequency": "Minute"},
  "splitOn": "@triggerOutputs()?['body/value']",
  "type": "OpenApiConnection",
  "inputs": {
    "host": {"apiId": "/providers/Microsoft.PowerApps/apis/shared_sharepointonline", "connectionName": "shared_sharepointonline", "operationId": "GetOnNewItems"},
    "parameters": {"dataset": "<<SITE_URL>>", "table": "<<LIST_X>>"},
    "authentication": "@parameters('$authentication')"
  }
}
```
Operation IDs: `GetOnNewItems` (item created), `GetOnUpdatedItems` (item created or modified), `GetOnChangedItems` (item or file modified, gives "has column changed"), `GetOnDeletedItems`, `GetOnNewFileItems` (file created, properties only), `GetOnUpdatedFileItems` (file created or modified). Libraries also take an optional `folderPath`.

Trigger conditions (stop runs you do not want, and stop loops):
```json
"conditions": [{"expression": "@equals(triggerOutputs()?['body/Status/Value'], 'Submitted')"}]
```
Put `conditions` beside `inputs` in the trigger.

Trigger outputs: `@triggerOutputs()?['body/ID']`, `['body/Title']`, `['body/<InternalName>']`, Choice `['body/Status/Value']`, Person `['body/Approver/Email']` and `['body/Approver/DisplayName']`, created by `['body/Author/Email']`, item link `['body/{Link}']`.

## 4. SharePoint actions

All take `dataset` (site URL) and most take `table` (list name or list GUID).

| Purpose | operationId | Key parameters |
|---|---|---|
| Create item | `PostItem` | `item/<InternalName>` |
| Update item | `PatchItem` | `id`, `item/<InternalName>` |
| Get item | `GetItem` | `id` |
| Get items | `GetItems` | `$filter`, `$orderby`, `$top`, `viewScopeOption` |
| Delete item | `DeleteItem` | `id` |
| Send HTTP request to SharePoint | `HttpRequest` | `parameters/method`, `parameters/uri`, `parameters/headers`, `parameters/body` |
| Create file | `CreateFile` | `folderPath`, `name`, `body` |
| Get file content | `GetFileContent` | `id` |

Writing column types:
* Text, Note, Number, Currency: `"item/Amount": "@{triggerBody()?['amount']}"`
* Date: ISO string, e.g. `"@{utcNow('yyyy-MM-dd')}"`
* Yes/No: `true` / `false`
* Choice: `"item/Status/Value": "Approved"`
* Person: `"item/Approver/Claims": "i:0#.f|membership|@{variables('ApproverEmail')}"`
* Lookup: `"item/Department/Id": 3`
* Multi-value fields take arrays of the same objects.

`GetItems` filter (OData; text in single quotes; use internal names):
`"$filter": "Status eq 'Submitted' and Amount gt 5000"`. For Person columns filter on `Approver/EMail`. For more than 100 items set `$top` (up to 5000) or turn on pagination in the designer.

## 5. Outlook, Teams, Approvals, Users

Send email (Office 365 Outlook, `SendEmailV2`):
```json
"parameters": {"emailMessage/To": "a@x.com;b@x.com", "emailMessage/Subject": "...",
  "emailMessage/Body": "<p>HTML body</p>", "emailMessage/Importance": "Normal"}
```
From a shared mailbox: operationId `SharedMailboxSendEmailV2`, extra parameter `emailMessage/MailboxAddress` (the user needs Send As rights).

Teams message to a channel (`PostMessageToConversation`):
```json
"parameters": {"poster": "Flow bot", "location": "Channel",
  "body/recipient/groupId": "<<TEAM_ID>>", "body/recipient/channelId": "<<CHANNEL_ID>>",
  "body/messageBody": "<p>Text</p>"}
```
Team and channel IDs are tenant specific; leave placeholders and tell the user to reselect them after import.

Approval (`OpenApiConnectionWebhook`, `StartAndWaitForAnApproval`):
```json
"parameters": {"approvalType": "Basic",
  "WebhookApprovalCreationInput/title": "...",
  "WebhookApprovalCreationInput/assignedTo": "a@x.com;b@x.com",
  "WebhookApprovalCreationInput/details": "Markdown text",
  "WebhookApprovalCreationInput/itemLink": "@{triggerOutputs()?['body/{Link}']}",
  "WebhookApprovalCreationInput/itemLinkDescription": "Open the item",
  "WebhookApprovalCreationInput/enableNotifications": true,
  "WebhookApprovalCreationInput/enableReassignment": true}
```
`approvalType`: `Basic` (first to respond), `BasicAwaitAll` (everyone must approve). Result: `@body('Start_and_wait_for_an_approval')?['outcome']` is `Approve` or `Reject`; comments in `first(body('...')?['responses'])?['comments']`. Approvals expire after 30 days; set a timeout and handle the `TimedOut` run-after status if that matters.

Manager lookup (Office 365 Users, `Manager_V2`): `"parameters": {"id": "@{triggerOutputs()?['body/Author/Email']}"}`; result `body('Get_manager')?['mail']`.

## 6. Control

Condition:
```json
"Is_high_value": {"type": "If",
  "expression": {"and": [{"greater": ["@triggerOutputs()?['body/Amount']", 50000]}]},
  "actions": { }, "else": {"actions": { }}, "runAfter": { }}
```
Operators: `equals`, `not` (wrap), `greater`, `greaterOrEquals`, `less`, `lessOrEquals`, `contains`, `startsWith`, `endsWith`; combine with `and` / `or`.

Loop:
```json
"For_each_item": {"type": "Foreach", "foreach": "@body('Get_items')?['value']",
  "actions": { }, "runAfter": { }, "runtimeConfiguration": {"concurrency": {"repetitions": 1}}}
```
Inside, use `@items('For_each_item')?['Title']`. Concurrency 1 keeps order and avoids write clashes.

Variables: `InitializeVariable` must be at the top level, never inside a loop, condition or scope:
```json
"Initialise_total": {"type": "InitializeVariable",
  "inputs": {"variables": [{"name": "Total", "type": "float", "value": 0}]}, "runAfter": {}}
```
Then `SetVariable`, `IncrementVariable`, `AppendToArrayVariable`.

Try / catch with scopes:
```json
"Try": {"type": "Scope", "actions": { }, "runAfter": { }},
"Catch": {"type": "Scope", "actions": {"Notify_owner": { }},
  "runAfter": {"Try": ["Failed", "TimedOut"]}}
```
In the catch, `@result('Try')` lists the failed actions. Every production flow that changes data should have this.

Other built-ins: `Compose` (`"inputs": ...`), `Terminate` (`"inputs": {"runStatus": "Failed", "runError": {"message": "..."}}`), `Wait` (`"inputs": {"interval": {"count": 1, "unit": "Day"}}`), `Query` (filter array), `Select`, `Join`, `Table` (HTML table).

## 7. Expressions cheat sheet

* Whole value: `"@triggerBody()?['x']"` keeps the type. Inside text: `"Hello @{triggerBody()?['name']}"`. A literal leading `@` is written `@@`.
* Null-safe access: always `?['key']`.
* Dates: `utcNow()`, `convertFromUtc(utcNow(), '<time zone setting>', '<date format setting> HH:mm')`, `addDays(utcNow(), 3, 'yyyy-MM-dd')`, `formatDateTime(x, 'dd MMM yyyy')`.
* Text: `concat()`, `toLower()`, `trim()`, `replace()`, `split()`, `substring()`, `formatNumber(x, 'N2')`.
* Logic: `if(cond, a, b)`, `coalesce(a, b)`, `empty(x)`, `equals(a, b)`, `and()`, `or()`, `not()`.
* Collections: `length()`, `first()`, `last()`, `union()`, `join(array, '; ')`.

## 8. Pitfalls

* **Infinite loop**: a "created or modified" trigger plus an "Update item" on the same list re-triggers itself. Use a trigger condition on a Status value, or the "when an item or a file is modified" trigger with "has column changed".
* **Internal names**: flows use internal column names (`DecisionDate`), not display names (`Decision Date`). A column created as "Decision Date" has the internal name `Decision_x0020_Date`.
* **List name with a full stop** fails as a `table` value; use the list GUID.
* **Lookup threshold**: a list query returning more than 12 lookup or person columns fails; select only what you need.
* **5,000 item view threshold**: index columns used in filters.
* **Variables inside loops**: initialise at the top level only.
* **Apply to each with concurrency** above 1 and variables gives wrong totals.
* **Date-only columns** take `yyyy-MM-dd`; time zone shifts can move a date by a day when you pass full UTC timestamps.
* **Emails go out from the connection owner's mailbox.** Use the shared mailbox action when that matters.
* **Child flows** ("Run a child flow") need solutions and cannot be imported through the legacy package.

## 9. When a parameter name is uncertain

Do not guess silently. Either mark the action in the Build Sheet as "check after import", or ask the user to build that single action in the designer, choose Copy action (or export the flow), and paste the JSON back. The exported definition is the authority.
