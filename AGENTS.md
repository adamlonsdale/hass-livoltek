# Contributor Guide

## Dev Environment Tips
- Run `scripts/setup` from the repository root to create a virtual environment and install requirements.
- Execute `scripts/develop` to start a Home Assistant instance with the integration loaded from `custom_components`.
- Use `scripts/cli-gen.sh` to regenerate the API client if you modify `openapi.yaml`.

## Testing Instructions
- Run `scripts/lint` to check the codebase with Ruff.
- Execute `pytest` to run the unit tests.
- Ensure all linting and tests pass before submitting a PR.

## PR instructions
Title format: `[hass-livoltek] <Title>`
