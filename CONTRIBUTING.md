# Contributing

Changes follow the reviewed [shared standards](STANDARDS.md), with current evidence
in [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md). They are project policy for this
HACS custom integration, not an official Home Assistant quality rating.

## Structure and tests

Runtime code lives in `custom_components/magic_caster_wand/`; platform files expose
HA entities, `config_flow.py` owns UI setup/options, and `mcw_ble/`, `mcb_ble/` and
`common_ble/` isolate protocol/session behavior. Preserve the domain, unique IDs,
entry schema and public action/state contracts unless an explicit migration is provided.

Use `tests/components/magic_caster_wand/` with real Home Assistant fixtures and
`enable_custom_integrations`. Exercise configuration, actual config-entry/platform
loading, HA states/actions, failure handling and unload. Mock external BLE/network
boundaries; do not replace HA core with stubs. Preserve existing regression coverage.

The current CI environment is declared in `requirements_test.txt`; the exact supported
HA floor uses `requirements_test_min.txt`. Follow the Python and plugin pairs in
`.github/workflows/tests.yml`, creating a separate virtual environment per pair.
Do not raise the existing HA **2025.4.0** floor to make a current test pass. Actual
installed versions, commands and results belong in the adoption checklist; a declared
CI matrix is not evidence of execution.

From the repository root, create and activate a separate virtual environment with
Python 3.14 for current HA or Python 3.13 for the minimum. Obtain the standards
checkout at the SHA in `STANDARDS.md`, then install through its environment script:

```sh
# Point this at the reviewed standards checkout.
export STANDARDS_CHECKOUT=../hass-repo-standards
export RUNNER_TEMP="$(mktemp -d)"
python -m pip install packaging==26.3
INPUT_DOMAIN=magic_caster_wand \
INPUT_REQUIREMENTS=requirements_test.txt \
INPUT_DEPENDENCY_MODE=current \
INPUT_MINIMUM_PACKAGES='["blesession", "bluetooth-sensor-state-data"]' \
INPUT_HA_COMPONENTS='bluetooth_adapters camera' \
INPUT_EXPECTED_HA_VERSION=2026.10.2 \
INPUT_TEST_PROFILE=ha \
python "$STANDARDS_CHECKOUT/actions/python-environment/install.py"
python -m pip install -r requirements_lint.txt
python -m ruff check .
python -m ruff format --check .
python -m pytest tests/components/magic_caster_wand/ -v
python -m pip check
```

For the exact minimum HA environment, use `requirements_test_min.txt` and
`INPUT_EXPECTED_HA_VERSION=2025.4.0` with Python 3.13. The script resolves manifest
requirements together with test requirements, recursively installs requirements of
loaded HA components (including `bluetooth_adapters` and `camera`), verifies versions
and runs `pip check`. Do not bypass dependencies with `--no-deps`.

Minimum blesession (`0.9.0`) and current blesession are separate dependency axes
from minimum/current HA. Run both as declared by CI, and record exact installed values.

## Dependencies and review

Declare third-party runtime packages in the manifest's `requirements`. Declare HA
integration domains in `dependencies`/`after_dependencies`; test/lint dependencies
belong in their own requirements files. Before adding a dependency, review package
source/license, supported Python/platforms, maintained public APIs and its need.
Preserve extras, operators and markers when updating, verify resolver and `pip check`,
and test the exact minimum/current combinations. Follow the [reviewed dependency
procedure](https://github.com/eigger/hass-repo-standards/blob/v1.0.0/docs/dependencies.md).

Update both READMEs and the detailed docs when behavior changes. Use the reviewed central
`python "$STANDARDS_CHECKOUT/scripts/check_integration.py" .` to check managed README
regions, the shared test foundation, CI callers, product category evidence and Bluetooth docs.
Preserve existing user examples and media outside managed regions. HACS Default status
requires dated evidence from the official default integration list in `.hass-standards.json`.
Run `python "$STANDARDS_CHECKOUT/scripts/sync_badges.py" . --check` for this
checkout and `python "$STANDARDS_CHECKOUT/scripts/check_repository.py"` for the
central documentation/workflow contracts when reviewing standards adoption. The latter
checks the standards checkout itself; it does not validate this caller automatically. Independent review must record failures and
unexecuted checks honestly. Hardware validation requires actual model, firmware,
adapter/proxy path and results; passing mocked BLE tests does not establish it.

Dependency updater PRs created with `GITHUB_TOKEN` do not automatically trigger
ordinary push/PR workflows. The shared updater validates the changed tree and exact
new dependency floor before synchronizing its bot PR. The pinned shared updater
does not dispatch the separate Tests/Validate workflows. After it creates or updates
a PR, manually dispatch both workflows on the bot branch and confirm those runs
match the proposed commit and succeed before merging. The updater's own successful
run does not establish that every required check ran. Do not auto-merge dependency
updates.

## Releases

A release is a separate reviewed operation. Run lint, actual minimum/current HA tests,
HACS and Hassfest; confirm manifest version matches the release tag and tested commit.
Describe changed behavior, required user actions, support changes, migration and known
limits in release notes. Dependency or standards updates do not automatically create
a tag, release or integration version bump.
