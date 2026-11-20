#!/usr/bin/env python3
"""Create the Automation Intake Workbook (.xlsx) that teams fill in.

The workbook is the deterministic input format for this skill: every list,
column, flow and step sits in a fixed cell with drop-down choices, so
scripts/intake_to_build.py converts it the same way every time.

Usage: python make_intake_template.py --out Automation_Intake_Template.xlsx [--blank]
--blank leaves out the worked example rows (purchase request approval).
"""
import argparse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
EXAMPLE_FONT = Font(name=FONT, size=10, color="0000FF")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

COLUMN_TYPES = ["text", "note", "richtext", "number", "currency", "date", "datetime", "boolean",
                "choice", "multichoice", "person", "personmulti", "url", "lookup"]
TRIGGERS = ["SharePoint item created", "SharePoint item created or modified", "SharePoint file created",
            "Schedule", "Manual button"]
STEP_TYPES = ["Start approval and wait", "Start approval and wait (everyone)", "Condition", "Update item",
              "Create item", "Send email", "Post to Teams channel", "Get manager", "Delay",
              "Custom (describe in Notes)"]
FREQ = ["Day", "Week", "Month", "Hour"]
YESNO = ["Yes", "No"]

SHEETS = {
    "Lists": ["List title", "URL name (no spaces)", "Description", "Title column display name", "Already exists?"],
    "Columns": ["List title", "Internal name (no spaces)", "Display name", "Type", "Required?", "Choices (separate with ;)",
                "Default", "Lookup list", "Lookup column", "Indexed?", "Notes"],
    "Flows": ["Flow no", "Flow name", "Trigger", "Trigger list", "Trigger condition", "Schedule frequency",
              "Schedule interval", "Schedule days (separate with ;)", "Schedule time (HH:MM)", "Description"],
    "Steps": ["Flow no", "Step no", "Step name", "Step type", "Inside step no", "Branch (Yes/No)", "Target list",
              "Item ID", "Field values (Column=value; ...)", "To / Assigned to", "Subject / Title / Duration",
              "Body / Details", "Condition (Left | operator | Right)", "Notes"],
}
WIDTHS = {
    "Lists": [26, 24, 40, 26, 16],
    "Columns": [22, 24, 24, 14, 11, 34, 16, 18, 16, 10, 30],
    "Flows": [9, 44, 32, 22, 40, 16, 14, 24, 16, 44],
    "Steps": [9, 9, 26, 30, 13, 13, 22, 16, 52, 34, 40, 52, 44, 30],
}

EXAMPLE = {
    "Process": {
        "Process name": "Purchase Requests", "Department": "Procurement",
        "Owner email": "owner@contoso.com", "Co-owner email": "coowner@contoso.com",
        "SharePoint site URL": "https://contoso.sharepoint.com/sites/Procurement",
        "Environment": "Default", "Time zone": "UTC", "Date format": "yyyy-MM-dd", "Currency": "",
        "Failure alert email": "owner@contoso.com",
        "Purpose": "Staff raise purchase requests; the named approver approves or rejects; the requester is told.",
    },
    "Lists": [
        ["Departments", "Departments", "Reference list of departments and their heads", "", "No"],
        ["Purchase Requests", "PurchaseRequests", "Purchase requests raised by staff", "Item Description", "No"],
    ],
    "Columns": [
        ["Departments", "DepartmentHead", "Department Head", "person", "Yes", "", "", "", "", "No", ""],
        ["Purchase Requests", "Amount", "Amount", "currency", "Yes", "", "", "", "", "No", ""],
        ["Purchase Requests", "Department", "Department", "lookup", "Yes", "", "", "Departments", "Title", "No", ""],
        ["Purchase Requests", "Justification", "Justification", "note", "Yes", "", "", "", "", "No", ""],
        ["Purchase Requests", "Approver", "Approver", "person", "Yes", "", "", "", "", "No", ""],
        ["Purchase Requests", "Status", "Status", "choice", "No", "Submitted;Approved;Rejected", "Submitted", "", "", "Yes", ""],
        ["Purchase Requests", "DecisionDate", "Decision Date", "date", "No", "", "", "", "", "No", ""],
        ["Purchase Requests", "ApproverComments", "Approver Comments", "note", "No", "", "", "", "", "No", ""],
    ],
    "Flows": [
        [1, "Approval on new request", "SharePoint item created", "Purchase Requests", "", "", "", "", "",
         "Send each new request to its approver and record the decision."],
    ],
    "Steps": [
        [1, 1, "Start approval", "Start approval and wait", "", "", "", "", "", "{Trigger.Approver}",
         "Purchase request: {Trigger.Title}",
         "Requested by: {Trigger.CreatedBy.Name}\nAmount: {Trigger.Amount}\nJustification: {Trigger.Justification}", "", ""],
        [1, 2, "Is approved", "Condition", "", "", "", "", "", "", "", "", "{Approval.Outcome} | equals | Approve", ""],
        [1, 3, "Mark as approved", "Update item", 2, "Yes", "Purchase Requests", "{Trigger.ID}",
         "Status=Approved; DecisionDate={Today}; ApproverComments={Approval.Comments}", "", "", "", "", ""],
        [1, 4, "Email requester approved", "Send email", 2, "Yes", "", "", "", "{Trigger.CreatedBy.Email}",
         "Approved: {Trigger.Title}", "Your purchase request {Trigger.Title} has been approved.\nComments: {Approval.Comments}", "", ""],
        [1, 5, "Mark as rejected", "Update item", 2, "No", "Purchase Requests", "{Trigger.ID}",
         "Status=Rejected; DecisionDate={Today}; ApproverComments={Approval.Comments}", "", "", "", "", ""],
        [1, 6, "Email requester rejected", "Send email", 2, "No", "", "", "", "{Trigger.CreatedBy.Email}",
         "Not approved: {Trigger.Title}", "Your purchase request {Trigger.Title} was not approved.\nComments: {Approval.Comments}", "", ""],
    ],
}

