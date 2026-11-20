---
name: power-automate-builder
description: Turns a business process into working Microsoft Power Automate cloud flows and the SharePoint lists they need, run with the user's own Microsoft 365 connections. Accepts a plain description, an uploaded process document (procedure, SOP, policy, flowchart) or the Automation Intake Workbook (Excel), which converts deterministically. Confirms a flow specification, then delivers importable .zip packages for Power Automate's Import Package (Legacy), one per flow, with a flow 0 package that creates the SharePoint lists, plus an Install Checklist and a Build Sheet. It never builds in the tenant directly. Use whenever someone wants to automate an approval, notification, reminder, request, register, tracker or hand-off in Microsoft 365, uploads a process to automate, or mentions Power Automate, Flow, SharePoint lists or approvals, even without naming Power Automate.
compatibility: Needs code execution (Python 3 with openpyxl) and file output to convert the workbook and build the packages. Works in claude.ai, Cowork and Claude Code.
license: Apache-2.0. Complete terms in LICENSE; attribution in NOTICE.
metadata:
  version: "1.0"
  updated: "2026-11-20"
---

# Power Automate Builder

Build Power Automate cloud flows and SharePoint lists from a description of what needs to happen. The user's own connections run everything, so flows act with their permissions and their mailbox.

The skill has one output: import packages (.zip) that the user imports into Power Automate through **My flows > Import > Import Package (Legacy)**. Flow 0 creates the lists; flows 1 onwards do the work. Claude never creates or changes flows or lists in the tenant itself.

## Organisation settings

These settings fit the skill to the organisation using it. None is tied to a particular company or country. "Ask" means: ask the user in the specification round (stage 1), suggest the default shown, and record the answer in the specification and the Build Sheet. A team that shares the skill can replace "ask" with its own values, so that its staff are not asked again.

| Setting | Value | Used for |
|---|---|---|
| Language and spelling | Match the user | Replies, list and column names, email and approval text. Reply in the language the user writes in. |
| Writing style | Plain language, short sentences, clear signposting | Everything written to the user, including the Build Sheet |
| Time zone | Ask. Suggest the user's own zone, as a Windows time zone name such as `UTC`, `GMT Standard Time`, `Eastern Standard Time` or `Arab Standard Time` | Scheduled triggers and local times in messages |
| Date format | Ask. Suggest `yyyy-MM-dd`, which reads the same everywhere | Dates shown in emails, approvals and Teams posts. Date columns always store `yyyy-MM-dd`. |
| Currency | Ask. Suggest the SharePoint site's own regional currency | Currency columns (`lcid`, see `references/sharepoint-lists.md`) |
| Approval authority | Ask whenever a flow approves something, for example a delegation of authority or an approval matrix | Who may approve what, and the thresholds |
| Connectors | Standard only, unless the user confirms a premium licence and DLP approval | Design |
| Naming | Flows `<Department> - <Process> - <n> <what it does>`; lists in plain words with URL names without spaces | Flow and list names |
| Ownership | Every flow that changes data gets a co-owner and a failure notification | Design and hand-over |

Ask only for the settings a build uses. A flow with no schedule and no local times needs no time zone; a build with no currency column needs no currency. The Automation Intake Workbook carries Time zone, Date format and Currency on its Process sheet. When one is blank, the converter uses UTC, `yyyy-MM-dd` or the site's currency, shows that in the specification, and warns when a schedule or local time has no time zone. Confirm these with the user before building.

## Workflow

Follow these stages in order. Do not build before the specification is confirmed; rework after the fact costs the user far more than one round of questions.

### 1. Understand and specify

First identify the input, because it decides how much interpretation is needed. Read `references/intake-inputs.md` for the detail.

| Input | What to do |
|---|---|
| Filled Automation Intake Workbook (.xlsx with Process, Lists, Columns, Flows, Steps sheets) | Run `scripts/intake_to_build.py`. It writes `specification.md`, `lists.json`, one flow file per flow and `conversion_report.txt`. Show the specification and every report line; resolve warnings with the user. This is the deterministic route. |
| Process document (procedure, SOP, policy, RACI, flowchart, minutes, email) | Read it fully. Extract triggers, actors, decisions, data and outcomes, citing the section each came from. Draft the specification, and list gaps and ambiguities as questions. For anything sizeable, fill a copy of the intake workbook from the document and give it back for the user to correct; then convert it as above. |
| Plain description in chat | As below. Offer the intake workbook (`assets/templates/Automation_Intake_Template.xlsx`) when the process has more than about five steps or several lists. |

