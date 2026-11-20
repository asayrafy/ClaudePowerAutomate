# Power Automate Builder: a skill for Claude

Turn a business process into Microsoft Power Automate cloud flows and the SharePoint lists they need. You describe the process, Claude writes a specification for you to confirm, and you receive ready-to-import packages (.zip) with step-by-step installation and test instructions.

- **Version:** 1.0, the first public release
- **Author:** Ahmed SERAFY, Perficio Limited
- **Co-authored by:** Claude Code
- **Licence:** [Apache 2.0](LICENSE), with attribution in [NOTICE](NOTICE)
- **Website:** [asayrafy.github.io/ClaudePowerAutomate](https://asayrafy.github.io/ClaudePowerAutomate/)

> **Provided as is.** This skill and everything in this repository comes with no warranty, and the author accepts no responsibility for its use. Please read the [disclaimer](#disclaimer) before you use it.

## Contents

- [What is in this repository](#what-is-in-this-repository)
- [What the skill does](#what-the-skill-does)
- [What you need](#what-you-need)
- [Install the skill in your own Claude](#install-the-skill-in-your-own-claude)
- [How to use the skill](#how-to-use-the-skill)
- [Install the flows in Power Automate](#install-the-flows-in-power-automate)
- [Sample flows](#sample-flows)
- [Disclaimer](#disclaimer)
- [Licence](#licence)
- [Authorship](#authorship)

## What is in this repository

| Path | What it is |
| --- | --- |
| [`dist/power-automate-builder.zip`](dist/power-automate-builder.zip) | The skill, ready to upload to Claude |
| [`power-automate-builder/`](power-automate-builder/) | The skill's source: `SKILL.md`, reference notes, Python scripts, the Excel intake workbook, a worked example, and copies of the licence and notice |
| [`docs/User_Guide.md`](docs/User_Guide.md) | A plain-language guide for the people who will use the skill |
| [`docs/index.html`](docs/index.html) | The project's landing page, published with GitHub Pages |
| [`docs/power-automate-builder-helper.html`](docs/power-automate-builder-helper.html) | A helper page that writes your request to Claude, builds tokens and conditions, and carries a generic install checklist and troubleshooting. Use it on the [project website](https://asayrafy.github.io/ClaudePowerAutomate/power-automate-builder-helper.html), or download it and open it in your browser. |
| [`docs/project-instructions.txt`](docs/project-instructions.txt) | Instructions to paste into a shared Claude project |
| [`sample-flows/`](sample-flows/) | Sample Power Automate flows published by the author |
| [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) | The Apache 2.0 licence that covers everything in this repository, and the attribution notice that must travel with it |

## What the skill does

- **Three ways in.** Describe the process in chat, attach a written procedure or policy, or fill in the Automation Intake Workbook (Excel), which converts the same way every time.
- **Nothing is built until you agree.** Claude first writes a Flow Specification: the lists, the flows, their triggers, steps, people and outcomes. It builds only after you confirm it.
- **One output: import packages.** You receive one .zip package per flow, plus a "flow 0" package that creates the SharePoint lists and columns. Each build also comes with an Install Checklist page and a Build Sheet, which records what was built and how to test it.
- **You stay in control.** Claude never signs in to your Microsoft 365 tenant, never builds anything there directly and never asks for a password. You import the packages yourself, and the flows run on your own connections.
- **Fits any organisation.** Time zone, date format, currency and the approval authority are settings. Claude asks for any that a build needs, unless your organisation has set them in the skill.
- **Standard connectors by default.** SharePoint, Office 365 Outlook, Office 365 Users, Teams and Approvals. Premium connectors are flagged rather than used silently.

## What you need

**For the skill**

- A Claude plan that supports custom skills, with code execution turned on. This works in Claude on the web, the desktop apps, Claude Code and Cowork. Check [Anthropic's help article](https://support.claude.com/en/articles/12512180-how-to-create-custom-skills) for the plans that currently support skills.
- The skill's scripts use Python 3 with `openpyxl`. If Claude reports that `openpyxl` is missing, ask it to install the package.

**For the flows**

- Microsoft 365 with Power Automate and SharePoint Online.
- Access to [make.powerautomate.com](https://make.powerautomate.com), with **Import Package (Legacy)** available in your environment. It is usually available in the default environment.
- Edit permission on the SharePoint site where the lists will live.
- Connections in Power Automate for the connectors your flows use, for example SharePoint, Approvals and Office 365 Outlook.

## Install the skill in your own Claude

### Claude on the web and in the desktop apps

1. Download [`dist/power-automate-builder.zip`](dist/power-automate-builder.zip). On GitHub, open the file and select **Download raw file**. Do not unzip it.
2. In Claude, open **Settings > Capabilities** and turn on **Code execution and file creation**. In newer layouts this is labelled **Create and edit files**.
3. Open **Customize > Skills**, select **+**, then **Create skill > Upload a skill**, and choose the .zip file.
4. Make sure **power-automate-builder** is switched on in the list of skills.

If the upload fails, check that the .zip still contains the `power-automate-builder` folder with `SKILL.md` inside it. Do not rename the folder, because the skill's name must match it.

### For a whole organisation (Team and Enterprise)

An organisation owner can make the skill available to every member:

1. Open **Organization settings > Plugins & skills**, select **Add**, then **Upload a skill**, and choose the .zip file.
2. On the **Policy** tab, make sure **Cloud code execution and file creation** and **Skills** are turned on.

The skill is then switched on for all members, and each member can switch it off for themselves. See [Provision and manage skills for your organization](https://support.claude.com/en/articles/13119606-provision-and-manage-skills-for-your-organization).

### Claude Code

Copy the skill folder into your personal skills folder.

macOS or Linux:

```bash
git clone https://github.com/asayrafy/ClaudePowerAutomate.git
mkdir -p ~/.claude/skills
cp -r ClaudePowerAutomate/power-automate-builder ~/.claude/skills/
python3 -m pip install openpyxl
```

Windows (PowerShell):

```powershell
git clone https://github.com/asayrafy/ClaudePowerAutomate.git
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse ClaudePowerAutomate\power-automate-builder "$HOME\.claude\skills\"
py -m pip install openpyxl
```

To share the skill with everyone working in one project instead, copy the folder to `.claude/skills/` inside that project and commit it. If the skill does not appear, run `/reload-skills`. See [Claude Code skills](https://code.claude.com/docs/en/skills).

### Cowork

Cowork has its own **Customize > Skills** area, where you can add the skill in the same way. Skills that your organisation provisions appear in Cowork automatically.

### Optional: set your organisation's settings

Out of the box, the skill asks for the time zone, date format, currency and approval authority whenever a build needs them. To set them once for your organisation:

1. Open `power-automate-builder/SKILL.md` and find the **Organisation settings** table.
2. Replace "Ask" with your values, for example `GMT Standard Time` for the time zone or `GBP` for the currency.
3. Zip the `power-automate-builder` folder itself, not just its contents, and upload the new .zip in place of the old one.

### Optional: a shared Claude project for your team

1. Create a project in Claude and paste [`docs/project-instructions.txt`](docs/project-instructions.txt) into its instructions.
2. Add [`docs/User_Guide.md`](docs/User_Guide.md) and the [intake workbook](power-automate-builder/assets/templates/Automation_Intake_Template.xlsx) to the project's knowledge.
3. Make sure each member has the skill switched on.

## How to use the skill

1. **Start a new chat** for each process, inside your team's project if you have one.
2. **Describe the process.** You can write it in chat, attach a procedure or policy, or attach a filled [Automation Intake Workbook](power-automate-builder/assets/templates/Automation_Intake_Template.xlsx). Always include the SharePoint site address. For example:

   ```
   Automate this process with the Power Automate Builder skill.
   Site: https://<tenant>.sharepoint.com/sites/<Site>
   Process: <what starts it, who does what, what is recorded, who is told>
   Owner: me. Co-owner: <name>. Failure alerts to: <email>.
   Time zone: <zone>. Date format: <format>. Currency: <code>.
   Write the specification first and wait for my confirmation.
   ```

   The [helper page](docs/power-automate-builder-helper.html) can build this message for you.
3. **Answer Claude's questions.** Claude asks for anything missing in one round, such as the co-owner, the failure alert address or the time zone.
4. **Confirm the specification.** Read the Flow Specification carefully. Reply "yes", or correct it. Claude builds nothing before you confirm.
5. **Receive the build.** You get the .zip packages, the Install Checklist and the Build Sheet.
6. **Install and test** the flows as described in the next section, then keep the Build Sheet as your change record.

The intake workbook gives the most repeatable result, and is best for anything beyond about five steps. Blue rows in the workbook are a worked example; overwrite or delete them. The [User Guide](docs/User_Guide.md) explains every sheet, token and format.

## Install the flows in Power Automate

Your Install Checklist carries these steps with your real file names, connections and lists. Work from the checklist; the steps below are the general version. Import the packages in number order: flow 0 creates the lists, so it goes first.

### Before you start

1. Sign in to [make.powerautomate.com](https://make.powerautomate.com) with your work account.
2. At the top right, check that the **Environment** is the one your team uses.
3. Under **Connections**, make sure you have working connections for each connector listed in the Build Sheet. If one is missing, select **New connection**, pick the connector and sign in.

### Import each package

1. Select **My flows > Import > Import Package (Legacy)**.
2. Select **Upload** and choose the .zip file. Do not unzip it first.
3. Under **Review package content**, leave the flow on **Create as new**.
4. For each connection row, choose **Select during import**, pick your connection, then **Save**.
5. Select **Import**. When it finishes, select **Open flow**.

### Create the lists (flow 0)

1. Open flow 0 and select **Run**, then **Run flow**.
2. Open the run. Every list step should be green.
3. Check that the lists now exist on your SharePoint site. Then delete flow 0, or leave it switched off.

Flow 0 skips lists that already exist. If you run it again, steps named `Add_...` show red for columns that already exist. That is expected.

### Finish each flow

1. Open the flow. Check that each SharePoint action shows its site and list. If one shows an error, select the value again from the drop-down.
2. Set anything listed under "Values to set after import" in the Build Sheet.
3. Select **Save** and clear any Flow checker errors.
4. On the flow's details page, select **Turn on**. Imported flows can arrive switched off.
5. Select **Share** and add your co-owner with edit rights, so the flow keeps working when you are away.

### Test and sign off

1. Run every test case in the Install Checklist or Build Sheet, using yourself as approver and recipient.
2. Test both branches of every condition, including rejection.
3. Test one failure on purpose, and confirm the failure alert arrives.
4. Check the run history after each test. SharePoint triggers poll, so allow one to two minutes.
5. Replace test people with real ones only after every case passes.

### If something goes wrong

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| No **Import Package (Legacy)** option | The environment only accepts solutions | Use the default environment, or ask your Power Platform admin to allow package import |
| "The package is invalid" | The .zip was unzipped and zipped again | Download the original file again and upload it untouched |
| The Import button stays grey | A connection row is not set | Set every row under **Select during import** |
| Blocked by a DLP policy | A data policy forbids that mix of connectors | Ask your admin, or ask Claude to redesign with allowed connectors |
| A 403 error when a flow runs | The connection owner lacks permission on the site or list | Grant Edit on the site or list |
| The flow runs again and again | It updates the list that triggers it | Add the trigger condition from the Build Sheet |

For anything else, paste the exact error text into the same chat with Claude. The [User Guide](docs/User_Guide.md#troubleshooting) has the full troubleshooting table.

## Sample flows

The [`sample-flows`](sample-flows/) folder holds sample flows published by the author. Each sample has its own folder with the import package and a README covering what it does, how to import it and how to test it. Samples install in the same way as the skill's own packages.

## Disclaimer

This skill, the flows and packages it produces, the sample flows and every other file in this repository are provided "as is", without warranty of any kind, express or implied. This includes, without limitation, any warranty of merchantability, fitness for a particular purpose, accuracy, reliability or non-infringement.

The author and Perficio Limited accept no responsibility or liability for any loss, damage, data loss, business interruption, cost or other consequence arising from the use of, or the inability to use, anything in this repository, however caused.

You use it entirely at your own risk. Flows produced with the help of an AI model can contain mistakes. Before any flow goes live, you are responsible for reviewing it, testing it in a safe environment, and making sure that it complies with your organisation's policies, including IT approval, data protection, data loss prevention and licensing.

This project is independent. It is not affiliated with, endorsed by or supported by Microsoft or Anthropic. Microsoft, Microsoft 365, Power Automate and SharePoint are trademarks of Microsoft Corporation. Claude is a trademark of Anthropic.

## Licence

Released under the [Apache License 2.0](LICENSE). You may use, copy, change and share the skill and the sample flows, including commercially. If you pass on the skill or a version of it, you must:

- include a copy of the licence;
- keep the attribution in the [NOTICE](NOTICE) file, which credits Ahmed SERAFY, Perficio Limited, in a NOTICE file, in your documentation or on your product's credits screen;
- mark every file you have changed, stating that you changed it;
- keep all existing copyright notices.

The licence gives no right to use the author's name or Perficio Limited's name to endorse or promote another product. Copies of `LICENSE` and `NOTICE` sit inside the skill folder, so they travel with the zip. The licence's own "as is" terms apply alongside the disclaimer above.

## Authorship

Written by **Ahmed SERAFY**, Perficio Limited.

Co-authored by **Claude Code**, Anthropic's AI coding assistant.