README = [
    ("Automation Intake Workbook", "title"),
    ("Describe the automation here. Claude converts this workbook into SharePoint lists and Power Automate flows the same way every time.", ""),
    ("", ""),
    ("How to fill it in", "head"),
    ("1. Process: one value per yellow cell. The SharePoint site URL is essential. Time zone, Date format and Currency are your organisation's settings (see below).", ""),
    ("2. Lists: one row per list. Mark 'Already exists?' Yes for lists you already have, and still list their columns on the Columns sheet.", ""),
    ("3. Columns: one row per column. Internal name has no spaces and never changes; Display name is what users see.", ""),
    ("4. Flows: one row per flow, numbered 1, 2, 3. Pick the trigger from the drop-down.", ""),
    ("5. Steps: one row per step, numbered within each flow. For steps inside a Condition, give the condition's step no and the branch (Yes or No).", ""),
    ("Blue rows are a worked example. Overwrite or delete them.", ""),
    ("", ""),
    ("Tokens you can use in any text, To, Item ID or Field values cell", "head"),
    ("{Trigger.ID}, {Trigger.Title}, {Trigger.Link}: the item that started the flow", ""),
    ("{Trigger.<Column>}: a column of that item, using its internal name. Choice gives the value; Person gives the email.", ""),
    ("{Trigger.<Column>.Name}: a Person column's display name", ""),
    ("{Trigger.CreatedBy.Email}, {Trigger.CreatedBy.Name}: who created the item", ""),
    ("{Approval.Outcome} (Approve or Reject), {Approval.Comments}, {Approval.Responder}: the latest approval step before this one", ""),
    ("{Manager.Email}, {Manager.Name}: the latest Get manager step before this one", ""),
    ("{Today} (yyyy-MM-dd), {Now} (local date and time, in your Date format), {Owner.Email}", ""),
    ("", ""),
    ("Your organisation's settings (Process sheet)", "head"),
    ("Time zone: a Windows time zone name, e.g. UTC, GMT Standard Time, Eastern Standard Time, W. Europe Standard Time, Arab Standard Time. Used by schedules and {Now}. Blank means UTC.", ""),
    ("Date format: how dates appear in messages, e.g. dd/MM/yyyy, MM/dd/yyyy or yyyy-MM-dd. Blank means yyyy-MM-dd. Date columns always store yyyy-MM-dd.", ""),
    ("Currency: a code such as USD, GBP, EUR, SAR, AED, CAD, AUD, INR, JPY or CHF, or a SharePoint locale ID. Blank means the site's own regional currency.", ""),
    ("", ""),
    ("Formats", "head"),
    ("Field values: Column=value; Column=value   e.g. Status=Approved; DecisionDate={Today}", ""),
    ("Condition and Trigger condition: Left | operator | Right   e.g. {Trigger.Amount} | greater than | 50000", ""),
    ("Operators: equals, not equals, greater than, greater or equal, less than, less or equal, contains, starts with, is empty, is not empty", ""),
    ("Delay: put the duration in 'Subject / Title / Duration', e.g. 2 Day or 4 Hour", ""),
    ("Post to Teams channel: To = team ID|channel ID, or leave blank and set it after import", ""),
    ("Custom step: describe what it must do in Notes; Claude writes it by hand and flags it for review.", ""),
]


