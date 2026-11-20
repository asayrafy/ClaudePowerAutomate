# Sample flows

This folder holds sample Power Automate flows published by the author. Each sample has its own folder with the import package and a short README that explains what the flow does and how to install it.

Samples are covered by the repository's [Apache 2.0 licence](../LICENSE) and are provided as is, without warranty. See the [disclaimer](../README.md#disclaimer) in the main README.

## Samples

| Sample | What it does | Connectors |
| --- | --- | --- |
| *None yet* | | |

## Folder layout

```
sample-flows/
├── README.md               this page, including the list of samples
├── _template/
│   └── README.md           copy this for every new sample
└── <sample-name>/
    ├── README.md           what the flow does, how to import and test it
    ├── <Flow name>.zip     the import package exported from Power Automate
    ├── lists.json          optional: the SharePoint lists the flow needs
    └── screenshots/        optional
```

Use a short folder name in lower case with hyphens, for example `leave-request-approval`.

## Adding a sample

### 1. Export the flow from Power Automate

1. Sign in to [make.powerautomate.com](https://make.powerautomate.com) and open **My flows**.
2. Select the flow, then **More commands (…) > Export > Package (.zip)**.
3. Enter a name and a short description.
4. Under **Related resources**, set each connection to **Select during import**, so that people who import it use their own connections.
5. Select **Export** and save the .zip file. Do not unzip it.

### 2. Check it before you publish

This repository is public. An exported package does not carry anyone's sign-in, but it does carry every value typed into the flow. Before uploading, remove or replace:

- email addresses and people's names;
- SharePoint site addresses, tenant names and internal list names;
- approval thresholds, cost centres or anything else that reveals internal policy;
- links to internal documents or systems.

If in doubt, rebuild the flow with neutral values such as `https://contoso.sharepoint.com/sites/Demo` and `someone@contoso.com`, then export it again.

### 3. Upload it to GitHub

Using the GitHub website:

1. Open this repository and go to the `sample-flows` folder.
2. Select **Add file > Create new file**. In the name box type `<sample-name>/README.md`. The slash creates the new folder.
3. Paste the contents of [`_template/README.md`](_template/README.md), fill it in, and select **Commit changes**.
4. Open the new folder, select **Add file > Upload files**, add the .zip file (and any screenshots), and select **Commit changes**.
5. Add a row for the sample to the table at the top of this page.

## Using a sample

Import a sample in the same way as the skill's own packages. Follow [Install the flows in Power Automate](../README.md#install-the-flows-in-power-automate) in the main README, and read the sample's own README for the lists it needs and the values to set after import.
