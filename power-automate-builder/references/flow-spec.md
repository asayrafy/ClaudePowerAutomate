# Capturing the flow specification

Most failed automations fail at the requirements stage, not the build. Turn the user's plain description into a written Flow Specification and get their confirmation before building anything. The specification is also the audit trail for what was built and why.

## The questions that matter

Ask only what the description leaves open. Group questions; one round is ideal, two at most. Offer a sensible default for each so the user can simply say "yes".

1. **Trigger.** What starts it? A new or changed list item, a file in a library, an email, a Forms response, a schedule (day, time, time zone), or a button press.
2. **Data.** Which SharePoint site holds the data (full URL)? Do the lists exist already? If yes, get the exact list names and column names. If no, agree the columns and types now.
3. **People.** Who approves, who is notified, who must never be emailed? Fixed people (email addresses) or people taken from the item (a Person column)?
4. **Steps and rules.** Conditions, thresholds, branches, escalations, reminders, deadlines.
5. **Outcome.** What is written back, to which column, and who hears about it?
6. **Failure.** Who should know if the flow fails? Does a timed-out approval need handling?
7. **Ownership.** Whose connections run it (emails go out from that person's mailbox)? Who is co-owner?
8. **Settings.** Any organisation setting marked "ask" in SKILL.md that this build uses: time zone (schedules, local times), date format (dates in messages), currency (currency columns) and, for approvals, the approval authority the routing must follow (for example a delegation of authority or an approval matrix).

## Defaults to propose

* Time zone, date format and currency: the organisation settings in SKILL.md. Where a setting says "ask", suggest the user's own time zone, `yyyy-MM-dd` and the site's own currency.
* Polling SharePoint triggers fire within about a minute of the change.
* Approvals: "Approve/Reject, first to respond", 7-day reminder, 30-day platform limit.
* Status tracked in a Choice column, decision date and comments written back to the item.
* Standard connectors only (SharePoint, Office 365 Outlook, Office 365 Users, Teams, Approvals, OneDrive, Excel Online, Forms, Planner).

## Specification template

Write this in the conversation (or in the Build Sheet) and ask the user to confirm or correct it.

```
FLOW SPECIFICATION: <Process name>
Purpose: <one sentence>
Owner / co-owner: <names>
Environment: <default, unless told otherwise>
Site: <https://tenant.sharepoint.com/sites/...>
Settings: time zone <...> | date format <...> | currency <...> | approval authority <...>

Lists
  <List title> (URL name: <NoSpaces>)
    - <Display name> | <type> | required? | choices/default | notes
  ...

Flow 1: <Department - Process - Trigger>
  Trigger: <connector, operation, list, conditions>
  Steps:
    1. ...
    2. If <condition>: ... Otherwise: ...
  Writes back: <columns>
  Notifies: <who, how>
  Error handling: <who is told>
Flow 2: ...

Connections needed: SharePoint, Approvals, Office 365 Outlook
Licensing: standard connectors only / premium needed for <X>
Open points: <anything not yet decided>
```

## Naming conventions

* Flows: `<Department> - <Process> - <what it does>`, numbered when several belong together (`HR - Onboarding - 1 New starter request`). The provisioning flow is number 0.
* Lists: display title in plain words; URL name without spaces (`PurchaseRequests`). Columns: create with an internal name without spaces (`DecisionDate`) and a friendly display name (`Decision Date`). Internal names are permanent and are what flows reference.
* Actions inside a flow: verb plus object (`Mark_as_approved`, `Email_requester`). The designer shows underscores as spaces.

## Sizing the job

* One flow per trigger. Split a long process into several flows linked by a Status column, rather than one flow that waits for weeks.
* If the description needs a premium connector (HTTP, Dataverse, SQL, custom connectors), Power Apps, or child flows (which require solutions), say so in Open points before building.
