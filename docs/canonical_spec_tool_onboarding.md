# Canonical Spec Tool Onboarding

## Success Criteria
- You can clone the CanonicalSpec repo into the shared workspace.
- You can create and activate a Python virtual environment.
- You can run the Canonical Spec pipeline end-to-end.
- You can use the guide to publish requirements into Feishu.

## Why You Are Doing This
We want a consistent pipeline for turning raw requirements into Feishu demand entries.
This doc shows the fastest path to set up, run, and publish.

## 1) Clone the Repo into the Shared Project
We keep the tool under `AndroidStudioProjects/canonical_frontend` so everyone uses the same path.

```
cd /Users/marvi/AndroidStudioProjects
git clone https://github.com/369795172/CanonicalSpec.git canonical_frontend
```

If the folder already exists:
```
cd /Users/marvi/AndroidStudioProjects/canonical_frontend
git pull
```

## 2) Create and Activate Virtual Environment (Required)
```
cd /Users/marvi/AndroidStudioProjects/canonical_frontend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3) Run the Canonical Spec Pipeline
```
python -m canonical.cli run --input /absolute/path/to/input.md
python -m canonical.cli plan F-2026-001
python -m canonical.cli vv F-2026-001
python -m canonical.cli review F-2026-001 --decision go
python -m canonical.cli publish F-2026-001
```

## 4) If Gates Fail, Answer Missing Fields
```
python -m canonical.cli answer F-2026-001 --answer "spec.background=补充背景信息"
python -m canonical.cli answer F-2026-001 --answer "spec.acceptance_criteria=[...]"
```

## 5) Use the Full Guide
Refer to `docs/canonical_spec_tool_guide.md` for:
- Required publish fields
- Prompt templates for Feishu entries
- Common failure points

## Notes
- Keep local config in your own environment files; do not commit secrets.
- The repo is independent; commit changes from the `canonical_frontend` folder.
