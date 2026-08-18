# Release and Rollback

## Current Baseline

- Product release: `capstone-v1.0.0`
- Data release: `data-capstone-v1`
- Index release: `index-capstone-v1`

## Release Checklist

1. Verify bootstrap, E2E, and evaluation evidence for the intended commit.
2. Confirm the release pointers reference the approved data, index, prompt, and graph releases.
3. Record the activation time and operator.

## Rollback Checklist

1. Select the prior approved release manifest.
2. Point the release environment to the previous release.
3. Verify service health, retrieval, and governed actions.
4. Record the rollback reason and resulting release IDs.
