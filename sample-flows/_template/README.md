# Sample name

> One sentence: what the flow does and who it is for.

| | |
| --- | --- |
| Package | `<file name>.zip` |
| Trigger | For example: when an item is created in a SharePoint list |
| Connectors | For example: SharePoint, Approvals, Office 365 Outlook |
| Licence needed | Standard Microsoft 365, or Premium (name the premium connector) |
| Built with | Power Automate Builder skill 1.0, or by hand |
| Last tested | dd/MM/yyyy |

## What it does

1. First step.
2. Second step.
3. Outcome: what is written back, and who is told.

## Before you import

- **SharePoint lists:** name each list and its columns, or point to `lists.json` or a flow 0 package in this folder.
- **Connections:** the connections the importer must have in Power Automate.
- **Permissions:** for example, Edit on the SharePoint site.

## Import

1. Sign in to [make.powerautomate.com](https://make.powerautomate.com).
2. Select **My flows > Import > Import Package (Legacy)**.
3. Select **Upload** and choose `<file name>.zip`. Do not unzip it first.
4. For each connection row, choose **Select during import**, pick your connection, then **Save**.
5. Select **Import**, then **Open flow**.

## Values to set after import

| Action | Field | Value |
| --- | --- | --- |
| For example: Get items | Site Address | Your SharePoint site |

## Test

| Do this | Expect this |
| --- | --- |
| For example: create an item with yourself as approver | An approval email reaches you within two minutes |

## Notes and limits

- For example: approvals expire after 30 days.

---

Provided as is, without warranty. See the [disclaimer](../../README.md#disclaimer) in the main README.