Read `references/flow-spec.md`. From the user's description, draft the Flow Specification (lists, flows, triggers, steps, people, outcomes). Ask only for what is missing, in one grouped round, offering defaults; include any organisation setting marked "ask" that this build uses. The site URL is the one value you must have; without it lists cannot be provisioned and flows need manual rebinding.

Present the specification and get an explicit "yes" or corrections. Record any premium connectors, solution-only features (child flows) or policy concerns as open points before going further.

### 2. Confirm the session can build packages

Packages need code execution and file output. Read `references/import-packages.md`. If the session has neither, say so plainly, hand over the confirmed specification, and explain that the packages need a Claude session with code execution and file creation turned on. Do not offer another way to build.

The claude.ai Microsoft 365 connector cannot create flows or lists. Use it only to confirm the site URL, read context or upload the finished files to SharePoint, and never imply a direct build.

### 3. Lists

Read `references/sharepoint-lists.md`. Write `lists.json` from the specification, generate the provisioning flow (`scripts/make_provisioning_flow.py`) and package it as flow 0, with the real site URL. The Build Sheet records each list's columns.

If the lists already exist, do not recreate them. Ask for (or read) the exact list and internal column names and use those.

### 4. Flows

Read `references/wdl-patterns.md` and model each flow on `assets/examples/purchase-request/flow_approval.json`. Write one flow file per flow. Then always:

```
python scripts/validate_definition.py <flow files>
```

Fix every ERROR. Then package each flow:

```
python scripts/build_package.py <flow files> --out /mnt/user-data/outputs --set SITE_URL=... --set KEY=VALUE
```

Design rules that prevent most failures:
* One trigger per flow; split long processes into several flows linked by a Status column.
* Guard every "created or modified" trigger that writes back to the same list with a trigger condition.
* Wrap data-changing steps in Try/Catch scopes and notify the owner on failure.
* Use internal column names, `?['key']` access, and ISO dates.
* Where you are not certain of a connector parameter name, say so in the Build Sheet and use the copy-action route in `wdl-patterns.md` section 9. Never present a guess as verified.

### 5. Hand over

Write the Build Sheet from `references/build-sheet-template.md`: what it does, the confirmed specification, prerequisites, lists, files in order, install steps, values to set after import, test cases, operating notes and open points. Be explicit about what has and has not been tested; packages have been validated statically, not imported, until the user imports them.

**Every set of zip packages comes with the Install Checklist page.** It is the user's working instruction: tick boxes for every step, with this build's real file names, connections, lists, values to set and test cases. Generate it with `scripts/make_install_checklist.py`, passing the same flow files, order and `--set` values as the packager, plus `--lists` and an `extras.json` holding the Build Sheet's test cases, co-owner, values and notes. Then:

* If the session has an artifact publishing tool, publish the .html as an artifact and give the link, so the user can keep it open beside Power Automate.
* Otherwise present the .html file with the zips.

Do not paste the import steps into chat as a substitute. The Build Sheet stays the record of what was built; the checklist is how the user installs it.

Deliver the zips, the Install Checklist and the Build Sheet together, with a short message: the order to import, the one or two things the user must do by hand, and the first test to run.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/intake_to_build.py Intake.xlsx --out build/` | Deterministic conversion of the intake workbook into specification, lists spec and flow files, with Try/Catch failure alerts and a report of every assumption. |
| `scripts/make_intake_template.py --out X.xlsx [--blank]` | Regenerates the intake template (with or without the worked example). |
| `scripts/make_provisioning_flow.py lists.json --out flow0.json` | Flow that creates lists and columns via "Send an HTTP request to SharePoint" (standard connector, idempotent). Spec format in the script header. |
| `scripts/validate_definition.py flow.json ...` | Static checks: one trigger, unique legal names, runAfter targets, references to missing actions or loops, bracket balance, connector host fields, leftover placeholders. |
| `scripts/make_install_checklist.py flows... --title T --site URL [--lists] [--extras] --out X.html` | Tailored install page with tick boxes (remembered in the browser), progress bar and test steps. Publish as an artifact. |
| `scripts/build_package.py flow.json ... --out DIR [--set K=V]` | Wraps each flow in an import package (.zip) for **Import Package (Legacy)**, detecting the connections needed. Python standard library only. |

## Boundaries

* Build only what the confirmed specification covers. Never alter or delete existing flows, lists or permissions unless the user names them and asks.
* Deliver import packages only. Never create, change or switch on flows or lists in the tenant directly; the user imports and enables them.
* Never ask for passwords, secrets or MFA codes. Users sign in themselves.
* Test messages go to the user, not to real approvers or customers, unless the user says otherwise.
* Flag privacy and governance concerns (personal data in lists, external sharing, emails to outside domains, premium licensing) as open points; do not silently design around them.
