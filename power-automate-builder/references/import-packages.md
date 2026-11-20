# Building import packages and guiding the user

The skill's only output. It works in any Claude surface that can run code and hand over files, and nothing touches the tenant until the user imports.

## Build steps (Claude)

1. Write one flow file per flow (see `wdl-patterns.md`), plus `lists.json` if lists are needed.
2. Fill real values wherever known. Site URL is essential; list names can be the display title. Use `<<PLACEHOLDER>>` only for values the user genuinely has not given (Teams channel IDs, people not yet chosen).
3. Generate, validate, package:
```
python scripts/make_provisioning_flow.py lists.json --out flow0.json        # if lists needed
python scripts/validate_definition.py flow0.json flow1.json flow2.json
python scripts/build_package.py flow0.json flow1.json flow2.json \
    --out /mnt/user-data/outputs \
    --set SITE_URL=https://tenant.sharepoint.com/sites/X \
    --set "LIST_REQUESTS=Purchase Requests"
```
4. Fix every validator ERROR before packaging. Warnings about placeholders go into the Build Sheet as post-import tasks.
5. Generate the Install Checklist page. This is mandatory with every set of zips:
```
python scripts/make_install_checklist.py flow0.json flow1.json flow2.json \
    --title "<Process name>" --site https://tenant.sharepoint.com/sites/X \
    --lists lists.json --extras extras.json \
    --set SITE_URL=... --set "LIST_REQUESTS=Purchase Requests" \
    --out /mnt/user-data/outputs/<Process>_Install_Checklist.html
```
   `extras.json` carries `coOwner`, `tests` (each `do` and `expect`, taken from the Build Sheet), `values` (anything to set after import) and `notes`. Publish the page as an artifact where the session allows; otherwise present the file.
6. Write the Build Sheet (`build-sheet-template.md`) and present the zips, the checklist and the sheet together.

One zip per flow. Name them so they sort in run order (`... - 0 Provision lists`, `... - 1 ...`).

## Import instructions (reference; the Install Checklist page carries these for the user)

Before you start
* Sign in to https://make.powerautomate.com with your work account.
* Top right, check the **Environment** is the one your team uses (usually the default environment named after the organisation).
* Under **Data > Connections** (or **More > Connections**), make sure you have working connections for: <list the connectors>. If one is missing, select **New connection**, pick it, sign in.

Import each package, in number order
1. Select **My flows**, then **Import > Import Package (Legacy)**.
2. Select **Upload**, choose the zip, wait for the package details.
3. Under **Review package content**, the flow row shows **Create as new**. Leave it (choose **Update** only when replacing a flow you imported before).
4. For each connection row (SharePoint, Approvals, Office 365 Outlook...), select **Select during import**, pick your connection, **Save**. A red icon means it is not yet set.
5. Select **Import**. When it finishes, select **Open flow**.

After import, for every flow
1. Open the flow in the designer. Open each SharePoint action and confirm **Site Address** and **List Name** show values, not errors. If one shows an error, reselect from the drop-down.
2. Set anything listed under "Values to set after import" in the Build Sheet.
3. **Save**. Fix any "Flow checker" errors shown at the top.
4. Imported flows can arrive switched off. On the flow's details page select **Turn on**.
5. **Share** (Edit) with your co-owner so the flow survives absences.

Provision the lists (flow 0)
1. Open flow 0, select **Run > Run flow**.
2. Open the run from the details page. All list steps should be green. Red steps named `Add_...` on a second run only mean the column already existed.
3. Check the lists on the SharePoint site. Then delete flow 0, or keep it switched off.

Test
Run the test cases in the Build Sheet. For triggered flows, create a real test item and watch **28-day run history**; SharePoint triggers poll, so allow a minute or two.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| No **Import Package (Legacy)** option | The environment requires solutions. Import into another environment you can use (often the default), or ask the Power Platform admin to allow package import. |
| "The package is invalid" / upload fails | Zip was altered or re-zipped with the folder on top. Re-download the original file; do not unzip and re-zip it. |
| Import fails with `WorkflowRunActionInputsMissingProperty` ... `host.connectionReferenceName is missing` | The package was built without connection references. Rebuild it with `build_package.py`, which declares every connection under `connectionReferences`, and import again. |
| Import button stays grey | A connection row is still unset. Set each one under **Select during import**. |
| "Connector blocked by DLP policy" | A data loss prevention policy forbids that connector combination. Ask the admin, or redesign with allowed connectors. |
| Action shows "The table ... not found" | List name differs or contains a full stop. Reselect the list in the action. |
| `InvalidTemplate` / expression error on save | Ask Claude with the exact error text; it usually names the action. |
| Run fails with 400 on Update item | A required column was not supplied, a Choice value does not match exactly, or a Person value is not a valid claim/email. |
| Run fails with 403 | The connection owner lacks permission on the site or list. |
| Flow runs twice or forever | Update-item loop. Add the trigger condition from the Build Sheet. |
| Flow 0 fails with 403, or its HTTP action is blocked | The person running it lacks Edit on the site, or a policy blocks "Send an HTTP request to SharePoint". Grant Edit, or ask the site owner to create the lists from the column tables in the Build Sheet. |

## Moving to solutions later

If the organisation wants ALM (dev/test/prod), import the package once into the development environment, then in **Solutions** open a solution, **Add existing > Automation > Cloud flow > Outside Dataverse**, and select the imported flow. From then on export the solution, not the package.