def style_header(ws, headers, widths):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(name=FONT, bold=True, color="FFFFFF", size=10)
        c.fill = HEAD_FILL
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = BORDER
        ws.column_dimensions[c.column_letter].width = widths[i - 1]
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"


def add_list_validation(ws, col_letter, formula, rows=300):
    dv = DataValidation(type="list", formula1=formula, allow_blank=True)
    dv.add(f"{col_letter}2:{col_letter}{rows}")
    ws.add_data_validation(dv)


def build(path, blank):
    wb = Workbook()
    rd = wb.active
    rd.title = "Read Me"
    rd.column_dimensions["A"].width = 130
    for r, (text, kind) in enumerate(README, 1):
        c = rd.cell(row=r, column=1, value=text)
        c.font = Font(name=FONT, size=14 if kind == "title" else 10, bold=kind in ("title", "head"),
                      color="1F3864" if kind else "000000")
        c.alignment = Alignment(wrap_text=True)

    ps = wb.create_sheet("Process")
    ps.column_dimensions["A"].width = 26
    ps.column_dimensions["B"].width = 80
    for i, h in enumerate(["Field", "Value"], 1):
        c = ps.cell(row=1, column=i, value=h)
        c.font = Font(name=FONT, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
    for r, key in enumerate(EXAMPLE["Process"], 2):
        ps.cell(row=r, column=1, value=key).font = Font(name=FONT, bold=True, size=10)
        v = ps.cell(row=r, column=2, value=None if blank else (EXAMPLE["Process"][key] or None))
        v.fill = INPUT_FILL
        v.font = EXAMPLE_FONT if not blank else Font(name=FONT, size=10)
        v.border = BORDER
        v.alignment = Alignment(wrap_text=True)
    ps.freeze_panes = "A2"

    opts = wb.create_sheet("Options")
    for col, values in enumerate([COLUMN_TYPES, TRIGGERS, STEP_TYPES, FREQ, YESNO], 1):
        for r, v in enumerate(values, 1):
            opts.cell(row=r, column=col, value=v)
    opts.sheet_state = "hidden"

    for name, headers in SHEETS.items():
        ws = wb.create_sheet(name)
        style_header(ws, headers, WIDTHS[name])
        if not blank:
            for r, row in enumerate(EXAMPLE[name], 2):
                for c, val in enumerate(row, 1):
                    cell = ws.cell(row=r, column=c, value=val if val != "" else None)
                    cell.font = EXAMPLE_FONT
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
                    cell.border = BORDER
    wb["Lists"]["E1"].comment = None
    add_list_validation(wb["Lists"], "E", "Options!$E$1:$E$2")
    add_list_validation(wb["Columns"], "D", f"Options!$A$1:$A${len(COLUMN_TYPES)}")
    add_list_validation(wb["Columns"], "E", "Options!$E$1:$E$2")
    add_list_validation(wb["Columns"], "J", "Options!$E$1:$E$2")
    add_list_validation(wb["Flows"], "C", f"Options!$B$1:$B${len(TRIGGERS)}")
    add_list_validation(wb["Flows"], "F", f"Options!$D$1:$D${len(FREQ)}")
    add_list_validation(wb["Steps"], "D", f"Options!$C$1:$C${len(STEP_TYPES)}")
    add_list_validation(wb["Steps"], "F", "Options!$E$1:$E$2")
    wb.move_sheet("Options", offset=10)
    wb.save(path)
    print(f"Wrote {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Automation_Intake_Template.xlsx")
    ap.add_argument("--blank", action="store_true")
    a = ap.parse_args()
    build(a.out, a.blank)
