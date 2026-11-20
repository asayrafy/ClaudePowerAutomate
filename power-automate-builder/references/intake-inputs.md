# Inputs: documents and the intake workbook

## Which input gives which certainty

| Input | Certainty | Why |
|---|---|---|
| Automation Intake Workbook | High, repeatable | Fixed cells, drop-down values, a token vocabulary and a script that converts it the same way every time. |
| Structured process document (procedure with numbered steps, RACI, swimlane chart) | Medium | Claude interprets it; good documents leave few gaps. |
| Narrative document, email or chat description | Lower | Many decisions are implicit; expect a round of questions. |

Recommend the workbook whenever the process will be maintained, audited or rebuilt in other sites. Word is the right place for the narrative and the policy rationale; Excel is the right place for what the build needs.

## Reading a process document

1. Read the whole document before drafting. Use the file-reading or pdf-reading skill for formats not already in context.
2. Extract, with the section reference for each:
   * **Trigger**: the event that starts the process.
   * **Actors**: roles and named people; map roles to Person columns or reference lists rather than hard-coded emails.
   * **Data**: every field captured or decided, with type and allowed values.
   * **Decisions**: thresholds, conditions, approval levels, delegation and escalation rules.
   * **Outputs**: records updated, notifications, documents produced.
   * **Timings**: deadlines, reminders, SLAs.
3. Separate what is automatable from what stays manual. Say which steps you are leaving out and why.
4. List contradictions and gaps as numbered questions (for example "Section 4.2 says the line manager approves; the approval matrix in Annex B says the department head. Which applies?"). Never resolve a policy conflict silently.
5. For more than a handful of steps, fill the intake workbook from the document: open the template, write rows, save a copy as `<Process>_Intake.xlsx`, and present it. The user corrects the workbook; you convert it.

## The intake workbook

Template: `assets/templates/Automation_Intake_Template.xlsx` (worked example in blue). Regenerate with `scripts/make_intake_template.py`.

Sheets: **Read Me** (instructions and tokens), **Process** (name, department, owner, co-owner, site URL, environment, time zone, date format, currency, failure alert email, purpose), **Lists**, **Columns**, **Flows**, **Steps**.

Supported triggers: SharePoint item created; item created or modified; file created; Schedule; Manual button.

Supported step types: Start approval and wait (first to respond, or everyone); Condition (with Yes and No branches through "Inside step no" and "Branch"); Update item; Create item; Send email; Post to Teams channel; Get manager; Delay; Custom.

Tokens: `{Trigger.<Column>}` (Choice gives its value, Person its email), `{Trigger.<Column>.Name}`, `{Trigger.ID}`, `{Trigger.Title}`, `{Trigger.Link}`, `{Trigger.CreatedBy.Email}`, `{Trigger.CreatedBy.Name}`, `{Approval.Outcome}`, `{Approval.Comments}`, `{Approval.Responder}`, `{Manager.Email}`, `{Manager.Name}`, `{Today}`, `{Now}`, `{Owner.Email}`.

Condition format: `Left | operator | Right`, operators equals, not equals, greater than, greater or equal, less than, less or equal, contains, starts with, is empty, is not empty.

What the converter adds by itself:
* Column write formats from the Columns sheet (Choice, Person claims, Lookup ID, numbers, Yes/No).
* A Try scope around every flow and a Catch scope that emails the failure alert address with a link to the failed run, when that address is given.
* A warning for a "created or modified" trigger that updates its own list without a trigger condition (a loop).
* Flow names `<Department> - <Process> - <n> <Flow name>` and a provisioning flow numbered 0 for lists not marked as existing.
* Organisation settings from the Process sheet. Time zone is a Windows time zone name; Date format shapes `{Now}`; Currency takes a code such as USD, GBP or EUR, or a SharePoint locale ID. Blank values fall back to UTC, `yyyy-MM-dd` and the site's own currency. The specification lists every setting, and a schedule or `{Now}` with no time zone is reported as a warning, so ask the user for it.

What it cannot do, so Claude must:
* **Custom** steps become clearly labelled placeholders. Write them by hand with `wdl-patterns.md`, replacing the placeholder action in the flow file, then validate again.
* Loops over many items, Get items with filters, multi-value fields and Teams channel IDs need hand-editing or post-import selection; the report names each one.

After converting: show `specification.md`, read out each line of `conversion_report.txt`, get confirmation, then continue at stage 2 of SKILL.md with the generated files. If the user changes anything, change the workbook and convert again, so the workbook stays the single source of truth.
