# Build Sheet template

The Build Sheet is the user's single handover document. Produce one for every build, whatever the mode. It doubles as the change record. Write it in the organisation's language and spelling conventions (see SKILL.md). Deliver it as a document the user can keep and share (a doc where the surface supports it, otherwise a Markdown file), next to the zips.

```
# <Process name>: Build Sheet
Version 1.0 | <date> | Prepared by Claude for <user>

## 1. What this automation does
<Three or four sentences in business language.>

## 2. Specification (as confirmed)
<The confirmed Flow Specification, including open points.>

## 3. Prerequisites
- Environment: <name>
- Site: <URL> (you need Edit permission)
- Connections: <SharePoint, Approvals, Office 365 Outlook...>
- Licence: standard connectors only / premium needed for <X>
- Co-owner: <name>
- Settings: time zone <...>; date format <...>; currency <...>; approval authority <...>

## 4. SharePoint lists
<Per list: table of Column | Internal name | Type | Required | Choices/default | Notes.>
How they are created: provisioning flow 0 (`<...> - 0 Provision lists.zip`).

## 5. Files delivered
| File | What it is | Order |
| <...> - 0 Provision lists.zip | creates the lists | 1 |
| <...> - 1 <name>.zip | <purpose> | 2 |

## 6. Install steps
<Link to the Install Checklist page, which carries the tick-box steps.>

## 7. Values to set after import
| Flow | Action | Field | Value |
<Every remaining <<PLACEHOLDER>> and any drop-down to reselect.>

## 8. Test cases
| # | Do this | Expect this | Pass? |
| 1 | Create an item with Amount 1,000, Approver = yourself | Approval email to you within 2 minutes | |
| 2 | Approve with a comment | Status = Approved, Decision Date = today, comment saved, requester emailed | |
| 3 | Reject | Status = Rejected, requester emailed | |
| 4 | <edge case: missing approver, large amount, etc.> | <expected> | |

## 9. Operating notes
- Runs as: <connection owner>; emails come from that mailbox.
- Failure alerts: <who>.
- Known limits: <approval expiry 30 days, polling delay, etc.>
- To change routing rules: <edit list X, not the flow>.

## 10. Open points and assumptions
<Anything assumed, untested, or awaiting a decision. Say plainly what was not tested.>
```
