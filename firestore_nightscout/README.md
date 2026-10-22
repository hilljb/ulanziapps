# Nightscout on the TC002

The clock pulls the live glucose value from Firestore and shows it as `128 mg/dl`.
This page is how to create the reader account and read that value from a computer.
Flashing the clock is a later step; Wi-Fi in `secrets.toml` can stay empty until then.

The value comes from [xdrip2gcp](https://github.com/hilljb/xdrip2gcp). xDrip uploads
about every five minutes, and xdrip2gcp overwrites one Firestore document,
`current/entries`. The number on the display is the integer field `sgv`, in mg/dL.

## What you need

* An xdrip2gcp project, or any Firestore Native database with that same document.
  The project needs a billing account. The reads themselves stay inside the
  Firestore free tier: one read a minute is about 1,440 a day, and the free
  allowance is 50,000 reads a day.
* The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install), signed in,
  with a project selected:

  ```bash
  gcloud auth login
  gcloud config set project YOUR_PROJECT_ID
  ```

  The signed-in account must be allowed to create a service account, create a
  custom role, create a service-account key, and change the project IAM policy.
  `roles/owner` covers that. No separate Python environment is required for
  `gcloud`.
* Python 3.9 or newer, and `openssl` on `PATH`. The reader signs a
  service-account JWT with `openssl`. There are no extra Python packages.
* A local `secrets.toml`, created in the next section.

## Secrets

From this directory:

```bash
cp secrets.example.toml secrets.toml
```

Set `project_id` if it is not already your `gcloud` default. Leave
`service_account_email` empty; `setup_reader.py` writes it. The JSON key is
created at `secrets/tc002-reader.json`.

`secrets.toml` and that JSON file are gitignored. `secrets.example.toml` is the
committed template and contains every key. Do not commit a firmware image
either: `*.img` is gitignored because a lasting image can contain the key or
the Wi-Fi password.

## Create the reader

```bash
python3 setup_reader.py
```

The script is safe to run again. It does not create a second account, role,
binding, or key. It does four things:

1. Service account `tc002-nightscout-reader@YOUR_PROJECT_ID.iam.gserviceaccount.com`.
2. Custom role `tc002NightscoutReader` with one permission, `datastore.entities.get`.
   That is a document read. It does not include list, write, delete, or export.
3. A project IAM binding for that account and role, with this condition:

   ```text
   resource.name=="projects/YOUR_PROJECT_ID/databases/(default)"
   ```

   `database_id` in `secrets.toml` is substituted for `(default)` when it differs.
4. A JSON key at `secrets/tc002-reader.json`, mode `0600`. If that file is
   already there, it is kept. Deleting it and running the script again creates
   a new key and leaves the old key on the account; delete unused keys in
   the Cloud console.

Firestore can take a few minutes to notice a new binding. The script retries
the read during that window, then prints the live line.

## Read the value

```bash
python3 read_current.py
```

Stdout is one line, for example `128 mg/dl`. The script does not use your
`gcloud` login. It signs a JWT with the JSON key, exchanges it for an access
token scoped only to `https://www.googleapis.com/auth/datastore`, and GETs:

```text
https://firestore.googleapis.com/v1/projects/YOUR_PROJECT_ID/databases/(default)/documents/current/entries
```

The glucose number is `fields.sgv.integerValue`. The units suffix is
`units_label` in `secrets.toml`.

Check the boundary as well:

```bash
python3 read_current.py --check-access
```

Listing collections must come back denied (`403`). A GET of another path is
reported too. See the next section for how to read that result.

## What this account can do

The key can GET documents in the one database named in the condition. It
cannot list collections, write, delete, export, or read a different database.

It is not limited to `current/entries`. Firestore IAM conditions support a
database resource name, `projects/PROJECT/databases/DATABASE`, and do not
support a document path. Google documents that resource name
[here](https://cloud.google.com/iam/docs/conditions-resource-attributes).
Security rules are not a substitute for this key: rules apply to Firebase
client sign-in, and this reader uses a Google service-account token, which
IAM evaluates and rules do not.

In an xdrip2gcp project the only document stored today is `current/entries`.
The reader asks for that path and no other. If a second document is added
later, this key will be able to read it. `--check-access` makes that visible:
a GET of an unused path returns `404` (allowed, but nothing is there) rather
than `403` (rejected). A `403` on that GET would mean the key was refused.

## Layout

| File | Committed | Purpose |
| --- | --- | --- |
| `secrets.example.toml` | yes | Every setting, with placeholders |
| `secrets.toml` | no | This machine's values |
| `secrets/tc002-reader.json` | no | Service-account key |
| `setup_reader.py` | yes | Creates the account, role, binding, and key |
| `read_current.py` | yes | Prints the live reading |
| `plan.md` | yes | Phases still ahead, including the clock itself |
